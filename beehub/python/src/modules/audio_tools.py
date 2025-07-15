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
    """VU meter function using PyAudio exclusively."""
    # Extract configuration
    sound_in_id = config['sound_in_id']
    sound_in_chs = config['sound_in_chs']
    channel = config['monitor_channel']
    sample_rate = config['PRIMARY_IN_SAMPLERATE']
    is_wsl = config['is_wsl']
    is_macos = config['is_macos']
    debug_verbose = config.get('DEBUG_VERBOSE', False)

    print(f"\nVU meter monitoring channel: {channel+1}")
    fullscale_bar = '*' * 50
    print("fullscale:", fullscale_bar.ljust(50, ' '))

    last_print = ""

    def callback_input(in_data, frame_count, time_info, status):
        nonlocal last_print
        try:
            # Convert PyAudio bytes to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            
            # Handle multi-channel
            if sound_in_chs > 1:
                audio_data = audio_data.reshape(-1, sound_in_chs)
                selected_channel = min(channel, audio_data.shape[1] - 1)
                channel_data = audio_data[:, selected_channel]
            else:
                channel_data = audio_data
            
            audio_level = np.max(np.abs(channel_data))
            normalized_value = int((audio_level / 1.0) * 50)
            
            asterisks = '*' * normalized_value
            current_print = ' ' * 11 + asterisks.ljust(50, ' ')
            
            if current_print != last_print:
                print(current_print, end='\r')
                last_print = current_print
                sys.stdout.flush()
                
            return (None, 0)  # paContinue
        except Exception as e:
            print(f"\rVU meter error: {e}", end='\r\n')
            return (None, 1)  # paAbort

    try:
        # Use PyAudio instead of sounddevice
        manager = AudioPortManager(target_sample_rate=sample_rate, target_bit_depth=16)
        
        if is_wsl and debug_verbose:
            print("[VU Debug] Using WSL audio configuration")
        
        # Create PyAudio stream
        stream = manager.create_input_stream(
            device_index=sound_in_id,
            sample_rate=sample_rate,
            channels=sound_in_chs,
            callback=callback_input,
            frames_per_buffer=1024
        )
        
        stream.start_stream()
        
        # Keep running until externally terminated
        while stream.is_active():
            time.sleep(0.1)
            
    except Exception as e:
        print(f"\nVU meter error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nStopping VU meter...")

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
