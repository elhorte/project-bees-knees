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
from scipy.io.wavfile import write
from scipy.signal import resample
from scipy.fft import rfft, rfftfreq
from scipy.signal import resample_poly
from pydub import AudioSegment
import os
##os.environ['NUMBA_NUM_THREADS'] = '1'
import keyboard
import atexit
import msvcrt
import signal
import sys
import warnings
import queue
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
vu_proc = None
oscope_proc = None
intercom_proc = None
fft_periodic_plot_proc = None
one_shot_fft_proc = None  

# event flags
stop_recording_event = threading.Event()
stop_event_event = threading.Event()

stop_tod_event = threading.Event()
stop_vu_event = threading.Event()
stop_intercom_event = threading.Event()
stop_fft_periodic_plot_event = threading.Event()

trigger_oscope_event = threading.Event()
trigger_fft_event = threading.Event()
stop_worker_event = threading.Event()

# misc globals
_dtype = None                   # parms sd lib cares about
_subtype = None
asterisks = '*'
device_ch = None                # total number of channels from device
current_time = None
timestamp = None
monitor_channel = 0
stop_program = [False]
buffer_size = None
buffer = None
buffer_index = None

# #############################################################
# #### Control Panel ##########################################
# #############################################################

# modes
MODE_CONTINUOUS = False                      # recording continuously to mp3 files
CONTINUOUS_TIMER = False                     # use a timer to start and stop time of day of continuous recording
MODE_PERIOD = True                          # period recording
PERIOD_TIMER = False                         # use a timer to start and stop time of day of period recording
MODE_EVENT = False                           # event recording
EVENT_TIMER = False                         # use a timer to start and stop time of day of event recording

MODE_FFT_PERIODIC_RECORD = True             # record fft periodically
KB_or_CP = "KB"                             # use keyboard or control panel (PyQT5) to control program

# hardware pointers
DEVICE_IN = 1                              # WASAPI: 17 Scarlett 2ch & Behr 4ch, 16 Behr 2ch, 1 for mme
DEVICE_OUT = 3                             # WASAPI: 14 Scarlett, 15 Behr 4ch, 14 Behr 2ch, 4 for mme
DEVICE_CHANNELS = 2                         # Number of channels

FULL_SCALE = 2 ** 16                        # just for cli vu meter level reference
BUFFER_SECONDS = 1000                       # seconds of a circular buffer
SAMPLE_RATE = 192000                        # Audio sample rate
BIT_DEPTH = 16                              # Audio bit depth
FILE_FORMAT = "WAV"                             # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

CONTINUOUS_SAMPLE_RATE = 48000              # For continuous audio
CONTINUOUS_BIT_DEPTH = 16                   # Audio bit depthv
CONTINUOUS_CHANNELS = 1                     # Number of channels
CONTINUOUS_QUALITY = 0                      # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
CONTINUOUS_FORMAT = "FLAC"                  # accepts mp3, flac, or wav

CONTINUOUS_START = datetime.time(4, 0, 0)   # time of day to start recording hr, min, sec
CONTINUOUS_END = datetime.time(23, 0, 0)    # time of day to stop recording hr, min, sec
CONTINUOUS_DURATION = 30                    # file size in seconds of continuous recording

PERIOD_START = datetime.time(4, 0, 0)
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = 20                                # seconds of recording
PERIOD_INTERVAL = 40                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                      # seconds to save before the event
SAVE_AFTER_EVENT = 30                       # seconds to save after the event
EVENT_THRESHOLD = 20000                     # audio level threshold to be considered an event
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

# single-shot plot of 'n' seconds of audio of each channels for an oscope view
def plot_oscope(): 
    # Constants
    TRACE_DURATION = 10     # Duration in seconds
    GAIN_DB = 20            # Gain in dB

    # Convert gain from dB to linear scale
    gain = 10 ** (GAIN_DB / 20)

    show_ch = 2
    # Record audio
    print("Recording audio for oscope traces for ch count:", show_ch)
    orecording = sd.rec(int(SAMPLE_RATE * TRACE_DURATION), samplerate=SAMPLE_RATE, channels=show_ch)
    sd.wait()  # Wait until recording is finished
    print("Recording oscope finished.")

    orecording *= gain
    plt.figure()

    # Plot number of channels
    for i in range(show_ch):
        plt.subplot(2, 1, i + 1)
        plt.plot(orecording[:, i])
        plt.title(f"Channel {i + 1}")

    plt.tight_layout()
    plt.show()
    print("press any key to continue...")


# single-shot fft plot of audio
def plot_fft():
    global monitor_channel

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
    print("press any key to continue...")

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


##########################  
# utilities
##########################

# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()


def show_audio_device_info_for_defaults():
    device_info = sd.query_devices(DEVICE_IN)  # Replace with your device index
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Input Channels: {}'.format(device_info['max_input_channels']))
    device_info = sd.query_devices(DEVICE_OUT)  # Replace with your device index
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Output Channels: {}'.format(device_info['max_output_channels']))


def show_audio_device_list():
    print(sd.query_devices())
    print(f"\nCurrent device in: {DEVICE_IN}, device out: {DEVICE_OUT}\n")
    show_audio_device_info_for_defaults()


# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
def vu_meter(stop_vu_queue, asterisks):
    global monitor_channel, device_ch

    buffer = np.zeros((SAMPLE_RATE,))

    def callback_input(indata, frames, time, status):
        global monitor_channel
        # Only process audio from the designated channel
        channel_data = indata[:, monitor_channel]
        buffer[:frames] = channel_data

        audio_level = np.max(np.abs(channel_data))
        normalized_value = int((audio_level / 1.0) * 50)  # scale based on max value of 1.0, and multiply by 50 for the length of the asterisks bar

        asterisks.value = '*' * normalized_value
        ##print(f"Audio level: {audio_level}, Normalized value: {normalized_value}")
        print(asterisks.value.ljust(50, ' '), end='\r')

    with sd.InputStream(callback=callback_input, channels=2, samplerate=SAMPLE_RATE):
        while not stop_vu_queue.get():
            ##sd.sleep(1)
            ##print(asterisks.value.ljust(50, ' '), end='\r')
            pass
        print("Stopping vu...")


def stop_vu(vu_proc, stop_vu_event):
    if vu_proc is not None:
        stop_vu_event.set()
        vu_proc.join()            # make sure its stopped, hate zombies


def toggle_vu_meter():
    global vu_proc, monitor_channel, asterisks, stop_vu_queue

    if vu_proc is None:
        print("\nVU meter monitoring channel:", monitor_channel)
        manager = multiprocessing.Manager()
        stop_vu_queue = multiprocessing.Queue()
        asterisks = manager.Value(str, '*' * 50)

        print("fullscale:",asterisks.value.ljust(50, ' '))

        if MODE_EVENT:
            normalized_value = int(EVENT_THRESHOLD / 1000)
            asterisks.value = '*' * normalized_value
            print("threshold:",asterisks.value.ljust(50, ' '))

        vu_proc = multiprocessing.Process(target=vu_meter, args=(stop_vu_queue, asterisks))
        vu_proc.start()
    else:
        stop_vu_queue.put(True)
        vu_proc.join()
        print("\nvu stopped")
        vu_proc = None


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

# ##################################################
# WORKER THREADS #
# ##################################################

#
# continuous recording functions at low sample rate
#

def call_continuous(index):
    global continuous_start_index, continuous_last_end_index, detected_level, buffer

    # just keep doing it, no test
    if continuous_start_index is None: 
        print("continous block started at:", datetime.datetime.now())
        if continuous_last_end_index == None:
            continuous_start_index = index 
        else:
            continuous_start_index = continuous_last_end_index
        # recording time per file
        t = CONTINUOUS_DURATION
        while t > 0:
            time.sleep(1)
            t -= 1
            if stop_recording_event.is_set():
                print("stop_continuous_event was set in save_audio_for_continuous")
                return

            if continuous_start_index is None:  # if this has been reset already, don't try to save
                return

            save_start_index = continuous_last_end_index % buffer_size
            save_end_index = (continuous_start_index + (CONTINUOUS_DURATION * SAMPLE_RATE)) % buffer_size

            # saving from a circular buffer so segments aren't necessarily contiguous
            if save_end_index > save_start_index:   # is contiguous
                audio_data = buffer[save_start_index:save_end_index]
            else:                                   # ain't contiguous
                audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))
            # Downsample audio before saving
            audio_data = signal.resample_poly(audio_data, CONTINUOUS_SAMPLE_RATE, SAMPLE_RATE)
            
            # Convert to 16-bit
            audio_data = audio_data.astype(np.int16)

            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            output_filename = f"{timestamp}_continuous_{CONTINUOUS_DURATION}_{LOCATION_ID}_{HIVE_ID}.{FILE_FORMAT.lower()}"
            full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)
            sf.write(full_path_name, audio_data, CONTINUOUS_SAMPLE_RATE, format=CONTINUOUS_FORMAT, subtype=_subtype)  # use DOWNSAMPLE_RATE

            print(f"Saved continuous audio to {full_path_name}, block size: {CONTINUOUS_DURATION} seconds")

            continuous_last_end_index = save_end_index   # save the end index for the next block starting point
            continuous_start_index = None

#
# period recording functions
#

def recording_worker_thread(period, interval, file_format):
    global buffer, buffer_size
    
    while not stop_recording_event.is_set:

        period_start_index = index_queue.get() 
            
        print("period started at:", datetime.datetime.now())
        # wait PERIOD seconds to accumulate audio
        t = period
        while t > 0:
            time.sleep(1)
            t -= 1
            if stop_recording_event.is_set():
                return
        
        period_end_index = index_queue.get() 

        save_start_index = period_start_index % buffer_size
        save_end_index = period_end_index % buffer_size
        # saving from a circular buffer so segments aren't necessarily contiguous
        if save_end_index > save_start_index:   # is contiguous
            audio_data = buffer[save_start_index:save_end_index]
        else:                                   # ain't contiguous
            audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

        print("some audio data:", audio_data[0:20])
        print("audio_data shape:", audio_data.shape)
        input("press to continue")
        sd.play(audio_data, SAMPLE_RATE, DEVICE_OUT)
        sd.wait()

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_filename = f"{timestamp}_period_{PERIOD_RECORD}_{PERIOD_INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{file_format.lower()}"
        full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)

        sf.write(full_path_name, audio_data, SAMPLE_RATE, format=file_format)

        print(f"Saved period audio to {full_path_name}, period: {period}, interval {interval} seconds")

        # wait PERIOD seconds to accumulate audio
        t = interval
        while t > 0:
            time.sleep(1)
            t -= 1
            if stop_recording_event.is_set():
                return

#
# event recording functions
#

def get_event(audio_data):
    global monitor_channel
    ##print("monitoring channel:", monitor_channel)
    if monitor_channel <= DEVICE_CHANNELS:
        audio_level = np.max(np.abs(audio_data[:,monitor_channel]))
    else: # all channels
        audio_level = np.max(np.abs(audio_data))

    return audio_level


def check_event(indata, index):
    global event_start_index, detected_level, buffer

    audio_level = get_level(indata, monitor_channel)

    if (audio_level > EVENT_THRESHOLD) and event_start_index is None:
        print("event detected at:", datetime.datetime.now(), "audio level:", audio_level)
        detected_level = audio_level
        event_start_index = index
        event_worker_thread(detected_level, event_start_index)


def event_worker_thread(detected_level, event_start_index):
    global buffer, buffer_size, _subtype    

    if event_start_index is None:
        return
        
    t = SAVE_AFTER_EVENT        # seconds of audio to save after an event is detected
    while t > 0:
        time.sleep(1)
        t -= 1
        if stop_event_event.is_set():   # is the program trying to shutdown?
            return
        
    save_start_index = (event_start_index - SAVE_BEFORE_EVENT * SAMPLE_RATE) % buffer_size
    save_end_index = (event_start_index + SAVE_AFTER_EVENT * SAMPLE_RATE) % buffer_size

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    output_filename = f"{timestamp}_event_{detected_level}_{SAVE_BEFORE_EVENT}_{SAVE_AFTER_EVENT}_{LOCATION_ID}_{HIVE_ID}.{FILE_FORMAT.lower()}"
    full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FILE_FORMAT, subtype=_subtype)

    print(f"Saved evemt audio to {full_path_name}, audio threshold level: {detected_level}, duration: {audio_data.shape[0] / SAMPLE_RATE} seconds")

    event_start_index = None

#
# audio stream and callback functions
#

if False: #continuous_save_thread is None:
    continuous_save_thread = threading.Thread(target=check_continuous)
    continuous_save_thread.start()

if True: #period_worker_thread is None:
    print("starting period_worker_thread")
    period_WT = threading.Thread(target=recording_worker_thread, args=PERIOD_RECORD, PERIOD_INTERVAL,, thread_id, downsample=False ).start()

if False: # event_save_thread is None:
    event_save_thread = threading.Thread(target=event_worker_thread)
    event_save_thread.start()


#
# #############################################################
# audio stream & callback functions
# ############################################################
#

# audio buffers and variables
buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
buffer = np.zeros((buffer_size, DEVICE_CHANNELS), dtype=_dtype)
buffer_index = 0
buffer_wrap = False
blocksize = 8196
buffer_wrap_event = threading.Event()

# Audio queue
audio_queue = queue.Queue()
index_queue = queue.Queue()


def callback(indata, frames, time, status):
    global buffer, buffer_index, current_time
    ##print("callback", indata.shape, frames, time, status)
    if status:
        print("Callback status:", status)

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

    # Cast to int16 for 16-bit audio
    ##audio_queue.put(indata.astype(np.int16).copy())
    index_queue.put(buffer_index.copy())

    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global stop_program

    stream = sd.InputStream(device=DEVICE_IN, channels=DEVICE_CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, blocksize=blocksize, callback=callback)

    with stream:
        print("Start audio_stream...")

        while stream.active and not stop_program[0]:
            pass
        
        stop_all()
        stream.stop()
        print("Stopped audio_stream...")


# #############################################################
# shutdown functions
# ############################################################


def list_all_threads():
    for thread in threading.enumerate():
        print(f"Thread name: {thread.name}, Thread ID: {thread.ident}, Alive: {thread.is_alive()}")


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

###########################
########## MAIN ###########
###########################

def main():
    global time_of_day_thread, one_shot_fft_proc, fft_periodic_plot_proc, intercom_proc, oscope_proc, stop_tod_event 
    global stop_intercom_event, monitor_channel, current_time, timestamp

    print("Acoustic Signal Capture\n")
    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/1000000:.2f} megabytes")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FILE_FORMAT}; Channels: {DEVICE_CHANNELS}")

    def get_time_of_day():
        global current_time, timestamp
        # this thread just keeps track of the time of day every second
        while not stop_tod_event.is_set():
            current_time = datetime.datetime.now().time()
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            time.sleep(1)
            
    # Create and start the thread for time of day
    time_of_day_thread = threading.Thread(target=get_time_of_day)
    time_of_day_thread.daemon = True 
    time_of_day_thread.start()

        # Create and start the process, note: using mp because matplotlib wants in be in the mainprocess threqad
    if MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")

    def trigger_fft():
        one_shot_fft_proc = multiprocessing.Process(target=plot_fft)
        one_shot_fft_proc.start()
        input()
        # fft one shot returns here when plot window is closed by user
        one_shot_fft_proc.terminate()
        one_shot_fft_proc.join()
        print("exit fft")

    def trigger_oscope():
        oscope_proc = multiprocessing.Process(target=plot_oscope)
        oscope_proc.start()
        input()
        # oscope returns here when plot window is closed by user
        oscope_proc.terminate()
        oscope_proc.join()
        print("exit oscope")

    # Function to switch the channel being listened to
    def switch_channel(channel):
        global monitor_channel

        print(f" switching to channel: {channel}", end='\r')
        monitor_channel = channel

    try:
        if KB_or_CP == 'KB':

            # Set up hotkeys for switching channels
            for i in range(DEVICE_CHANNELS):
                keyboard.add_hotkey(str(i), lambda channel=i: switch_channel(channel))

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

        # Start the audio stream
        audio_stream()

        if KB_or_CP == "KB":
            # Unhook all hooks
            keyboard.unhook_all()

        print("\nHopefully we have turned off all the lights...")
            
    except KeyboardInterrupt: # ctrl-c in windows
        print('\nRecording process stopped by user.')
        stop_all()

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1) 


if __name__ == "__main__":
    main()


'''
        # process info
        if MODE_CONTINUOUS:
            print(f"Starting continuous, low-sample-rate recording mode, duration per file: {CONTINUOUS_DURATION/60:.2f} minutes")
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
            print(f"Starting event detect mode, threshold trigger: {EVENT_THRESHOLD}, time before: {SAVE_BEFORE_EVENT} sec, time after: {SAVE_AFTER_EVENT} sec")
            if EVENT_TIMER:
                print(f"    Operational between: {EVENT_START} and {EVENT_END}")
            else:
                print("    Timer off")
'''                