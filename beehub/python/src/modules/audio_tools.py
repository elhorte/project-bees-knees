"""
BMAR Audio Tools Module - SOUNDDEVICE VERSION
Contains VU meter, intercom monitoring, and audio diagnostic utilities.
"""

import numpy as np
import threading
import time
import logging
import sounddevice as sd
import sys

def vu_meter(config, stop_event=None):
    """Real-time VU meter using sounddevice exclusively."""
    
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
        
        # Use sounddevice exclusively
        return _vu_meter_sounddevice(config, stop_event)
            
    except Exception as e:
        print(f"VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _vu_meter_sounddevice(config, stop_event=None):
    """VU meter using sounddevice exclusively."""
    
    try:
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 256)  # Smaller buffer for faster updates
        monitor_channel = config.get('monitor_channel', 0)
        
        # Force smaller blocksize for responsive VU meter
        if blocksize > 256:
            blocksize = 256  # ~5.8ms at 44100Hz for very responsive updates
        
        # Validate device and channels
        try:
            device_info = sd.query_devices(device_index, 'input')
            max_input_channels = int(device_info['max_input_channels'])
            actual_channels = min(channels, max_input_channels)
            
            if monitor_channel >= actual_channels:
                print(f"Channel {monitor_channel + 1} not available, using channel 1")
                monitor_channel = 0
                
        except Exception as e:
            print(f"Error getting device info: {e}")
            actual_channels = channels
        
        # Global variable to track VU meter data
        vu_data = {'db_level': -80, 'rms_level': 0.0}
        
        # Audio callback for VU meter
        def audio_callback(indata, frames, time, status):
            try:
                # Check for stop event first
                if stop_event and stop_event.is_set():
                    raise sd.CallbackStop()
                    
                # Check for input overflow
                if status.input_overflow:
                    print(f"\nAudio input overflow")
                
                # Extract channel data
                if actual_channels > 1:
                    channel_data = indata[:, monitor_channel]
                else:
                    channel_data = indata.flatten()
                
                # Calculate RMS level
                rms_level = np.sqrt(np.mean(channel_data**2))
                
                # Convert to dB
                if rms_level > 0:
                    db_level = 20 * np.log10(rms_level)
                else:
                    db_level = -80
                
                # Update global data
                vu_data['db_level'] = db_level
                vu_data['rms_level'] = rms_level
                
            except Exception as e:
                print(f"VU meter callback error: {e}")
                raise sd.CallbackStop()
        
        # Start stream with sounddevice
        with sd.InputStream(
            device=device_index,
            channels=actual_channels,
            samplerate=int(samplerate),
            blocksize=blocksize,
            dtype='float32',
            callback=audio_callback
        ):
            try:
                while True:
                    # Check for stop event
                    if stop_event and stop_event.is_set():
                        break
                    
                    # Display VU meter
                    _display_vu_meter(vu_data['db_level'], vu_data['rms_level'])
                    time.sleep(0.05)  # Update display at ~20Hz
                    
            except KeyboardInterrupt:
                pass
        
        # Clear the VU meter line and print stop message
        print("\r" + " " * 80 + "\r", end="", flush=True)  # Clear the line
        print("VU meter stopped")
        
    except Exception as e:
        print(f"Sounddevice VU meter error: {e}")
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
    
    def audio_callback(indata, frames, time, status):
        try:
            # Pure intercom audio processing - no VU meter calculations
            # Audio data flows through for monitoring, no level processing
            # Use separate 'v' command for VU meter display
            
            return True
            
        except (OSError, ValueError) as e:
            # Silent error handling - no terminal output
            return False
    
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
        
        try:
            # Use sounddevice instead of PyAudio for streaming
            with sd.InputStream(
                device=input_device,
                channels=channels,
                samplerate=samplerate,
                dtype='int16' if bit_depth == 16 else 'float32',
                blocksize=1024,
                callback=audio_callback
            ) as stream:
                # Monitor with user input check
                import select
                
                try:
                    while True:
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
                
                except (OSError, ValueError):
                    # Silent error handling - no terminal output to avoid interfering with VU meter
                    pass
                
                # Display stop message only if VU meter is not active
                if not vu_meter_active:
                    print("\nMicrophone monitoring stopped")
                
        except (OSError, ValueError):
            # Silent error handling - no terminal output to avoid interfering with VU meter
            pass
            
    except (OSError, ValueError):
        # Silent error handling - no terminal output to avoid interfering with VU meter
        pass

def audio_device_test(device_index, samplerate=44100, duration=3.0):
    """Test audio device using sounddevice directly."""
    try:
        # Generate test tone
        t = np.linspace(0, duration, int(duration * samplerate), False)
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        
        # Test the device using sounddevice
        try:
            print(f"Testing device {device_index} at {samplerate}Hz for {duration}s")
            
            # Play test tone through the device
            sd.play(tone, samplerate=samplerate, device=device_index)
            sd.wait()  # Wait until playback is done
            
            print(f"Device {device_index} test completed successfully")
            return True
            
        except Exception as e:
            print(f"Device {device_index} test failed: {e}")
            return False
            
    except Exception as e:
        print(f"Error in device test: {e}")
        return False

def check_audio_driver_info():
    """Check audio driver info using sounddevice."""
    try:
        print("\nAudio Driver Information:")
        print("-" * 40)
        
        # Get sounddevice version
        try:
            print(f"Sounddevice version: {sd.__version__}")
        except AttributeError:
            print("Sounddevice version: Unknown")
        
        # Get host API information
        host_apis = sd.query_hostapis()
        print(f"Available host APIs: {len(host_apis)}")
        for i, api in enumerate(host_apis):
            print(f"  API {i}: {api['name']} - {api['device_count']} devices")
        
        # Get default devices
        try:
            default_input = sd.query_devices(kind='input')
            default_output = sd.query_devices(kind='output')
            print(f"Default input: {default_input['name']}")
            print(f"Default output: {default_output['name']}")
        except Exception:
            print("Default devices: Not available")
        
        print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

def benchmark_audio_performance(device_index, samplerate=44100, duration=10.0):
    """Benchmark using sounddevice directly."""
    callback_count = 0
    underrun_count = 0
    total_frames = 0
    
    def audio_callback(indata, frames, time, status):
        nonlocal callback_count, underrun_count, total_frames
        
        callback_count += 1
        total_frames += frames
        
        if status.input_underflow or status.input_overflow:
            underrun_count += 1
        
        # Simple processing
        _ = np.mean(indata**2)
    
    try:
        # Use sounddevice for benchmarking
        with sd.InputStream(
            device=device_index,
            channels=1,
            samplerate=samplerate,
            dtype='float32',
            blocksize=1024,
            callback=audio_callback
        ):
            start_time = time.time()
            sd.sleep(int(duration * 1000))  # Convert to milliseconds
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
            
    except Exception as e:
        print(f"Benchmark error: {e}")
        return None

# Stub functions for compatibility - not yet fully implemented in sounddevice version
def measure_device_latency(input_device, output_device, samplerate=44100, duration=2.0):
    """Latency measurement not yet implemented for sounddevice."""
    _ = (input_device, output_device, samplerate, duration)  # Avoid unused warnings
    print("Latency measurement not yet implemented for sounddevice")
    return None

def audio_spectrum_analyzer(config, duration=10.0):
    """Spectrum analyzer not yet implemented for sounddevice."""
    _ = (config, duration)  # Avoid unused warnings
    print("Spectrum analyzer not yet implemented for sounddevice")

def audio_loopback_test(input_device, output_device, samplerate=44100, duration=5.0):
    """Loopback test not yet implemented for sounddevice."""
    _ = (input_device, output_device, samplerate, duration)  # Avoid unused warnings
    print("Loopback test not yet implemented for sounddevice")
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
