"""
BMAR Audio Processing Module
Handles audio streaming, buffer management, and core audio processing operations.
"""

import logging
import sys, time, threading, os, datetime, platform
import numpy as np
import sounddevice as sd
import soundfile as sf
from .audio_conversion import ensure_pcm16, pcm_to_mp3_write, downsample_audio
from .file_utils import check_and_create_date_folders, log_saved_file
from .system_utils import interruptable_sleep

def callback(indata, _frames, _time_info, status):
    """Callback function for audio input stream (sounddevice compatible)."""
    if status:
        print("Sounddevice callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    # Get app reference from the current stream
    app = getattr(callback, 'app', None)
    if app is None:
        return
    
    # sounddevice already provides numpy array
    audio_data = indata.copy()

    # Always keep callback data as float32 in [-1, 1]
    audio_data = audio_data.astype(np.float32, copy=False)
    audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
    audio_data = np.clip(audio_data, -1.0, 1.0)

    # If your circular buffer expects a specific dtype, store float32 consistently:
    if getattr(app, "_dtype", np.float32) != np.float32:
        app._dtype = np.float32
    # write audio_data (float32) into the circular buffer here
    
    # Ensure proper shape for multi-channel
    if audio_data.ndim == 1:
        audio_data = audio_data.reshape(-1, 1)
    
    data_len = len(audio_data)

    # Managing the circular buffer using sounddevice data
    if app.buffer_index + data_len <= app.buffer_size:
        app.buffer[app.buffer_index:app.buffer_index + data_len] = audio_data
        app.buffer_wrap_event.clear()
    else:
        overflow = (app.buffer_index + data_len) - app.buffer_size
        app.buffer[app.buffer_index:] = audio_data[:-overflow]
        app.buffer[:overflow] = audio_data[-overflow:]
        app.buffer_wrap_event.set()

    app.buffer_index = (app.buffer_index + data_len) % app.buffer_size

def setup_audio_circular_buffer(app):
    """Set up the circular buffer for audio recording."""
    # Force float32 pipeline for capture; convert only at write time
    app._dtype = np.float32
    app.buffer_size = int(app.BUFFER_SECONDS * app.PRIMARY_IN_SAMPLERATE)
    app.buffer = np.zeros((app.buffer_size, app.sound_in_chs), dtype=app._dtype)
    app.buffer_index = 0
    app.buffer_wrap = False
    app.blocksize = 8196
    app.buffer_wrap_event.clear()
    print(f"\naudio buffer size: {sys.getsizeof(app.buffer)}\n")
    sys.stdout.flush()

def audio_stream(app):
    """Main audio streaming function."""
    
    # Reset terminal settings before printing
    from .system_utils import reset_terminal_settings
    reset_terminal_settings(app)

    # Print initialization info with forced output
    logging.info("Initializing audio stream...")
    logging.info(f"Device ID: [{app.sound_in_id}]")
    logging.info(f"Channels: {app.sound_in_chs}")
    logging.info(f"Sample Rate: {int(app.PRIMARY_IN_SAMPLERATE)} Hz")
    logging.info(f"Bit Depth: {app.PRIMARY_BITDEPTH} bits")
    logging.info(f"Data Type: {app._dtype}")

    try:
        # First verify the device configuration
        try:
            device_info = sd.query_devices(app.sound_in_id, 'input')
            logging.info("Selected device info:")
            logging.info(f"Name: [{app.sound_in_id}] {device_info['name']}")
            logging.info(f"Max Input Channels: {device_info['max_input_channels']}")
            logging.info(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz")

            if device_info['max_input_channels'] < app.sound_in_chs:
                raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {app.sound_in_chs} channels are required")
        except Exception as e:
            logging.error(f"Error getting device info: {e}")
            return

        # Set up callback reference to app
        callback.app = app
        
        # Determine sounddevice dtype (float32 for consistency)
        dtype = 'float32'
        app._dtype = np.float32
        
        # Build the capture callback and initialize the stream
        cb = _make_stream_callback(app)
        stream = sd.InputStream(
            device=app.sound_in_id,
            channels=app.sound_in_chs,
            samplerate=int(app.PRIMARY_IN_SAMPLERATE),
            blocksize=app.blocksize,
            dtype=dtype,
            callback=cb
        )

        logging.info("Sounddevice stream initialized successfully")
        logging.info(f"Stream sample rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
        logging.info(f"Stream bit depth: {app.PRIMARY_BITDEPTH} bits")

        # Store references for cleanup
        app.audio_stream = stream
        stream.start()

        # Start recording threads based on flags (independently)
        threads_started = 0

        if getattr(app.config, 'MODE_AUDIO_MONITOR', False):
            logging.info("Starting recording_worker_thread: Audio_monitor (MP3)")
            threading.Thread(target=recording_worker_thread, args=(
                app,
                app.config.AUDIO_MONITOR_RECORD,
                app.config.AUDIO_MONITOR_INTERVAL,
                "Audio_monitor",
                app.config.AUDIO_MONITOR_FORMAT,
                app.config.AUDIO_MONITOR_SAMPLERATE,
                getattr(app.config, 'AUDIO_MONITOR_START', None),
                getattr(app.config, 'AUDIO_MONITOR_END', None),
                app.stop_auto_recording_event
            ), daemon=True).start()
            threads_started += 1

        if getattr(app.config, 'MODE_PERIOD', False):
            logging.info("Starting recording_worker_thread: Period_recording (primary)")
            threading.Thread(target=recording_worker_thread, args=(
                app,
                app.config.PERIOD_RECORD,
                app.config.PERIOD_INTERVAL,
                "Period_recording",
                app.config.PRIMARY_FILE_FORMAT,
                app.PRIMARY_IN_SAMPLERATE,
                getattr(app.config, 'PERIOD_START', None),
                getattr(app.config, 'PERIOD_END', None),
                app.stop_auto_recording_event
            ), daemon=True).start()
            threads_started += 1

        if getattr(app.config, 'MODE_EVENT', False):
            logging.info("Starting recording_worker_thread: Event_recording (primary)")
            threading.Thread(target=recording_worker_thread, args=(
                app,
                app.config.SAVE_BEFORE_EVENT,
                app.config.SAVE_AFTER_EVENT,
                "Event_recording",
                app.config.PRIMARY_FILE_FORMAT,
                app.PRIMARY_IN_SAMPLERATE,
                getattr(app.config, 'EVENT_START', None),
                getattr(app.config, 'EVENT_END', None),
                app.stop_auto_recording_event
            ), daemon=True).start()
            threads_started += 1

        if threads_started == 0:
            logging.warning("No recording modes enabled (MODE_AUDIO_MONITOR / MODE_PERIOD / MODE_EVENT).")

        # Keep running until stop is requested (regardless of which modes are active)
        while not app.stop_program[0]:
            time.sleep(0.1)

        # Cleanup sounddevice stream
        try:
            stream.stop()
            stream.close()
            logging.info("Sounddevice stream cleaned up successfully")
        except Exception as cleanup_error:
            logging.error(f"Error during sounddevice cleanup: {cleanup_error}")

        logging.info("Audio stream stopped normally")
        return True

    except Exception as e:
        logging.error(f"Error in sounddevice stream: {e}")
        logging.info("Please check your audio device configuration and ensure it supports the required settings")
        
        # Cleanup on error
        try:
            if 'stream' in locals() and stream:
                stream.stop()
                stream.close()
        except Exception as cleanup_error:
            logging.error(f"Error during cleanup after exception: {cleanup_error}")
        
        sys.stdout.flush()
        return False

    return True  # Normal exit path

def recording_worker_thread(app, record_period, interval, thread_id, file_format, _target_sample_rate, start_tod, end_tod, stop_event=None):
    """Worker thread for recording audio to files."""
    
    # Use the provided stop event, or fall back to the default one for backward compatibility
    if stop_event is None:
        stop_event = app.stop_recording_event
    
    if start_tod is None:
        print(f"{thread_id} is recording continuously\r")

    while not stop_event.is_set():
        try:
            current_time = datetime.datetime.now().time()
            
            if start_tod is None or (start_tod <= current_time <= end_tod):        
                print(f"{thread_id} started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec\n\r")

                app.period_start_index = app.buffer_index 
                # Wait record_period seconds to accumulate audio
                interruptable_sleep(record_period, stop_event)
                if stop_event.is_set():
                    break

                # Ensure the buffer has enough data (first iteration safety)
                need_frames = int(record_period * app.PRIMARY_IN_SAMPLERATE)
                while _buffer_available_frames(app) < min(need_frames, app.buffer_size) and not app.stop_program[0]:
                    time.sleep(0.05)

                # Snapshot the most recent record_period seconds
                segment = _snapshot_from_buffer(app, record_period, app.PRIMARY_IN_SAMPLERATE)
                _log_array_stats(f"{thread_id}/segment before save", segment)

                # Optional resample (only if target is lower than capture)
                save_sr = _target_sample_rate or app.PRIMARY_IN_SAMPLERATE
                if save_sr < app.PRIMARY_IN_SAMPLERATE:
                    segment = downsample_audio(segment, app.PRIMARY_IN_SAMPLERATE, save_sr)

                # Build output folder and filename
                ts = datetime.datetime.now()
                out_dir = _resolve_audio_output_dir(app, thread_id)

                ext = (file_format or "flac").lower()
                if ext not in ("mp3", "wav", "flac"):
                    ext = "flac"
                filename = f"{thread_id}_{ts:%Y%m%d_%H%M%S}_dev{app.sound_in_id}_{app.sound_in_chs}ch_sr{save_sr}.{ext}"
                full_path = os.path.join(out_dir, filename)

                # Write and verify
                try:
                    if ext == "mp3":
                        write_mp3_with_logging(segment, full_path, app.config)
                    else:
                        write_pcm_with_logging(segment, full_path, save_sr, subtype="PCM_16")
                    log_saved_file(full_path, f"{thread_id}")
                except Exception as e:
                    logging.error(f"Error saving {thread_id} file {filename}: {e}")

                # Wait for the next recording interval
                if not stop_event.is_set():
                    interruptable_sleep(interval, stop_event)
            else:
                # Not in recording time window, wait briefly and check again
                interruptable_sleep(10, stop_event)
                
        except Exception as e:
            logging.error(f"Error in {thread_id}: {e}")
            if not stop_event.is_set():
                interruptable_sleep(30, stop_event)  # Wait before retrying

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
    
    # Calculate percentage (0-100)
    percent = int(current * 100 / total)
    
    # Calculate filled length, ensuring it can reach full bar_length
    if current >= total:
        filled_length = bar_length  # Force full bar when complete
    else:
        filled_length = int(bar_length * current / total)
    
    bar = '#' * filled_length + ' ' * (bar_length - filled_length)
    
    return f"[{bar}] {percent}%"

def _record_audio_sounddevice(duration, sound_in_id, sound_in_chs, stop_queue, task_name="audio recording"):
    """
    Helper function to record a chunk of audio using sounddevice and return it as a numpy array.
    This function encapsulates the sounddevice stream setup and recording.
    """
    try:
        device_info = sd.query_devices(sound_in_id, 'input')
        max_channels = int(device_info['max_input_channels'])
        
        actual_channels = min(sound_in_chs, max_channels)
        actual_channels = max(1, actual_channels)

        logging.info(f"Starting {task_name} for {duration:.1f}s on {actual_channels} channel(s).")

        # Use configured sample rate
        sample_rate = 48000  # Default, should be passed as parameter
        
        # Record audio using sounddevice
        recording_array = sd.rec(
            frames=int(sample_rate * duration),
            samplerate=sample_rate,
            channels=actual_channels,
            device=sound_in_id,
            dtype='float32'
        )
        
        # Wait for recording to complete, checking stop queue periodically
        start_time = time.time()
        timeout = duration + 10
        
        while not recording_array.flags.writeable and (time.time() - start_time) < timeout:
            if not stop_queue.empty():
                sd.stop()
                break
            progress = min(100, int((time.time() - start_time) / duration * 100))
            progress_bar = create_progress_bar(progress, 100)
            print(f"Recording progress: {progress_bar}", end='\r')
            time.sleep(0.1)
        
        # Wait for recording completion
        sd.wait()
        
        print()  # Newline after progress bar
        logging.info(f"Finished {task_name}.")
        return recording_array, actual_channels

    except Exception:
        logging.error(f"Failed to record audio with sounddevice for {task_name}", exc_info=True)
        return None, 0

def _make_stream_callback(app):
    """
    Capture callback: writes float32 into circular buffer and logs periodic stats.
    """
    app._last_cb_log = 0.0

    def _cb(indata, frames, _time_info, status):
        if status:
            logging.warning("audio callback status: %s", status)

        x = np.asarray(indata, dtype=np.float32)
        if x.ndim == 1:
            x = x[:, None]

        ch = min(x.shape[1], app.sound_in_chs)
        n = x.shape[0]
        idx = app.buffer_index
        end = idx + n
        if end <= app.buffer_size:
            app.buffer[idx:end, :ch] = x[:, :ch]
        else:
            first = app.buffer_size - idx
            app.buffer[idx:, :ch] = x[:first, :ch]
            app.buffer[:n-first, :ch] = x[first:, :ch]
            app.buffer_wrap = True
        app.buffer_index = (idx + n) % app.buffer_size

        # Optional periodic stats (now computed correctly)
        now = time.time()
        if now - app._last_cb_log > 2.0:
            if getattr(app.config, "LOG_AUDIO_CALLBACK", False):
                wb = x[:, :ch]
                absmax = float(np.abs(wb).max()) if wb.size else 0.0
                rms = float(np.sqrt(np.mean(np.square(wb.astype(np.float64))))) if wb.size else 0.0
                logging.info(
                    "callback: frames=%d ch=%d absmax=%.6f rms=%.6f idx=%d wrap=%s",
                    n, ch, absmax, rms, app.buffer_index, app.buffer_wrap
                )
            app._last_cb_log = now
    return _cb

def _log_array_stats(tag: str, arr) -> None:
    try:
        a = np.asarray(arr)
        if a.size == 0:
            logging.info("%s: empty array", tag)
            return
        rms = float(np.sqrt(np.mean(np.square(a.astype(np.float64)))))
        logging.info(
            "%s: dtype=%s shape=%s min=%.6f max=%.6f mean=%.6f rms=%.6f absmax=%.6f",
            tag, a.dtype, a.shape,
            float(a.min()), float(a.max()),
            float(a.mean()), rms, float(np.max(np.abs(a))),
        )
    except Exception as e:
        logging.warning("array-stats failed for %s: %s", tag, e)

def _buffer_available_frames(app) -> int:
    """How many valid frames are currently in the circular buffer."""
    return app.buffer_size if getattr(app, "buffer_wrap", False) else int(getattr(app, "buffer_index", 0))

def _snapshot_from_buffer(app, seconds: float, sr: int) -> np.ndarray:
    """Return most recent 'seconds' from the circular buffer (float32, shape [N, C])."""
    n = max(0, min(int(seconds * sr), app.buffer_size))
    if n == 0:
        return np.empty((0, app.sound_in_chs), dtype=np.float32)
    end = app.buffer_index
    start = (end - n) % app.buffer_size
    if start < end:
        out = app.buffer[start:end]
    else:
        out = np.vstack((app.buffer[start:], app.buffer[:end]))
    return out.astype(np.float32, copy=True)

def write_pcm_with_logging(frames, path, sr, subtype="PCM_16"):
    _log_array_stats("PCM/write input", frames)
    if frames is None or np.asarray(frames).size == 0:
        logging.error("PCM/write aborted: empty frames for %s", path)
        return
    pcm16 = np.ascontiguousarray(ensure_pcm16(frames))
    _log_array_stats("PCM/write pcm16", pcm16)
    sf.write(path, pcm16, int(sr), subtype=subtype)
    log_saved_file(path, "Audio")
    try:
        y, r = sf.read(path, dtype='int16', always_2d=False)
        _log_array_stats("PCM/roundtrip read", y)
        logging.info("PCM/roundtrip sr=%s ch=%s", r, (y.shape[1] if y.ndim == 2 else 1))
    except Exception as e:
        logging.warning("PCM/roundtrip failed for %s: %s", path, e)

def write_mp3_with_logging(frames, path, config):
    _log_array_stats("MP3/write input", frames)
    if frames is None or np.asarray(frames).size == 0:
        logging.error("MP3/write aborted: empty frames for %s", path)
        return
    pcm16 = np.ascontiguousarray(ensure_pcm16(frames))
    _log_array_stats("MP3/write pcm16", pcm16)
    pcm_to_mp3_write(pcm16, path, config)
    log_saved_file(path, "Audio")

def _first_defined_path(*candidates):
    for p in candidates:
        if isinstance(p, str) and p.strip():
            return os.path.abspath(os.path.expanduser(p))
    return None

def _resolve_audio_output_dir(app, thread_id: str) -> str:
    """
    Resolve output dir strictly from BMAR_config via check_and_create_date_folders.
    """
    cfg = app.config
    res = check_and_create_date_folders(cfg)  # will raise/log if config invalid
    out_dir = res.get("audio_dir") or res.get("audio") or res.get("AUDIO_DIR")
    out_dir = os.path.normpath(os.path.expanduser(out_dir))
    os.makedirs(out_dir, exist_ok=True)
    return out_dir
