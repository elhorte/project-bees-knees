"""
BMAR Audio Tools Module
Contains VU meter, intercom monitoring, and audio diagnostic utilities.
"""

import numpy as np
import sounddevice as sd
import threading
import time
import logging
import multiprocessing
import subprocess
import os
import sys

def vu_meter(config):
    """VU meter function for displaying audio levels - matches original BMAR_class.py implementation."""
    # Extract configuration
    sound_in_id = config['sound_in_id']
    sound_in_chs = config['sound_in_chs']
    channel = config['monitor_channel']
    sample_rate = config['PRIMARY_IN_SAMPLERATE']
    is_wsl = config['is_wsl']
    is_macos = config['is_macos']
    os_info = config['os_info']
    debug_verbose = config.get('DEBUG_VERBOSE', False)

    # Debug: Print incoming parameter types
    if debug_verbose:
        print(f"\n[VU Debug] Parameter types:")
        print(f"  sound_in_id: {sound_in_id} (type: {type(sound_in_id)})")
        print(f"  sample_rate: {sample_rate} (type: {type(sample_rate)})")
        print(f"  sound_in_chs: {sound_in_chs} (type: {type(sound_in_chs)})")
        print(f"  channel: {channel} (type: {type(channel)})")
        print(f"  is_wsl: {is_wsl}")
        print(f"  is_macos: {is_macos}")
    
    # Ensure sample rate is an integer for buffer size calculation
    buffer_size = int(sample_rate)
    buffer = np.zeros(buffer_size)
    last_print = ""
    
    # Validate the channel is valid for the device
    if channel >= sound_in_chs:
        print(f"\nError: Selected channel {channel+1} exceeds available channels ({sound_in_chs})", end='\r\n')
        print(f"Defaulting to channel 1", end='\r\n')
        channel = 0  # Default to first channel
    
    print(f"\nVU meter monitoring channel: {channel+1}")
    
    # Display reference bars (matches original BMAR_class.py)
    fullscale_bar = '*' * 50
    print("fullscale:", fullscale_bar.ljust(50, ' '))

    def callback_input(indata, frames, time, status):
        nonlocal last_print
        try:
            # Debug first callback
            if debug_verbose and last_print == "":
                print(f"\n[VU Debug] First callback: frames={frames}, indata.shape={indata.shape}")
            
            # Always validate channel before accessing the data
            selected_channel = int(min(channel, indata.shape[1] - 1))
            
            channel_data = indata[:, selected_channel]
            # Ensure frames is an integer for array slicing
            frames_int = int(frames)
            buffer[:frames_int] = channel_data
            audio_level = np.max(np.abs(channel_data))
            normalized_value = int((audio_level / 1.0) * 50)
            
            asterisks = '*' * normalized_value
            current_print = ' ' * 11 + asterisks.ljust(50, ' ')
            
            # Only print if the value has changed
            if current_print != last_print:
                print(current_print, end='\r')
                last_print = current_print
                import sys
                sys.stdout.flush()  # Ensure output is displayed immediately
        except Exception as e:
            # Log the error but don't crash
            print(f"\rVU meter callback error: {e}", end='\r\n')
            if debug_verbose:
                print(f"Error details: channel={channel}, frames={frames}, indata.shape={indata.shape}", end='\r\n')
                import traceback
                traceback.print_exc()
            time.sleep(0.1)  # Prevent too many messages

    try:
        # Debug platform detection
        if debug_verbose:
            print(f"\n[VU Debug] Platform detection:")
            print(f"  sys.platform: {sys.platform}")
            print(f"  is_wsl: {is_wsl}")
            print(f"  is_macos: {is_macos}")
            print(f"  os_info: {os_info}")

        # In WSL, we need to use different stream parameters
        if is_wsl:
            if debug_verbose:
                print("[VU Debug] Using WSL audio configuration")
            # Check audio configuration first
            from .platform_manager import check_wsl_audio
            if not check_wsl_audio():
                raise Exception("Audio configuration check failed")
            
            # Try with minimal configuration
            try:
                with sd.InputStream(callback=callback_input,
                                  device=None,  # Use system default
                                  channels=1,   # Use mono
                                  samplerate=48000,  # Use standard rate
                                  blocksize=1024,    # Use smaller block size
                                  latency='low'):
                    # Simple loop - run until process is terminated externally
                    while True:
                        sd.sleep(100)  # Sleep for 100ms
            except Exception as e:
                print(f"\nError with default configuration: {e}")
                print("\nPlease ensure your WSL audio is properly configured.")
                raise
        else:
            if debug_verbose:
                print("[VU Debug] Using standard audio configuration (non-WSL)")
            # Make sure we request at least as many channels as our selected channel
            # Ensure all parameters are integers for compatibility
            try:
                # Simple approach - just ensure the critical parameters are integers
                with sd.InputStream(callback=callback_input,
                                  device=int(sound_in_id) if sound_in_id is not None else None,
                                  channels=int(sound_in_chs),
                                  samplerate=int(sample_rate),
                                  blocksize=1024,
                                  latency='low'):
                    # Simple loop - run until process is terminated externally
                    while True:
                        sd.sleep(100)  # Sleep for 100ms
            except Exception as e:
                print(f"\nError in VU meter InputStream: {e}")
                print(f"Debug info:")
                print(f"  sound_in_id={sound_in_id} (type: {type(sound_in_id)})")
                print(f"  sound_in_chs={sound_in_chs} (type: {type(sound_in_chs)})")
                print(f"  sample_rate={sample_rate} (type: {type(sample_rate)})")
                import traceback
                traceback.print_exc()
                raise
    except Exception as e:
        print(f"\nError in VU meter: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nStopping VU meter...")

def intercom_m(config):
    """Intercom monitoring subprocess function."""
    
    def audio_callback(indata, outdata, frames, time_info, status):
        nonlocal peak_level, avg_level, sample_count
        
        # Calculate peak and average levels
        current_peak = np.max(np.abs(indata))
        current_avg = np.sqrt(np.mean(indata**2))
        
        # Update running statistics
        peak_level = max(peak_level, current_peak)
        avg_level = (avg_level * sample_count + current_avg) / (sample_count + 1)
        sample_count += 1
        
        # Apply gain to input signal
        gain = config.get('gain', 1.0)
        outdata[:] = indata * gain
        
        if status:
            print(f"Intercom callback status: {status}")
    
    try:
        # Extract configuration
        input_device = config['input_device']
        output_device = config['output_device']
        samplerate = config['samplerate']
        channels = config.get('channels', 1)
        blocksize = config.get('blocksize', 1024)
        gain = config.get('gain', 1.0)
        
        # Initialize monitoring variables
        peak_level = 0.0
        avg_level = 0.0
        sample_count = 0
        
        print(f"\nIntercom monitoring active")
        print(f"Input: device {input_device}, Output: device {output_device}")
        print(f"Sample rate: {samplerate}Hz, Gain: {gain:.2f}")
        print("Press Ctrl+C to stop")
        
        # Start duplex audio stream
        stream = sd.Stream(
            device=(input_device, output_device),
            channels=channels,
            samplerate=samplerate,
            blocksize=blocksize,
            callback=audio_callback
        )
        
        with stream:
            start_time = time.time()
            last_stats_time = start_time
            
            while stream.active:
                current_time = time.time()
                
                # Print statistics every 5 seconds
                if current_time - last_stats_time >= 5.0:
                    elapsed = current_time - start_time
                    print(f"\nStats (after {elapsed:.1f}s):")
                    print(f"  Peak level: {peak_level:.3f}")
                    print(f"  Average level: {avg_level:.3f}")
                    print(f"  Samples processed: {sample_count}")
                    
                    # Reset peak for next period
                    peak_level = 0.0
                    last_stats_time = current_time
                
                time.sleep(1.0)
                
    except KeyboardInterrupt:
        print("\nIntercom monitoring stopped by user")
    except Exception as e:
        print(f"Intercom monitoring error: {e}")
        logging.error(f"Intercom monitoring error: {e}")

def audio_device_test(device_index, samplerate=44100, duration=3.0):
    """Test an audio device with a simple tone."""
    
    try:
        print(f"Testing audio device {device_index} at {samplerate}Hz for {duration}s...")
        
        # Generate test tone (440 Hz sine wave)
        t = np.linspace(0, duration, int(duration * samplerate), False)
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        
        # Play the tone
        sd.play(tone, samplerate=samplerate, device=device_index)
        sd.wait()  # Wait until playback is finished
        
        print(f"Audio device {device_index} test completed successfully")
        return True
        
    except Exception as e:
        print(f"Audio device {device_index} test failed: {e}")
        return False

def measure_device_latency(input_device, output_device, samplerate=44100, duration=2.0):
    """Measure the round-trip latency of audio devices."""
    
    def audio_callback(indata, outdata, frames, time_info, status):
        nonlocal recorded_data, playback_data, frame_count
        
        # Store input data
        start_idx = frame_count
        end_idx = frame_count + frames
        
        if end_idx <= len(recorded_data):
            recorded_data[start_idx:end_idx] = indata.flatten()
        
        # Output test signal
        if end_idx <= len(playback_data):
            outdata[:] = playback_data[start_idx:end_idx].reshape(-1, 1)
        else:
            outdata[:] = 0
        
        frame_count += frames
        
        if status:
            print(f"Latency test callback status: {status}")
    
    try:
        print(f"Measuring latency between devices {input_device} and {output_device}...")
        
        # Generate impulse response test signal
        total_samples = int(duration * samplerate)
        playback_data = np.zeros(total_samples)
        playback_data[int(0.5 * samplerate)] = 0.5  # Impulse at 0.5 seconds
        
        recorded_data = np.zeros(total_samples)
        frame_count = 0
        
        # Start duplex stream
        stream = sd.Stream(
            device=(input_device, output_device),
            channels=1,
            samplerate=samplerate,
            blocksize=1024,
            callback=audio_callback
        )
        
        with stream:
            time.sleep(duration)
        
        # Analyze recorded data to find the impulse
        impulse_threshold = 0.1
        impulse_indices = np.where(np.abs(recorded_data) > impulse_threshold)[0]
        
        if len(impulse_indices) > 0:
            # Find first significant response
            response_sample = impulse_indices[0]
            impulse_sample = int(0.5 * samplerate)
            
            latency_samples = response_sample - impulse_sample
            latency_ms = (latency_samples / samplerate) * 1000
            
            print(f"Measured latency: {latency_ms:.1f} ms ({latency_samples} samples)")
            return latency_ms
        else:
            print("No impulse response detected - check audio routing")
            return None
            
    except Exception as e:
        print(f"Latency measurement failed: {e}")
        return None

def audio_spectrum_analyzer(config, duration=10.0):
    """Real-time audio spectrum analyzer."""
    
    def audio_callback(indata, frames, time_info, status):
        nonlocal audio_buffer, buffer_index
        
        # Store audio data in circular buffer
        samples = indata.flatten()
        end_idx = (buffer_index + len(samples)) % len(audio_buffer)
        
        if end_idx > buffer_index:
            audio_buffer[buffer_index:end_idx] = samples
        else:
            # Wrap around
            first_part = len(audio_buffer) - buffer_index
            audio_buffer[buffer_index:] = samples[:first_part]
            audio_buffer[:end_idx] = samples[first_part:]
        
        buffer_index = end_idx
        
        if status:
            print(f"Spectrum analyzer callback status: {status}")
    
    try:
        # Extract configuration
        device_index = config['device_index']
        samplerate = config['samplerate']
        fft_size = config.get('fft_size', 2048)
        
        # Initialize audio buffer
        buffer_size = samplerate * 2  # 2 seconds of audio
        audio_buffer = np.zeros(buffer_size)
        buffer_index = 0
        
        print(f"Spectrum analyzer active (device {device_index}, {samplerate}Hz)")
        print(f"FFT size: {fft_size}, Duration: {duration}s")
        
        # Start audio stream
        stream = sd.InputStream(
            device=device_index,
            channels=1,
            samplerate=samplerate,
            blocksize=1024,
            callback=audio_callback
        )
        
        with stream:
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Get recent audio data
                if buffer_index >= fft_size:
                    # Get the most recent fft_size samples
                    if buffer_index >= fft_size:
                        start_idx = buffer_index - fft_size
                        fft_data = audio_buffer[start_idx:buffer_index]
                    else:
                        # Wrap around case
                        fft_data = np.concatenate([
                            audio_buffer[buffer_index - fft_size:],
                            audio_buffer[:buffer_index]
                        ])
                    
                    # Apply window and compute FFT
                    windowed = fft_data * np.hanning(fft_size)
                    fft_result = np.fft.rfft(windowed)
                    magnitude = np.abs(fft_result)
                    
                    # Convert to dB
                    magnitude_db = 20 * np.log10(magnitude + 1e-10)
                    
                    # Find peak frequency
                    peak_bin = np.argmax(magnitude_db)
                    peak_freq = peak_bin * samplerate / fft_size
                    peak_level = magnitude_db[peak_bin]
                    
                    # Print simple spectrum info
                    print(f"\rPeak: {peak_freq:.1f}Hz ({peak_level:.1f}dB)", end='', flush=True)
                
                time.sleep(0.1)
        
        print("\nSpectrum analyzer completed")
        
    except Exception as e:
        print(f"Spectrum analyzer error: {e}")
        logging.error(f"Spectrum analyzer error: {e}")

def audio_loopback_test(input_device, output_device, samplerate=44100, duration=5.0):
    """Test audio loopback between input and output devices."""
    
    def audio_callback(indata, outdata, frames, time_info, status):
        nonlocal correlation_sum, sample_count
        
        # Simple delay line for correlation
        outdata[:] = indata  # Direct loopback
        
        # Calculate correlation
        correlation = np.corrcoef(indata.flatten(), outdata.flatten())[0, 1]
        if not np.isnan(correlation):
            correlation_sum += correlation
            sample_count += 1
        
        if status:
            print(f"Loopback test callback status: {status}")
    
    try:
        print(f"Audio loopback test: {input_device} -> {output_device}")
        print(f"Duration: {duration}s at {samplerate}Hz")
        
        correlation_sum = 0.0
        sample_count = 0
        
        # Start duplex stream
        stream = sd.Stream(
            device=(input_device, output_device),
            channels=1,
            samplerate=samplerate,
            blocksize=1024,
            callback=audio_callback
        )
        
        with stream:
            start_time = time.time()
            
            while time.time() - start_time < duration:
                if sample_count > 0:
                    avg_correlation = correlation_sum / sample_count
                    print(f"\rAverage correlation: {avg_correlation:.3f}", end='', flush=True)
                
                time.sleep(0.5)
        
        if sample_count > 0:
            final_correlation = correlation_sum / sample_count
            print(f"\nFinal average correlation: {final_correlation:.3f}")
            
            if final_correlation > 0.8:
                print("Loopback test: PASSED (good correlation)")
            elif final_correlation > 0.5:
                print("Loopback test: MARGINAL (moderate correlation)")
            else:
                print("Loopback test: FAILED (poor correlation)")
            
            return final_correlation
        else:
            print("\nLoopback test: NO DATA")
            return 0.0
            
    except Exception as e:
        print(f"Loopback test error: {e}")
        return 0.0

def check_audio_driver_info():
    """Check and display audio driver information."""
    
    try:
        print("\nAudio Driver Information:")
        print("-" * 40)
        
        # Check PortAudio version
        try:
            print(f"PortAudio version: {sd.get_portaudio_version()[1]}")
        except:
            print("PortAudio version: Unknown")
        
        # Check default devices
        try:
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]
            print(f"Default input device: {default_input}")
            print(f"Default output device: {default_output}")
        except:
            print("Default devices: Not available")
        
        # Check sample rate
        try:
            default_samplerate = sd.default.samplerate
            print(f"Default sample rate: {default_samplerate}Hz")
        except:
            print("Default sample rate: Unknown")
        
        # Platform-specific driver info
        import platform
        system = platform.system()
        
        if system == "Windows":
            try:
                # Try to get ASIO driver info
                result = subprocess.run(
                    ["wmic", "sounddev", "get", "name"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    print(f"\nWindows audio devices:")
                    for line in result.stdout.strip().split('\n')[1:]:
                        if line.strip():
                            print(f"  {line.strip()}")
            except:
                print("Windows driver info: Not available")
        
        elif system == "Linux":
            try:
                # Check ALSA devices
                if os.path.exists("/proc/asound/cards"):
                    with open("/proc/asound/cards", "r") as f:
                        print(f"\nALSA sound cards:")
                        print(f.read())
            except:
                print("Linux driver info: Not available")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"Error checking audio driver info: {e}")

def benchmark_audio_performance(device_index, samplerate=44100, duration=10.0):
    """Benchmark audio device performance."""
    
    def audio_callback(indata, frames, time_info, status):
        nonlocal callback_count, underrun_count, overrun_count, total_frames
        
        callback_count += 1
        total_frames += frames
        
        if status.input_underflow:
            underrun_count += 1
        if status.input_overflow:
            overrun_count += 1
        
        # Simple processing load test
        _ = np.mean(indata**2)  # RMS calculation
    
    try:
        print(f"Benchmarking audio device {device_index} for {duration}s...")
        
        callback_count = 0
        underrun_count = 0
        overrun_count = 0
        total_frames = 0
        
        # Start audio stream
        stream = sd.InputStream(
            device=device_index,
            channels=1,
            samplerate=samplerate,
            blocksize=1024,
            callback=audio_callback
        )
        
        start_time = time.time()
        
        with stream:
            time.sleep(duration)
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # Calculate performance metrics
        expected_callbacks = int(actual_duration * samplerate / 1024)
        callback_rate = callback_count / actual_duration
        frame_rate = total_frames / actual_duration
        
        print(f"\nPerformance Results:")
        print(f"  Duration: {actual_duration:.2f}s")
        print(f"  Callbacks: {callback_count} (expected: {expected_callbacks})")
        print(f"  Callback rate: {callback_rate:.1f} Hz")
        print(f"  Frame rate: {frame_rate:.0f} frames/s")
        print(f"  Underruns: {underrun_count}")
        print(f"  Overruns: {overrun_count}")
        
        if underrun_count == 0 and overrun_count == 0:
            print("  Status: EXCELLENT (no dropouts)")
        elif underrun_count + overrun_count < 5:
            print("  Status: GOOD (minimal dropouts)")
        else:
            print("  Status: POOR (frequent dropouts)")
        
        return {
            'callback_count': callback_count,
            'underrun_count': underrun_count,
            'overrun_count': overrun_count,
            'callback_rate': callback_rate,
            'frame_rate': frame_rate
        }
        
    except Exception as e:
        print(f"Benchmark error: {e}")
        return None
