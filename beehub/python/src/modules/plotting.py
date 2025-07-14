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

# Set matplotlib to use non-interactive backend
matplotlib.use('Agg')

def plot_oscope(config):
    """Oscilloscope plot subprocess function."""
    
    def update_plot(frame_data):
        """Update the oscilloscope plot with new data."""
        ax.clear()
        
        # Plot the waveform
        time_axis = np.linspace(0, len(frame_data) / samplerate, len(frame_data))
        ax.plot(time_axis, frame_data, 'b-', linewidth=0.8)
        
        # Set plot properties
        ax.set_xlim(0, time_axis[-1])
        ax.set_ylim(-1.0, 1.0)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude')
        ax.set_title(f'Oscilloscope - Device {device_index}')
        ax.grid(True, alpha=0.3)
        
        # Add level indicators
        rms_level = np.sqrt(np.mean(frame_data**2))
        peak_level = np.max(np.abs(frame_data))
        
        ax.text(0.02, 0.95, f'RMS: {rms_level:.3f}', transform=ax.transAxes, 
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
        ax.text(0.02, 0.88, f'Peak: {peak_level:.3f}', transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen"))
    
    try:
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        plot_duration = config.get('plot_duration', 2.0)  # Duration of display in seconds
        
        # Calculate buffer size for display
        buffer_size = int(samplerate * plot_duration)
        audio_buffer = np.zeros(buffer_size)
        
        print(f"Oscilloscope active (device {device_index}, {samplerate}Hz)")
        print(f"Display duration: {plot_duration}s")
        
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(12, 6))
        plt.tight_layout()
        
        # Audio callback function
        def audio_callback(indata, frames, time_info, status):
            nonlocal audio_buffer
            
            # Shift buffer and add new data
            new_data = indata.flatten()[:buffer_size]
            audio_buffer = np.roll(audio_buffer, -len(new_data))
            audio_buffer[-len(new_data):] = new_data
            
            if status:
                print(f"Oscope callback status: {status}")
        
        # Start audio stream
        import sounddevice as sd
        stream = sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        )
        
        # Animation function for real-time updates
        def animate(frame):
            update_plot(audio_buffer)
            return []
        
        with stream:
            # Create animation
            ani = animation.FuncAnimation(fig, animate, interval=50, blit=False)
            
            # Save plots periodically
            plot_count = 0
            last_save_time = time.time()
            
            while stream.active:
                current_time = time.time()
                
                # Save plot every 10 seconds
                if current_time - last_save_time >= 10.0:
                    try:
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"oscope_{timestamp}_{plot_count:03d}.png"
                        
                        # Create plots directory if it doesn't exist
                        plots_dir = config.get('plots_dir', 'plots')
                        if not os.path.exists(plots_dir):
                            os.makedirs(plots_dir)
                        
                        filepath = os.path.join(plots_dir, filename)
                        
                        # Update plot and save
                        update_plot(audio_buffer)
                        fig.savefig(filepath, dpi=100, bbox_inches='tight')
                        
                        print(f"Saved oscilloscope plot: {filename}")
                        plot_count += 1
                        last_save_time = current_time
                        
                    except Exception as e:
                        print(f"Error saving oscilloscope plot: {e}")
                
                time.sleep(1.0)
                
    except KeyboardInterrupt:
        print("\nOscilloscope stopped by user")
    except Exception as e:
        print(f"Oscilloscope error: {e}")
        logging.error(f"Oscilloscope error: {e}")
    finally:
        plt.close('all')

def plot_spectrogram(config):
    """Spectrogram plot subprocess function."""
    
    try:
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        fft_size = config.get('fft_size', 2048)
        overlap = config.get('overlap', 0.5)
        freq_range = config.get('freq_range', [0, samplerate//2])
        
        # Calculate spectrogram parameters
        hop_length = int(fft_size * (1 - overlap))
        spectrogram_length = config.get('spectrogram_length', 200)  # Number of time slices
        
        # Initialize spectrogram buffer
        freq_bins = fft_size // 2 + 1
        spectrogram_buffer = np.zeros((freq_bins, spectrogram_length))
        buffer_index = 0
        
        # Audio buffer for windowing
        audio_buffer = np.zeros(fft_size)
        
        print(f"Spectrogram active (device {device_index}, {samplerate}Hz)")
        print(f"FFT size: {fft_size}, Overlap: {overlap*100:.0f}%")
        print(f"Frequency range: {freq_range[0]}-{freq_range[1]} Hz")
        
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(12, 8))
        plt.tight_layout()
        
        # Audio callback function
        def audio_callback(indata, frames, time_info, status):
            nonlocal audio_buffer, spectrogram_buffer, buffer_index
            
            # Update audio buffer
            new_data = indata.flatten()
            if len(new_data) >= len(audio_buffer):
                audio_buffer = new_data[:len(audio_buffer)]
            else:
                audio_buffer = np.roll(audio_buffer, -len(new_data))
                audio_buffer[-len(new_data):] = new_data
            
            # Compute FFT when we have enough data
            if len(new_data) > 0:
                # Apply window
                windowed = audio_buffer * np.hanning(fft_size)
                
                # Compute FFT
                fft_result = np.fft.rfft(windowed)
                magnitude = np.abs(fft_result)
                
                # Convert to dB
                magnitude_db = 20 * np.log10(magnitude + 1e-10)
                
                # Add to spectrogram buffer
                spectrogram_buffer[:, buffer_index] = magnitude_db
                buffer_index = (buffer_index + 1) % spectrogram_length
            
            if status:
                print(f"Spectrogram callback status: {status}")
        
        def update_spectrogram():
            """Update the spectrogram display."""
            ax.clear()
            
            # Create frequency axis
            freqs = np.fft.rfftfreq(fft_size, 1/samplerate)
            
            # Filter frequency range
            freq_mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
            display_freqs = freqs[freq_mask]
            display_data = spectrogram_buffer[freq_mask, :]
            
            # Create time axis
            time_axis = np.arange(spectrogram_length) * (blocksize / samplerate)
            
            # Plot spectrogram
            im = ax.imshow(display_data, aspect='auto', origin='lower', 
                          extent=[0, time_axis[-1], display_freqs[0], display_freqs[-1]],
                          cmap='viridis', vmin=-80, vmax=0)
            
            # Set labels and title
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Frequency (Hz)')
            ax.set_title(f'Spectrogram - Device {device_index}')
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Magnitude (dB)')
            
            return im
        
        # Start audio stream
        import sounddevice as sd
        stream = sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        )
        
        with stream:
            plot_count = 0
            last_save_time = time.time()
            
            while stream.active:
                current_time = time.time()
                
                # Save plot every 15 seconds
                if current_time - last_save_time >= 15.0:
                    try:
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"spectrogram_{timestamp}_{plot_count:03d}.png"
                        
                        # Create plots directory if it doesn't exist
                        plots_dir = config.get('plots_dir', 'plots')
                        if not os.path.exists(plots_dir):
                            os.makedirs(plots_dir)
                        
                        filepath = os.path.join(plots_dir, filename)
                        
                        # Update and save plot
                        update_spectrogram()
                        fig.savefig(filepath, dpi=100, bbox_inches='tight')
                        
                        print(f"Saved spectrogram plot: {filename}")
                        plot_count += 1
                        last_save_time = current_time
                        
                    except Exception as e:
                        print(f"Error saving spectrogram plot: {e}")
                
                time.sleep(2.0)
                
    except KeyboardInterrupt:
        print("\nSpectrogram stopped by user")
    except Exception as e:
        print(f"Spectrogram error: {e}")
        logging.error(f"Spectrogram error: {e}")
    finally:
        plt.close('all')

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
        
        # Audio callback function
        def audio_callback(indata, frames, time_info, status):
            nonlocal audio_buffer, buffer_index, triggered, trigger_index, last_sample
            
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
            
            if status:
                print(f"Trigger callback status: {status}")
        
        # Start audio stream
        import sounddevice as sd
        stream = sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        )
        
        with stream:
            trigger_count = 0
            
            while stream.active:
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
