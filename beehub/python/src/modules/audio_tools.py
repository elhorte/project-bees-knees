"""
BMAR Audio Tools Module - CONVERTED TO PYAUDIO
Contains VU meter, intercom monitoring, and audio diagnostic utilities.
"""

import numpy as np
import threading
import time
import logging
import multiprocessing
import subprocess
import os
import sys
from .class_PyAudio import AudioPortManager

def vu_meter(config):
    """Real-time VU meter with virtual device support."""
    
    try:
        # Extract configuration
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        monitor_channel = config.get('monitor_channel', 0)
        
        print(f"VU meter monitoring channel: {monitor_channel + 1}")
        
        # Check for virtual device
        if device_index is None:
            print("Virtual device detected - running VU meter with synthetic audio")
            return _vu_meter_virtual(config)
        
        # Try PyAudio first
        try:
            import pyaudio
            return _vu_meter_pyaudio(config)
        except ImportError:
            print("PyAudio not available, trying sounddevice...")
            
        # Fall back to sounddevice
        try:
            import sounddevice as sd
            return _vu_meter_sounddevice(config)
        except ImportError:
            print("No audio libraries available for VU meter")
            return
            
    except Exception as e:
        print(f"VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _vu_meter_pyaudio(config):
    """VU meter using PyAudio."""
    
    try:
        import pyaudio
        
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        monitor_channel = config.get('monitor_channel', 0)
        
        print(f"Starting PyAudio VU meter (device {device_index}, channel {monitor_channel + 1})")
        
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
                if status:
                    print(f"Audio status: {status}")
                
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
        
        print("VU meter running... Press Ctrl+C to stop")
        stream.start_stream()
        
        try:
            while stream.is_active():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nVU meter stopped by user")
        
        # Cleanup
        stream.stop_stream()
        stream.close()
        pa.terminate()
        
    except Exception as e:
        print(f"PyAudio VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _vu_meter_sounddevice(config):
    """VU meter using sounddevice."""
    
    try:
        import sounddevice as sd
        
        device_index = config.get('device_index')
        samplerate = config.get('samplerate', 44100)
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        monitor_channel = config.get('monitor_channel', 0)
        
        print(f"Starting sounddevice VU meter (device {device_index}, channel {monitor_channel + 1})")
        
        # Audio callback for VU meter
        def audio_callback(indata, frames, time, status):
            try:
                if status:
                    print(f"Audio status: {status}")
                
                # Extract monitor channel
                if channels > 1 and monitor_channel < indata.shape[1]:
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
                
                # Create VU meter display
                _display_vu_meter(db_level, rms_level)
                
            except Exception as e:
                print(f"VU meter callback error: {e}")
        
        # Start audio stream
        with sd.InputStream(
            device=device_index,
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        ):
            print("VU meter running... Press Ctrl+C to stop")
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nVU meter stopped by user")
        
    except Exception as e:
        print(f"Sounddevice VU meter error: {e}")
        import traceback
        traceback.print_exc()

def _vu_meter_virtual(config):
    """VU meter with virtual/synthetic audio."""
    
    try:
        monitor_channel = config.get('monitor_channel', 0)
        
        print(f"Starting virtual VU meter (synthetic audio, channel {monitor_channel + 1})")
        print("VU meter running... Press Ctrl+C to stop")
        
        import random
        
        try:
            while True:
                # Generate synthetic audio levels
                # Simulate varying audio levels
                base_level = 0.1 + 0.4 * random.random()  # 0.1 to 0.5
                
                # Add some periodic variation
                import time
                t = time.time()
                modulation = 0.3 * np.sin(2 * np.pi * 0.5 * t)  # 0.5 Hz modulation
                rms_level = base_level + modulation
                rms_level = max(0.001, min(1.0, rms_level))  # Clamp to valid range
                
                # Convert to dB
                db_level = 20 * np.log10(rms_level)
                
                # Display VU meter
                _display_vu_meter(db_level, rms_level)
                
                time.sleep(0.05)  # 20 updates per second
                
        except KeyboardInterrupt:
            print("\nVirtual VU meter stopped by user")
        
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
    """Intercom monitoring using PyAudio."""
    peak_level = 0.0
    avg_level = 0.0
    sample_count = 0
    
    def audio_callback(in_data, out_data, frame_count, time_info, status):
        nonlocal peak_level, avg_level, sample_count
        
        try:
            # Convert PyAudio input to numpy
            indata = np.frombuffer(in_data, dtype=np.float32)
            
            if config['channels'] > 1:
                indata = indata.reshape(-1, config['channels'])
                monitor_ch = config.get('monitor_channel', 0)
                monitor_data = indata[:, min(monitor_ch, indata.shape[1] - 1)]
            else:
                monitor_data = indata
            
            # Calculate levels
            current_peak = np.max(np.abs(monitor_data))
            current_avg = np.sqrt(np.mean(monitor_data**2))
            
            peak_level = max(peak_level, current_peak)
            avg_level = (avg_level * sample_count + current_avg) / (sample_count + 1)
            sample_count += 1
            
            # Apply gain and output
            gain = config.get('gain', 1.0)
            output_data = monitor_data * gain
            
            # Convert back to bytes for PyAudio
            if config['channels'] > 1:
                output_array = np.tile(output_data.reshape(-1, 1), (1, config['channels']))
                output_bytes = output_array.astype(np.float32).tobytes()
            else:
                output_bytes = output_data.astype(np.float32).tobytes()
            
            # Copy to output buffer
            bytes_to_copy = min(len(output_bytes), len(out_data))
            out_data[:bytes_to_copy] = output_bytes[:bytes_to_copy]
            
            return (None, 0)  # paContinue
        except Exception as e:
            print(f"Intercom error: {e}")
            return (None, 1)  # paAbort
    
    try:
        input_device = config['input_device']
        output_device = config.get('output_device', input_device)
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        
        manager = AudioPortManager(target_sample_rate=samplerate, target_bit_depth=16)
        
        print(f"\nIntercom monitoring active")
        print(f"Input: device {input_device}, Output: device {output_device}")
        print("Press Ctrl+C to stop")
        
        # Create PyAudio duplex stream
        stream = manager.create_duplex_stream(
            input_device=input_device,
            output_device=output_device,
            sample_rate=samplerate,
            channels=channels,
            callback=audio_callback,
            frames_per_buffer=1024
        )
        
        stream.start_stream()
        start_time = time.time()
        
        while stream.is_active():
            time.sleep(5.0)
            elapsed = time.time() - start_time
            print(f"\nStats: Peak={peak_level:.3f}, Avg={avg_level:.3f}, Time={elapsed:.1f}s")
            peak_level = 0.0
                
    except KeyboardInterrupt:
        print("\nIntercom stopped by user")
    except Exception as e:
        print(f"Intercom error: {e}")

def audio_device_test(device_index, samplerate=44100, duration=3.0):
    """Test audio device using PyAudio."""
    try:
        manager = AudioPortManager(target_sample_rate=samplerate, target_bit_depth=16)
        
        # Generate test tone
        t = np.linspace(0, duration, int(duration * samplerate), False)
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        
        # Create output stream
        stream = manager.create_output_stream(
            device_index=device_index,
            sample_rate=samplerate,
            channels=1,
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
    except Exception as e:
        print(f"Device {device_index} test failed: {e}")
        return False

def check_audio_driver_info():
    """Check audio driver info using PyAudio."""
    try:
        print("\nAudio Driver Information:")
        print("-" * 40)
        
        manager = AudioPortManager()
        
        try:
            print(f"PortAudio version: {manager.pa.get_version_text()}")
        except:
            print("PortAudio version: Unknown")
        
        try:
            default_input = manager.pa.get_default_input_device_info()
            default_output = manager.pa.get_default_output_device_info()
            print(f"Default input: {default_input['name']}")
            print(f"Default output: {default_output['name']}")
        except:
            print("Default devices: Not available")
        
        print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")

def benchmark_audio_performance(device_index, samplerate=44100, duration=10.0):
    """Benchmark using PyAudio."""
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
        
        return (None, 0)  # paContinue
    
    try:
        manager = AudioPortManager(target_sample_rate=samplerate, target_bit_depth=16)
        
        stream = manager.create_input_stream(
            device_index=device_index,
            sample_rate=samplerate,
            channels=1,
            callback=audio_callback,
            frames_per_buffer=1024
        )
        
        start_time = time.time()
        stream.start_stream()
        time.sleep(duration)
        stream.stop_stream()
        end_time = time.time()
        
        actual_duration = end_time - start_time
        expected_callbacks = int(actual_duration * samplerate / 1024)
        
        print(f"\nBenchmark Results:")
        print(f"  Duration: {actual_duration:.2f}s")
        print(f"  Callbacks: {callback_count} (expected: {expected_callbacks})")
        print(f"  Underruns: {underrun_count}")
        
        if underrun_count == 0:
            print("  Status: EXCELLENT")
        elif underrun_count < 5:
            print("  Status: GOOD")
        else:
            print("  Status: POOR")
            
        return {
            'callback_count': callback_count,
            'underrun_count': underrun_count,
            'total_frames': total_frames
        }
    except Exception as e:
        print(f"Benchmark error: {e}")
        return None

# Add simplified versions of other functions...
def measure_device_latency(input_device, output_device, samplerate=44100, duration=2.0):
    """Simplified latency measurement using PyAudio."""
    print(f"Latency measurement not yet implemented for PyAudio")
    return None

def audio_spectrum_analyzer(config, duration=10.0):
    """Simplified spectrum analyzer using PyAudio."""
    print(f"Spectrum analyzer not yet implemented for PyAudio")

def audio_loopback_test(input_device, output_device, samplerate=44100, duration=5.0):
    """Simplified loopback test using PyAudio."""
    print(f"Loopback test not yet implemented for PyAudio")
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
