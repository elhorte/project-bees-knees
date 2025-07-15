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

def _record_audio_pyaudio(duration, device_index, channels, samplerate, blocksize, task_name="audio recording"):
    """Record audio using PyAudio with progress bar and virtual device support."""
    
    # Check for virtual device (device_index=None)
    if device_index is None:
        print(f"Virtual device detected for {task_name} - generating synthetic audio")
        return _generate_synthetic_audio(duration, channels, samplerate, task_name)
    
    try:
        import pyaudio
    except ImportError:
        print("PyAudio not available, falling back to sounddevice")
        return _record_audio_sounddevice(duration, device_index, channels, samplerate, blocksize, task_name)
    
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
            print(f"Device only supports {max_input_channels} input channels, using {actual_channels}")
        
        # Create recording array
        recording_array = np.zeros((num_frames, actual_channels), dtype=np.float32)
        
        print(f"Recording {duration}s of audio from device {device_index}...")
        print(f"Sample rate: {samplerate}Hz, Channels: {actual_channels}, Block size: {chunk_size}")
        
        def callback(indata, frame_count, time_info, status):
            nonlocal frames_recorded, recording_complete
            try:
                if status:
                    print(f"PyAudio stream status: {status}")
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
                print(f"Error in PyAudio callback: {e}")
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
            print(f"Recording progress: {progress_bar}")
        
        stream.stop_stream()
        stream.close()
        
        if frames_recorded < num_frames * 0.9:
            print(f"Warning: Recording incomplete: only got {frames_recorded}/{num_frames} frames.")
            return None, 0
        
        print(f"Finished {task_name}.")
        return recording_array, actual_channels

    except Exception as e:
        print(f"Failed to record audio with PyAudio for {task_name}: {e}")
        return None, 0
    finally:
        if p:
            try:
                p.terminate()
                time.sleep(0.1)  # Allow time for resources to be released
            except Exception as e:
                print(f"Error terminating PyAudio instance for {task_name}: {e}")

def _generate_synthetic_audio(duration, channels, samplerate, task_name="synthetic audio"):
    """Generate synthetic audio data for virtual devices."""
    try:
        print(f"Generating {duration}s of synthetic audio for {task_name}...")
        
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
            
            print(f"Generated {duration}s synthetic audio ({channels} channels)")
            return multi_channel_data, channels
        else:
            print(f"Generated {duration}s synthetic audio (mono)")
            return synthetic_data, 1
            
    except Exception as e:
        print(f"Error generating synthetic audio for {task_name}: {e}")
        return None, 0

# Add progress bar function if it doesn't exist
def create_progress_bar(current, total, width=40):
    """Create a text progress bar."""
    if total == 0:
        return "[" + "=" * width + "] 100%"
    
    progress = min(current / total, 1.0)
    filled = int(width * progress)
    bar = "=" * filled + "-" * (width - filled)
    percentage = int(progress * 100)
    
    return f"[{bar}] {percentage}%"

def _record_audio_pyaudio(duration, device_index, channels, samplerate, blocksize, task_name="audio recording"):
    """Record audio using PyAudio with progress bar and virtual device support."""
    
    # Check for virtual device (device_index=None)
    if device_index is None:
        print(f"Virtual device detected for {task_name} - generating synthetic audio")
        return _generate_synthetic_audio(duration, channels, samplerate, task_name)
    
    try:
        import pyaudio
    except ImportError:
        print("PyAudio not available, falling back to sounddevice")
        return _record_audio_sounddevice(duration, device_index, channels, samplerate, blocksize, task_name)
    
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
            print(f"Device only supports {max_input_channels} input channels, using {actual_channels}")
        
        # Create recording array
        recording_array = np.zeros((num_frames, actual_channels), dtype=np.float32)
        
        print(f"Recording {duration}s of audio from device {device_index}...")
        print(f"Sample rate: {samplerate}Hz, Channels: {actual_channels}, Block size: {chunk_size}")
        
        def callback(indata, frame_count, time_info, status):
            nonlocal frames_recorded, recording_complete
            try:
                if status:
                    print(f"PyAudio stream status: {status}")
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
                print(f"Error in PyAudio callback: {e}")
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
            print(f"Recording progress: {progress_bar}")
        
        stream.stop_stream()
        stream.close()
        
        if frames_recorded < num_frames * 0.9:
            print(f"Warning: Recording incomplete: only got {frames_recorded}/{num_frames} frames.")
            return None, 0
        
        print(f"Finished {task_name}.")
        return recording_array, actual_channels

    except Exception as e:
        print(f"Failed to record audio with PyAudio for {task_name}: {e}")
        return None, 0
    finally:
        if p:
            try:
                p.terminate()
                time.sleep(0.1)  # Allow time for resources to be released
            except Exception as e:
                print(f"Error terminating PyAudio instance for {task_name}: {e}")

def _record_audio_sounddevice(duration, device_index, channels, samplerate, blocksize, task_name="audio recording"):
    """Fallback recording using sounddevice with manual progress tracking."""
    
    try:
        import sounddevice as sd
        
        # Calculate total samples needed
        total_samples = int(samplerate * duration)
        
        # Validate device channels
        try:
            device_info = sd.query_devices(device_index)
            max_input_channels = int(device_info['max_input_channels'])
            actual_channels = min(channels, max_input_channels)
            
            if actual_channels != channels:
                print(f"Device only supports {max_input_channels} input channels, using {actual_channels}")
        except:
            actual_channels = channels
        
        # Initialize multi-channel recording array
        recording_array = np.zeros((total_samples, actual_channels), dtype=np.float32)
        samples_collected = 0
        
        print(f"Recording {duration}s of audio from device {device_index} using sounddevice...")
        print(f"Sample rate: {samplerate}Hz, Channels: {actual_channels}, Block size: {blocksize}")
        
        # Progress tracking
        progress_lock = threading.Lock()
        
        # Audio callback function
        def audio_callback(indata, frames, time_info, status):
            nonlocal recording_array, samples_collected
            
            if status:
                print(f"Audio status: {status}")
            
            with progress_lock:
                if samples_collected < total_samples:
                    # Record all channels (not just first channel)
                    data_frames = min(len(indata), total_samples - samples_collected)
                    
                    if data_frames > 0:
                        # Handle channel mismatch
                        if indata.shape[1] >= actual_channels:
                            # Take only the channels we need
                            channel_data = indata[:data_frames, :actual_channels]
                        else:
                            # Pad with zeros if device has fewer channels than expected
                            channel_data = np.zeros((data_frames, actual_channels), dtype=np.float32)
                            available_channels = min(indata.shape[1], actual_channels)
                            channel_data[:, :available_channels] = indata[:data_frames, :available_channels]
                        
                        # Store in recording array
                        end_idx = samples_collected + data_frames
                        recording_array[samples_collected:end_idx] = channel_data
                        samples_collected += data_frames
        
        # Start audio stream
        with sd.InputStream(
            device=device_index,
            channels=actual_channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        ):
            # Wait for capture to complete with progress
            while samples_collected < total_samples:
                progress_bar = create_progress_bar(samples_collected, total_samples)
                print(f"Recording progress: {progress_bar}", end='\r')
                time.sleep(0.1)
        
        # Final progress
        progress_bar = create_progress_bar(total_samples, total_samples)
        print(f"Recording progress: {progress_bar}")
        
        print(f"Finished {task_name}.")
        return recording_array, actual_channels

    except Exception as e:
        print(f"Failed to record audio with sounddevice for {task_name}: {e}")
        return None, 0

def plot_oscope(config):
    """One-shot oscilloscope plot with GUI display and progress bar."""
    
    try:
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        plot_duration = config.get('plot_duration', 10.0)  # Duration to capture
        
        print(f"Oscilloscope capturing {plot_duration}s from device {device_index} ({samplerate}Hz)")
        
        # Record audio using PyAudio with progress bar (like original BMAR)
        recording_data, actual_channels = _record_audio_pyaudio(
            duration=plot_duration,
            device_index=device_index, 
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            task_name="oscilloscope"
        )
        
        if recording_data is None:
            print("Failed to record audio for oscilloscope.")
            return
        
        print(f"\nAudio capture complete! Recorded {len(recording_data)} samples")
        
        # Determine actual number of channels recorded
        if len(recording_data.shape) > 1:
            actual_channels = recording_data.shape[1]
            print(f"Multi-channel recording: {actual_channels} channels")
        else:
            actual_channels = 1
            # Reshape single channel data to 2D for consistent processing
            recording_data = recording_data.reshape(-1, 1)
            print(f"Single channel recording")
        
        # Create time axis
        time_axis = np.linspace(0, plot_duration, len(recording_data))
        
        # Create the plot with subplots for each channel
        print("Creating oscilloscope plot...")
        fig_height = max(6, 3 * actual_channels)  # Minimum 6" height, 3" per channel
        fig, axes = plt.subplots(actual_channels, 1, figsize=(12, fig_height))
        
        # Handle single channel case (axes won't be a list)
        if actual_channels == 1:
            axes = [axes]
        
        # Plot each channel
        for i in range(actual_channels):
            ax = axes[i]
            
            # Get channel data
            channel_data = recording_data[:, i]
            
            # Plot the waveform for this channel
            ax.plot(time_axis, channel_data, 'b-', linewidth=0.8, alpha=0.8)
            
            # Set plot properties for this channel
            ax.set_xlim(0, plot_duration)
            ax.set_ylim(-1.0, 1.0)
            ax.set_ylabel('Amplitude')
            ax.set_title(f'Oscilloscope Ch{i+1} - Device {device_index} ({samplerate}Hz, {plot_duration}s)')
            ax.grid(True, alpha=0.3)
            
            # Add graticule
            # Horizontal line at 0
            ax.axhline(y=0, color='gray', linewidth=0.5, alpha=0.7)
            
            # Vertical lines at each second
            for t in range(0, int(plot_duration) + 1):
                ax.axvline(x=t, color='gray', linewidth=0.5, alpha=0.5)
            
            # Add minor vertical lines at 0.5 second intervals
            for t in np.arange(0.5, plot_duration, 0.5):
                ax.axvline(x=t, color='gray', linewidth=0.3, alpha=0.3, linestyle='--')
            
            # Configure grid and ticks
            ax.set_xticks(range(0, int(plot_duration) + 1))
            ax.set_yticks([-1.0, -0.5, 0, 0.5, 1.0])
            
            # Calculate and display statistics for this channel
            rms_level = np.sqrt(np.mean(channel_data**2))
            peak_level = np.max(np.abs(channel_data))
            zero_crossings = np.sum(np.diff(np.sign(channel_data)) != 0)
            
            # Add statistics text box for this channel
            stats_text = f'RMS: {rms_level:.4f}\nPeak: {peak_level:.4f}\nZero X: {zero_crossings}'
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.8),
                    verticalalignment='top', fontsize=9)
            
            # Add frequency estimation for this channel if possible
            if len(channel_data) > samplerate:  # At least 1 second of data
                try:
                    # Simple frequency estimation using zero crossings
                    estimated_freq = zero_crossings / (2 * plot_duration)
                    ax.text(0.02, 0.75, f'Est. Freq: {estimated_freq:.1f} Hz', 
                            transform=ax.transAxes,
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.8),
                            fontsize=9)
                except:
                    pass
            
            # Only add X-axis label to the bottom subplot
            if i == actual_channels - 1:
                ax.set_xlabel('Time (seconds)')
        
        plt.tight_layout()
        
        # Save the plot
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"oscope_{timestamp}.png"
        
        plots_dir = config.get('plots_dir', 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
        
        filepath = os.path.join(plots_dir, filename)
        
        print(f"Saving plot: {filename}")
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        
        # Try to show the plot in a GUI window
        if GUI_AVAILABLE:
            try:
                print("Displaying oscilloscope plot...")
                plt.show(block=True)  # Force blocking display
                print("Oscilloscope plot window closed.")
            except Exception as e:
                print(f"Could not display GUI window: {e}")
                print("Opening plot file instead...")
                _try_open_plot_file(filepath)
        else:
            print("GUI not available. Opening plot file...")
            _try_open_plot_file(filepath)
        
        print(f"Oscilloscope plot saved: {filepath}")
        
    except KeyboardInterrupt:
        print("\nOscilloscope cancelled by user")
    except Exception as e:
        print(f"Oscilloscope error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        plt.close('all')

def plot_oscope_continuous(config):
    """Continuous oscilloscope plot for background monitoring."""
    
    # Set matplotlib to non-interactive backend for background processes
    matplotlib.use('Agg')
    
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
        
        print(f"Continuous oscilloscope active (device {device_index}, {samplerate}Hz)")
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
            # Create animation with explicit save_count to avoid warning
            ani = animation.FuncAnimation(fig, animate, interval=50, blit=False, 
                                        save_count=100, cache_frame_data=False)
            
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
                        
                        print(f"Saved continuous oscilloscope plot: {filename}")
                        plot_count += 1
                        last_save_time = current_time
                        
                    except Exception as e:
                        print(f"Error saving continuous oscilloscope plot: {e}")
                
                time.sleep(1.0)
                
    except KeyboardInterrupt:
        print("\nContinuous oscilloscope stopped by user")
    except Exception as e:
        print(f"Continuous oscilloscope error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        plt.close('all')

def plot_spectrogram(config):
    """One-shot spectrogram plot with GUI display and progress bar."""
    
    try:
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        fft_size = config.get('fft_size', 2048)
        overlap = config.get('overlap', 0.75)
        capture_duration = config.get('capture_duration', 5.0)  # Duration to capture
        
        print(f"Spectrogram capturing {capture_duration}s from device {device_index} ({samplerate}Hz)")
        
        # Calculate total samples needed
        total_samples = int(samplerate * capture_duration)
        audio_data = []
        samples_collected = 0
        
        import sounddevice as sd
        import threading
        from scipy import signal as scipy_signal
        
        # Progress tracking
        progress_lock = threading.Lock()
        
        # Audio callback function
        def audio_callback(indata, frames, time_info, status):
            nonlocal audio_data, samples_collected
            
            if status:
                print(f"Audio status: {status}")
            
            with progress_lock:
                if samples_collected < total_samples:
                    # Take only the first channel if multi-channel
                    if channels > 1:
                        data = indata[:, 0]  # First channel only
                    else:
                        data = indata.flatten()
                    
                    # Don't exceed total samples needed
                    remaining_samples = total_samples - samples_collected
                    samples_to_take = min(len(data), remaining_samples)
                    
                    if samples_to_take > 0:
                        audio_data.extend(data[:samples_to_take])
                        samples_collected += samples_to_take
                        
                        # Show progress
                        progress = (samples_collected / total_samples) * 100
                        if samples_collected % (samplerate // 4) == 0:  # Update every 0.25 seconds
                            print(f"\rCapturing audio: {progress:.1f}% complete", end='', flush=True)
        
        print("Starting audio capture...")
        
        # Start audio stream
        with sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        ):
            # Wait for capture to complete
            while samples_collected < total_samples:
                time.sleep(0.1)
        
        print(f"\nAudio capture complete! Collected {len(audio_data)} samples")
        
        # Convert to numpy array
        audio_data = np.array(audio_data)
        
        # Calculate spectrogram parameters
        hop_length = int(fft_size * (1 - overlap))
        
        print("Computing spectrogram...")
        
        # Compute spectrogram using scipy
        frequencies, times, Sxx = scipy_signal.spectrogram(
            audio_data,
            fs=samplerate,
            window='hann',
            nperseg=fft_size,
            noverlap=int(fft_size * overlap),
            scaling='density'
        )
        
        # Convert to dB
        Sxx_db = 10 * np.log10(Sxx + 1e-10)
        
        # Filter frequency range if specified
        freq_range = config.get('freq_range', [0, samplerate // 2])
        freq_mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
        display_freqs = frequencies[freq_mask]
        display_Sxx = Sxx_db[freq_mask, :]
        
        # Create the plot
        print("Creating spectrogram plot...")
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Plot spectrogram
        im = ax.imshow(
            display_Sxx, 
            aspect='auto', 
            origin='lower',
            extent=[0, capture_duration, display_freqs[0], display_freqs[-1]],
            cmap='viridis',
            vmin=np.percentile(display_Sxx, 5),  # Use percentiles for better contrast
            vmax=np.percentile(display_Sxx, 95)
        )
        
        # Set labels and title
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Frequency (Hz)')
        ax.set_title(f'Spectrogram - Device {device_index} ({samplerate}Hz, {capture_duration}s capture)')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Power Spectral Density (dB/Hz)')
        
        # Add statistics
        peak_freq_idx = np.unravel_index(np.argmax(display_Sxx), display_Sxx.shape)
        peak_freq = display_freqs[peak_freq_idx[0]]
        peak_time = times[peak_freq_idx[1]]
        
        # Calculate average power in different frequency bands
        low_band = (display_freqs >= 0) & (display_freqs <= 1000)
        mid_band = (display_freqs > 1000) & (display_freqs <= 5000)
        high_band = (display_freqs > 5000)
        
        low_power = np.mean(display_Sxx[low_band, :]) if np.any(low_band) else 0
        mid_power = np.mean(display_Sxx[mid_band, :]) if np.any(mid_band) else 0
        high_power = np.mean(display_Sxx[high_band, :]) if np.any(high_band) else 0
        
        # Add statistics text box
        stats_text = f'Peak: {peak_freq:.1f} Hz @ {peak_time:.2f}s\n'
        stats_text += f'Low (0-1kHz): {low_power:.1f} dB\n'
        stats_text += f'Mid (1-5kHz): {mid_power:.1f} dB\n'
        stats_text += f'High (>5kHz): {high_power:.1f} dB'
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8),
                verticalalignment='top', fontsize=10)
        
        plt.tight_layout()
        
        # Save the plot
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"spectrogram_{timestamp}.png"
        
        plots_dir = config.get('plots_dir', 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
        
        filepath = os.path.join(plots_dir, filename)
        
        print(f"Saving plot: {filename}")
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        
        # Try to show the plot in a GUI window
        if GUI_AVAILABLE:
            try:
                print("Displaying spectrogram plot...")
                plt.show(block=True)  # Force blocking display
                print("Spectrogram plot window closed.")
            except Exception as e:
                print(f"Could not display GUI window: {e}")
                print("Opening plot file instead...")
                _try_open_plot_file(filepath)
        else:
            print("GUI not available. Opening plot file...")
            _try_open_plot_file(filepath)
        
        print(f"Spectrogram plot saved: {filepath}")
        
    except KeyboardInterrupt:
        print("\nSpectrogram cancelled by user")
    except Exception as e:
        print(f"Spectrogram error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        plt.close('all')

def plot_spectrogram_continuous(config):
    """Continuous spectrogram plot for background monitoring."""
    
    # Set matplotlib to non-interactive backend for background processes
    matplotlib.use('Agg')
    
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
        
        print(f"Continuous spectrogram active (device {device_index}, {samplerate}Hz)")
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
            ax.set_title(f'Continuous Spectrogram - Device {device_index}')
            
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
                        
                        print(f"Saved continuous spectrogram plot: {filename}")
                        plot_count += 1
                        last_save_time = current_time
                        
                    except Exception as e:
                        print(f"Error saving continuous spectrogram plot: {e}")
                
                time.sleep(2.0)
                
    except KeyboardInterrupt:
        print("\nContinuous spectrogram stopped by user")
    except Exception as e:
        print(f"Continuous spectrogram error: {e}")
        logging.error(f"Continuous spectrogram error: {e}")
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

def plot_fft(config):
    """Single-shot FFT plot of audio with progress bar."""
    
    try:
        # Force garbage collection before starting
        import gc
        gc.collect()
        
        # Ensure clean matplotlib state for this process
        import matplotlib
        matplotlib.use('Agg', force=True)
        import matplotlib.pyplot as plt
        plt.close('all')  # Close any existing figures
        
        # Brief delay to ensure clean audio device state
        time.sleep(0.1)
        
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        channels = config['channels']
        blocksize = config.get('blocksize', 1024)
        plots_dir = config['plots_dir']
        monitor_channel = config.get('monitor_channel', 0)
        
        # Import configuration values
        from .bmar_config import FFT_DURATION, FFT_GAIN, LOCATION_ID, HIVE_ID, PRIMARY_BITDEPTH
        
        # Record audio with progress bar
        print(f"Starting FFT analysis on channel {monitor_channel + 1}...")
        recording, actual_channels = _record_audio_pyaudio(
            FFT_DURATION, device_index, channels, samplerate, blocksize, "FFT analysis"
        )
        
        if recording is None:
            logging.error("Failed to record audio for FFT.")
            return

        # Ensure channel index is valid
        if monitor_channel >= actual_channels:
            logging.warning(f"Channel {monitor_channel+1} not available for FFT, using channel 1.")
            monitor_channel = 0
            
        # Extract the requested channel
        if len(recording.shape) > 1:
            single_channel_audio = recording[:, monitor_channel]
        else:
            single_channel_audio = recording.flatten()
        
        # Apply gain if needed
        if FFT_GAIN > 0:
            gain = 10 ** (FFT_GAIN / 20)
            logging.info(f"Applying FFT gain of: {gain:.1f}")
            single_channel_audio *= gain

        logging.info("Performing FFT...")
        
        # Import FFT functions
        from scipy.fft import rfft, rfftfreq
        
        # Perform FFT
        yf = rfft(single_channel_audio.flatten())
        xf = rfftfreq(len(single_channel_audio), 1 / samplerate)

        # Define bucket width
        FFT_BW = 1000  # bandwidth of each bucket in hertz
        bucket_width = FFT_BW
        bucket_size = int(bucket_width * len(single_channel_audio) / samplerate)

        # Calculate the number of complete buckets
        num_buckets = len(yf) // bucket_size
        
        # Average buckets - ensure both arrays have the same length
        buckets = []
        bucket_freqs = []
        for i in range(num_buckets):
            start_idx = i * bucket_size
            end_idx = start_idx + bucket_size
            buckets.append(yf[start_idx:end_idx].mean())
            bucket_freqs.append(xf[start_idx:end_idx].mean())
        
        buckets = np.array(buckets)
        bucket_freqs = np.array(bucket_freqs)

        logging.info("Creating FFT plot...")
        # Create figure with reduced DPI for better performance
        fig = plt.figure(figsize=(10, 6), dpi=80)
        plt.plot(bucket_freqs, np.abs(buckets), linewidth=1.0)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title(f'FFT Plot monitoring ch: {monitor_channel + 1} of {actual_channels} channels')
        plt.grid(True)

        # Save the plot
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        plotname = os.path.join(plots_dir, f"{timestamp}_fft_{int(samplerate/1000)}_kHz_{PRIMARY_BITDEPTH}_{LOCATION_ID}_{HIVE_ID}.png")
        logging.info(f"Saving FFT plot to: {plotname}")
        
        # Make sure the directory exists
        os.makedirs(os.path.dirname(plotname), exist_ok=True)
        
        # Display the expanded path
        expanded_path = os.path.abspath(os.path.expanduser(plotname))
        logging.info(f"Absolute path: {expanded_path}")
        
        # Save with optimized settings
        logging.info("Saving figure...")
        plt.savefig(expanded_path, dpi=80, bbox_inches='tight', pad_inches=0.1, format='png')
        logging.info("Plot saved successfully")
        plt.close('all')  # Close all figures

        # Open the saved image
        try:
            # First verify the file exists
            if not os.path.exists(expanded_path):
                logging.error(f"Plot file does not exist at: {expanded_path}")
                return
                
            logging.info(f"Plot file exists, size: {os.path.getsize(expanded_path)} bytes")
            print(f"FFT plot saved to: {expanded_path}")
            
            # Open the plot file
            _try_open_plot_file(expanded_path)
                
        except Exception as e:
            logging.error("Could not open image viewer", exc_info=True)
            logging.info(f"Image saved at: {expanded_path}")
            logging.info("You can manually open this file with your image viewer")
            
    except Exception as e:
        logging.error("Error in FFT analysis", exc_info=True)
        print(f"Error in FFT analysis: {e}")
    finally:
        # Ensure cleanup happens
        try:
            plt.close('all')
            import gc
            gc.collect()
        except:
            pass
