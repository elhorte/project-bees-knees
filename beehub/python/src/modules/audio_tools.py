"""
BMAR Audio Tools Module - SOUNDDEVICE VERSION
Contains VU meter, intercom monitoring, and audio diagnostic utilities.
"""

import numpy as np
import time
import sounddevice as sd
import sys
from .audio_conversion import downsample_audio
import traceback
from collections import deque
import random
import select
if sys.platform == "win32": import msvcrt


# Notes for VU meter tuning (config keys):
# - vu_dynamic_range_db (default 40.0)
# - vu_floor_percentile (default 0.2)
# - vu_floor_margin_db (default 0.0)
# - vu_hist_seconds (default 10.0)
# DC removal is applied before RMS so the noise floor tracks cleanly.

def vu_meter(config, stop_event=None):
    """Real-time VU meter.
    Prefer tapping the existing audio_processing circular buffer (no new input stream).
    Falls back to opening an InputStream if no buffer is available; uses virtual if no device.
    """
    # Try to use the live circular buffer managed by audio_processing
    try:
        from . import audio_processing  # local import to avoid cycles
        app_ref = getattr(audio_processing.callback, 'app', None)
    except (ImportError, AttributeError, NameError):
        app_ref = None

    if app_ref is not None and getattr(app_ref, 'buffer', None) is not None:
        return _vu_meter_from_buffer(app_ref, config, stop_event)

    # No shared buffer available: use previous paths
    try:
        device_index = config.get('device_index')

        # Virtual device path
        if device_index is None:
            return _vu_meter_virtual(config, stop_event)

        # Fallback: standalone sounddevice stream
        return _vu_meter_sounddevice(config, stop_event)

    except (sd.PortAudioError, ValueError, RuntimeError) as e:
        print(f"VU meter error: {e}")

        traceback.print_exc()


def _vu_meter_from_buffer(app, config, stop_event=None):
    """Render VU meter by reading from the existing circular buffer in audio_processing.
    Requires app.buffer (int16), app.buffer_index, app.buffer_size, app.sound_in_chs, app.PRIMARY_IN_SAMPLERATE.
    """
    try:
        sr = int(getattr(app, 'PRIMARY_IN_SAMPLERATE', config.get('samplerate', 44100)))
        channels = int(getattr(app, 'sound_in_chs', config.get('channels', 1)))

        # Window length for RMS calculation and UI update cadence
        update_interval = 0.05  # ~20 Hz UI updates
        window_sec = 0.10       # analyze last 100 ms
        n_win = max(1, int(sr * window_sec))

        # Dynamic scaling parameters (anchored to noise floor)
        dyn_range_db = float(config.get('vu_dynamic_range_db', 40.0))     # width of bar in dB
        floor_percentile = float(config.get('vu_floor_percentile', 0.2))  # 20th percentile
        floor_margin_db = float(config.get('vu_floor_margin_db', 0.0))    # shift above floor if desired
        hist_seconds = float(config.get('vu_hist_seconds', 10.0))         # history duration for floor

        max_hist_len = max(1, int(hist_seconds / max(1e-3, update_interval)))
        rms_db_hist = deque(maxlen=max_hist_len)

        # Main UI loop
        while True:
            if stop_event and stop_event.is_set():
                break
            if getattr(app, 'stop_program', [False])[0]:
                break

            # Read current monitor channel each iteration to reflect UI changes
            monitor_channel = int(getattr(app, 'monitor_channel', config.get('monitor_channel', 0)))
            if monitor_channel < 0 or monitor_channel >= max(1, channels):
                monitor_channel = 0

            buf = getattr(app, 'buffer', None)
            if buf is None or buf.size == 0:
                time.sleep(update_interval)
                continue

            # Defensive fetch of indices
            try:
                end = int(getattr(app, 'buffer_index', 0))
                total = int(getattr(app, 'buffer_size', buf.shape[0]))
                if total <= 0:
                    time.sleep(update_interval)
                    continue
                n = min(n_win, total)
                start = (end - n) % total

                if buf.ndim == 1:
                    # Mono stored as [N]
                    if start < end:
                        x_i16 = buf[start:end]
                    else:
                        x_i16 = np.concatenate((buf[start:], buf[:end]))
                else:
                    # Multi-channel stored as [N, C]
                    ch = min(max(1, buf.shape[1]), channels)
                    mon = min(max(0, monitor_channel), ch - 1)
                    if start < end:
                        x_i16 = buf[start:end, mon]
                    else:
                        x_i16 = np.concatenate((buf[start:, mon], buf[:end, mon]))

                if x_i16.size == 0:
                    time.sleep(update_interval)
                    continue

                # Convert int16 -> float in [-1, 1] and remove DC before RMS
                x = x_i16.astype(np.float32, copy=False) / 32768.0
                x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
                x -= float(x.mean())

                # Robust RMS and dB
                rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
                db = 20.0 * np.log10(max(rms, 1e-6)) if rms > 0.0 else -120.0

                # Update noise-floor history (log-domain)
                rms_db_hist.append(db)
                if len(rms_db_hist) >= max(3, int(0.5 / max(1e-3, update_interval))):  # wait ~0.5s before using
                    arr = np.fromiter(rms_db_hist, dtype=np.float32)
                    perc = max(0.0, min(1.0, floor_percentile)) * 100.0
                    floor_db = float(np.percentile(arr, perc))
                else:
                    floor_db = -60.0

                # Compute dynamic mapping range
                min_db = floor_db + floor_margin_db
                # Keep within sensible bounds
                min_db = min(min_db, -5.0)  # never push min above -5 dB
                max_db = min_db + max(6.0, dyn_range_db)  # at least 6 dB span

                _display_vu_meter(db, rms, min_db=min_db, max_db=max_db)
                time.sleep(update_interval)

            except (IndexError, ValueError, AttributeError, RuntimeError):
                # Non-fatal; keep UI alive
                time.sleep(update_interval)
                continue

    finally:
        # Clean up display line and exit
        print("\r" + " " * 80 + "\r", end="", flush=True)
        print("VU meter stopped")


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
                
        except (sd.PortAudioError, ValueError) as e:
            print(f"Error getting device info: {e}")
            actual_channels = channels
        
        # Global variable to track VU meter data and state
        vu_data = {'db_level': -80, 'rms_level': 0.0, 'callback_active': True}
        
        # Audio callback for VU meter
        def audio_callback(indata, _frames, _time_info, _status):
            try:
                # Check for stop event first - exit immediately if stopping
                if stop_event and stop_event.is_set():
                    vu_data['callback_active'] = False
                    raise sd.CallbackStop()
                
                # Skip processing if callback is not active
                if not vu_data['callback_active']:
                    raise sd.CallbackStop()
                
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
                
            except sd.CallbackStop:
                # Normal callback stop - re-raise without error message
                raise
            except Exception as e:
                # Only print error if callback is still active (not during shutdown)
                if vu_data['callback_active']:
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
                    # Check for stop event or callback inactive
                    if stop_event and stop_event.is_set():
                        vu_data['callback_active'] = False
                        break
                    
                    if not vu_data['callback_active']:
                        break
                    
                    # Display VU meter
                    _display_vu_meter(vu_data['db_level'], vu_data['rms_level'])
                    time.sleep(0.05)  # Update display at ~20Hz
                    
            except KeyboardInterrupt:
                vu_data['callback_active'] = False
            finally:
                # Always clean up display when exiting loop
                vu_data['callback_active'] = False
                print("\r" + " " * 80 + "\r", end="", flush=True)
        
        # Final cleanup message
        print("VU meter stopped")
        
    except (sd.PortAudioError, ValueError, RuntimeError) as e:
        # Clean up display on error
        print("\r" + " " * 80 + "\r", end="", flush=True)
        print(f"Sounddevice VU meter error: {e}")
        traceback.print_exc()


def _vu_meter_virtual(config, stop_event=None):
    """VU meter with virtual/synthetic audio."""
    
    try:
        # Access config for completeness and future use
        _ = config.get('monitor_channel', 0)

        
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
                
        except (OSError, ValueError):
            print("\nVirtual VU meter error occurred")
        finally:
            # Always clean up display when exiting loop
            print("\r" + " " * 80 + "\r", end="", flush=True)
            
        print("Virtual VU meter stopped")
        
    except (ValueError, RuntimeError) as e:
        print(f"Virtual VU meter error: {e}")
        traceback.print_exc()


def _display_vu_meter(db_level, rms_level, min_db=-60.0, max_db=0.0):
    """Display VU meter bar with configurable dB range.
    db_level: measured level in dBFS
    rms_level: measured RMS in linear units
    min_db/max_db: mapping range for full-scale bar utilization
    """
    
    try:
        # Ensure valid range
        if max_db <= min_db:
            max_db = min_db + 40.0
        
        # Clamp dB level to range
        clamped_db = max(min_db, min(max_db, db_level))
        
        # Create meter bar (50 characters wide)
        meter_width = 50
        
        # Map dB level to meter position (min_db..max_db -> 0..meter_width)
        span = (max_db - min_db) if (max_db - min_db) > 1e-6 else 1.0
        meter_pos = int((clamped_db - min_db) / span * meter_width)
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
        
        # Format the display (show measured dB and mapping range)
        level_display = f"[{meter_bar}] {db_level:5.1f}dB (RMS: {rms_level:.4f})"
        range_display = f" [{min_db:4.0f}..{max_db:3.0f} dB]"
        
        # Print with carriage return to overwrite previous line
        print(f"\rVU: {level_display}{range_display}", end="", flush=True)
        
    except (ValueError, TypeError) as e:
        print(f"Display error: {e}")


def intercom_m(config):
    """Microphone monitoring - route input to output (intercom).
    Prefer tapping the existing circular buffer if available (no input device handle).
    """
    
    input_device = config.get('input_device')
    output_device = config.get('output_device', input_device)
    samplerate = int(config.get('samplerate', 48000))
    in_channels_req = int(config.get('channels', 1))
    blocksize = int(config.get('blocksize', 1024))
    gain = float(config.get('gain', 1.0))
    monitor_channel = int(config.get('monitor_channel', 0))
    bit_depth = int(config.get('bit_depth', 16))

    # Suppress prints if VU meter is active
    vu_meter_active = bool(config.get('vu_meter_active', False))

    # If the shared buffer exists, use it for monitoring
    try:
        from . import audio_processing  # local import to avoid cycles
        app_ref = getattr(audio_processing.callback, 'app', None)
    except (ImportError, AttributeError, NameError):
        app_ref = None
    # Allow explicit app object in config to force buffer path
    app_ref = config.get('app', app_ref)

    if app_ref is not None and getattr(app_ref, 'buffer', None) is not None:
        return _intercom_from_buffer(app_ref, config)

    # Helper: check and resolve a valid output device
    def _is_output_device(dev):
        try:
            sd.query_devices(dev, 'output')
            return True
        except Exception:
            return False

    def _resolve_output_device(out_dev_hint, in_dev_hint):
        # If hint is valid, keep it
        if out_dev_hint is not None and _is_output_device(out_dev_hint):
            return out_dev_hint
        # Try system default output
        try:
            defaults = sd.default.device
            if isinstance(defaults, (list, tuple)) and len(defaults) >= 2:
                out_def = defaults[1]
                if out_def is not None and _is_output_device(out_def):
                    if not vu_meter_active and out_dev_hint is not None:
                        try:
                            name = sd.query_devices(out_def)['name']
                            print(f"Output device '{out_dev_hint}' is not an output; using default output '{name}'.")
                        except Exception:
                            print(f"Output device '{out_dev_hint}' is not an output; using system default output.")
                    return out_def
        except Exception:
            pass
        # As a last resort, pick the first available output device
        try:
            all_devs = sd.query_devices()
            for idx, dev in enumerate(all_devs):
                try:
                    if int(dev.get('max_output_channels', 0)) > 0:
                        if not vu_meter_active and out_dev_hint is not None:
                            print(f"Output device '{out_dev_hint}' is not an output; using '{dev['name']}'.")
                        return idx
                except Exception:
                    continue
        except Exception:
            pass
        # Nothing found
        raise ValueError("No valid output device available")

    try:
        # Query device capabilities (resolve output device if needed)
        in_info = sd.query_devices(input_device, 'input')
        resolved_output_device = _resolve_output_device(output_device, input_device)
        out_info = sd.query_devices(resolved_output_device, 'output')
        in_channels = max(1, min(in_channels_req, int(in_info['max_input_channels'])))
        out_channels = max(1, int(out_info['max_output_channels']))
        # Use up to 2 output channels for monitoring
        out_channels = 2 if out_channels >= 2 else 1

        if monitor_channel < 0 or monitor_channel >= in_channels:
            monitor_channel = 0

        # dtype
        dtype = 'int16' if bit_depth == 16 else 'float32'

        if not vu_meter_active:
            try:
                out_name = sd.query_devices(resolved_output_device)['name']
            except Exception:
                out_name = str(resolved_output_device)
            print(f"Starting intercom: in_dev={input_device} out_dev={out_name} sr={samplerate} in_ch={in_channels} out_ch={out_channels}")
            print("Press 'i' again to stop from main UI.")

        def callback(indata, outdata, frames, _time, status):
            # Use frames to avoid unused-var warnings
            _ = frames
            if status:
                # Keep silent on minor glitches
                pass
            try:
                # Extract selected input channel
                if in_channels > 1:
                    x = indata[:, monitor_channel]
                else:
                    x = indata[:, 0]

                # Convert to float for gain and clip
                if indata.dtype == np.int16:
                    y = x.astype(np.float32)
                    y *= gain
                    y = np.clip(y, -32768.0, 32767.0)
                    if out_channels == 1:
                        outdata[:, 0] = y.astype(np.int16)
                    else:
                        y16 = y.astype(np.int16)
                        outdata[:, 0] = y16
                        outdata[:, 1] = y16
                else:
                    # float32 pipeline
                    y = x.astype(np.float32) * gain
                    y = np.clip(y, -1.0, 1.0)
                    if out_channels == 1:
                        outdata[:, 0] = y
                    else:
                        outdata[:, 0] = y
                        outdata[:, 1] = y
            except (ValueError, RuntimeError, IndexError, TypeError):
                # On any error, output silence to avoid noise
                outdata.fill(0)

        # Use full-duplex stream
        with sd.Stream(
            device=(input_device, resolved_output_device),
            samplerate=samplerate,
            blocksize=blocksize,
            dtype=(dtype, dtype),
            channels=(in_channels, out_channels),
            callback=callback
        ):
            try:
                # Keep process alive; allow user input to stop when attached to a console

                while True:
                    if sys.platform == "win32":
                        try:
                            if msvcrt.kbhit():
                                key = msvcrt.getch()
                                if key in [b'\r', b'\n']:
                                    break
                        except (ImportError, OSError):
                            pass
                    else:
                        try:
                            if select.select([sys.stdin], [], [], 0.1)[0]:
                                _ = sys.stdin.read(1)
                                if _ in ('\n', '\r'):
                                    break
                        except (OSError, ValueError):
                            # Likely no TTY; ignore
                            pass
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
        
        if not vu_meter_active:
            print("Intercom stopped")

    except (sd.PortAudioError, ValueError, RuntimeError, OSError) as e:
        if not vu_meter_active:
            print(f"Intercom error: {e}")
        traceback.print_exc()


def _intercom_from_buffer(app, config):
    """Local monitor by reading from the capture circular buffer and resampling to playback.
    Avoids opening any input stream. Supports dynamic channel switching via app.monitor_channel.
    """
    # Config
    output_device = config.get('output_device')
    out_sr = int(config.get('samplerate', 48000))
    blocksize = int(config.get('blocksize', 1024))
    gain = float(config.get('gain', 1.0))
    vu_meter_active = bool(config.get('vu_meter_active', False))

    # Source properties
    in_sr = int(getattr(app, 'PRIMARY_IN_SAMPLERATE', out_sr))

    # Helper: resolve a valid output device
    def _is_output_device(dev):
        try:
            sd.query_devices(dev, 'output')
            return True
        except Exception:
            return False

    def _resolve_output_device(out_dev_hint):
        if out_dev_hint is not None and _is_output_device(out_dev_hint):
            return out_dev_hint
        try:
            defaults = sd.default.device
            if isinstance(defaults, (list, tuple)) and len(defaults) >= 2:
                out_def = defaults[1]
                if out_def is not None and _is_output_device(out_def):
                    if not vu_meter_active and out_dev_hint is not None:
                        try:
                            name = sd.query_devices(out_def)['name']
                            print(f"Output device '{out_dev_hint}' is not an output; using default output '{name}'.")
                        except Exception:
                            print(f"Output device '{out_dev_hint}' is not an output; using system default output.")
                    return out_def
        except Exception:
            pass
        try:
            all_devs = sd.query_devices()
            for idx, dev in enumerate(all_devs):
                try:
                    if int(dev.get('max_output_channels', 0)) > 0:
                        if not vu_meter_active and out_dev_hint is not None:
                            print(f"Output device '{out_dev_hint}' is not an output; using '{dev['name']}'.")
                        return idx
                except Exception:
                    continue
        except Exception:
            pass
        raise ValueError("No valid output device available")

    try:
        # Resolve and query output device
        out_dev = _resolve_output_device(output_device)
        out_info = sd.query_devices(out_dev, 'output')
        out_channels = 2 if int(out_info['max_output_channels']) >= 2 else 1

        if not vu_meter_active:
            try:
                out_name = sd.query_devices(out_dev)['name']
            except Exception:
                out_name = str(out_dev)
            print(f"Starting intercom (buffer): out_dev={out_name} sr={out_sr} out_ch={out_channels} (src_sr={in_sr})")
            print("Press 'i' again to stop from main UI.")

        # Callback: fill output from the latest buffer audio
        def callback(outdata, frames, _time, status):
            if status:
                # ignore minor glitches
                pass
            try:
                buf = getattr(app, 'buffer', None)
                if buf is None or buf.size == 0:
                    outdata.fill(0)
                    return
                total = int(getattr(app, 'buffer_size', buf.shape[0]))
                end = int(getattr(app, 'buffer_index', 0))
                channels = int(getattr(app, 'sound_in_chs', 1))
                mon = int(getattr(app, 'monitor_channel', 0))
                if mon < 0 or mon >= max(1, channels):
                    mon = 0

                # Determine how many input samples are needed for `frames` output
                if out_sr <= 0 or in_sr <= 0:
                    outdata.fill(0)
                    return

                if in_sr == out_sr:
                    n_in_needed = frames
                else:
                    n_in_needed = int(np.ceil(frames * (in_sr / float(out_sr))))

                # Add a small safety margin to ensure we can trim to exact length after resampling
                n_in = min(total, max(2, n_in_needed + 32))
                start = (end - n_in) % total

                # Extract latest n_in samples for the monitor channel
                if buf.ndim == 1:
                    if start < end:
                        x = buf[start:end]
                    else:
                        x = np.concatenate((buf[start:], buf[:end]))
                else:
                    mon = min(max(0, mon), buf.shape[1] - 1)
                    if start < end:
                        x = buf[start:end, mon]
                    else:
                        x = np.concatenate((buf[start:, mon], buf[:end, mon]))

                if x.size < 2:
                    outdata.fill(0)
                    return

                # Convert to float32 in [-1, 1] if integer input
                if np.issubdtype(x.dtype, np.integer):
                    maxv = float(np.iinfo(x.dtype).max) or 32767.0
                    xf = (x.astype(np.float32) / maxv)
                else:
                    xf = x.astype(np.float32, copy=False)
                xf = np.nan_to_num(xf, nan=0.0, posinf=0.0, neginf=0.0)

                # Resample with anti-aliasing to the output sample rate
                if in_sr != out_sr:
                    y = downsample_audio(xf, in_sr, out_sr).astype(np.float32, copy=False)
                else:
                    y = xf.astype(np.float32, copy=False)

                # Ensure exactly `frames` samples by trimming or padding the tail (latest audio)
                if y.size >= frames:
                    y = y[-frames:]
                else:
                    pad = np.zeros(frames - y.size, dtype=np.float32)
                    y = np.concatenate((pad, y), axis=0)

                # Apply gain and clip to [-1, 1]
                y = np.clip(y * gain, -1.0, 1.0).astype(np.float32)

                # Write to output channels (mono mirrored to stereo if needed)
                if out_channels == 1:
                    outdata[:, 0] = y
                else:
                    outdata[:, 0] = y
                    outdata[:, 1] = y

            except (ValueError, RuntimeError, IndexError, TypeError):
                outdata.fill(0)

        # Use output-only stream
        with sd.OutputStream(
            device=out_dev,
            samplerate=out_sr,
            blocksize=blocksize,
            dtype='float32',
            channels=out_channels,
            callback=callback,
        ):
            try:
                while True:
                    if sys.platform == "win32":
                        try:
                            if msvcrt.kbhit():
                                key = msvcrt.getch()
                                if key in [b'\r', b'\n']:
                                    break
                        except (ImportError, OSError):
                            pass
                    else:
                        try:
                            if select.select([sys.stdin], [], [], 0.1)[0]:
                                _ = sys.stdin.read(1)
                                if _ in ('\n', '\r'):
                                    break
                        except (OSError, ValueError):
                            pass
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass

        if not vu_meter_active:
            print("Intercom stopped")

    except (sd.PortAudioError, ValueError, RuntimeError, OSError) as e:
        if not vu_meter_active:
            print(f"Intercom error: {e}")
        traceback.print_exc()


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
            
        except (sd.PortAudioError, ValueError) as e:
            print(f"Device {device_index} test failed: {e}")
            return False
            
    except (sd.PortAudioError, ValueError, RuntimeError) as e:
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
        except (sd.PortAudioError, ValueError):
            print("Default devices: Not available")
        
        print("-" * 40)
    except (sd.PortAudioError, ValueError, RuntimeError) as e:
        print(f"Error: {e}")


def benchmark_audio_performance(device_index, samplerate=44100, duration=10.0):
    """Benchmark using sounddevice directly."""
    callback_count = 0
    underrun_count = 0
    total_frames = 0
    
    def audio_callback(indata, frames, _time_info, status):
        nonlocal callback_count, underrun_count, total_frames
        
        callback_count += 1
        total_frames += frames
        
        if status.input_underflow or status.input.overflow:
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
                
            return {
                'callback_count': callback_count,
                'underrun_count': underrun_count,
                'total_frames': total_frames
            }
            
    except (sd.PortAudioError, ValueError, RuntimeError) as e:
        print(f"Benchmark error: {e}")
        return None


# Stub functions for compatibility - not yet fully implemented in sounddevice version

def create_progress_bar(current, total, width=40):
    """Create a text progress bar."""
    if total == 0:
        return "[" + "=" * width + "] 100%"
    
    progress = min(current / total, 1.0)
    filled = int(width * progress)
    bar = "=" * filled + "-" * (width - filled)
    percentage = int(progress * 100)
    
    return f"[{bar}] {percentage}%"
