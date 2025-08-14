"""
BMAR Plotting Module
Contains oscilloscope, spectrogram, and other plotting functionality.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import os
from pathlib import Path
from datetime import datetime
from scipy import signal
import time
import logging
import sys
import sounddevice as sd
import subprocess
import traceback

def _as_plots_sibling(path_like) -> Path:
    """Map any raw/monitor date folder (or its trailing 'plots') to the sibling plots/DATE."""
    try:
        p = Path(path_like)
        parts_lower = [s.lower() for s in p.parts]
        # Find 'audio' anchor
        try:
            idx_audio = next(i for i, s in enumerate(parts_lower) if s == 'audio')
        except StopIteration:
            return p
        # Already a proper plots/DATE path
        if len(parts_lower) > idx_audio + 2 and parts_lower[idx_audio + 1] == 'plots':
            return p
        # raw/DATE or monitor/DATE
        if len(parts_lower) > idx_audio + 2 and parts_lower[idx_audio + 1] in ('raw', 'monitor'):
            date_seg = p.parts[idx_audio + 2]
            root = Path(*p.parts[:idx_audio + 1])  # up to 'audio'
            return root / 'plots' / date_seg
        # raw/DATE/plots or monitor/DATE/plots (mis-constructed)
        if len(parts_lower) > idx_audio + 3 and parts_lower[idx_audio + 1] in ('raw', 'monitor') and parts_lower[idx_audio + 3] == 'plots':
            date_seg = p.parts[idx_audio + 2]
            root = Path(*p.parts[:idx_audio + 1])
            return root / 'plots' / date_seg
        return p
    except Exception:
        today = datetime.now().strftime("%Y-%m-%d")
        return Path.cwd() / "plots" / today

# Centralized directory resolver and saver
def _resolve_plots_dir(config: dict | None) -> str:
    # 1) caller override
    if isinstance(config, dict):
        pd = config.get("plots_dir")
        if isinstance(pd, (str, os.PathLike, Path)) and str(pd):
            p = _as_plots_sibling(pd)
            p.mkdir(parents=True, exist_ok=True)
            return str(p)
    # 2) module-level from bmar_config if already wired
    try:
        from . import bmar_config as _cfg
        pd = getattr(_cfg, "PLOTS_DIRECTORY", None)
        if isinstance(pd, (str, os.PathLike, Path)) and str(pd):
            p = _as_plots_sibling(pd)
            p.mkdir(parents=True, exist_ok=True)
            return str(p)
    except Exception:
        pass
    # 3) env
    pd_env = os.environ.get("BMAR_PLOTS_DIR")
    if pd_env:
        p = _as_plots_sibling(pd_env)
        p.mkdir(parents=True, exist_ok=True)
        return str(p)
    # 4) fallback: ./plots/DATE
    today = datetime.now().strftime("%Y-%m-%d")
    p = Path.cwd() / "plots" / today
    p.mkdir(parents=True, exist_ok=True)
    return str(p)

def _ensure_dir_path(p: str | os.PathLike | Path | None) -> str:
    try:
        path = _as_plots_sibling(p) if isinstance(p, (str, os.PathLike, Path)) and str(p) else Path.cwd() / "plots" / datetime.now().strftime("%Y-%m-%d")
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception:
        fb = Path.cwd() / "plots"
        fb.mkdir(parents=True, exist_ok=True)
        return str(fb)

def _save_plot(fig, plots_dir_like, filename: str) -> str:
    base = _ensure_dir_path(_as_plots_sibling(plots_dir_like))
    # Sanitize filename to avoid accidental subfolders like "plots/fft_...png"
    name = Path(filename).name
    fp = str(Path(base) / name)
    fig.savefig(fp, dpi=150, bbox_inches='tight')
    return fp

def plot_spectrogram(config):
    """Generate and display a spectrogram using sounddevice for audio capture."""
    try:
        config = config or {}
        plots_dir = _resolve_plots_dir(config)
        device_index = config.get('device_index', 0)
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        fft_size = config.get('fft_size', 2048)
        overlap = config.get('overlap', 0.75)
        try:
            from . import bmar_config as _cfg
            _default_spec = float(getattr(_cfg, 'SPECTROGRAM_DURATION', 5.0))
        except Exception:
            _default_spec = 5.0
        capture_duration = float(config.get('capture_duration', _default_spec))
        freq_range = config.get('freq_range', [0, samplerate // 2])

        print(f"Spectrogram capturing {capture_duration}s from device {device_index} ({samplerate}Hz)\r")
        
        try:
            # Validate device
            if device_index is not None:
                device_info = sd.query_devices(device_index, 'input')
                print(f"Using device: {device_info['name']}\r")
                
                if device_info['max_input_channels'] == 0:
                    print(f"Error: Device {device_index} has no input channels\r")
                    return
                    
                # Adjust channels if device doesn't support requested channels
                max_channels = device_info['max_input_channels']
                if channels > max_channels:
                    channels = max_channels
                    print(f"Adjusted to {channels} channels (device maximum)\r")
            else:
                print("Error: No device specified\r")
                return
            
            print("Starting audio capture...\r")
            
            # Calculate total samples needed
            total_samples = int(samplerate * capture_duration)
            audio_data = []
            
            samples_captured = 0
            capture_complete = False
            
            def callback(indata, frames, _time, status):
                nonlocal samples_captured, capture_complete
                try:
                    if status:
                        print(f"Sounddevice status: {status}\r")
                        
                    if samples_captured >= total_samples:
                        capture_complete = True
                        raise sd.CallbackStop()
                    
                    # Handle multi-channel data
                    if channels > 1:
                        audio_chunk = indata[:, 0]  # Use first channel
                    else:
                        audio_chunk = indata.flatten()
                    
                    audio_data.extend(audio_chunk.tolist())
                    samples_captured += frames
                    
                    # Show progress
                    progress = min((samples_captured / total_samples) * 100, 100)
                    print(f"\rCapturing: {progress:.1f}%", end="", flush=True)
                    
                except sd.CallbackStop:
                    raise
                except Exception as e:
                    print(f"\rError in audio callback: {e}\r")
                    capture_complete = True
                    raise sd.CallbackStop()
            
            # Capture audio data with sounddevice
            with sd.InputStream(
                device=device_index,
                channels=channels,
                samplerate=samplerate,
                blocksize=blocksize,
                dtype='float32',
                callback=callback
            ):
                # Wait for capture to complete
                while not capture_complete and samples_captured < total_samples:
                    time.sleep(0.1)
            
            print(f"\rCaptured {len(audio_data)} samples\r")
            
            if len(audio_data) == 0:
                print("No audio data captured\r")
                return
            
            # Convert to numpy array
            audio_data = np.array(audio_data[:total_samples])
            
            print("Generating spectrogram...\r")
            
            # Calculate spectrogram parameters
            hop_length = int(fft_size * (1 - overlap))
            
            # Compute spectrogram
            freqs = np.fft.fftfreq(fft_size, 1/samplerate)[:fft_size//2]
            times = np.arange(0, len(audio_data) - fft_size + 1, hop_length) / samplerate
            
            spectrogram = np.zeros((fft_size//2, len(times)))
            
            for i, start_idx in enumerate(range(0, len(audio_data) - fft_size + 1, hop_length)):
                if i >= len(times):
                    break
                
                # Extract window
                window = audio_data[start_idx:start_idx + fft_size]
                
                # Apply window function
                window = window * np.hanning(len(window))
                
                # Compute FFT
                fft = np.fft.fft(window)
                magnitude = np.abs(fft[:fft_size//2])
                
                # Convert to dB
                magnitude_db = 20 * np.log10(magnitude + 1e-10)
                spectrogram[:, i] = magnitude_db
            
            # Create plot
            plt.figure(figsize=(12, 8))
            
            # Apply frequency range filter
            freq_mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
            filtered_freqs = freqs[freq_mask]
            filtered_spectrogram = spectrogram[freq_mask, :]

            # Read color scale (dBFS) from config with sensible defaults
            try:
                from . import bmar_config as _cfg
                vmin = float(getattr(_cfg, 'SPECTROGRAM_DB_MIN', -90.0))
                vmax = float(getattr(_cfg, 'SPECTROGRAM_DB_MAX', 0.0))
            except Exception:
                vmin, vmax = -90.0, 0.0
            if vmin >= vmax:
                # Ensure valid range
                vmin, vmax = -90.0, 0.0
            
            # Plot spectrogram
            plt.imshow(
                filtered_spectrogram,
                aspect='auto',
                origin='lower',
                extent=[times[0], times[-1], filtered_freqs[0], filtered_freqs[-1]],
                cmap='viridis',
                interpolation='nearest',
                vmin=vmin,
                vmax=vmax
            )
            
            plt.colorbar(label='Magnitude (dBFS)')
            plt.xlabel('Time (seconds)')
            plt.ylabel('Frequency (Hz)')
            plt.title(f'Spectrogram - Device {device_index} ({samplerate}Hz)')
            plt.grid(True, alpha=0.3)
            
            # Save plot (force-safe path handling)
            plots_dir = _resolve_plots_dir(config)
            filename = f"spectrogram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            saved = _save_plot(plt.gcf(), plots_dir, filename)
            print(f"Spectrogram saved: {saved}\r")
            
            # Show plot
            plt.show()
            
        except Exception as e:
            print(f"Spectrogram error: {e}\r")
            traceback.print_exc()
            
    except Exception as e:
        print(f"Spectrogram setup error: {e}\r")
        traceback.print_exc()

def plot_oscope(config):
    """Generate and display oscilloscope plot with all active audio channels in stacked traces."""
    try:
        config = config or {}
        plots_dir = _resolve_plots_dir(config)
        device_index = config.get('device_index', 0)
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        try:
            from . import bmar_config as _cfg
            _default_trace = float(getattr(_cfg, 'TRACE_DURATION', 5.0))
        except Exception:
            _default_trace = 5.0
        plot_duration = float(config.get('plot_duration', _default_trace))
        monitor_channel = int(config.get('monitor_channel', 0))
        try:
            from . import bmar_config as _cfg
            oscope_gain_db = getattr(_cfg, 'OSCOPE_GAIN_DB', 0)
        except Exception:
            oscope_gain_db = 0
        oscope_gain = float(10 ** (oscope_gain_db / 20.0))

        print(f"Oscilloscope capturing {plot_duration}s from device {device_index} ({samplerate}Hz, {channels} channels)\r")
        
        try:
            # Validate device
            if device_index is not None:
                device_info = sd.query_devices(device_index, 'input')
                print(f"Using device: {device_info['name']}\r")
                
                if device_info['max_input_channels'] == 0:
                    print(f"Error: Device {device_index} has no input channels\r")
                    return
                
                # Ensure we don't request more channels than available
                max_channels = device_info['max_input_channels']
                if channels > max_channels:
                    print(f"Warning: Requested {channels} channels, but device only has {max_channels}. Using {max_channels} channels.\r")
                    channels = max_channels
                
            else:
                print("Error: No device specified\r")
                return
            
            print("Starting multi-channel audio capture...\r")
            
            # Calculate total samples needed
            total_samples = int(samplerate * plot_duration)
            audio_data = {i: [] for i in range(channels)}  # Store data for each channel
            
            samples_captured = 0
            capture_complete = False
            
            def callback(indata, frames, _time, status):
                nonlocal samples_captured, capture_complete
                try:
                    if status:
                        print(f"Sounddevice status: {status}\r")
                        
                    if samples_captured >= total_samples:
                        capture_complete = True
                        raise sd.CallbackStop()
                    
                    # Handle multi-channel data (float32 in [-1, 1] from sounddevice)
                    if channels > 1:
                        for ch in range(channels):
                            audio_data[ch].extend(indata[:, ch])
                    else:
                        audio_data[0].extend(indata.flatten())
                    
                    samples_captured += frames
                    
                    # Show progress
                    progress = min((samples_captured / total_samples) * 100, 100)
                    print(f"\rCapturing: {progress:.1f}%", end="", flush=True)
                    
                except sd.CallbackStop:
                    raise
                except Exception as e:
                    print(f"\rError in audio callback: {e}\r")
                    capture_complete = True
                    raise sd.CallbackStop()
            
            # Capture audio data with sounddevice (no scaling, no AGC applied by code)
            with sd.InputStream(
                device=device_index,
                channels=channels,
                samplerate=samplerate,
                blocksize=blocksize,
                dtype='float32',
                callback=callback
            ):
                # Wait for capture to complete
                while not capture_complete and samples_captured < total_samples:
                    time.sleep(0.1)
            
            print("\rGenerating multi-channel oscilloscope plot...\r")
            
            # Check if we have data
            if not any(len(audio_data[ch]) > 0 for ch in range(channels)):
                print("No audio data captured\r")
                return
            
            # Convert to numpy arrays and create time axis
            for ch in range(channels):
                audio_data[ch] = np.array(audio_data[ch][:total_samples], dtype=np.float32)
            time_axis = np.arange(total_samples) / samplerate
            
            # Apply optional gain just for plotting (no normalization)
            plot_data = {}
            for ch in range(channels):
                plot_data[ch] = audio_data[ch] * oscope_gain
            
            # Create stacked subplot layout
            fig, axes = plt.subplots(channels, 1, figsize=(15, 3 + 2*channels), sharex=True)
            if channels == 1:
                axes = [axes]
            # Clamp monitor channel to range
            mon = min(max(0, monitor_channel), channels - 1)
            channel_stats = []
            clipped_any = False
            for ch in range(channels):
                ax = axes[ch]
                y = plot_data[ch]
                
                # Compute statistics and clipping
                rms = float(np.sqrt(np.mean(y**2))) if y.size else 0.0
                peak = float(np.max(np.abs(y))) if y.size else 0.0
                clipped = bool(np.any(np.abs(y) >= 0.999))
                clipped_any = clipped_any or clipped
                channel_stats.append({'rms': rms, 'peak': peak, 'clipped': clipped})
                
                # Plot waveform
                color = 'tab:red' if ch == mon else f'C{ch}'
                lw = 0.9 if ch == mon else 0.5
                ax.plot(time_axis, y, linewidth=lw, color=color)
                ax.set_ylabel(f'Ch {ch+1}\nAmplitude')
                ax.grid(True, alpha=0.3)
                ax.set_xlim(0, plot_duration)
                ax.set_ylim(-1.05, 1.05)  # Fixed scale to reveal true clipping
                ax.axhline(1.0, color='r', linestyle='--', linewidth=0.8, alpha=0.7)
                ax.axhline(-1.0, color='r', linestyle='--', linewidth=0.8, alpha=0.7)
                
                # Stats box with clipping indicator
                clip_text = "\nCLIP" if clipped else ""
                ax.text(0.02, 0.98, f'RMS: {rms:.4f}\nPeak: {peak:.4f}{clip_text}', 
                        transform=ax.transAxes, va='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                        fontsize=9)
                
                if ch == 0:
                    title_extra = " - CLIPPING DETECTED" if clipped_any else ""
                    ax.set_title(f'Multi-Channel Oscilloscope - Device {device_index} ({samplerate}Hz, {channels} ch){title_extra} [Gain: {oscope_gain_db} dB]  Mon CH: {mon+1}')
            
            axes[-1].set_xlabel('Time (seconds)')
            plt.tight_layout()
            
            # Overall stats
            overall_rms = float(np.sqrt(np.mean([s['rms']**2 for s in channel_stats]))) if channel_stats else 0.0
            overall_peak = float(np.max([s['peak'] for s in channel_stats])) if channel_stats else 0.0
            fig.text(0.99, 0.02, f'Overall - RMS: {overall_rms:.4f}, Peak: {overall_peak:.4f}', 
                     ha='right', va='bottom',
                     bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                     fontsize=10)
            
            # Save plot (force-safe path handling)
            plots_dir = _resolve_plots_dir(config)
            filename = f"oscilloscope_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            saved = _save_plot(plt.gcf(), plots_dir, filename)
            print(f"Multi-channel oscilloscope plot saved: {saved}\r")
            
            plt.show()
            
        except Exception as e:
            print(f"Oscilloscope error: {e}\r")
            traceback.print_exc()
            
    except Exception as e:
        print(f"Oscilloscope setup error: {e}\r")
        traceback.print_exc()

def plot_fft(config):
    """Generate and display FFT analysis using sounddevice for audio capture."""
    try:
        config = config or {}
        plots_dir = _resolve_plots_dir(config)
        device_index = config.get('device_index', 0)
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        monitor_channel = config.get('monitor_channel', 0)
        mon = int(monitor_channel)
        try:
            from . import bmar_config as _cfg
            fft_gain_db = getattr(_cfg, 'FFT_GAIN', 0)
        except Exception:
            fft_gain_db = 0
        fft_gain = float(10 ** (fft_gain_db / 20.0))

        print(f"Starting FFT analysis on channel {mon + 1}...\r")
        
        # Check for virtual device first
        if device_index is None:
            print("Virtual device detected for FFT - generating synthetic audio\r")
            duration = 2.0
            audio_data, _ = _generate_synthetic_audio(duration, channels, samplerate, "FFT analysis")
            if audio_data is None or len(audio_data) == 0:
                print("No synthetic audio generated\r")
                return
            if isinstance(audio_data, np.ndarray) and audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32767.0
            windowed_data = audio_data * np.hanning(len(audio_data))
        else:
            try:
                device_info = sd.query_devices(device_index, 'input')
                print(f"Using device: {device_info['name']}\r")
                
                if device_info['max_input_channels'] == 0:
                    print(f"Error: Device {device_index} has no input channels\r")
                    return
                
                # Ensure requested monitor channel is capturable; open enough channels
                max_in = int(device_info['max_input_channels'])
                channels_to_open = max(1, min(max_in, int(monitor_channel) + 1))
                
                print("Capturing audio for FFT analysis...\r")
                # Use default duration from config
                try:
                    from . import bmar_config as _cfg
                    _default_fft = float(getattr(_cfg, 'FFT_DURATION', 2.0))
                except Exception:
                    _default_fft = 2.0
                capture_duration = float(config.get('capture_duration', _default_fft))
                total_samples = int(samplerate * capture_duration)
                audio_data = []
                samples_captured = 0
                capture_complete = False
                
                def callback(indata, frames, _time, status):
                    nonlocal samples_captured, capture_complete
                    try:
                        if status:
                            print(f"Sounddevice status: {status}\r")
                        if samples_captured >= total_samples:
                            capture_complete = True
                            raise sd.CallbackStop()
                        
                        # Select channel safely
                        if indata.ndim == 2 and indata.shape[1] > 1:
                            ch_idx = monitor_channel if monitor_channel < indata.shape[1] else 0
                            audio_chunk = indata[:, ch_idx]
                        else:
                            audio_chunk = indata.flatten()
                        
                        audio_data.extend(audio_chunk.tolist())
                        samples_captured += frames
                        
                        progress = min((samples_captured / total_samples) * 100, 100)
                        print(f"\rCapturing: {progress:.1f}%", end="", flush=True)
                    except sd.CallbackStop:
                        raise
                    except Exception as e:
                        print(f"\rError in audio callback: {e}\r")
                        capture_complete = True
                        raise sd.CallbackStop()
                
                with sd.InputStream(
                    device=device_index,
                    channels=channels_to_open,
                    samplerate=samplerate,
                    blocksize=blocksize,
                    dtype='float32',
                    callback=callback
                ):
                    while not capture_complete and samples_captured < total_samples:
                        time.sleep(0.1)
                
                print("\rProcessing FFT...\r")
                if len(audio_data) == 0:
                    print("No audio data captured\r")
                    return
                
                audio_data = np.array(audio_data[:total_samples], dtype=np.float32)
                windowed_data = audio_data * np.hanning(len(audio_data))
            except Exception as e:
                print(f"Error with sounddevice: {e}\r")
                traceback.print_exc()
                return
        
        # Compute FFT
        if windowed_data is None or len(windowed_data) == 0:
            print("No data for FFT\r")
            return
        
        fft_size = len(windowed_data)
        fft_vals = np.fft.fft(windowed_data)
        freqs = np.fft.fftfreq(fft_size, 1/samplerate)
        pos_mask = np.arange(fft_size//2)
        positive_freqs = freqs[:fft_size//2]
        magnitude = np.abs(fft_vals[:fft_size//2])
        
        max_mag = np.max(magnitude) if magnitude.size else 0.0
        if max_mag <= 0.0 or not np.isfinite(max_mag):
            print("Silence or invalid data captured for FFT\r")
            magnitude_normalized = np.zeros_like(magnitude)
        else:
            magnitude_normalized = (magnitude / max_mag) * (0.008 * fft_gain)
        
        # Read FFT frequency axis limits from config
        try:
            from . import bmar_config as _cfg
            fmin = float(getattr(_cfg, 'FFT_FREQ_MIN_HZ', 0.0))
            fmax_cfg = getattr(_cfg, 'FFT_FREQ_MAX_HZ', None)
            fmax = float(fmax_cfg) if fmax_cfg is not None else float(int(samplerate) // 2)
        except Exception:
            fmin, fmax = 0.0, float(int(samplerate) // 2)
        # Sanitize
        nyq = float(int(samplerate) // 2)
        if not np.isfinite(fmin) or fmin < 0:
            fmin = 0.0
        if not np.isfinite(fmax) or fmax <= 0:
            fmax = nyq
        fmax = min(fmax, nyq)
        if fmin >= fmax:
            fmin = 0.0
        
        plt.figure(figsize=(12, 6))
        plt.plot(positive_freqs, magnitude_normalized, 'b-', linewidth=1)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title(f'FFT Plot monitoring ch: {int(mon) + 1} of {int(channels)} channels [Gain: {fft_gain_db} dB]')
        plt.grid(True, alpha=0.3)
        plt.xlim(fmin, fmax)
        plt.ylim(0, 0.009 * max(1.0, fft_gain))
        
        # Save plot (force-safe path handling)
        plots_dir = _resolve_plots_dir(config)
        filename = f"fft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        saved = _save_plot(plt.gcf(), plots_dir, filename)
        print(f"FFT plot saved: {saved}\r")
        
        plt.show()
        
    except Exception as e:
        print(f"FFT setup error: {e}\r")
        traceback.print_exc()

def trigger(config):
    """Triggered plotting subprocess function."""
    
    try:
        config = config or {}
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        trigger_level = config.get('trigger_level', 0.1)
        trigger_mode = config.get('trigger_mode', 'rising')  # 'rising', 'falling', 'both'
        pre_trigger_samples = config.get('pre_trigger_samples', 1024)
        post_trigger_samples = config.get('post_trigger_samples', 2048)
        
        total_samples = pre_trigger_samples + post_trigger_samples
        
        # Circular buffer for continuous data
        buffer_size = total_samples * 4  # Extra buffer space
        audio_buffer = np.zeros(buffer_size)
        buffer_index = 0
        
        # Trigger detection state
        triggered = False
        trigger_index = 0
        last_sample = 0.0
        
        print(f"Trigger plotting active (device {device_index}, {samplerate}Hz)")
        print(f"Trigger level: {trigger_level}, Mode: {trigger_mode}")
        print(f"Pre-trigger: {pre_trigger_samples}, Post-trigger: {post_trigger_samples}")
        
        # Create matplotlib figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        plt.tight_layout()
        
        def check_trigger(new_sample, last_sample, level, mode):
            """Check if trigger condition is met."""
            if mode == 'rising':
                return last_sample <= level < new_sample
            elif mode == 'falling':
                return last_sample >= level > new_sample
            elif mode == 'both':
                return ((last_sample <= level < new_sample) or 
                        (last_sample >= level > new_sample))
            return False
        
        def plot_triggered_data(trigger_data):
            """Plot the triggered waveform and its spectrum."""
            # Clear axes
            ax1.clear()
            ax2.clear()
            
            # Time domain plot
            time_axis = np.linspace(-pre_trigger_samples/samplerate, 
                                   post_trigger_samples/samplerate, 
                                   len(trigger_data))
            
            ax1.plot(time_axis, trigger_data, 'b-', linewidth=1.0)
            ax1.axvline(x=0, color='r', linestyle='--', label='Trigger')
            ax1.axhline(y=trigger_level, color='g', linestyle=':', label=f'Level ({trigger_level})')
            ax1.axhline(y=-trigger_level, color='g', linestyle=':', alpha=0.5)
            
            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('Amplitude')
            ax1.set_title('Triggered Waveform')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Frequency domain plot
            window = np.hanning(len(trigger_data))
            windowed_data = trigger_data * window
            
            fft_result = np.fft.rfft(windowed_data)
            magnitude = np.abs(fft_result)
            magnitude_db = 20 * np.log10(magnitude + 1e-10)
            
            freqs = np.fft.rfftfreq(len(trigger_data), 1/samplerate)
            
            ax2.plot(freqs, magnitude_db, 'g-', linewidth=1.0)
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Magnitude (dB)')
            ax2.set_title('Triggered Spectrum')
            ax2.grid(True, alpha=0.3)
            ax2.set_xlim(0, samplerate//2)
        
        # Audio callback function for sounddevice
        def audio_callback(indata, _frames, _time, status):
            nonlocal audio_buffer, buffer_index, triggered, trigger_index, last_sample
            
            if status:
                print(f"Trigger callback status: {status}")
            
            # Handle multi-channel data (use first channel for trigger)
            if channels > 1:
                new_data = indata[:, 0]  # Use first channel for trigger detection
            else:
                new_data = indata.flatten()
            
            for sample in new_data:
                # Check for trigger
                if not triggered and check_trigger(sample, last_sample, trigger_level, trigger_mode):
                    triggered = True
                    trigger_index = buffer_index
                    print(f"Trigger detected at sample {trigger_index}")
                
                # Store sample in circular buffer
                audio_buffer[buffer_index] = sample
                buffer_index = (buffer_index + 1) % buffer_size
                last_sample = sample
        
        # Start sounddevice stream
        with sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=int(samplerate),
            blocksize=blocksize,
            dtype='float32',
            callback=audio_callback
        ):
            try:
                trigger_count = 0
                
                while True:
                    if triggered:
                        # Extract triggered data
                        start_idx = (trigger_index - pre_trigger_samples) % buffer_size
                        end_idx = (trigger_index + post_trigger_samples) % buffer_size
                        
                        if end_idx > start_idx:
                            trigger_data = audio_buffer[start_idx:end_idx]
                        else:
                            # Handle wraparound
                            trigger_data = np.concatenate([
                                audio_buffer[start_idx:],
                                audio_buffer[:end_idx]
                            ])
                        
                        # Plot and save
                        try:
                            plot_triggered_data(trigger_data)
                            
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            filename = f"trigger_{timestamp}_{trigger_count:03d}.png"
                            
                            # Create plots directory if it doesn't exist
                            plots_dir = _ensure_dir_path(_resolve_plots_dir(config))
                            filepath = str(Path(plots_dir) / filename)
                            fig.savefig(filepath, dpi=100, bbox_inches='tight')
                            
                            print(f"Saved trigger plot: {filename}")
                            trigger_count += 1
                        except Exception as e:
                            print(f"Error saving trigger plot: {e}")
                        
                        # Reset trigger
                        triggered = False
                    
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nTrigger plotting stopped by user")
                
    except KeyboardInterrupt:
        print("\nTrigger plotting stopped by user")
    except Exception as e:
        print(f"Trigger plotting error: {e}")
        logging.error(f"Trigger plotting error: {e}")
    finally:
        plt.close('all')

def plot_audio_analysis(audio_data, samplerate, output_path="audio_analysis.png"):
    """Create a comprehensive audio analysis plot."""
    
    try:
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Audio Analysis', fontsize=16)
        
        # Time domain plot
        time_axis = np.linspace(0, len(audio_data) / samplerate, len(audio_data))
        axes[0, 0].plot(time_axis, audio_data, 'b-', linewidth=0.5)
        axes[0, 0].set_xlabel('Time (s)')
        axes[0, 0].set_ylabel('Amplitude')
        axes[0, 0].set_title('Waveform')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Frequency domain plot
        window = np.hanning(len(audio_data))
        windowed_data = audio_data * window
        
        fft_result = np.fft.rfft(windowed_data)
        magnitude = np.abs(fft_result)
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        
        freqs = np.fft.rfftfreq(len(audio_data), 1/samplerate)
        
        axes[0, 1].plot(freqs, magnitude_db, 'g-', linewidth=1.0)
        axes[0, 1].set_xlabel('Frequency (Hz)')
        axes[0, 1].set_ylabel('Magnitude (dB)')
        axes[0, 1].set_title('Frequency Spectrum')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Spectrogram
        f, t, Sxx = signal.spectrogram(audio_data, samplerate, nperseg=1024, noverlap=512)
        im = axes[1, 0].pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud')
        axes[1, 0].set_xlabel('Time (s)')
        axes[1, 0].set_ylabel('Frequency (Hz)')
        axes[1, 0].set_title('Spectrogram')
        plt.colorbar(im, ax=axes[1, 0], label='Power (dB)')
        
        # Statistical analysis
        rms = np.sqrt(np.mean(audio_data**2))
        peak = np.max(np.abs(audio_data))
        crest_factor = peak / rms if rms > 0 else 0
        zero_crossings = len(np.where(np.diff(np.signbit(audio_data)))[0])
        zcr = zero_crossings / len(audio_data) * samplerate
        
        stats_text = f"RMS: {rms:.4f}\n"
        stats_text += f"Peak: {peak:.4f}\n"
        stats_text += f"Crest Factor: {crest_factor:.2f}\n"
        stats_text += f"Zero Crossing Rate: {zcr:.1f} Hz\n"
        stats_text += f"Duration: {len(audio_data)/samplerate:.2f} s\n"
        stats_text += f"Sample Rate: {samplerate} Hz\n"
        stats_text += f"Samples: {len(audio_data)}"
        
        axes[1, 1].text(0.1, 0.9, stats_text, transform=axes[1, 1].transAxes,
                        verticalalignment='top', fontfamily='monospace',
                        bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray"))
        axes[1, 1].set_xlim(0, 1)
        axes[1, 1].set_ylim(0, 1)
        axes[1, 1].set_title('Statistics')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Audio analysis plot saved: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error creating audio analysis plot: {e}")
        return False

def create_comparison_plot(audio_data_list, labels, samplerate, output_path="comparison.png"):
    """Create a comparison plot of multiple audio signals."""
    
    try:
        num_signals = len(audio_data_list)
        fig, axes = plt.subplots(num_signals, 1, figsize=(12, 3*num_signals))
        
        if num_signals == 1:
            axes = [axes]
        
        fig.suptitle('Audio Signal Comparison', fontsize=16)
        
        for i, (audio_data, label) in enumerate(zip(audio_data_list, labels)):
            time_axis = np.linspace(0, len(audio_data) / samplerate, len(audio_data))
            
            axes[i].plot(time_axis, audio_data, linewidth=0.8)
            axes[i].set_ylabel('Amplitude')
            axes[i].set_title(f'{label} (RMS: {np.sqrt(np.mean(audio_data**2)):.4f})')
            axes[i].grid(True, alpha=0.3)
            
            if i == num_signals - 1:
                axes[i].set_xlabel('Time (s)')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Comparison plot saved: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error creating comparison plot: {e}")
        return False

def _try_open_plot_file(filepath):
    """Try to open a plot file using the system's default image viewer."""
    try:
        
        if sys.platform == 'win32':
            # Windows
            subprocess.run(['start', filepath], shell=True, check=False)
        elif sys.platform == 'darwin':
            # macOS
            subprocess.run(['open', filepath], check=False)
        else:
            # Linux/Unix
            try:
                subprocess.run(['xdg-open', filepath], check=False)
            except FileNotFoundError:
                # Fallback for WSL
                try:
                    subprocess.run(['wslview', filepath], check=False)
                except FileNotFoundError:
                    print(f"Cannot automatically open file. Please open manually: {filepath}")
                    
    except Exception as e:
        print(f"Could not open plot file automatically: {e}")
        print(f"Please open manually: {filepath}")
