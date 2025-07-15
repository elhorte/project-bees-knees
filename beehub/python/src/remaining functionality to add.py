# remaining functionality to add
#!/usr/bin/env python3

# ###########################################################
# processes and functions from BMAR_lmw.py
# ###########################################################

# periodic recording of spectrograms

#
# continuous fft plot of audio in a separate background process
#

def plot_and_save_fft(channel):
    interval = FFT_INTERVAL * 60    # convert to seconds, time betwwen ffts
    N = int(config.PRIMARY_IN_SAMPLERATE * config.FFT_DURATION)  # Number of samples, ensure it's an integer
    # Convert gain from dB to linear scale
    gain = 10 ** (config.FFT_GAIN / 20)

    while not stop_fft_periodic_plot_event.is_set():
        # Record audio
        print(f"Recording audio for auto fft in {FFT_INTERVAL} minutes...")
        # Wait for the desired time interval before recording and plotting again
        interruptable_sleep(interval, stop_fft_periodic_plot_event)
            
        myrecording = sd.rec(N, samplerate=config.PRIMARY_IN_SAMPLERATE, channels=channel + 1)
        sd.wait()  # Wait until recording is finished
        myrecording *= gain
        print("Recording auto fft finished.")

        # Perform FFT
        yf = rfft(myrecording.flatten())
        xf = rfftfreq(N, 1 / config.PRIMARY_IN_SAMPLERATE)

        # Define bucket width
        bucket_width = FFT_BW  # Hz
        bucket_size = int(bucket_width * N / config.PRIMARY_IN_SAMPLERATE)  # Number of indices per bucket

        # Average buckets
        buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
        bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

        # Plot results
        plt.plot(bucket_freqs, np.abs(buckets))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT Plot monitoring ch: ' + str(channel + 1) + ' of ' + str(sound_in_chs) + ' channels')

        plt.grid(True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Save plot to disk with a unique filename based on current time
        output_filename = f"{timestamp}_fft_{config.PRIMARY_IN_SAMPLERATE/1000:.0F}_{config.PRIMARY_BITDEPTH}_{channel}_{config.LOCATION_ID}_{config.HIVE_ID}.png"
        full_path_name = os.path.join(PLOT_DIRECTORY, output_filename)
        plt.savefig(full_path_name)

    print("Exiting fft periodic")

#
# Function to switch the channel being monitored
#

def change_monitor_channel():
    global monitor_channel, change_ch_event, vu_proc, intercom_proc, sound_in_chs

    # Clear input buffer before starting to ensure no leftover keystrokes
    clear_input_buffer()
    
    # Print available channels
    print(f"\nAvailable channels: 1-{sound_in_chs}")
    print("Press channel number (1-9) to monitor, or 0/q to exit:")
    
    while True:
        try:
            key = get_key()
            if key is None:
                time.sleep(0.01)  # Small delay to prevent high CPU usage
                continue
                
            # First, check for exit conditions and handle them immediately
            if key == '0' or key.lower() == 'q':
                print("\nExiting channel change")
                # Clear the input buffer before returning to prevent stray keystrokes
                clear_input_buffer()
                return
                
            # Handle digit keys for channel selection
            if key.isdigit() and int(key) > 0:
                # Convert the key to 0-indexed channel number
                key_int = int(key) - 1
                
                # Check if the channel is within the valid range (less than sound_in_chs)
                if key_int < sound_in_chs:
                    monitor_channel = key_int
                    print(f"\nNow monitoring channel: {monitor_channel+1} (of {sound_in_chs})")
                    
                    # Handle intercom channel change if active
                    if intercom_proc is not None:
                        change_ch_event.set()
                    
                    # Only restart VU meter if running
                    if vu_proc is not None:
                        print(f"Restarting VU meter on channel: {monitor_channel+1}")
                        toggle_vu_meter()
                        time.sleep(0.1)
                        toggle_vu_meter()
                    
                    # Exit after successful channel change
                    clear_input_buffer()
                    return
                else:
                    print(f"\nInvalid channel selection: Device has only {sound_in_chs} channel(s) (1-{sound_in_chs})")
            else:
                # Handle non-numeric, non-exit keys
                if key.isprintable() and key != '0' and key.lower() != 'q':
                    print(f"\nInvalid input: '{key}'. Use 1-{sound_in_chs} for channels or 0/q to exit.")
                    
        except Exception as e:
            print(f"\nError reading input: {e}")
            continue


def recording_worker_thread(record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
    global buffer, buffer_size, buffer_index, stop_recording_event, _subtype

    if start_tod is None:
        print(f"{thread_id} is recording continuously\r")

    samplerate = config.PRIMARY_IN_SAMPLERATE

    while not stop_recording_event.is_set():
        try:
            current_time = datetime.datetime.now().time()
            
            if start_tod is None or (start_tod <= current_time <= end_tod):        
                print(f"{thread_id} started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec\r")

                period_start_index = buffer_index 
                # wait PERIOD seconds to accumulate audio
                interruptable_sleep(record_period, stop_recording_event)

                # Check if we're shutting down before saving
                if stop_recording_event.is_set():
                    break

                period_end_index = buffer_index 
                save_start_index = period_start_index % buffer_size
                save_end_index = period_end_index % buffer_size

                # saving from a circular buffer so segments aren't necessarily contiguous
                if save_end_index > save_start_index:   # indexing is contiguous
                    audio_data = buffer[save_start_index:save_end_index]
                else:                                   # ain't contiguous so concatenate to make it contiguous
                    audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

                # Determine the sample rate to use for saving
                save_sample_rate = config.PRIMARY_SAVE_SAMPLERATE if config.PRIMARY_SAVE_SAMPLERATE is not None else config.PRIMARY_IN_SAMPLERATE
                
                # Resample if needed
                if save_sample_rate < config.PRIMARY_IN_SAMPLERATE:
                    # resample to lower sample rate
                    audio_data = downsample_audio(audio_data, config.PRIMARY_IN_SAMPLERATE, save_sample_rate)
                    print(f"Resampling from {config.PRIMARY_IN_SAMPLERATE}Hz to {save_sample_rate}Hz for saving")

                # Check if we're shutting down before saving
                if stop_recording_event.is_set():
                    break

                # Check and create new date folders if needed
                check_and_create_date_folders()

                # Get current date for folder name
                current_date = datetime.datetime.now()
                date_folder = current_date.strftime('%y%m%d')  # Format: YYMMDD

                # Handle different file formats
                if file_format.upper() == 'MP3':
                    if target_sample_rate == 44100 or target_sample_rate == 48000:
                        full_path_name = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                                    folders[0], "mp3", date_folder, 
                                                    f"{current_date.strftime('%H%M%S')}_{thread_id}_{record_period}_{interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}")
                        print(f"\nAttempting to save MP3 file: {full_path_name}")
                        try:
                            pcm_to_mp3_write(audio_data, full_path_name)
                            print(f"Successfully saved: {full_path_name}")
                        except Exception as e:
                            print(f"Error saving MP3 file: {e}")
                    else:
                        print("MP3 only supports 44.1k and 48k sample rates")
                        quit(-1)
                elif file_format.upper() in ['FLAC', 'WAV']:
                    full_path_name = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                                folders[0], "raw", date_folder, 
                                                f"{current_date.strftime('%H%M%S')}_{thread_id}_{record_period}_{interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}")
                    print(f"\nAttempting to save {file_format.upper()} file: {full_path_name}")
                    # Ensure sample rate is an integer
                    save_sample_rate = int(save_sample_rate)
                    try:
                        sf.write(full_path_name, audio_data, save_sample_rate, 
                                format=file_format.upper(), 
                                subtype=_subtype)
                        print(f"Successfully saved: {full_path_name}")
                    except Exception as e:
                        print(f"Error saving {file_format.upper()} file: {e}")
                else:
                    print(f"Unsupported file format: {file_format}")
                    print("Supported formats are: MP3, FLAC, WAV")
                    quit(-1)
                
                if not stop_recording_event.is_set():
                    print(f"Saved {thread_id} audio to {full_path_name}, period: {record_period}, interval {interval} seconds\r")
                # wait "interval" seconds before starting recording again
                interruptable_sleep(interval, stop_recording_event)
            
        except Exception as e:
            print(f"Error in recording_worker_thread: {e}")
            stop_recording_event.set()

def callback(indata, frames, time, status):
    """Callback function for audio input stream."""
    global buffer, buffer_index
    if status:
        print("Callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    data_len = len(indata)

    # managing the circular buffer
    if buffer_index + data_len <= buffer_size:
        buffer[buffer_index:buffer_index + data_len] = indata
        buffer_wrap_event.clear()
    else:
        overflow = (buffer_index + data_len) - buffer_size
        buffer[buffer_index:] = indata[:-overflow]
        buffer[:overflow] = indata[-overflow:]
        buffer_wrap_event.set()

    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global stop_program, sound_in_id, sound_in_chs, _dtype, testmode

    # Reset terminal settings before printing
    reset_terminal_settings()

    # Print initialization info with forced output
    print("Initializing audio stream...", flush=True)
    print(f"Device ID: [{sound_in_id}]", end='\r', flush=True)
    print(f"Channels: {sound_in_chs}", end='\r', flush=True)
    print(f"Sample Rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz", end='\r', flush=True)
    print(f"Bit Depth: {config.PRIMARY_BITDEPTH} bits", end='\r', flush=True)
    print(f"Data Type: {_dtype}", end='\r', flush=True)

    try:
        # First verify the device configuration
        device_info = sd.query_devices(sound_in_id)
        print("\nSelected device info:", flush=True)
        print(f"Name: [{sound_in_id}] {device_info['name']}", end='\r', flush=True)
        print(f"Max Input Channels: {device_info['max_input_channels']}", end='\r', flush=True)
        print(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz", end='\r', flush=True)

        if device_info['max_input_channels'] < sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {sound_in_chs} channels are required")

        # Set the device's sample rate to match our configuration
        sd.default.samplerate = config.PRIMARY_IN_SAMPLERATE
        
        # Initialize the stream with the configured sample rate and bit depth
        stream = sd.InputStream(
            device=sound_in_id,
            channels=sound_in_chs,
            samplerate=config.PRIMARY_IN_SAMPLERATE,  # Use configured rate
            dtype=_dtype,  # Use configured bit depth
            blocksize=blocksize,
            callback=callback
        )

        print("\nAudio stream initialized successfully\r", flush=True)
        print(f"Stream sample rate: {stream.samplerate} Hz", end='\r', flush=True)
        print(f"Stream bit depth: {config.PRIMARY_BITDEPTH} bits", end='\r', flush=True)

        with stream:
            # start the recording worker threads
            if config.MODE_AUDIO_MONITOR:
                print("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...\r")
                #sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=( config.AUDIO_MONITOR_RECORD, \
                                                                        config.AUDIO_MONITOR_INTERVAL, \
                                                                        "Audio_monitor", \
                                                                        config.AUDIO_MONITOR_FORMAT, \
                                                                        config.AUDIO_MONITOR_SAMPLERATE, \
                                                                        config.AUDIO_MONITOR_START, \
                                                                        config.AUDIO_MONITOR_END)).start()

            if config.MODE_PERIOD and not testmode:
                print("Starting recording_worker_thread for caching period audio at primary sample rate and all channels...\r")
                #sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=( config.PERIOD_RECORD, \
                                                                        config.PERIOD_INTERVAL, \
                                                                        "Period_recording", \
                                                                        config.PRIMARY_FILE_FORMAT, \
                                                                        config.PRIMARY_IN_SAMPLERATE, \
                                                                        config.PERIOD_START, \
                                                                        config.PERIOD_END)).start()

            if config.MODE_EVENT and not testmode:
                print("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...\r")
                #sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=( config.SAVE_BEFORE_EVENT, \
                                                                        config.SAVE_AFTER_EVENT, \
                                                                        "Event_recording", \
                                                                        config.PRIMARY_FILE_FORMAT, \
                                                                        config.PRIMARY_IN_SAMPLERATE, \
                                                                        config.EVENT_START, \
                                                                        config.EVENT_END)).start()

            # Wait for keyboard input to stop
            while not stop_program[0]:
                time.sleep(0.1)

    except Exception as e:
        print(f"\nError initializing audio stream: {str(e)}")
        print("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        return False

    return True


def main():
    global fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel, sound_in_id, sound_in_chs, MICS_ACTIVE, keyboard_listener_running, make_name, model_name, device_name, api_name, hostapi_name, hostapi_index, device_id, original_terminal_settings

    # --- Setup Logging ---
    log_file_path = os.path.join(data_drive, data_path, 'BMAR.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(processName)s - %(threadName)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("--- Starting Beehive Multichannel Acoustic-Signal Recorder ---")

    # Save original terminal settings at startup
    original_terminal_settings = save_terminal_settings()

    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, emergency_cleanup)   # Ctrl+C
    signal.signal(signal.SIGTERM, emergency_cleanup)  # Termination request
    if sys.platform != 'win32':
        signal.signal(signal.SIGHUP, emergency_cleanup)   # Terminal closed
        signal.signal(signal.SIGQUIT, emergency_cleanup)  # Ctrl+\

    # --- Audio format validation ---
    allowed_primary_formats = ["FLAC", "WAV"]
    allowed_monitor_formats = ["MP3", "FLAC", "WAV"]
    if config.PRIMARY_FILE_FORMAT.upper() not in allowed_primary_formats:
        print(f"WARNING: PRIMARY_FILE_FORMAT '{config.PRIMARY_FILE_FORMAT}' is not allowed. Must be one of: {allowed_primary_formats}")
    if config.AUDIO_MONITOR_FORMAT.upper() not in allowed_monitor_formats:
        print(f"WARNING: AUDIO_MONITOR_FORMAT '{config.AUDIO_MONITOR_FORMAT}' is not allowed. Must be one of: {allowed_monitor_formats}")

    logging.info("Beehive Multichannel Acoustic-Signal Recorder")
   
    # Display platform-specific messages
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        logging.info("Running on Windows - some terminal features will be limited.")
        logging.info("Note: You can safely ignore the 'No module named termios' warning.")
   
    # Check dependencies
    if not check_dependencies():
        logging.warning("Some required packages are missing or outdated.")
        logging.warning("The script may not function correctly.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    logging.info(f"Saving data to: {PRIMARY_DIRECTORY}")

    # Try to set up the input device
    if not set_input_device(model_name, api_name):
        logging.critical("Exiting due to no suitable audio input device found.")
        sys.exit(1)

    # Validate and adjust monitor_channel after device setup
    if monitor_channel >= sound_in_chs:
        logging.warning(f"Monitor channel {monitor_channel+1} exceeds available channels ({sound_in_chs})")
        monitor_channel = 0  # Default to first channel
        logging.info(f"Setting monitor channel to {monitor_channel+1}")

    setup_audio_circular_buffer()

    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/500000:.2f} megabytes")
    print(f"Sample Rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz; File Format: {config.PRIMARY_FILE_FORMAT}; Channels: {sound_in_chs}")

    # Check and create date-based directories
    if not check_and_create_date_folders():
        logging.critical("Critical directories could not be created. Exiting.")
        sys.exit(1)
    
    # Print directories for verification
    logging.info("Directory setup:")
    logging.info(f"  Primary recordings: {PRIMARY_DIRECTORY}")
    logging.info(f"  Monitor recordings: {MONITOR_DIRECTORY}")
    logging.info(f"  Plot files: {PLOT_DIRECTORY}")
    
    # Ensure all required directories exist
    if not ensure_directories_exist([PRIMARY_DIRECTORY, MONITOR_DIRECTORY, PLOT_DIRECTORY]):
        logging.critical("Critical directories could not be created. Exiting.")
        sys.exit(1)

    # Create and start the process
    if config.MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft, args=(monitor_channel,)) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")

    try:
        if KB_or_CP == 'KB':
            # Give a small delay to ensure prints are visible before starting keyboard listener
            time.sleep(1)
            # Start keyboard listener in a separate thread
            keyboard_thread = threading.Thread(target=keyboard_listener)
            keyboard_thread.daemon = True
            keyboard_thread.start()
            
        # Start the audio stream
        audio_stream()
            
    except KeyboardInterrupt: # ctrl-c in windows
        print('\nCtrl-C: Recording process stopped by user.')
        cleanup()

    except Exception as e:
        logging.critical("An error occurred while attempting to execute this script", exc_info=True)
        cleanup()
    finally:
        # Ensure terminal is reset even if an error occurs
        restore_terminal_settings(original_terminal_settings)
