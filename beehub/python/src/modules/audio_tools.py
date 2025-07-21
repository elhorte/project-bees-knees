"""
BMAR Audio Tools Module - PURE PYAUDIO
Contains VU meter, intercom monitoring, and audio diagnostic utilities.
"""

import numpy as np
import threading
import time
import logging
import pyaudio
import sys

def vu_meter(config, stop_event=None):
    """Real-time VU meter using PyAudio exclusively."""
    
    try:
        # Extract configuration
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 256)  # Smaller for responsive VU meter
        monitor_channel = config.get('monitor_channel', 0)
        
        # Check for virtual device
        if device_index is None:
            print("Virtual device detected - running VU meter with synthetic audio")
            return _vu_meter_virtual(config, stop_event)
        
        # Use PyAudio exclusively
        return _vu_meter_pyaudio(config, stop_event)
            
    except Exception as e:
        print(f"VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _vu_meter_pyaudio(config, stop_event=None):
    """VU meter using PyAudio exclusively."""
    
    try:
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 256)  # Smaller buffer for faster updates
        monitor_channel = config.get('monitor_channel', 0)
        
        # Force smaller blocksize for responsive VU meter
        if blocksize > 256:
            blocksize = 256  # ~5.8ms at 44100Hz for very responsive updates
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        
        # Validate device and channels
        try:
            device_info = pa.get_device_info_by_index(device_index)
            max_input_channels = int(device_info['maxInputChannels'])
            actual_channels = min(channels, max_input_channels)
            
            if monitor_channel >= actual_channels:
                print(f"Channel {monitor_channel + 1} not available, using channel 1")
                monitor_channel = 0
                
        except Exception as e:
            print(f"Error getting device info: {e}")
            actual_channels = channels
        
        # Audio callback for VU meter
        def audio_callback(in_data, frame_count, time_info, status):
            try:
                # Check for stop event first
                if stop_event and stop_event.is_set():
                    return (in_data, pyaudio.paAbort)
                    
                # Only print status for critical errors, not normal overflow conditions
                # Status 2 = paInputOverflow (common, not critical)
                # Status 1 = paOutputUnderflow  
                # Status 0 = No error
                if status and status > 2:
                    print(f"\nAudio status error: {status}")
                
                # Convert audio data
                audio_data = np.frombuffer(in_data, dtype=np.float32)
                
                if actual_channels > 1:
                    audio_data = audio_data.reshape(-1, actual_channels)
                    channel_data = audio_data[:, monitor_channel]
                else:
                    channel_data = audio_data
                
                # Calculate RMS level
                rms_level = np.sqrt(np.mean(channel_data**2))
                
                # Convert to dB
                if rms_level > 0:
                    db_level = 20 * np.log10(rms_level)
                else:
                    db_level = -80
                
                # Create VU meter display
                _display_vu_meter(db_level, rms_level)
                
                return (in_data, pyaudio.paContinue)
                
            except Exception as e:
                print(f"VU meter callback error: {e}")
                return (in_data, pyaudio.paAbort)
        
        # Open audio stream
        stream = pa.open(
            format=pyaudio.paFloat32,
            channels=actual_channels,
            rate=int(samplerate),
            input=True,
            input_device_index=device_index,
            frames_per_buffer=blocksize,
            stream_callback=audio_callback
        )
        
        stream.start_stream()
        
        try:
            while stream.is_active():
                # Check for stop event instead of keyboard input
                if stop_event and stop_event.is_set():
                    break
                time.sleep(0.1)
        except (OSError, ValueError) as e:
            print(f"\nVU meter error: {e}")
        
        # Cleanup
        stream.stop_stream()
        stream.close()
        pa.terminate()
        
        # Clear the VU meter line and print stop message
        print("\r" + " " * 80 + "\r", end="", flush=True)  # Clear the line
        print("VU meter stopped")
        
    except Exception as e:
        print(f"PyAudio VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _vu_meter_virtual(config, stop_event=None):
    """VU meter with virtual/synthetic audio."""
    
    try:
        monitor_channel = config.get('monitor_channel', 0)
        
        print(f"Starting virtual VU meter (synthetic audio, channel {monitor_channel + 1})")
        
        import random
        
        try:
            while True:
                # Check for stop event instead of keyboard input
                if stop_event and stop_event.is_set():
                    break
                        
                # Generate synthetic audio levels
                # Simulate varying audio levels
                base_level = 0.1 + 0.4 * random.random()  # 0.1 to 0.5
                
                # Add some periodic variation
                t = time.time()
                modulation = 0.3 * np.sin(2 * np.pi * 0.5 * t)  # 0.5 Hz modulation
                rms_level = base_level + modulation
                rms_level = max(0.001, min(1.0, rms_level))  # Clamp to valid range
                
                # Convert to dB
                db_level = 20 * np.log10(rms_level)
                
                # Display VU meter
                _display_vu_meter(db_level, rms_level)
                
                time.sleep(0.02)  # 50 updates per second for very responsive virtual meter
                
        except (OSError, ValueError) as e:
            print(f"\nVirtual VU meter error: {e}")
            
        print("\nVirtual VU meter stopped")
        
    except Exception as e:
        print(f"Virtual VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _display_vu_meter(db_level, rms_level):
    """Display VU meter bar."""
    
    try:
        # Clamp dB level to reasonable range
        db_level = max(-60, min(0, db_level))
        
        # Create meter bar (50 characters wide)
        meter_width = 50
        
        # Map dB level to meter position (-60dB to 0dB -> 0 to 50)
        meter_pos = int((db_level + 60) / 60 * meter_width)
        meter_pos = max(0, min(meter_width, meter_pos))
        
        # Create the meter bar
        green_zone = int(meter_width * 0.7)   # 70% green
        yellow_zone = int(meter_width * 0.9)  # 20% yellow
        # Remaining 10% is red
        
        meter_bar = ""
        for i in range(meter_width):
            if i < meter_pos:
                if i < green_zone:
                    meter_bar += "█"  # Green zone
                elif i < yellow_zone:
                    meter_bar += "▆"  # Yellow zone  
                else:
                    meter_bar += "▅"  # Red zone
            else:
                meter_bar += "·"
        
        # Format the display
        level_display = f"[{meter_bar}] {db_level:5.1f}dB (RMS: {rms_level:.4f})"
        
        # Print with carriage return to overwrite previous line
        print(f"\rVU: {level_display}", end="", flush=True)
        
    except Exception as e:
        print(f"Display error: {e}")

def intercom_m(config):
    """Microphone monitoring - listen to remote microphone audio input only."""
    
    def audio_callback(in_data, frame_count, time_info, status):
        try:
            # Pure intercom audio processing - no VU meter calculations
            # Audio data flows through for monitoring, no level processing
            # Use separate 'v' command for VU meter display
            
            return (in_data, pyaudio.paContinue)
            
        except (OSError, ValueError) as e:
            # Silent error handling - no terminal output
            return (in_data, pyaudio.paAbort)
    
    try:
        input_device = config['input_device']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        bit_depth = config.get('bit_depth', 16)
        
        # Ensure we use the exact configured parameters, not defaults
        # Note: samplerate and channels should come from bmar_config.py settings
        
        # Check if VU meter is running - use passed status instead of app object
        vu_meter_active = config.get('vu_meter_active', False)
        
        # Display status only if VU meter is not active
        if not vu_meter_active:
            print("\nMicrophone monitoring active")
            print(f"Monitoring device {input_device} ({channels} channels at {samplerate}Hz)")
            print("Press Enter to stop monitoring...")
        
        # Create input-only stream for microphone monitoring
        pa = pyaudio.PyAudio()
        
        try:
            audio_format = pyaudio.paInt16 if bit_depth == 16 else pyaudio.paFloat32
            
            stream = pa.open(
                format=audio_format,
                channels=channels,
                rate=samplerate,
                input=True,
                input_device_index=input_device,
                frames_per_buffer=1024,
                stream_callback=audio_callback
            )
            
            if stream is None:
                print("Failed to create microphone monitoring stream")
                return
            
            stream.start_stream()
            
            # Monitor with user input check
            import select
            
            try:
                while stream.is_active():
                    # Check for user input (Enter key) on Windows
                    if sys.platform == "win32":
                        import msvcrt
                        if msvcrt.kbhit():
                            key = msvcrt.getch()
                            if key in [b'\r', b'\n']:  # Enter key
                                break
                    else:
                        # Unix-like systems
                        if select.select([sys.stdin], [], [], 0)[0]:
                            input()  # Read the enter key
                            break
                    
                    time.sleep(1.0)
                    # Pure microphone monitoring - no output to terminal
            
            except (OSError, ValueError) as e:
                # Silent error handling - no terminal output to avoid interfering with VU meter
                pass
            
            # Clean up
            try:
                stream.stop_stream()
                stream.close()
                # Display stop message only if VU meter is not active
                if not vu_meter_active:
                    print("\nMicrophone monitoring stopped")
            except (OSError, ValueError):
                pass
            
        finally:
            pa.terminate()
                
    except (OSError, ValueError) as e:
        # Silent error handling - no terminal output to avoid interfering with VU meter
        pass

def audio_device_test(device_index, samplerate=44100, duration=3.0):
    """Test audio device using PyAudio directly."""
    try:
        # Generate test tone
        t = np.linspace(0, duration, int(duration * samplerate), False)
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        
        try:
            # Create output stream
            stream = pa.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=int(samplerate),
                output=True,
                output_device_index=device_index,
                frames_per_buffer=1024
            )
            
            stream.start_stream()
            
            # Write audio data
            for i in range(0, len(tone), 1024):
                chunk = tone[i:i+1024]
                if len(chunk) < 1024:
                    chunk = np.pad(chunk, (0, 1024 - len(chunk)))
                stream.write(chunk.astype(np.float32).tobytes())
            
            stream.stop_stream()
            stream.close()
            
            print(f"Device {device_index} test completed successfully")
            return True
        finally:
            pa.terminate()
            
    except Exception as e:
        print(f"Device {device_index} test failed: {e}")
        return False

def check_audio_driver_info():
    """Check audio driver info using PyAudio."""
    try:
        print("\nAudio Driver Information:")
        print("-" * 40)
        
        pa = pyaudio.PyAudio()
        
        try:
            # Get PortAudio version
            try:
                version_info = pa.get_version_text()
                print(f"PortAudio version: {version_info}")
            except AttributeError:
                print("PortAudio version: Unknown")
        
            # Get default devices
            try:
                default_input = pa.get_default_input_device_info()
                default_output = pa.get_default_output_device_info()
                print(f"Default input: {default_input['name']}")
                print(f"Default output: {default_output['name']}")
            except (OSError, ValueError):
                print("Default devices: Not available")
        finally:
            pa.terminate()
        
        print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

def benchmark_audio_performance(device_index, samplerate=44100, duration=10.0):
    """Benchmark using PyAudio directly."""
    callback_count = 0
    underrun_count = 0
    total_frames = 0
    
    def audio_callback(in_data, frame_count, time_info, status):
        nonlocal callback_count, underrun_count, total_frames
        
        callback_count += 1
        total_frames += frame_count
        
        if len(in_data) < frame_count * 4:  # Check for underruns
            underrun_count += 1
        
        # Simple processing
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        _ = np.mean(audio_data**2)
        
        return (None, pyaudio.paContinue)
    
    try:
        pa = pyaudio.PyAudio()
        
        try:
            stream = pa.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=int(samplerate),
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024,
                stream_callback=audio_callback
            )
            
            start_time = time.time()
            stream.start_stream()
            time.sleep(duration)
            stream.stop_stream()
            end_time = time.time()
            
            actual_duration = end_time - start_time
            expected_callbacks = int(actual_duration * samplerate / 1024)
            
            print("\nBenchmark Results:")
            print(f"  Duration: {actual_duration:.2f}s")
            print(f"  Callbacks: {callback_count} (expected: {expected_callbacks})")
            print(f"  Underruns: {underrun_count}")
            
            if underrun_count == 0:
                print("  Status: EXCELLENT")
            elif underrun_count < 5:
                print("  Status: GOOD")
            else:
                print("  Status: POOR")
                
            stream.close()
            
            return {
                'callback_count': callback_count,
                'underrun_count': underrun_count,
                'total_frames': total_frames
            }
        finally:
            pa.terminate()
            
    except Exception as e:
        print(f"Benchmark error: {e}")
        return None

# Stub functions for compatibility - not yet fully implemented in PyAudio version
def measure_device_latency(input_device, output_device, samplerate=44100, duration=2.0):
    """Latency measurement not yet implemented for PyAudio."""
    _ = (input_device, output_device, samplerate, duration)  # Avoid unused warnings
    print("Latency measurement not yet implemented for PyAudio")
    return None

def audio_spectrum_analyzer(config, duration=10.0):
    """Spectrum analyzer not yet implemented for PyAudio."""
    _ = (config, duration)  # Avoid unused warnings
    print("Spectrum analyzer not yet implemented for PyAudio")

def audio_loopback_test(input_device, output_device, samplerate=44100, duration=5.0):
    """Loopback test not yet implemented for PyAudio."""
    _ = (input_device, output_device, samplerate, duration)  # Avoid unused warnings
    print("Loopback test not yet implemented for PyAudio")
    return 0.0

def create_progress_bar(current, total, width=40):
    """Create a text progress bar."""
    if total == 0:
        return "[" + "=" * width + "] 100%"
    
    progress = min(current / total, 1.0)
    filled = int(width * progress)
    bar = "=" * filled + "-" * (width - filled)
    percentage = int(progress * 100)
    
    return f"[{bar}] {percentage}%"
