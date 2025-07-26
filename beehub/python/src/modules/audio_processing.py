"""
BMAR Audio Processing Module
Handles audio streaming, buffer management, and core audio processing operations.
"""

import numpy as np
import sounddevice as sd
import threading
import datetime
import time
import logging
import sys
import os
import soundfile as sf

from .system_utils import interruptable_sleep
from .file_utils import check_and_create_date_folders
from .audio_conversion import downsample_audio, pcm_to_mp3_write

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
    
    # Handle invalid values (NaN, infinity) in audio data
    if not np.all(np.isfinite(audio_data)):
        # Replace NaN and infinity values with zeros
        audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Convert to the buffer's data type to avoid casting warnings
    if hasattr(app, '_dtype') and app._dtype != np.float32:
        # Clamp audio data to valid range [-1.0, 1.0] to prevent overflow
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # Scale float32 data to the target data type range
        if app._dtype == np.int16:
            # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767]
            audio_data = (audio_data * 32767).astype(np.int16)
        elif app._dtype == np.int32:
            # Convert float32 [-1.0, 1.0] to int32 [-2147483648, 2147483647]
            audio_data = (audio_data * 2147483647).astype(np.int32)
        # If _dtype is np.float32, no conversion needed
    # If no _dtype attribute, keep as float32 (fallback)
    
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
    # Calculate buffer size and initialize buffer
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
        
        # Determine sounddevice dtype
        if app._dtype == np.float32:
            dtype = 'float32'
        elif app._dtype == np.int16:
            dtype = 'int16'
        elif app._dtype == np.int32:
            dtype = 'int32'
        else:
            dtype = 'float32'  # Default fallback
        
        # Initialize the stream with the configured sample rate and bit depth
        stream = sd.InputStream(
            device=app.sound_in_id,
            channels=app.sound_in_chs,
            samplerate=int(app.PRIMARY_IN_SAMPLERATE),
            blocksize=app.blocksize,
            dtype=dtype,
            callback=callback
        )

        logging.info("Sounddevice stream initialized successfully")
        logging.info(f"Stream sample rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
        logging.info(f"Stream bit depth: {app.PRIMARY_BITDEPTH} bits")

        # Store references for cleanup
        app.audio_stream = stream
        
        stream.start()

        # Start the recording worker threads
        if hasattr(app.config, 'MODE_AUDIO_MONITOR') and app.config.MODE_AUDIO_MONITOR:
            logging.info("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...")
            threading.Thread(target=recording_worker_thread, args=(
                app,
                app.config.AUDIO_MONITOR_RECORD,
                app.config.AUDIO_MONITOR_INTERVAL,
                "Audio_monitor",
                    app.config.AUDIO_MONITOR_FORMAT,
                    app.config.AUDIO_MONITOR_SAMPLERATE,
                    getattr(app.config, 'AUDIO_MONITOR_START', None),
                    getattr(app.config, 'AUDIO_MONITOR_END', None),
                    app.stop_auto_recording_event  # Use separate event for automatic recording
                )).start()

            if hasattr(app.config, 'MODE_PERIOD') and app.config.MODE_PERIOD:
                logging.info("Starting recording_worker_thread for caching period audio at primary sample rate and all channels...")
                threading.Thread(target=recording_worker_thread, args=(
                    app,
                    app.config.PERIOD_RECORD,
                    app.config.PERIOD_INTERVAL,
                    "Period_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'PERIOD_START', None),
                    getattr(app.config, 'PERIOD_END', None),
                    app.stop_auto_recording_event  # Use separate event for automatic recording
                )).start()

            if hasattr(app.config, 'MODE_EVENT') and app.config.MODE_EVENT:
                logging.info("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
                threading.Thread(target=recording_worker_thread, args=(
                    app,
                    app.config.SAVE_BEFORE_EVENT,
                    app.config.SAVE_AFTER_EVENT,
                    "Event_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'EVENT_START', None),
                    getattr(app.config, 'EVENT_END', None),
                    app.stop_auto_recording_event  # Use separate event for automatic recording
                )).start()

            # Wait for keyboard input to stop
            while not app.stop_program[0]:
                time.sleep(0.1)
            
            # Cleanup sounddevice stream
            try:
                stream.stop()
                stream.close()
                logging.info("Sounddevice stream cleaned up successfully")
            except Exception as cleanup_error:
                logging.error(f"Error during sounddevice cleanup: {cleanup_error}")
            
            # Normal exit - return True
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
                # Wait PERIOD seconds to accumulate audio
                interruptable_sleep(record_period, stop_event)

                # Check if we're shutting down before saving
                if stop_event.is_set():
                    break

                period_end_index = app.buffer_index 
                save_start_index = app.period_start_index % app.buffer_size
                save_end_index = period_end_index % app.buffer_size

                # Saving from a circular buffer so segments aren't necessarily contiguous
                if save_end_index > save_start_index:
                    audio_segment = app.buffer[save_start_index:save_end_index].copy()
                else:
                    # Buffer wrapped around
                    part1 = app.buffer[save_start_index:].copy()
                    part2 = app.buffer[:save_end_index].copy()
                    audio_segment = np.concatenate([part1, part2], axis=0)

                # Determine the sample rate to use for saving
                save_sample_rate = app.PRIMARY_SAVE_SAMPLERATE if app.PRIMARY_SAVE_SAMPLERATE is not None else app.PRIMARY_IN_SAMPLERATE
                
                # Resample if needed
                if save_sample_rate < app.PRIMARY_IN_SAMPLERATE:
                    audio_segment = downsample_audio(audio_segment, app.PRIMARY_IN_SAMPLERATE, save_sample_rate)

                # Check if we're shutting down before saving
                if stop_event.is_set():
                    break

                # Check and create new date folders if needed
                if not check_and_create_date_folders(app):
                    logging.error(f"Failed to create date folders for {thread_id}")
                    continue

                # Calculate the saving sample rate for the filename
                filename_sample_rate = int(save_sample_rate)
                
                # Generate timestamp and filename
                timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"{timestamp}_{filename_sample_rate}_{app.PRIMARY_BITDEPTH}_{thread_id}_{app.config.LOCATION_ID}_{app.config.HIVE_ID}.{file_format.lower()}"
                
                # Choose directory based on thread type
                if "Audio_monitor" in thread_id:
                    full_path = os.path.join(app.MONITOR_DIRECTORY, filename)
                else:
                    full_path = os.path.join(app.PRIMARY_DIRECTORY, filename)

                try:
                    # Save the file
                    if file_format.lower() == 'mp3':
                        pcm_to_mp3_write(audio_segment, full_path, app.config)
                    else:
                        # Save as WAV or other format using soundfile
                        sf.write(full_path, audio_segment, save_sample_rate, subtype='PCM_16')
                    
                    logging.info(f"Saved {thread_id} file: {filename}")
                    
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
