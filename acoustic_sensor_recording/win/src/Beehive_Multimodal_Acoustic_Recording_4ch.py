#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 

# Using sounddevice and soundfile libraries, record audio from a device ID and save it to a FLAC file.
# Input audio from a device ID at a defineable sample rate, bit depth, and channel count. 
# Write incoming audio into a circular buffer that is of a definable length. 
# Monitor the incoming audio for levels above a definable threshold for a defineable duration and set a flag when conditions are met. 
# Note the position in the buffer of the event and then continue to record audio until a definable time period after the start of the event. 
# Note the position in the buffer of the end of the time period after the start of the event.
# Continue recording audio into the circular buffer while saving the audio to a FLAC file.
# Save audio in the circular buffer from the start of a defineable time period before the event to the end of the defineable time period after the event.
# Reset the audio threshold level flag and event_start_time after saving audio.


import sounddevice as sd
import soundfile as sf
import datetime
import time
import threading
import numpy as np
from scipy.signal import resample
import matplotlib.pyplot as plt
from scipy.fft import rfft, rfftfreq
from pydub import AudioSegment
import os
os.environ['NUMBA_NUM_THREADS'] = '1'
import keyboard

# init recording varibles
continuous_start_index = None
continuous_save_thread = None
continuous_end_index = 0        # so that the next start = this end

period_start_index = None
period_save_thread = None

event_start_index = None
event_save_thread = None
detected_level = None

_dtype = None                   # parms sd lib cares about
_subtype = None
device_CH = None                # total number of channels from device

current_time = None

time_of_day_thread = None
intercom_thread = None
stop_tod_event = threading.Event()
stop_intercom_event = threading.Event()

# Control Panel =====================================================================================

# hardware pointers
DEVICE_IN = 1                               # Device ID of input device - 16 for 4ch audio I/F
DEVICE_OUT = 3                              # Device ID of output device
CHANNELS = 2                                # Number of channels

FULL_SCALE = 2 ** 16                        # just for cli vu meter level reference
BUFFER_SECONDS = 1000                       # seconds of a circular buffer
SAMPLE_RATE = 192000                        # Audio sample rate
BIT_DEPTH = 16                              # Audio bit depth
FORMAT = 'FLAC'                             # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

CONTINUOUS_SAMPLE_RATE = 48000              # For continuous audio
CONTINUOUS_BIT_DEPTH = 16                   # Audio bit depth
CONTINUOUS_CHANNELS = 2                     # Number of channels
CONTINUOUS_QUALITY = 0                      # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
CONTINUOUS_FORMAT = 'MP3'                   # accepts mp3, flac, or wav


MODE_CONTINUOUS = True                      # recording continuously to mp3 files
CONTINUOUS_TIMER = True                     # use a timer to start and stop time of day of continuous recording
CONTINUOUS_START = datetime.time(4, 0, 0)   # time of day to start recording hr, min, sec
CONTINUOUS_END = datetime.time(23, 0, 0)    # time of day to stop recording hr, min, sec
CONTINUOUS = 900                            # file size in seconds of continuous recording

MODE_PERIOD = True                          # period recording
PERIOD_TIMER = True                         # use a timer to start and stop time of day of period recording
PERIOD_START = datetime.time(4, 0, 0)
PERIOD_END = datetime.time(20, 0, 0)
PERIOD = 300                                # seconds of recording
INTERVAL = 1800                             # seconds between start of period, must be > period, of course

MODE_EVENT = True                           # event recording
EVENT_TIMER = False                         # use a timer to start and stop time of day of event recording
EVENT_START = datetime.time(9, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                      # seconds to save before the event
SAVE_AFTER_EVENT = 30                       # seconds to save after the event
THRESHOLD = 40000                           # audio level threshold to be considered an event
MONITOR_CH = 0                              # channel to monitor for event (if > number of chs, all channels are monitored)

MODE_VU = True                              # show audio level on cli



##OUTPUT_DIRECTORY = "."                    # for debugging
OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"

# ==================================================================================================

# audio buffers and variables
buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
buffer = np.zeros((buffer_size, CHANNELS), dtype=_dtype)
buffer_index = 0

### startup housekeeping ###

# Check on parms
if (SAVE_BEFORE_EVENT + SAVE_AFTER_EVENT) * 1.2 > BUFFER_SECONDS:
    print("The buffer is not large enough to hold the maximum amount of audio that can be saved.")
    print("Reduce SAVE_DURATION_BEFORE and/or SAVE_DURATION_AFTER or increase the size of the circular buffer 'BUFFER_SECONDS'")
    quit(-1)

if (PERIOD) * 1.1 > BUFFER_SECONDS:
    print("The buffer is not large enough to hold the maximum amount of audio that can be saved.")
    print("Reduce PERIOD or increase the size of the circular buffer 'BUFFER_SECONDS'")
    quit(-1)

# Check on input device parms or if input device even exits
try:
    device_info = sd.query_devices(DEVICE_IN)  
    device_CH = device_info['max_input_channels'] 
    if CHANNELS > device_CH:
        print(f"The device only has {device_CH} channel(s) but requires {CHANNELS} channels.")
        print("These are the available devices: \n", sd.query_devices())
        quit(-1)
    ##device_SR = device_info['default_samplerate'] 
    ##if device_SR != SAMPLE_RATE:
    ##    print(f"The device sample rate {device_SR} is not equal to the required 'SAMPLE_RATE' of {SAMPLE_RATE}")
    ##    quit(-1)
except Exception as e:
    print(f"An error occurred while attempting to access the input device: {e}")
    print("These are the available devices: \n", sd.query_devices())
    quit(-1)

# Create the output directory if it doesn't exist
try:
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
except Exception as e:
    print(f"An error occurred while trying to make or find output directory: {e}")
    quit(-1)

# translate human to machine
if BIT_DEPTH == 16:
    _dtype = 'int16'
    _subtype = 'PCM_16'
elif BIT_DEPTH == 24:
    _dtype = 'int24'
    _subtype = 'PCM_24'
elif BIT_DEPTH == 32:
    _dtype = 'int32' 
    _subtype = 'PCM_32'
else:
    print("The bit depth is not supported: ", BIT_DEPTH)
    quit(-1)


# #############################################################
# Audio conversion functions
# #############################################################

# convert audio to mp3 and save to file using downsampled data
def pcm_to_mp3_write(np_array, full_path, sample_rate=48000,  quality=CONTINUOUS_QUALITY):

    int_array = np_array.astype(np.int16)
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=sample_rate,
        channels=2
    )
    if quality >= 64 and quality <= 320:    # use constant bitrate, 64k would be the min, 320k the best
        cbr = str(quality) + "k"
        audio_segment.export(full_path, format="mp3", bitrate=cbr)
    elif quality < 10:                      # use variable bitrate, 0 to 9, 0 is highest quality
        audio_segment.export(full_path, format="mp3", parameters=["-q:a", "0"])
    else:
        print("Don't know of a mp3 mode with parameter:", quality)
        quit(-1)


# resample audio to a lower sample rate using scipy library
def resample_audio(audio_data, orig_sample_rate, target_sample_rate):
    # assuming audio_data is stereo 16-bit PCM in a numpy array
    audio_data = audio_data.astype(np.float32)
    audio_data = audio_data.T
    sample_ratio = target_sample_rate / orig_sample_rate
    downsampled_data = np.zeros((audio_data.shape[0], int(audio_data.shape[1] * sample_ratio)))

    # apply resampling to each channel
    for ch in range(audio_data.shape[0]):
        downsampled_data[ch] = resample(audio_data[ch], num=int(audio_data[ch].shape[0] * sample_ratio))

    # transposing the downsampled_data back
    downsampled_data = downsampled_data.T
    audio_data = downsampled_data.astype(np.int16)

    return audio_data


# #############################################################
# signal display functions
# #############################################################

# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
def fake_vu_meter(value, end):
    normalized_value = int(value / 1000)
    asterisks = '*' * normalized_value
    print(asterisks.ljust(50, ' '), end=end)


def get_level(audio_data, channel_select):
    if channel_select <= device_CH:
        audio_level = np.max(np.abs(audio_data[:,channel_select]))
    else: # both channels
        audio_level = np.max(np.abs(audio_data))

    return audio_level


def plot_fft_audio():
    # Constants
    FFT_DURATION = 3  # Duration in seconds
    N = SAMPLE_RATE * FFT_DURATION  # Number of samples

    # Record audio
    print("Recording...")
    myrecording = sd.rec(int(N), samplerate=SAMPLE_RATE, channels=1)
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")

    # Perform FFT
    yf = rfft(myrecording.flatten())
    xf = rfftfreq(N, 1 / SAMPLE_RATE)

    # Define bucket width
    bucket_width = 1000  # Hz
    bucket_size = int(bucket_width * N / SAMPLE_RATE)  # Number of indices per bucket

    # Average buckets
    buckets = np.array([yf[i:i+bucket_size].mean() for i in range(0, len(yf), bucket_size)])
    bucket_freqs = np.array([xf[i:i+bucket_size].mean() for i in range(0, len(xf), bucket_size)])

    # Plot results
    plt.plot(bucket_freqs, np.abs(buckets))
    plt.show()


# plot 'n' seconds of audio of each channels for an oscope view
def plot_oscope_audio(): 
    # Constants
    TRACE_DURATION = 10  # Duration in seconds
    GAIN_DB = 20  # Gain in dB

    # Convert gain from dB to linear scale
    GAIN = 10 ** (GAIN_DB / 20)

    # Record audio
    print("Recording...")
    myrecording = sd.rec(int(SAMPLE_RATE * TRACE_DURATION), samplerate=SAMPLE_RATE, channels=CHANNELS)
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")

    # Apply gain
    myrecording *= GAIN

    # Plot results
    plt.figure()

    # Assume we have 2 channels
    for i in range(2):
        plt.subplot(2, 1, i + 1)
        plt.plot(myrecording[:, i])
        plt.title(f"Channel {i + 1}")

    plt.tight_layout()
    plt.show()

##########################  
# utilities
##########################

# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()


def show_audio_device_info(device_id):
    device_info = sd.query_devices(device_id)  # Replace with your device index
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Input Channels: {}'.format(device_info['max_input_channels']))


def show_audio_device_list():
    print(sd.query_devices())


def toggle_intercom():
    global intercom_thread

    if intercom_thread is None or not intercom_thread.is_alive():
        print("Starting intercom, listening to channel 0")
        intercom_thread = threading.Thread(target=intercom)
        intercom_thread.start()
    else:
        stop_intercom_event.set()
        intercom_thread.join()
        print("\nIntercom stopped")
        intercom_thread = None
        stop_intercom_event.clear()


def intercom():
    global SAMPLE_RATE, CHANNELS, MODE_VU

    # first, stop the vu meter if it's running
    vu_mode = MODE_VU
    MODE_VU = False

    # Create a buffer to hold the audio data
    buffer = np.zeros((SAMPLE_RATE,))
    channel_to_listen_to = [0]

    # Callback function to handle audio input
    def callback_input(indata, frames, time, status):
        # Only process audio from the designated channel
        channel_data = indata[:, channel_to_listen_to[0]]
        buffer[:frames] = channel_data

    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        # Play back the audio from the buffer
        outdata[:, 0] = buffer[:frames]  # Play back on the first channel
        outdata[:, 1] = buffer[:frames]  # Play back on the second channel

    # Function to switch the channel being listened to
    def switch_channel(channel):
        print(f" switching to channel: {channel}", end='\r')
        channel_to_listen_to[0] = channel

    # Set up hotkeys for switching channels
    for i in range(CHANNELS):
        keyboard.add_hotkey(str(i), lambda channel=i: switch_channel(channel))

    # Open an input stream and an output stream with the callback function
    with sd.InputStream(callback=callback_input, channels=CHANNELS, samplerate=SAMPLE_RATE), \
        sd.OutputStream(callback=callback_output, channels=CHANNELS, samplerate=SAMPLE_RATE):
        # The streams are now open and the callback function will be called every time there is audio input and output
        # We'll just use a blocking wait here for simplicity
        while not stop_intercom_event.is_set():
            sd.sleep(100)

        print("Stopping intercom...")
        MODE_VU = vu_mode   # restore vu mode


# #############################################################
# recording functions in various modes
# #############################################################

#
# continuous recording functions at low sample rate
#
def save_audio_for_continuous():
    time.sleep(CONTINUOUS)
    save_continuous_audio()


def save_continuous_audio():
    global buffer, continuous_start_index, continuous_save_thread, continuous_end_index, current_time

    if continuous_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = continuous_start_index % buffer_size
    save_end_index = (continuous_start_index + (CONTINUOUS * SAMPLE_RATE)) % buffer_size
    continuous_end_index = save_end_index

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    # resample to lower sample rate
    audio_data = resample_audio(audio_data, SAMPLE_RATE, CONTINUOUS_SAMPLE_RATE)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}_continuous_{CONTINUOUS_SAMPLE_RATE/1000:.0F}_{BIT_DEPTH}_{CONTINUOUS_CHANNELS}_{CONTINUOUS}_{LOCATION_ID}_{HIVE_ID}.{CONTINUOUS_FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)

    if CONTINUOUS_FORMAT == 'MP3':
        pcm_to_mp3_write(audio_data, full_path_name) 
    elif CONTINUOUS_FORMAT == 'FLAC' or CONTINUOUS_FORMAT == 'WAV': 
        sf.write(full_path_name, audio_data, CONTINUOUS_SAMPLE_RATE, format=CONTINUOUS_FORMAT, subtype=_subtype)
    else:
        print("don't know about file format:", CONTINUOUS_FORMAT)
        quit(-1)

    print(f"Saved continuous audio to {full_path_name}, block size: {CONTINUOUS} seconds")

    continuous_save_thread = None
    continuous_start_index = None


def check_continuous(audio_data, index):
    global continuous_start_index, continuous_save_thread, continuous_end_index

    # just keep doing it, no testing
    if continuous_start_index is None: 
        print("continuous block started at:", datetime.datetime.now())
        continuous_start_index = continuous_end_index 
        ##continuous_start_index = index
        continuous_save_thread = threading.Thread(target=save_audio_for_continuous)
        continuous_save_thread.start()

    if MODE_VU and MODE_CONTINUOUS and not MODE_EVENT:
        audio_level = get_level(audio_data, MONITOR_CH)
        fake_vu_meter(audio_level,'\r')

#
# period recording functions
#

def save_audio_for_period():
    time.sleep(PERIOD)
    save_period_audio()


def save_period_audio():
    global buffer, period_start_index, period_save_thread

    if period_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = period_start_index % buffer_size
    save_end_index = (period_start_index + (PERIOD * SAMPLE_RATE)) % buffer_size

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}_period_{SAMPLE_RATE/1000:.0F}_{BIT_DEPTH}_{CHANNELS}_{PERIOD}_every_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved period audio to {full_path_name}, period: {PERIOD}, interval {INTERVAL} seconds")

    period_save_thread = None
    period_start_index = None


def check_period(audio_data, index):
    global period_start_index, period_save_thread, detected_level

    ##print("Time:", int(time.time()),"INTERVAL:", INTERVAL, "modulo:", int(time.time()) % INTERVAL)
    # if modulo INTERVAL == zero then start of period
    if not int(time.time()) % INTERVAL and period_start_index is None: 
        period_start_index = index 
        period_save_thread = threading.Thread(target=save_audio_for_period)
        period_save_thread.start()

    if MODE_VU and not MODE_CONTINUOUS and not MODE_EVENT:
        audio_level = get_level(audio_data, MONITOR_CH)
        fake_vu_meter(audio_level,'\r')

#
# event recording functions
#

def save_audio_around_event():
    time.sleep(SAVE_AFTER_EVENT)
    save_event_audio()


def save_event_audio():
    global buffer, event_start_index, event_save_thread, detected_level

    if event_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = (event_start_index - SAVE_BEFORE_EVENT * SAMPLE_RATE) % buffer_size
    save_end_index = (event_start_index + SAVE_AFTER_EVENT * SAMPLE_RATE) % buffer_size

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}_event_{detected_level}_{SAVE_BEFORE_EVENT}_{SAVE_AFTER_EVENT}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved evemt audio to {full_path_name}, audio threshold level: {detected_level}, duration: {audio_data.shape[0] / SAMPLE_RATE} seconds")

    event_save_thread = None
    event_start_index = None


def check_level(audio_data, index):
    global event_start_index, event_save_thread, detected_level

    audio_level = get_level(audio_data, MONITOR_CH)

    if (audio_level > THRESHOLD) and event_start_index is None:
        print("event detected at:", datetime.datetime.now(), "audio level:", audio_level)
        detected_level = audio_level
        event_start_index = index
        event_save_thread = threading.Thread(target=save_audio_around_event)
        event_save_thread.start()

    if MODE_VU:
        fake_vu_meter(audio_level,'\r') 

#
# #############################################################
# audio stream callback functions
# ############################################################
#

def callback(indata, frames, time, status):
    global buffer, buffer_index, current_time

    if status:
        print("Callback status:", status)

    data_len = len(indata)

    # managing a circular buffer
    if buffer_index + data_len <= buffer_size:
        buffer[buffer_index:buffer_index + data_len] = indata
    else:
        overflow = (buffer_index + data_len) - buffer_size
        buffer[buffer_index:] = indata[:-overflow]
        buffer[:overflow] = indata[-overflow:]
        print("Buffer overflow, data lost:", overflow)

    if MODE_EVENT:
        if EVENT_TIMER and not (EVENT_START <= current_time <= EVENT_END):
            pass
        else:
            check_level(indata, buffer_index) 

    if MODE_PERIOD:
        if PERIOD_TIMER and not (PERIOD_START <= current_time <= PERIOD_END):
            pass
        else:
            check_period(indata, buffer_index) 

    if MODE_CONTINUOUS:
        if CONTINUOUS_TIMER and not (CONTINUOUS_START <= current_time <= CONTINUOUS_END):
            pass
        else:
            check_continuous(indata, buffer_index)  

    buffer_index = (buffer_index + data_len) % buffer_size


def get_time_of_day():
    global current_time
    # this thread just keeps track of the time of day every second
    while not stop_tod_event.is_set():
        current_time = datetime.datetime.now().time()
        time.sleep(1)


def audio_stream():
    global buffer, buffer_index, _dtype, time_of_day_thread

    stream = sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, callback=callback)
    with stream:
        print("Start recording...")

        if MODE_VU:
            print("VU meter monitoring channel:", MONITOR_CH)
            fake_vu_meter(FULL_SCALE, '\n')  # mark max audio level on the CLI
            if MODE_EVENT:
                fake_vu_meter(THRESHOLD, '\n')  # mark audio event threshold on the CLI for ref
        else:
            print("Audio level display on cli is off")

        time_of_day_thread = threading.Thread(target=get_time_of_day)
        time_of_day_thread.start()

        while stream.active:
            pass


###########################
########## MAIN ###########
###########################

def main():
    print("Acoustic Signal Capture\n")
    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/1000000:.2f} megabytes")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FORMAT}; Channels: {CHANNELS}")
    # show mode status
    try:
        if MODE_CONTINUOUS:
            print(f"Starting continuous, low-sample-rate recording mode, duration per file: {CONTINUOUS/60:.2f} minutes")
            if CONTINUOUS_TIMER:
                print(f"    Operational between: {CONTINUOUS_START} and {CONTINUOUS_END}")
            else:
                print("    Timer off")
        if MODE_PERIOD:
            print(f"Starting periodic recording mode, {PERIOD/60:.2f} minutes every {INTERVAL/60:.2f} minutes")
            if PERIOD_TIMER:
                print(f"    Operational between: {PERIOD_START} and {PERIOD_END}")
            else:
                print("    Timer off")
        if MODE_EVENT:
            print(f"Starting event detect mode, threshold trigger: {THRESHOLD},  time before: {SAVE_BEFORE_EVENT} sec, time after: {SAVE_AFTER_EVENT} sec")
            if EVENT_TIMER:
                print(f"    Operational between: {EVENT_START} and {EVENT_END}")
            else:
                print("    Timer off")

        # one shot process to see fft
        keyboard.on_press_key("f", lambda _: plot_fft_audio())  
        # one shot process to see oscope
        keyboard.on_press_key("o", lambda _: plot_oscope_audio()) 
        # one shot process to see device list
        keyboard.on_press_key("d", lambda _: show_audio_device_list()) 
        # one shot process to listen live to individual audio channels
        #   usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
        #   needs to be on a separate thread so it doesn't block the main thread and keyboard bindings will work
        keyboard.on_press_key("i", lambda _: toggle_intercom())

        # continuous recording process
        audio_stream()

    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')
        stop_tod_event.set()    # stop the time_of_day_thread
        time_of_day_thread.join() 
        
    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1)         # quit with error


if __name__ == "__main__":
    main()
