"""
BMAR Audio Tools Module - SOUNDDEVICE VERSION
Contains VU meter, intercom monitoring, and audio diagnostic utilities.
"""

from typing import Optional
import math
import numpy as np
import soundfile as sf
from typing import Optional
from collections import deque
import sounddevice as sd
import time
import sys
import traceback
import select
try:
    import msvcrt  # Windows-only keyboard helper (used in intercom loops)
except Exception:
    msvcrt = None
import random

# Helpers to normalize to/from float for resampling only
def _to_float_norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x)
    if np.issubdtype(x.dtype, np.integer):
        if x.dtype == np.int16:
            return (x.astype(np.float32) / 32768.0)
        elif x.dtype == np.int32:
            return (x.astype(np.float32) / 2147483648.0)
        else:
            # Fallback: scale by max of dtype
            maxv = float(np.iinfo(x.dtype).max)
            return (x.astype(np.float32) / maxv) if maxv else x.astype(np.float32)
    # assume already -1..1 float
    return x.astype(np.float32, copy=False)

def _from_float_to_int16(x: np.ndarray) -> np.ndarray:
    y = np.asarray(x, dtype=np.float32)
    y = np.clip(y, -1.0, 1.0) * 32767.0
    return np.asarray(np.rint(y), dtype=np.int16)

# High-quality resampling helper (already used for FLAC); keep near top-level
def _resample_linear(data: np.ndarray, in_sr: int, out_sr: int, axis: int = 0) -> np.ndarray:
    if int(in_sr) == int(out_sr):
        return data
    n_in = data.shape[axis]
    n_out = int(round(n_in * (int(out_sr) / float(int(in_sr)))))
    if n_in <= 1 or n_out <= 1:
        return data
    x_old = np.linspace(0.0, 1.0, num=n_in, endpoint=True, dtype=np.float64)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=True, dtype=np.float64)
    x = np.moveaxis(np.asarray(data), axis, 0).astype(np.float32, copy=False)
    if x.ndim == 1:
        y = np.interp(x_new, x_old, x).astype(np.float32)
    else:
        y = np.vstack([np.interp(x_new, x_old, x[:, ch]) for ch in range(x.shape[1])]).T.astype(np.float32)
    return np.moveaxis(y, 0, axis)

def _resample_poly_or_linear(data: np.ndarray, in_sr: int, out_sr: int, axis: int = 0) -> np.ndarray:
    if int(in_sr) == int(out_sr):
        return data
    try:
        from scipy.signal import resample_poly
        g = math.gcd(int(out_sr), int(in_sr))
        up = int(out_sr // g)
        down = int(in_sr // g)
        x = np.moveaxis(np.asarray(data), axis, 0).astype(np.float32, copy=False)
        y = resample_poly(x, up=up, down=down, axis=0).astype(np.float32, copy=False)
        return np.moveaxis(y, 0, axis)
    except Exception:
        return _resample_linear(data, in_sr, out_sr, axis=axis)

# Public helpers used by intercom code
def resample_audio(data: np.ndarray, in_sr: int, out_sr: int) -> np.ndarray:
    """Resample audio frames along time axis (axis=0)."""
    return _resample_poly_or_linear(np.asarray(data), int(in_sr), int(out_sr), axis=0)

def downsample_audio(data: np.ndarray, in_sr: int, out_sr: int) -> np.ndarray:
    """Alias for resample_audio; kept for backward compatibility."""
    return resample_audio(data, in_sr, out_sr)

def upsample_audio(data: np.ndarray, in_sr: int, out_sr: int) -> np.ndarray:
    """Alias for resample_audio; kept for backward compatibility."""
    return resample_audio(data, in_sr, out_sr)

def save_flac_with_target_sr(path: str,
                             data: np.ndarray,
                             in_samplerate: int,
                             target_samplerate: Optional[int],
                             bitdepth: int = 16) -> None:
    """
    Save audio to FLAC at target_samplerate if provided; otherwise use in_samplerate.
    - data: shape (frames,) or (frames, channels), dtype float32/float64/int16/int32
    - bitdepth: 16 or 24 controls FLAC subtype
    """
    if target_samplerate and int(target_samplerate) != int(in_samplerate):
        data = _resample_poly_or_linear(np.asarray(data), int(in_samplerate), int(target_samplerate), axis=0)
        sr = int(target_samplerate)
    else:
        sr = int(in_samplerate)

    subtype = "PCM_16" if int(bitdepth) <= 16 else "PCM_24"
    # SoundFile accepts float32 for FLAC; ensure finite values
    x = np.asarray(data)
    if np.issubdtype(x.dtype, np.integer):
        x = x.astype(np.float32)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    sf.write(path, x, sr, format="FLAC", subtype=subtype)


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
        # Announce the initial monitored channel once
        try:
            _mon0 = int(getattr(app, 'monitor_channel', config.get('monitor_channel', 0)))
            _mon0 = 0 if _mon0 < 0 else min(_mon0, max(1, channels) - 1)
            print(f"VU meter: monitoring channel {(_mon0 + 1)} of {max(1, channels)}")
        except Exception:
            pass

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

        # Smoothing params
        latency_ms = int(config.get('VU_METER_LATENCY_MS', 150))
        damping = float(config.get('VU_METER_DAMPING', 0.90))
        damping = min(0.99, max(0.0, damping))
        # Approximate blocks per latency using current analysis window as block
        block_dt = max(1e-6, n_win / float(sr))
        window_len = max(1, int(round((latency_ms / 1000.0) / block_dt)))
        vu_window = deque(maxlen=window_len)
        smooth_db = -120.0

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

                # --- VU METER SMOOTHING AND DISPLAY ---
                # Use the instantaneous dB just computed (db), then smooth it
                inst_db = float(db)
                vu_window.append(inst_db)
                avg_db = float(np.mean(vu_window)) if len(vu_window) > 0 else inst_db
                alpha = 1.0 - damping
                smooth_db = (damping * smooth_db) + (alpha * avg_db)

                # Display smoothed dB within dynamic range
                _display_vu_meter(smooth_db, rms, min_db=min_db, max_db=max_db)
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
        samplerate = int(config.get('samplerate', 44100))
        channels = int(config.get('channels', 1))
        blocksize = int(config.get('blocksize', 256))  # Smaller buffer for faster updates
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
            # Announce initial channel selection
            try:
                print(f"VU meter: monitoring channel {monitor_channel + 1} of {max(1, actual_channels)}")
            except Exception:
                pass
                
        except (sd.PortAudioError, ValueError) as e:
            print(f"Error getting device info: {e}")
            actual_channels = channels
        
        # Smoothing params and state
        try:
            latency_ms = int(config.get('VU_METER_LATENCY_MS', 150))
        except Exception:
            latency_ms = 150
        try:
            damping = float(config.get('VU_METER_DAMPING', 0.90))
        except Exception:
            damping = 0.90
        damping = min(0.99, max(0.0, damping))
        block_dt = max(1e-6, blocksize / float(samplerate))
        window_len = max(1, int(round((latency_ms / 1000.0) / block_dt)))
        vu_window = deque(maxlen=window_len)
        smooth_db = -120.0

        # Shared data for callback
        vu_data = {'db_level': -80.0, 'rms_level': 0.0, 'callback_active': True}
        
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
                
                # Update shared data
                vu_data['db_level'] = float(db_level)
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
            dtype='int16',
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
                    
                    # Smooth and display
                    inst_db = float(vu_data['db_level'])
                    vu_window.append(inst_db)
                    avg_db = float(np.mean(vu_window)) if len(vu_window) > 0 else inst_db
                    alpha = 1.0 - damping
                    smooth_db = (damping * smooth_db) + (alpha * avg_db)
                    _display_vu_meter(smooth_db, vu_data['rms_level'])
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
        _mon = int(config.get('monitor_channel', 0))
        try:
            print(f"VU meter (virtual): monitoring channel {_mon + 1}")
        except Exception:
            pass

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


def _display_vu_meter(db_level, rms_level, min_db: float = -60.0, max_db: float = 0.0):
    """Display VU meter bar with configurable dB range."""
    try:
        db = float(db_level)
        rms = float(rms_level)
        lo = float(min_db)
        hi = float(max_db)
        if hi <= lo:
            hi = lo + 40.0

        clamped_db = max(lo, min(hi, db))
        meter_width = 50
        span = (hi - lo) if (hi - lo) > 1e-6 else 1.0
        meter_pos = int((clamped_db - lo) / span * meter_width)
        meter_pos = max(0, min(meter_width, meter_pos))

        green_zone = int(meter_width * 0.7)
        yellow_zone = int(meter_width * 0.9)
        meter_bar = ""
        for i in range(meter_width):
            if i < meter_pos:
                meter_bar += "█" if i < green_zone else ("▆" if i < yellow_zone else "▅")
            else:
                meter_bar += "·"

        print(f"\rVU: [{meter_bar}] {db:5.1f}dB (RMS: {rms:.4f}) [{lo:4.0f}..{hi:3.0f} dB]", end="", flush=True)
    except (ValueError, TypeError) as e:
        print(f"\rDisplay error: {e}", end="", flush=True)


def intercom_m(config, stop_event=None):
    """
    Intercom monitor loop.
    - config: dict with keys: output_device, samplerate, channels, blocksize, gain, monitor_channel, bit_depth
    - stop_event: threading.Event or multiprocessing.Event to request shutdown
    """
    # Provide a no-op event if none supplied
    class _DummyEvt:
        def is_set(self): return False
    stop_event = stop_event or _DummyEvt()

    input_device = config.get('input_device')
    output_device = config.get('output_device', input_device)
    samplerate = int(config.get('samplerate', 48000))
    in_channels_req = int(config.get('channels', 1))
    blocksize = int(config.get('blocksize', 1024))
    gain = float(config.get('gain', 1.0))
    monitor_channel = int(config.get('monitor_channel', 0))
    bit_depth = int(config.get('bit_depth', 16))

    vu_meter_active = bool(config.get('vu_meter_active', False))

    # If the shared buffer exists, use it for monitoring
    try:
        from . import audio_processing  # local import to avoid cycles
        app_ref = getattr(audio_processing.callback, 'app', None)
    except (ImportError, AttributeError, NameError):
        app_ref = None
    app_ref = config.get('app', app_ref)

    if app_ref is not None and getattr(app_ref, 'buffer', None) is not None:
        return _intercom_from_buffer(app_ref, config, stop_event)  # pass stop_event through

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
        out_channels = 2 if out_channels >= 2 else 1

        if monitor_channel < 0 or monitor_channel >= in_channels:
            monitor_channel = 0

        dtype = 'int16' if bit_depth == 16 else 'float32'

        if not vu_meter_active:
            try:
                out_name = sd.query_devices(resolved_output_device)['name']
            except Exception:
                out_name = str(resolved_output_device)
            print(f"Starting intercom: in_dev={input_device} out_dev={out_name} sr={samplerate} in_ch={in_channels} out_ch={out_channels}")
            print("Press 'i' again to stop from main UI.")

        def callback(indata, outdata, frames, _time, status):
            # Stop immediately if requested
            if stop_event and stop_event.is_set():
                raise sd.CallbackStop()
            _ = frames
            if status:
                pass
            try:
                if in_channels > 1:
                    x = indata[:, monitor_channel]
                else:
                    x = indata[:, 0]

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
                    y = x.astype(np.float32) * gain
                    y = np.clip(y, -1.0, 1.0)
                    if out_channels == 1:
                        outdata[:, 0] = y
                    else:
                        outdata[:, 0] = y
                        outdata[:, 1] = y
            except (ValueError, RuntimeError, IndexError, TypeError):
                outdata.fill(0)

        with sd.Stream(
            device=(input_device, resolved_output_device),
            samplerate=samplerate,
            blocksize=blocksize,
            dtype=(dtype, dtype),
            channels=(in_channels, out_channels),
            callback=callback
        ):
            try:
                # Exit on stop_event or Enter key (for standalone mode)
                while True:
                    if stop_event and stop_event.is_set():
                        break
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
                    time.sleep(0.05)
            except KeyboardInterrupt:
                pass

        if not vu_meter_active:
            print("Intercom stopped")

    except (sd.PortAudioError, ValueError, RuntimeError, OSError) as e:
        if not vu_meter_active:
            print(f"Intercom error: {e}")
        traceback.print_exc()


def _intercom_from_buffer(app, config, stop_event=None):
    """Local monitor by reading from the capture circular buffer and resampling to playback.
    Avoids opening any input stream. Supports dynamic channel switching via app.monitor_channel.
    """
    # Provide a no-op event if none supplied
    class _DummyEvt:
        def is_set(self): return False
    stop_event = stop_event or _DummyEvt()

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

        def callback(outdata, frames, _time, status):
            if status:
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
                    if stop_event and stop_event.is_set():
                        break
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
                    time.sleep(0.05)
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

def _rms_dbfs(samples: np.ndarray) -> float:
    """Compute RMS in dBFS (-120..0) from mono float/int samples."""
    if samples is None or samples.size == 0:
        return -120.0
    if np.issubdtype(samples.dtype, np.integer):
        info = np.iinfo(samples.dtype)
        x = samples.astype(np.float32) / max(1.0, float(info.max))
    else:
        x = samples.astype(np.float32)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    rms = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    return -120.0 if rms <= 1e-9 else float(20.0 * np.log10(min(1.0, max(1e-9, rms))))

def _db_to_percent(db: float, floor_db: float = -60.0) -> float:
    if db <= floor_db:
        return 0.0
    if db >= 0.0:
        return 1.0
    return (db - floor_db) / (0.0 - floor_db)

def _vu_meter_dummy():
    """Removed stray token fix: placeholder to avoid syntax errors."""
    return None

# Global FLAC save override: preserves integer PCM for FLAC
_ORIGINAL_SF_WRITE = None
_FLAC_TARGET_SR: Optional[int] = None

def set_global_flac_target_samplerate(sr: Optional[int]) -> None:
    """
    Set a global target sample rate for all FLAC writes. If set and different
    from the provided samplerate, audio is resampled before saving.
    FLAC writes are always integer PCM (PCM_16 by default).
    """
    global _FLAC_TARGET_SR, _ORIGINAL_SF_WRITE
    _FLAC_TARGET_SR = int(sr) if sr is not None else None

    if _ORIGINAL_SF_WRITE is None:
        _ORIGINAL_SF_WRITE = sf.write

        def _patched_sf_write(file, data, samplerate, subtype=None, format=None, endian=None, closefd=True):
            try:
                fmt = format
                # Infer format from filename if format is None
                if fmt is None and isinstance(file, (str, bytes, bytearray)):
                    if str(file).lower().endswith(".flac"):
                        fmt = "FLAC"

                if fmt == "FLAC":
                    target_sr = _FLAC_TARGET_SR
                    in_sr = int(samplerate)
                    # Default to PCM_16 unless caller specified otherwise
                    out_subtype = subtype or "PCM_16"

                    x = np.asarray(data)

                    # If resampling is required, normalize -> resample -> back to int16
                    if target_sr and int(target_sr) != in_sr:
                        xf = _to_float_norm(x)
                        yr = _resample_poly_or_linear(xf, in_sr, int(target_sr), axis=0)
                        x_out = _from_float_to_int16(yr)
                        return _ORIGINAL_SF_WRITE(file, x_out, int(target_sr),
                                                  subtype="PCM_16", format="FLAC", endian=endian, closefd=closefd)

                    # No resample: if integer, write as-is; if float, convert to int16 first
                    if np.issubdtype(x.dtype, np.integer):
                        return _ORIGINAL_SF_WRITE(file, x, in_sr,
                                                  subtype=out_subtype, format="FLAC", endian=endian, closefd=closefd)
                    else:
                        x_out = _from_float_to_int16(x)
                        return _ORIGINAL_SF_WRITE(file, x_out, in_sr,
                                                  subtype="PCM_16", format="FLAC", endian=endian, closefd=closefd)

                # Non-FLAC: default behavior untouched
                return _ORIGINAL_SF_WRITE(file, data, samplerate,
                                          subtype=subtype, format=format, endian=endian, closefd=closefd)
            except Exception:
                # On any error, fall back to original to avoid losing data
                return _ORIGINAL_SF_WRITE(file, data, samplerate,
                                          subtype=subtype, format=format, endian=endian, closefd=closefd)

        sf.write = _patched_sf_write
