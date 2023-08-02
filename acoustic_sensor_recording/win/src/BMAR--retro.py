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
import multiprocessing
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import resample
from scipy.fft import rfft, rfftfreq
from pydub import AudioSegment
import os
##os.environ['NUMBA_NUM_THREADS'] = '1'
import keyboard
import atexit
import msvcrt
import signal
import sys
import warnings
##import TestPyQT5

lock = threading.Lock()

# Ignore this specific warning
warnings.filterwarnings("ignore", category=UserWarning)

def signal_handler(sig, frame):
    print('Stopping all threads...')
    stop_all()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# init recording varibles
continuous_start_index = None
continuous_end_index = 0        # so that the next start = this end
period_start_index = None
event_start_index = None
detected_level = None

# threads
continuous_save_thread = None
period_save_thread = None
event_save_thread = None
time_of_day_thread = None

# procs
oscope_proc = None
intercom_proc = None
fft_periodic_plot_proc = None
one_shot_fft_proc = None
oscope_proc = None   

# event flags
stop_continuous_event = threading.Event()
stop_period_event = threading.Event()
stop_event_event = threading.Event()

stop_tod_event = threading.Event()
stop_intercom_event = threading.Event()
stop_fft_periodic_plot_event = threading.Event()

trigger_oscope_event = threading.Event()
trigger_fft_event = threading.Event()

# misc globals
_dtype = None                   # parms sd lib cares about
_subtype = None
device_ch = None                # total number of channels from device
current_time = None
timestamp = None
monitor_channel = 0
stop_program = [False]

# #############################################################
# #### Control Panel ##########################################
# #############################################################

# modes
MODE_CONTINUOUS = False                      # recording continuously to mp3 files
CONTINUOUS_TIMER = True                     # use a timer to start and stop time of day of continuous recording
MODE_PERIOD = True                          # period recording
PERIOD_TIMER = True                         # use a timer to start and stop time of day of period recording
MODE_EVENT = False                           # event recording
EVENT_TIMER = False                         # use a timer to start and stop time of day of event recording
MODE_VU = False                             # show audio level on cli
MODE_FFT_PERIODIC_RECORD = False             # record fft periodically
KB_or_CP = "KB"                             # use keyboard or control panel (PyQT5) to control program

# hardware pointers
DEVICE_IN = 17                              # Device ID of input device - 17 Scarlett, 16 for 4ch audio I/F
DEVICE_OUT = 14                             # Device ID of output device - 14 Scarlett
DEVICE_CHANNELS = 2                                # Number of channels

FULL_SCALE = 2 ** 16                        # just for cli vu meter level reference
BUFFER_SECONDS = 1000                       # seconds of a circular buffer
SAMPLE_RATE = 192000                        # Audio sample rate
BIT_DEPTH = 16                              # Audio bit depth
FORMAT = "FLAC"                             # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

CONTINUOUS_SAMPLE_RATE = 48000              # For continuous audio
CONTINUOUS_BIT_DEPTH = 16                   # Audio bit depth
CONTINUOUS_CHANNELS = 1                     # Number of channels
CONTINUOUS_QUALITY = 0                      # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
CONTINUOUS_FORMAT = "MP3"                   # accepts mp3, flac, or wav

CONTINUOUS_START = datetime.time(4, 0, 0)   # time of day to start recording hr, min, sec
CONTINUOUS_END = datetime.time(23, 0, 0)    # time of day to stop recording hr, min, sec
CONTINUOUS_DURATION = 300                            # file size in seconds of continuous recording

PERIOD_START = datetime.time(4, 0, 0)
PERIOD_END = datetime.time(20, 0, 0)
PERIOD = 300                                # seconds of recording
INTERVAL = 1800                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                      # seconds to save before the event
SAVE_AFTER_EVENT = 30                       # seconds to save after the event
THRESHOLD = 40000                           # audio level threshold to be considered an event
MONITOR_CH = 0                              # channel to monitor for event (if > number of chs, all channels are monitored)

# instrumentation parms
FFT_BINS = 900                              # number of bins for fft
FFT_BW = 1000                               # bandwidth of each bucket in hertz
FFT_DURATION = 5                            # seconds of audio to show on fft
FFT_GAIN = 20                               # gain in dB for fft
FFT_INTERVAL = 30                           # minutes between ffts

OSCOPE_DURATION = 10                        # seconds of audio to show on oscope
OSCOPE_GAIN = 20                            # gain in dB for oscope

##SIGNAL_DIRECTORY = "."                    # for debugging
SIGNAL_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
PLOT_DIRECTORY = "D:/OneDrive/data/Zeev/plots"

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"

# ==================================================================================================

# audio buffers and variables
buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
buffer = np.zeros((buffer_size, DEVICE_CHANNELS), dtype=_dtype)
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
    device_ch = device_info['max_input_channels'] 
    if DEVICE_CHANNELS > device_ch:
        print(f"The device only has {device_ch} channel(s) but requires {DEVICE_CHANNELS} channels.")
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
    os.makedirs(SIGNAL_DIRECTORY, exist_ok=True)
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


def get_time_of_day():
    global current_time, timestamp
    # this thread just keeps track of the time of day every second
    while not stop_tod_event.is_set():
        current_time = datetime.datetime.now().time()
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        time.sleep(1)

# #############################################################
# Audio conversion functions
# #############################################################

# convert audio to mp3 and save to file using downsampled data
def pcm_to_mp3_write(np_array, full_path):

    int_array = np_array.astype(np.int16)
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=CONTINUOUS_SAMPLE_RATE,
        channels=CONTINUOUS_CHANNELS
    )
    if CONTINUOUS_QUALITY >= 64 and CONTINUOUS_QUALITY <= 320:    # use constant bitrate, 64k would be the min, 320k the best
        cbr = str(CONTINUOUS_QUALITY) + "k"
        audio_segment.export(full_path, format="mp3", bitrate=cbr)
    elif CONTINUOUS_QUALITY < 10:                      # use variable bitrate, 0 to 9, 0 is highest quality
        audio_segment.export(full_path, format="mp3", parameters=["-q:a", "0"])
    else:
        print("Don't know of a mp3 mode with parameter:", CONTINUOUS_QUALITY)
        quit(-1)

# resample audio to a lower sample rate using scipy library
def resample_audio(audio_data, orig_sample_rate, target_sample_rate):
    # check if audio_data needs to be transposed
    if audio_data.shape[0] < audio_data.shape[1]:
        audio_data = audio_data.T

    # assuming audio_data is stereo 16-bit PCM in a numpy array
    audio_data = audio_data.astype(np.float32)
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


def get_level(audio_data):
    global monitor_channel, device_ch

    ##print("channel_to_listen_to", monitor_channel)
    channel = monitor_channel
    if channel <= device_ch:
        audio_level = np.max(np.abs(audio_data[:,channel]))
    else: # all channels
        audio_level = np.max(np.abs(audio_data))

    return audio_level


def toggle_vu_meter():
    global MODE_VU, monitor_channel

    if MODE_VU:
        print("\nStopping VU meter")
        MODE_VU = False
    else:
        # mark max audio level on the CLI
        print("\nVU meter monitoring channel:", monitor_channel)
        normalized_value = int(FULL_SCALE / 1000)
        asterisks = '*' * (normalized_value - 11)
        print("fullscale:",asterisks.ljust(50, ' '))

        if MODE_EVENT:
            # mark audio event threshold on the CLI for ref
            normalized_value = int(THRESHOLD / 1000)
            asterisks = '*' * (normalized_value - 11)
            print("threshold:",asterisks.ljust(50, ' '))

        MODE_VU = True

# single-shot fft plot of audio
def plot_fft():
    global monitor_channel, FFT_INTERVAL, FFT_GAIN  

    interval = FFT_INTERVAL * 60    # convert to seconds, time betwwen ffts
    N = SAMPLE_RATE * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)
    # Record audio
    print("Recording audio for fft one shot...")
    myrecording = sd.rec(int(N), samplerate=SAMPLE_RATE, channels=1)
    sd.wait()  # Wait until recording is finished
    myrecording *= gain
    print("Recording fft finished.")

    # Perform FFT
    yf = rfft(myrecording.flatten())
    xf = rfftfreq(N, 1 / SAMPLE_RATE)

    # Define bucket width
    bucket_width = FFT_BW  # Hz
    bucket_size = int(bucket_width * N / SAMPLE_RATE)  # Number of indices per bucket

    # Average buckets
    buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
    bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

    # Plot results
    plt.plot(bucket_freqs, np.abs(buckets))
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude')
    plt.title('FFT Plot')
    plt.grid(True)

    plt.show()


# continuous fft plot of audio in a separate process
def plot_and_save_fft():
    global monitor_channel, FFT_GAIN, FFT_INTERVAL

    interval = FFT_INTERVAL * 60    # convert to seconds, time betwwen ffts
    N = SAMPLE_RATE * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)

    while not stop_fft_periodic_plot_event.is_set():
        # Record audio
        print("Recording audio for auto fft...")
        myrecording = sd.rec(int(N), samplerate=SAMPLE_RATE, channels=1)
        sd.wait()  # Wait until recording is finished
        myrecording *= gain
        print("Recording auto fft finished.")

        # Perform FFT
        yf = rfft(myrecording.flatten())
        xf = rfftfreq(N, 1 / SAMPLE_RATE)

        # Define bucket width
        bucket_width = FFT_BW  # Hz
        bucket_size = int(bucket_width * N / SAMPLE_RATE)  # Number of indices per bucket

        # Average buckets
        buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
        bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

        # Plot results
        plt.plot(bucket_freqs, np.abs(buckets))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT Plot')
        plt.grid(True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Save plot to disk with a unique filename based on current time
        output_filename = f"{timestamp}_fft_{SAMPLE_RATE/1000:.0F}_{BIT_DEPTH}_{monitor_channel}_{LOCATION_ID}_{HIVE_ID}.png"
        full_path_name = os.path.join(PLOT_DIRECTORY, output_filename)
        plt.savefig(full_path_name)

        # Wait for the desired time interval before recording and plotting again
        # not using time.sleep() alone because it blocks the main thread
        t = interval
        while t > 0:
            time.sleep(1)
            t -= 1
            if stop_fft_periodic_plot_event.is_set():
                return
    print("Exiting fft periodic")


# single-shot plot of 'n' seconds of audio of each channels for an oscope view
def plot_oscope(): 
    # Constants
    TRACE_DURATION = 10     # Duration in seconds
    GAIN_DB = 20            # Gain in dB

    # Convert gain from dB to linear scale
    gain = 10 ** (GAIN_DB / 20)

    # Record audio
    print("Recording audio for oscope traces...")
    myrecording = sd.rec(int(SAMPLE_RATE * TRACE_DURATION), samplerate=SAMPLE_RATE, channels=DEVICE_CHANNELS)
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")

    myrecording *= gain
    plt.figure()

    # Plot number of channels
    for i in range(DEVICE_CHANNELS):
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


def intercom():
    global monitor_channel

    # Create a buffer to hold the audio data
    buffer = np.zeros((SAMPLE_RATE,))
    channel = monitor_channel

    # Callback function to handle audio input
    def callback_input(indata, frames, time, status):
        # Only process audio from the designated channel
        channel_data = indata[:, channel]
        buffer[:frames] = channel_data

    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        # Play back the audio from the buffer
        outdata[:, 0] = buffer[:frames]  # Play back on the first channel
        outdata[:, 1] = buffer[:frames]  # Play back on the second channel

    # Function to switch the channel being listened to
    def switch_channel(channel):
        global monitor_channel
        print(f" switching to channel: {channel}", end='\r')
        monitor_channel = channel

    # Set up hotkeys for switching channels
    for i in range(DEVICE_CHANNELS):
        keyboard.add_hotkey(str(i), lambda channel=i: switch_channel(channel))

    # Open an input stream and an output stream with the callback function
    with sd.InputStream(callback=callback_input, channels=DEVICE_CHANNELS, samplerate=SAMPLE_RATE), \
        sd.OutputStream(callback=callback_output, channels=DEVICE_CHANNELS, samplerate=SAMPLE_RATE):
        # The streams are now open and the callback function will be called every time there is audio input and output
        # We'll just use a blocking wait here for simplicity
        while not stop_intercom_event.is_set():
            sd.sleep(1)
        print("Stopping intercom...")


def stop_intercom():
    global intercom_proc

    if intercom_proc is not None:
        stop_intercom_event.set()
        intercom_proc.terminate()
        intercom_proc.join()            # make sure its stopped, hate zombies


def toggle_intercom():
    global intercom_proc

    if intercom_proc is None:
        print("Starting intercom...")
        print("listening to channel 0",  end='\r')
        intercom_proc = multiprocessing.Process(target=intercom)
        intercom_proc.start()
    else:
        stop_intercom()
        print("\nIntercom stopped")
        intercom_proc = None


# #############################################################
# recording functions in various modes
# #############################################################

# ####################################################
# continuous recording functions at low sample rate
# ####################################################

def save_audio_for_continuous():
    t = CONTINUOUS_DURATION
    while t > 0:
        time.sleep(1)
        t -= 1
        if stop_continuous_event.is_set():
            print("stop_continuous_event was set in save_audio_for_continuous")
            return
    save_continuous_audio()


def save_continuous_audio():
    global buffer, continuous_start_index, continuous_save_thread, continuous_end_index

    if continuous_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = continuous_start_index % buffer_size
    save_end_index = (continuous_start_index + (CONTINUOUS_DURATION * SAMPLE_RATE)) % buffer_size
    continuous_end_index = save_end_index

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    # resample to lower sample rate
    audio_data = resample_audio(audio_data, SAMPLE_RATE, CONTINUOUS_SAMPLE_RATE)

    output_filename = f"{timestamp}_continuous_{CONTINUOUS_SAMPLE_RATE/1000:.0F}_{BIT_DEPTH}_{CONTINUOUS_CHANNELS}_{CONTINUOUS_DURATION}_{LOCATION_ID}_{HIVE_ID}.{CONTINUOUS_FORMAT.lower()}"
    full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)

    with lock:
        if CONTINUOUS_FORMAT == 'MP3':
            pcm_to_mp3_write(audio_data, full_path_name) 
        elif CONTINUOUS_FORMAT == 'FLAC' or CONTINUOUS_FORMAT == 'WAV': 
            sf.write(full_path_name, audio_data, CONTINUOUS_SAMPLE_RATE, format=CONTINUOUS_FORMAT, subtype=_subtype)
        else:
            print("don't know about file format:", CONTINUOUS_FORMAT)
            quit(-1)

    print(f"Saved continuous audio to {full_path_name}, block size: {CONTINUOUS_DURATION} seconds")

    continuous_start_index = None
    continuous_save_thread.terminate()        
    continuous_save_thread.join()     


def check_continuous(audio_data, index):
    global continuous_start_index, continuous_save_thread, continuous_end_index, stop_continuous_event
    
    if not stop_continuous_event.is_set():
        # just keep doing it, no testing
        ##if continuous_start_index is None and not stop_continuous_event.is_set(): 
        print("continuous block started at:", current_time)
        continuous_start_index = continuous_end_index 
        continuous_save_thread = threading.Thread(target=save_audio_for_continuous)
        continuous_save_thread.start()        
        save_audio_for_continuous()
    else:
        print("check_continuous exited with event flag")

# #######################################
# period recording functions
# #######################################

def save_audio_for_period():
    t = PERIOD
    while t > 0:
        time.sleep(1)
        t -= 1
        if stop_period_event.is_set():
            return
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

    output_filename = f"{timestamp}_period_{SAMPLE_RATE/1000:.0F}_{BIT_DEPTH}_{DEVICE_CHANNELS}_{PERIOD}_every_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)
    with lock:
        sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved period audio to {full_path_name}, period: {PERIOD}, interval {INTERVAL} seconds")

    period_start_index = None
    save_audio_for_period.terminate()
    save_audio_for_period.join()


def check_period(audio_data, index):
    global period_start_index, period_save_thread

    ##print("Time:", int(time.time()),"INTERVAL:", INTERVAL, "modulo:", int(time.time()) % INTERVAL)
    if not stop_period_event.is_set():
        # if modulo INTERVAL == zero then start of period
        if not int(time.time()) % INTERVAL and period_start_index is None: 
            period_start_index = index
            period_save_thread = threading.Thread(target=save_audio_for_period)
            period_save_thread.start()            
            save_audio_for_period()
    else:
        print("check_period exited with event flag")

# ####################################
# event recording functions
# ####################################

def save_audio_for_event():
    t = SAVE_AFTER_EVENT        # seconds of audio to save after an event is detected
    while t > 0:
        time.sleep(1)
        t -= 1
        if stop_event_event.is_set():   # is the program trying to shutdown?
            return
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

    output_filename = f"{timestamp}_event_{detected_level}_{SAVE_BEFORE_EVENT}_{SAVE_AFTER_EVENT}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)
    with lock:
        sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved evemt audio to {full_path_name}, audio threshold level: {detected_level}, duration: {audio_data.shape[0] / SAMPLE_RATE} seconds")

    event_start_index = None
    save_audio_for_event.terminate()
    save_audio_for_event.join()


def check_level(audio_data, index):
    global event_start_index, event_save_thread, detected_level

    if not stop_event_event.is_set():
        audio_level = get_level(audio_data)
        if (audio_level > THRESHOLD) and event_start_index is None:
            print("event detected at:", current_time, "audio level:", audio_level)
            detected_level = audio_level
            event_start_index = index
            continuous_save_thread = threading.Thread(target=save_audio_for_event)
            continuous_save_thread.start()
            save_audio_for_event()
    else:
        print("check_level exited with event flag")

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

    if MODE_VU:
        audio_level = get_level(indata)
        fake_vu_meter(audio_level,'\r')

    buffer_index = (buffer_index + data_len) % buffer_size


def signal_stop_all():
    global stop_program
    print("Signalling stop all processes...")
    stop_program[0] = True
    ##stop_all()


def clear_input_buffer():
    while msvcrt.kbhit():
        msvcrt.getch()


def stop_all():
    global stop_program, continuous_save_thread, period_save_thread, event_save_thread, time_of_day_thread, stop_tod_event

    print("\n\nStopping all threads...\n")

    list_all_threads()

    print("\nClearing input buffer of keystrokes\n")
    clear_input_buffer()    # clear the input buffer so we don't get any unwanted characters

    for t in threading.enumerate():
        print("thread name:", t)

        if "save_audio_for_continuous" in t.name:
            if t.is_alive():
                stop_continuous_event.set()
                t.join
                print("continuous stopped ***")  
        if "save_audio_for_period" in t.name:
            if t.is_alive():
                stop_period_event.set()
                t.join
                print("period stopped ***")
        if "save_audio_for_event" in t.name:
            if t.is_alive():
                stop_event_event.set()
                t.join
                print("event stopped ***")                
        if "get_time_of_day" in t.name:
            if t.is_alive():
                stop_tod_event.set()
                t.join
                print("tod stopped ***")       

    stop_fft_periodic_plot_event.set()
    if fft_periodic_plot_proc is not None:
        fft_periodic_plot_proc.join()

    stop_intercom()
    keyboard.unhook_all()
    print("\nHopefully we have turned off all the lights...")


def audio_stream():
    global buffer, buffer_index, _dtype, time_of_day_thread, stop_program
    global fft_periodic_plot_proc

    stream = sd.InputStream(device=DEVICE_IN, channels=DEVICE_CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, callback=callback)

    with stream:
        print("Start audio_stream...")

        # Create and start the process, note: using mp because matplotlib wants in be in the mainprocess threqad
        if MODE_FFT_PERIODIC_RECORD:
            fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft) 
            fft_periodic_plot_proc.daemon = True  
            fft_periodic_plot_proc.start()
            print("started fft_periodic_plot_process")

        # Create and start the thread
        if MODE_CONTINUOUS:
            print(f"Starting continuous, low-sample-rate recording mode, duration per file: {CONTINUOUS_DURATION/60:.2f} minutes")
            if CONTINUOUS_TIMER:
                print(f"    Operational between: {CONTINUOUS_START} and {CONTINUOUS_END}")
            else:
                print("    Timer off")

        # Create and start the thread
        if MODE_PERIOD:
            print(f"Starting periodic recording mode, {PERIOD/60:.2f} minutes every {INTERVAL/60:.2f} minutes")
            if PERIOD_TIMER:
                print(f"    Operational between: {PERIOD_START} and {PERIOD_END}")
            else:
                print("    Timer off")

        # Create and start the thread
        if MODE_EVENT:
            print(f"Starting event detect mode, threshold trigger: {THRESHOLD}, time before: {SAVE_BEFORE_EVENT} sec, time after: {SAVE_AFTER_EVENT} sec")
            if EVENT_TIMER:
                print(f"    Operational between: {EVENT_START} and {EVENT_END}")
            else:
                print("    Timer off")

        while stream.active and not stop_program[0]:
            pass
        
        stop_all()
        stream.stop()
        print("Stopped audio_stream...")


###########################
########## MAIN ###########
###########################

def main():
    global time_of_day_thread, intercom_thread, stop_tod_event, stop_intercom_event

    print("Acoustic Signal Capture\n")
    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/1000000:.2f} megabytes")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FORMAT}; Channels: {DEVICE_CHANNELS}")


    def trigger_fft():
        trigger_fft_event
        one_shot_fft_proc = multiprocessing.Process(target=plot_fft)
        one_shot_fft_proc.start()
        # fft one shot returns here when plot window is closed by user
        one_shot_fft_proc.terminate()
        one_shot_fft_proc.join()
        print("exit fft")


    def trigger_oscope():
        oscope_proc = multiprocessing.Process(target=plot_oscope)
        oscope_proc.start()
        # oscope returns here when plot window is closed by user
        oscope_proc.terminate()
        oscope_proc.join()
        print("exit oscope")


    # Create and start the thread for time of day
    time_of_day_thread = threading.Thread(target=get_time_of_day)
    time_of_day_thread.daemon = True 
    time_of_day_thread.start()

    try:
        if KB_or_CP == 'KB':
            # beehive keyboard triggered management utilities
            # one shot process to see fft
            keyboard.on_press_key("f", lambda _: trigger_fft(), suppress=True)   
            # one shot process to see oscope
            keyboard.on_press_key("o", lambda _: trigger_oscope(), suppress=True) 
            # one shot process to see device list
            keyboard.on_press_key("d", lambda _: show_audio_device_list(), suppress=True) 
            # usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
            keyboard.on_press_key("i", lambda _: toggle_intercom(), suppress=True)
            # usage: press v to start cli vu meter, press v again to stop
            keyboard.on_press_key("v", lambda _: toggle_vu_meter(), suppress=True)
            # usage: press q to stop all processes
            keyboard.on_press_key("q", lambda _: signal_stop_all(), suppress=True)
            # usage: press t to see all threads
            keyboard.on_press_key("t", lambda _: list_all_threads(), suppress=True)

        audio_stream()

        if KB_or_CP == "KB":
            # Unhook all hooks
            keyboard.unhook_all()

            # Get the list of all currently active hooks after unhooking
            hooks_after = list(keyboard._hooks.values())

            # If unhook_all worked, hooks_after should be empty
            if len(hooks_after) == 0:
                print("All hooks unhooked successfully")
            else:
                print("Some hooks were not unhooked")

        print("\nHopefully we have turned off all the lights...")
            
    except KeyboardInterrupt: # ctrl-c in windows
        print('\nRecording process stopped by user.')
        stop_all()

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1) 


if __name__ == "__main__":
    # Register the stop_all function to be called when the script exits

    main()
    ##atexit.register(stop_all)
