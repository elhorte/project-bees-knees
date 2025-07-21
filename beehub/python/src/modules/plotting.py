"""
BMAR Plotting Module
Contains oscilloscope, spectrogram, and other plotting functionality.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_agg import FigureCanvasAgg
import time
import logging
import multiprocessing
import threading
import os
from scipy import signal

# Try to set matplotlib to use interactive backend for GUI display
GUI_AVAILABLE = False
try:
    # On Windows, try TkAgg first as it's most reliable
    import sys
    if sys.platform == 'win32':
        matplotlib.use('TkAgg')
        print("Using TkAgg backend for GUI display")
    else:
        # For Linux/macOS, try Qt5Agg first
        try:
            matplotlib.use('Qt5Agg')
            print("Using Qt5Agg backend for GUI display")
        except ImportError:
            matplotlib.use('TkAgg')
            print("Using TkAgg backend for GUI display")
    
    # Test if the backend is working
    fig_test = plt.figure()
    plt.close(fig_test)
    GUI_AVAILABLE = True
    
except Exception as e:
    print(f"Interactive backend not available: {e}")
    matplotlib.use('Agg')  # Non-interactive fallback
    GUI_AVAILABLE = False
    print("Using non-interactive Agg backend")

def create_progress_bar(current, total, bar_length=50):
    """Create a progress bar string.
    Args:
        current: Current progress value
        total: Total value
        bar_length: Length of the progress bar (default 50)
    Returns:
        String representation of progress bar like [######     ]
    """
    if total == 0:
        return f"[{'#' * bar_length}] 100%"
    
    # Ensure current doesn't exceed total
    current = min(current, total)
    
    # Calculate percentage (0-100) with proper rounding
    if current >= total:
        percent = 100  # Force 100% when complete
    else:
        percent = round(current * 100 / total)
    
    # Calculate filled length, ensuring it can reach full bar_length
    if current >= total:
        filled_length = bar_length  # Force full bar when complete
    else:
        filled_length = int(bar_length * current / total)
    
    # Create the bar
    bar = '#' * filled_length + ' ' * (bar_length - filled_length)
    return f"[{bar}] {percent}%"

def _generate_synthetic_audio(duration, channels, samplerate, task_name="synthetic audio"):
    """Generate synthetic audio data for virtual devices."""
    try:
        print(f"Generating {duration}s of synthetic audio for {task_name}...\r")
        
        # Generate time array
        t = np.linspace(0, duration, int(samplerate * duration))
        
        # Create a complex synthetic signal
        # Base frequencies
        freq1 = 440  # A4 note
        freq2 = 880  # A5 note
        freq3 = 1320  # E6 note
        
        # Generate signal with multiple components
        signal = (0.6 * np.sin(2 * np.pi * freq1 * t) +      # Primary tone
                 0.3 * np.sin(2 * np.pi * freq2 * t) +      # Harmonic
                 0.2 * np.sin(2 * np.pi * freq3 * t) +      # Higher harmonic
                 0.1 * np.sin(2 * np.pi * 100 * t) +        # Low frequency
                 0.05 * np.random.randn(len(t)))            # Noise
        
        # Add some time-varying effects
        # Amplitude modulation
        am_freq = 2.0  # 2 Hz modulation
        am_signal = signal * (0.7 + 0.3 * np.sin(2 * np.pi * am_freq * t))
        
        # Add frequency sweep
        sweep_start = 200
        sweep_end = 2000
        sweep_freq = sweep_start + (sweep_end - sweep_start) * t / duration
        sweep_signal = 0.2 * np.sin(2 * np.pi * sweep_freq * t)
        
        # Combine all components
        final_signal = am_signal + sweep_signal
        
        # Convert to int16 range
        max_amplitude = 0.8  # Leave some headroom
        final_signal = final_signal / np.max(np.abs(final_signal)) * max_amplitude
        synthetic_data = (final_signal * 32767).astype(np.int16)
        
        # Handle multi-channel
        if channels > 1:
            # Create slightly different signals for each channel
            multi_channel_data = np.zeros((len(synthetic_data), channels), dtype=np.int16)
            multi_channel_data[:, 0] = synthetic_data
            
            for ch in range(1, channels):
                # Add phase shift and slight frequency variation for other channels
                phase_shift = ch * np.pi / 4
                freq_mult = 1.0 + ch * 0.1
                
                ch_signal = (0.6 * np.sin(2 * np.pi * freq1 * freq_mult * t + phase_shift) +
                           0.3 * np.sin(2 * np.pi * freq2 * freq_mult * t + phase_shift) +
                           0.05 * np.random.randn(len(t)))
                
                ch_signal = ch_signal / np.max(np.abs(ch_signal)) * max_amplitude
                multi_channel_data[:, ch] = (ch_signal * 32767).astype(np.int16)
            
            print(f"Generated {duration}s synthetic audio ({channels} channels)\r")
            return multi_channel_data, channels
        else:
            print(f"Generated {duration}s synthetic audio (mono)\r")
            return synthetic_data, 1
            
    except Exception as e:
        logging.error(f"Error generating synthetic audio for {task_name}: {e}")
        return None, 0

def _record_audio_pyaudio(duration, device_index, channels, samplerate, blocksize, task_name="audio recording"):
    """Record audio using PyAudio with progress bar and virtual device support."""
    
    # Check for virtual device (device_index=None)
    if device_index is None:
        print(f"Virtual device detected for {task_name} - generating synthetic audio\r")
        return _generate_synthetic_audio(duration, channels, samplerate, task_name)
    
    try:
        import pyaudio
    except ImportError:
        logging.error("PyAudio not available - cannot record audio")
        return None, 0
    
    p = None
    recording_complete = False
    frames_recorded = 0
    
    try:
        # Calculate recording parameters
        num_frames = int(samplerate * duration)
        chunk_size = blocksize
        
        # Validate device channels
        p = pyaudio.PyAudio()
        device_info = p.get_device_info_by_index(device_index)
        max_input_channels = int(device_info['maxInputChannels'])
        actual_channels = min(channels, max_input_channels)
        
        if actual_channels != channels:
            print(f"Device only supports {max_input_channels} input channels, using {actual_channels}\r")
        
        # Create recording array
        recording_array = np.zeros((num_frames, actual_channels), dtype=np.float32)
        
        print(f"Recording {duration}s of audio from device {device_index}...\r")
        print(f"Sample rate: {samplerate}Hz, Channels: {actual_channels}, Block size: {chunk_size}\r")
        
        def callback(indata, frame_count, time_info, status):
            nonlocal frames_recorded, recording_complete
            try:
                if status:
                    print(f"PyAudio stream status: {status}\r")
                if frames_recorded < num_frames and not recording_complete:
                    data = np.frombuffer(indata, dtype=np.float32)
                    if len(data) > 0:
                        start_idx = frames_recorded
                        end_idx = min(start_idx + len(data) // actual_channels, num_frames)
                        data = data.reshape(-1, actual_channels)
                        recording_array[start_idx:end_idx] = data[:(end_idx - start_idx)]
                        frames_recorded += len(data) // actual_channels
                        if frames_recorded >= num_frames:
                            recording_complete = True
                            return (None, pyaudio.paComplete)
                return (None, pyaudio.paContinue)
            except Exception as e:
                logging.error(f"Error in PyAudio callback: {e}\r")
                recording_complete = True
                return (None, pyaudio.paAbort)
        
        stream = p.open(format=pyaudio.paFloat32,
                        channels=actual_channels,
                        rate=int(samplerate),
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=chunk_size,
                        stream_callback=callback)
        
        stream.start_stream()
        
        start_time = time.time()
        timeout = duration + 10
        
        while not recording_complete and (time.time() - start_time) < timeout:
            progress_bar = create_progress_bar(frames_recorded, num_frames)
            print(f"Recording progress: {progress_bar}", end='\r')
            time.sleep(0.1)
        
        # Ensure we show 100% completion when done
        if recording_complete or frames_recorded >= num_frames:
            progress_bar = create_progress_bar(num_frames, num_frames)  # Force 100%
            print(f"Recording progress: {progress_bar}\r")
        
        stream.stop_stream()
        stream.close()
        
        if frames_recorded < num_frames * 0.9:
            print(f"Warning: Recording incomplete: only got {frames_recorded}/{num_frames} frames.\r")
            return None, 0
        
        print(f"Finished {task_name}.\r")
        return recording_array, actual_channels

    except Exception as e:
        logging.error(f"Failed to record audio with PyAudio for {task_name}: {e}\r")
        return None, 0
    finally:
        if p:
            try:
                p.terminate()
                time.sleep(0.1)  # Allow time for resources to be released
            except Exception as e:
                logging.error(f"Error terminating PyAudio instance for {task_name}: {e}")

def plot_oscope(config):
    """Generate and display oscilloscope plot with all active audio channels in stacked traces."""
    
    import numpy as np
    import matplotlib.pyplot as plt
    import pyaudio
    import time
    from datetime import datetime
    import os
    
    try:
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        plot_duration = config.get('plot_duration', 10.0)
        plots_dir = config.get('plots_dir')
        
        print(f"Oscilloscope capturing {plot_duration}s from device {device_index} ({samplerate}Hz, {channels} channels)\r")
        
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        try:
            # Validate device
            if device_index is not None:
                device_info = p.get_device_info_by_index(device_index)
                print(f"Using device: {device_info['name']}\r")
                
                if device_info['maxInputChannels'] == 0:
                    print(f"Error: Device {device_index} has no input channels\r")
                    return
                
                # Ensure we don't request more channels than available
                max_channels = device_info['maxInputChannels']
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
            
            # Open audio stream
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=samplerate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=blocksize
            )
            
            # Capture audio data
            samples_captured = 0
            while samples_captured < total_samples:
                try:
                    # Read audio chunk
                    data = stream.read(blocksize, exception_on_overflow=False)
                    audio_chunk = np.frombuffer(data, dtype=np.float32)
                    
                    # Handle multi-channel data
                    if channels > 1:
                        audio_chunk = audio_chunk.reshape(-1, channels)
                        # Store each channel separately
                        for ch in range(channels):
                            audio_data[ch].extend(audio_chunk[:, ch])
                    else:
                        # Single channel
                        audio_data[0].extend(audio_chunk)
                    
                    samples_captured += len(audio_chunk) if channels == 1 else len(audio_chunk) // channels
                    
                    # Show progress
                    progress = (samples_captured / total_samples) * 100
                    print(f"\rCapturing: {progress:.1f}%", end="", flush=True)
                    
                except Exception as e:
                    print(f"\rError reading audio: {e}\r")
                    break
            
            # Close stream
            stream.stop_stream()
            stream.close()
            
            print(f"\rGenerating multi-channel oscilloscope plot...\r")
            
            # Check if we have data
            if not any(len(audio_data[ch]) > 0 for ch in range(channels)):
                print("No audio data captured\r")
                return
            
            # Convert to numpy arrays and create time axis
            for ch in range(channels):
                audio_data[ch] = np.array(audio_data[ch][:total_samples])
            time_axis = np.arange(total_samples) / samplerate
            
            # Create stacked subplot layout
            fig, axes = plt.subplots(channels, 1, figsize=(15, 3 + 2*channels), sharex=True)
            
            # Handle single channel case (axes won't be an array)
            if channels == 1:
                axes = [axes]
            
            # Plot each channel in its own subplot
            channel_stats = []
            for ch in range(channels):
                ax = axes[ch]
                
                # Plot the waveform
                ax.plot(time_axis, audio_data[ch], linewidth=0.5, color=f'C{ch}')
                ax.set_ylabel(f'Ch {ch+1}\nAmplitude')
                ax.grid(True, alpha=0.3)
                ax.set_xlim(0, plot_duration)
                
                # Calculate and display statistics
                rms = np.sqrt(np.mean(audio_data[ch]**2))
                peak = np.max(np.abs(audio_data[ch]))
                channel_stats.append({'rms': rms, 'peak': peak})
                
                # Add statistics text box
                ax.text(0.02, 0.98, f'RMS: {rms:.4f}\nPeak: {peak:.4f}', 
                       transform=ax.transAxes, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                       fontsize=9)
                
                # Set title for first subplot
                if ch == 0:
                    ax.set_title(f'Multi-Channel Oscilloscope - Device {device_index} ({samplerate}Hz, {channels} channels)')
            
            # Set x-label only on bottom subplot
            axes[-1].set_xlabel('Time (seconds)')
            
            # Adjust layout to prevent overlapping
            plt.tight_layout()
            
            # Add overall statistics as figure text
            overall_rms = np.sqrt(np.mean([stats['rms']**2 for stats in channel_stats]))
            overall_peak = np.max([stats['peak'] for stats in channel_stats])
            
            fig.text(0.99, 0.02, f'Overall - RMS: {overall_rms:.4f}, Peak: {overall_peak:.4f}', 
                    horizontalalignment='right', verticalalignment='bottom',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                    fontsize=10)
            
            # Save plot
            if plots_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"oscilloscope_multichannel_{timestamp}_dev{device_index}_{channels}ch.png"
                filepath = os.path.join(plots_dir, filename)
                plt.savefig(filepath, dpi=150, bbox_inches='tight')
                print(f"Multi-channel oscilloscope plot saved: {filepath}\r")
            
            # Show plot
            plt.show()
            
        except Exception as e:
            print(f"Oscilloscope error: {e}\r")
            import traceback
            traceback.print_exc()
            
        finally:
            # Cleanup PyAudio
            p.terminate()
            
    except Exception as e:
        print(f"Oscilloscope setup error: {e}\r")
        import traceback
        traceback.print_exc()

def plot_spectrogram(config):
    """Generate and display a spectrogram using PyAudio for audio capture."""
    
    import numpy as np
    import matplotlib.pyplot as plt
    import pyaudio
    import time
    from datetime import datetime
    import os
    
    try:
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        fft_size = config.get('fft_size', 2048)
        overlap = config.get('overlap', 0.75)
        capture_duration = config.get('capture_duration', 5.0)
        freq_range = config.get('freq_range', [0, samplerate // 2])
        plots_dir = config.get('plots_dir')
        
        print(f"Spectrogram capturing {capture_duration}s from device {device_index} ({samplerate}Hz)\r")
        
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        try:
            # Validate device
            if device_index is not None:
                device_info = p.get_device_info_by_index(device_index)
                print(f"Using device: {device_info['name']}\r")
                
                if device_info['maxInputChannels'] == 0:
                    print(f"Error: Device {device_index} has no input channels\r")
                    return
                    
                # Adjust channels if device doesn't support requested channels
                max_channels = device_info['maxInputChannels']
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
            
            # Open audio stream
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=samplerate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=blocksize
            )
            
            # Capture audio data
            samples_captured = 0
            while samples_captured < total_samples:
                try:
                    # Read audio chunk
                    data = stream.read(blocksize, exception_on_overflow=False)
                    audio_chunk = np.frombuffer(data, dtype=np.float32)
                    
                    # Handle multi-channel data
                    if channels > 1:
                        audio_chunk = audio_chunk.reshape(-1, channels)
                        audio_chunk = audio_chunk[:, 0]  # Use first channel
                    
                    audio_data.extend(audio_chunk)
                    samples_captured += len(audio_chunk)
                    
                    # Show progress
                    progress = (samples_captured / total_samples) * 100
                    print(f"\rCapturing: {progress:.1f}%", end="", flush=True)
                    
                except Exception as e:
                    print(f"\rError reading audio: {e}\r")
                    break
            
            # Close stream
            stream.stop_stream()
            stream.close()
            
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
            
            # Plot spectrogram
            plt.imshow(
                filtered_spectrogram,
                aspect='auto',
                origin='lower',
                extent=[times[0], times[-1], filtered_freqs[0], filtered_freqs[-1]],
                cmap='viridis',
                interpolation='nearest'
            )
            
            plt.colorbar(label='Magnitude (dB)')
            plt.xlabel('Time (seconds)')
            plt.ylabel('Frequency (Hz)')
            plt.title(f'Spectrogram - Device {device_index} ({samplerate}Hz)')
            plt.grid(True, alpha=0.3)
            
            # Save plot
            if plots_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"spectrogram_{timestamp}_dev{device_index}.png"
                filepath = os.path.join(plots_dir, filename)
                plt.savefig(filepath, dpi=150, bbox_inches='tight')
                print(f"Spectrogram saved: {filepath}\r")
            
            # Show plot
            plt.show()
            
        except Exception as e:
            print(f"Spectrogram error: {e}\r")
            import traceback
            traceback.print_exc()
            
        finally:
            # Cleanup PyAudio
            p.terminate()
            
    except Exception as e:
        print(f"Spectrogram setup error: {e}\r")
        import traceback
        traceback.print_exc()

def plot_fft(config):
    """Generate and display FFT analysis using PyAudio for audio capture."""
    
    import numpy as np
    import matplotlib.pyplot as plt
    import pyaudio
    import time
    from datetime import datetime
    import os
    
    try:
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        plots_dir = config.get('plots_dir')
        monitor_channel = config.get('monitor_channel', 0)
        
        print(f"Starting FFT analysis on channel {monitor_channel + 1}...\r")
        
        # Check for virtual device first
        if device_index is None:
            print("Virtual device detected for FFT - generating synthetic audio\r")
            # Generate synthetic audio data for FFT analysis
            duration = 2.0  # 2 seconds for FFT
            audio_data, actual_channels = _generate_synthetic_audio(duration, channels, samplerate, "FFT analysis")
            
            # Convert int16 synthetic data to float32 range [-1, 1] like real audio
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32767.0
            
            # Process the synthetic data for FFT
            windowed_data = audio_data * np.hanning(len(audio_data))
            
        else:
            # Initialize PyAudio for real device
            p = pyaudio.PyAudio()
            
            try:
                # Validate device
                device_info = p.get_device_info_by_index(device_index)
                print(f"Using device: {device_info['name']}\r")
                
                if device_info['maxInputChannels'] == 0:
                    print(f"Error: Device {device_index} has no input channels\r")
                    return
                
                # Validate monitor channel
                if monitor_channel >= device_info['maxInputChannels']:
                    monitor_channel = 0
                    print(f"Adjusted to channel 1 (device has {device_info['maxInputChannels']} channels)\r")
                
                print("Capturing audio for FFT analysis...\r")
                
                # Capture duration for FFT (2 seconds)
                capture_duration = 2.0
                total_samples = int(samplerate * capture_duration)
                audio_data = []
                
                # Open audio stream
                stream = p.open(
                    format=pyaudio.paFloat32,
                    channels=channels,
                    rate=samplerate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=blocksize
                )
                
                # Capture audio data
                samples_captured = 0
                while samples_captured < total_samples:
                    try:
                        # Read audio chunk
                        data = stream.read(blocksize, exception_on_overflow=False)
                        audio_chunk = np.frombuffer(data, dtype=np.float32)
                        
                        # Handle multi-channel data
                        if channels > 1:
                            audio_chunk = audio_chunk.reshape(-1, channels)
                            if monitor_channel < audio_chunk.shape[1]:
                                audio_chunk = audio_chunk[:, monitor_channel]
                            else:
                                audio_chunk = audio_chunk[:, 0]  # Fallback to first channel
                        
                        audio_data.extend(audio_chunk)
                        samples_captured += len(audio_chunk)
                        
                        # Show progress
                        progress = (samples_captured / total_samples) * 100
                        print(f"\rCapturing: {progress:.1f}%", end="", flush=True)
                        
                    except Exception as e:
                        print(f"\rError reading audio: {e}\r")
                        break
                
                # Close stream
                stream.stop_stream()
                stream.close()
                
                print(f"\rProcessing FFT...\r")
                
                if len(audio_data) == 0:
                    print("No audio data captured\r")
                    return
                
                # Convert to numpy array and apply window
                audio_data = np.array(audio_data[:total_samples])
                windowed_data = audio_data * np.hanning(len(audio_data))
                
            finally:
                # Cleanup PyAudio
                p.terminate()
        
        # Compute FFT (common path for both virtual and real devices)
        fft_size = len(windowed_data)
        fft = np.fft.fft(windowed_data)
        freqs = np.fft.fftfreq(fft_size, 1/samplerate)
        
        # Take only positive frequencies
        positive_freqs = freqs[:fft_size//2]
        magnitude = np.abs(fft[:fft_size//2])
        
        # Convert to linear amplitude (not dB) to match original format
        # Normalize the magnitude to match original scale
        magnitude_normalized = magnitude / np.max(magnitude) * 0.008  # Scale to match your example
        
        # Create plot matching the original format
        plt.figure(figsize=(12, 6))
        plt.plot(positive_freqs, magnitude_normalized, 'b-', linewidth=1)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title(f'FFT Plot monitoring ch: {monitor_channel + 1} of {channels} channels')
        plt.grid(True, alpha=0.3)
        plt.xlim(0, min(samplerate // 2, 100000))  # Limit to 100kHz max like original
        plt.ylim(0, 0.009)  # Match the amplitude scale from your example
        
        # Save plot
        if plots_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fft_{timestamp}_dev{device_index}_ch{monitor_channel + 1}.png"
            filepath = os.path.join(plots_dir, filename)
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            print(f"FFT plot saved: {filepath}\r")
        
        # Show plot
        plt.show()
        
    except Exception as e:
        print(f"FFT setup error: {e}\r")
        import traceback
        traceback.print_exc()

def trigger(config):
    """Triggered plotting subprocess function."""
    
    try:
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
        
        # Audio callback function for PyAudio
        def audio_callback(indata, frames, time_info, status):
            nonlocal audio_buffer, buffer_index, triggered, trigger_index, last_sample
            
            if status:
                print(f"Trigger callback status: {status}")
            
            # Convert PyAudio bytes to numpy array
            audio_data = np.frombuffer(indata, dtype=np.float32)
            
            # Handle multi-channel data (use first channel for trigger)
            if channels > 1:
                audio_data = audio_data.reshape(-1, channels)
                new_data = audio_data[:, 0]  # Use first channel for trigger detection
            else:
                new_data = audio_data
            
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
            
            return (indata, pyaudio.paContinue)
        
        # Start PyAudio stream
        import pyaudio
        pa = pyaudio.PyAudio()
        
        stream = pa.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=int(samplerate),
            input=True,
            input_device_index=device_index,
            frames_per_buffer=blocksize,
            stream_callback=audio_callback
        )
        
        stream.start_stream()
        
        try:
            trigger_count = 0
            
            while stream.is_active():
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
                        plots_dir = config.get('plots_dir', 'plots')
                        if not os.path.exists(plots_dir):
                            os.makedirs(plots_dir)
                        
                        filepath = os.path.join(plots_dir, filename)
                        fig.savefig(filepath, dpi=100, bbox_inches='tight')
                        
                        print(f"Saved trigger plot: {filename}")
                        trigger_count += 1
                        
                    except Exception as e:
                        print(f"Error saving trigger plot: {e}")
                    
                    # Reset trigger
                    triggered = False
                
                time.sleep(0.1)
        finally:
            # Clean up PyAudio resources
            stream.stop_stream()
            stream.close()
            pa.terminate()
                
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
        import subprocess
        import sys
        
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
