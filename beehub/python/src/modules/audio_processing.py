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

from .system_utils import interruptable_sleep
from .file_utils import check_and_create_date_folders
from .audio_conversion import downsample_audio, pcm_to_mp3_write

def callback(app, indata, frames, time, status):
    """Callback function for audio input stream."""
    if status:
        print("Callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    data_len = len(indata)

    # Managing the circular buffer
    if app.buffer_index + data_len <= app.buffer_size:
        app.buffer[app.buffer_index:app.buffer_index + data_len] = indata
        app.buffer_wrap_event.clear()
    else:
        overflow = (app.buffer_index + data_len) - app.buffer_size
        app.buffer[app.buffer_index:] = indata[:-overflow]
        app.buffer[:overflow] = indata[-overflow:]
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
        device_info = sd.query_devices(app.sound_in_id)
        logging.info("Selected device info:")
        logging.info(f"Name: [{app.sound_in_id}] {device_info['name']}")
        logging.info(f"Max Input Channels: {device_info['max_input_channels']}")
        logging.info(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz")

        if device_info['max_input_channels'] < app.sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {app.sound_in_chs} channels are required")

        # Set the device's sample rate to match our configuration
        sd.default.samplerate = app.PRIMARY_IN_SAMPLERATE
        
        # Create a partial function to pass app to the callback
        app_callback = lambda indata, frames, time, status: callback(app, indata, frames, time, status)
        
        # Initialize the stream with the configured sample rate and bit depth
        stream = sd.InputStream(
            device=app.sound_in_id,
            channels=app.sound_in_chs,
            samplerate=app.PRIMARY_IN_SAMPLERATE,
            dtype=app._dtype,
            blocksize=app.blocksize,
            callback=app_callback
        )

        logging.info("Audio stream initialized successfully")
        logging.info(f"Stream sample rate: {stream.samplerate} Hz")
        logging.info(f"Stream bit depth: {app.PRIMARY_BITDEPTH} bits")

        with stream:
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
                    getattr(app.config, 'AUDIO_MONITOR_END', None)
                )).start()

            if hasattr(app.config, 'MODE_PERIOD') and app.config.MODE_PERIOD and not app.testmode:
                logging.info("Starting recording_worker_thread for caching period audio at primary sample rate and all channels...")
                threading.Thread(target=recording_worker_thread, args=(
                    app,
                    app.config.PERIOD_RECORD,
                    app.config.PERIOD_INTERVAL,
                    "Period_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'PERIOD_START', None),
                    getattr(app.config, 'PERIOD_END', None)
                )).start()

            if hasattr(app.config, 'MODE_EVENT') and app.config.MODE_EVENT and not app.testmode:
                logging.info("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
                threading.Thread(target=recording_worker_thread, args=(
                    app,
                    app.config.SAVE_BEFORE_EVENT,
                    app.config.SAVE_AFTER_EVENT,
                    "Event_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'EVENT_START', None),
                    getattr(app.config, 'EVENT_END', None)
                )).start()

            # Wait for keyboard input to stop
            while not app.stop_program[0]:
                time.sleep(0.1)
            
            # Normal exit - return True
            logging.info("Audio stream stopped normally")
            return True

    except Exception as e:
        logging.error(f"Error in audio stream: {e}")
        logging.info("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        return False

    return True  # Normal exit path

def recording_worker_thread(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
    """Worker thread for recording audio to files."""
    
    if start_tod is None:
        print(f"{thread_id} is recording continuously\r")

    samplerate = app.PRIMARY_IN_SAMPLERATE

    while not app.stop_recording_event.is_set():
        try:
            current_time = datetime.datetime.now().time()
            
            if start_tod is None or (start_tod <= current_time <= end_tod):        
                print(f"{thread_id} started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec\n\r")

                app.period_start_index = app.buffer_index 
                # Wait PERIOD seconds to accumulate audio
                interruptable_sleep(record_period, app.stop_recording_event)

                # Check if we're shutting down before saving
                if app.stop_recording_event.is_set():
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
                if app.stop_recording_event.is_set():
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
                        import soundfile as sf
                        sf.write(full_path, audio_segment, save_sample_rate, subtype='PCM_16')
                    
                    logging.info(f"Saved {thread_id} file: {filename}")
                    
                except Exception as e:
                    logging.error(f"Error saving {thread_id} file {filename}: {e}")

                # Wait for the next recording interval
                if not app.stop_recording_event.is_set():
                    interruptable_sleep(interval, app.stop_recording_event)
            else:
                # Not in recording time window, wait briefly and check again
                interruptable_sleep(10, app.stop_recording_event)
                
        except Exception as e:
            logging.error(f"Error in {thread_id}: {e}")
            if not app.stop_recording_event.is_set():
                interruptable_sleep(30, app.stop_recording_event)  # Wait before retrying

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

def _record_audio_pyaudio(duration, sound_in_id, sound_in_chs, stop_queue, task_name="audio recording"):
    """
    Helper function to record a chunk of audio using PyAudio and return it as a numpy array.
    This function encapsulates the PyAudio stream setup, callback, and teardown.
    """
    import pyaudio
    from . import bmar_config
    
    p = pyaudio.PyAudio()
    recording = None
    try:
        device_info = p.get_device_info_by_index(sound_in_id)
        max_channels = int(device_info['maxInputChannels'])
        
        actual_channels = min(sound_in_chs, max_channels)
        actual_channels = max(1, actual_channels)

        logging.info(f"Starting {task_name} for {duration:.1f}s on {actual_channels} channel(s).")

        # Note: This would need access to config.PRIMARY_IN_SAMPLERATE
        # For now, we'll use a default or pass it as parameter
        sample_rate = 48000  # Default, should be passed as parameter
        num_frames = int(sample_rate * duration)
        chunk_size = 4096
        
        recording_array = np.zeros((num_frames, actual_channels), dtype=np.float32)
        frames_recorded = 0
        recording_complete = False

        def callback(indata, frame_count, time_info, status):
            nonlocal frames_recorded, recording_complete
            try:
                if status:
                    logging.warning(f"PyAudio callback status: {status}")
                    
                if frames_recorded < num_frames and not recording_complete:
                    frames_to_copy = min(frame_count, num_frames - frames_recorded)
                    recording_array[frames_recorded:frames_recorded + frames_to_copy] = indata[:frames_to_copy]
                    frames_recorded += frames_to_copy
                    
                    if frames_recorded >= num_frames:
                        recording_complete = True
                        
                return (None, pyaudio.paContinue)
            except Exception as e:
                logging.error(f"Error in PyAudio callback: {e}", exc_info=True)
                recording_complete = True
                return (None, pyaudio.paAbort)

        stream = p.open(format=pyaudio.paFloat32,
                        channels=actual_channels,
                        rate=int(sample_rate),
                        input=True,
                        input_device_index=sound_in_id,
                        frames_per_buffer=chunk_size,
                        stream_callback=callback)
        
        stream.start_stream()
        
        start_time = time.time()
        timeout = duration + 10
        
        while not recording_complete and stop_queue.empty() and (time.time() - start_time) < timeout:
            progress_bar = create_progress_bar(frames_recorded, num_frames)
            print(f"Recording progress: {progress_bar}", end='\r')
            time.sleep(0.1)
        
        # Ensure we show 100% completion when done
        if recording_complete or frames_recorded >= num_frames:
            progress_bar = create_progress_bar(num_frames, num_frames)  # Force 100%
            print(f"Recording progress: {progress_bar}", end='\r')
        
        stream.stop_stream()
        stream.close()
        
        print()  # Newline after progress bar
        if frames_recorded < num_frames * 0.9:
            logging.warning(f"Recording incomplete: only got {frames_recorded}/{num_frames} frames.")
            return None, 0
        
        logging.info(f"Finished {task_name}.")
        return recording_array, actual_channels

    except Exception as e:
        logging.error(f"Failed to record audio with PyAudio for {task_name}", exc_info=True)
        return None, 0
    finally:
        if p:
            try:
                p.terminate()
                time.sleep(0.1)  # Allow time for resources to be released
            except Exception as e:
                logging.error(f"Error terminating PyAudio instance for {task_name}", exc_info=True)
