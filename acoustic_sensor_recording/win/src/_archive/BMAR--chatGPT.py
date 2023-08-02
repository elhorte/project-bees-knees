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
period_start_index = None
event_start_index = None
detected_level = None

# threads
period_save_thread = None
event_save_thread = None
time_of_day_thread = None

# event flags
stop_period_event = threading.Event()
stop_event_event = threading.Event()
stop_tod_event = threading.Event()
stop_intercom_event = threading.Event()

trigger_oscope_event = threading.Event()
trigger_fft_event = threading.Event()

# misc globals
_dtype = None                   # parms sd lib cares about
_subtype = None
device_ch = None                # total number of channels from device
CURRENT_TIME = None
TIMESTAMP = None
monitor_channel = 0
stop_program = [False]

# #############################################################
# #### Control Panel ##########################################
# #############################################################

# modes
MODE_PERIOD = False                          # period recording
PERIOD_TIMER = True                         # use a timer to start and stop time of day of period recording
MODE_EVENT = False                           # event recording
EVENT_TIMER = False                         # use a timer to start and stop time of day of event recording
MODE_VU = False                             # show audio level on cli

# hardware pointers
DEVICE_IN = 17                              # Device ID of input device - 16 for 4ch audio I/F
DEVICE_OUT = 14                             # Device ID of output device
DEVICE_CHANNELS = 2                         # Number of channels

FULL_SCALE = 2 ** 16                        # just for cli vu meter level reference
BUFFER_SECONDS = 1000                       # seconds of a circular buffer
SAMPLE_RATE = 192000                         # Audio sample rate
BIT_DEPTH = 16                              # Audio bit depth
FORMAT = "FLAC"                             # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

PERIOD_START = datetime.time(4, 0, 0)
PERIOD_END = datetime.time(20, 0, 0)
PERIOD = 35                                # seconds of recording
INTERVAL = 45                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                      # seconds to save before the event
SAVE_AFTER_EVENT = 30                       # seconds to save after the event
THRESHOLD = 40000                           # audio level threshold to be considered an event
MONITOR_CH = 0                              # channel to monitor for event (if > number of chs, all channels are monitored)


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

def get_time_of_day():
    global CURRENT_TIME, TIMESTAMP
    # this thread just keeps track of the time of day every second
    while not stop_tod_event.is_set():
        CURRENT_TIME = datetime.datetime.now().time()
        TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        time.sleep(1)


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
    print("period t =", t)
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

    output_filename = f"{TIMESTAMP}_period_{SAMPLE_RATE/1000:.0F}_{BIT_DEPTH}_{DEVICE_CHANNELS}_{PERIOD}_every_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)
    with lock:
        sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved period audio to {full_path_name}, period: {PERIOD}, interval {INTERVAL} seconds")
    period_start_index = None


def check_period(audio_data, index):
    global period_start_index, period_save_thread, detected_level

    ##print("Time:", int(time.time()),"INTERVAL:", INTERVAL, "modulo:", int(time.time()) % INTERVAL)
    if not stop_period_event.is_set():
        # if modulo INTERVAL == zero then start of period
        if not int(time.time()) % INTERVAL and period_start_index is None: 
            period_start_index = index 
            save_audio_for_period()
    else:
        print("check_period exited with event flag")

# #######################################
# event recording functions
# #######################################

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

    output_filename = f"{TIMESTAMP}_event_{detected_level}_{SAVE_BEFORE_EVENT}_{SAVE_AFTER_EVENT}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)
    with lock:
        sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved evemt audio to {full_path_name}, audio threshold level: {detected_level}, duration: {audio_data.shape[0] / SAMPLE_RATE} seconds")
    event_start_index = None


def check_level(audio_data, index):
    global event_start_index, event_save_thread, detected_level

    if not stop_event_event.is_set():
        audio_level = get_level(audio_data)
        if (audio_level > THRESHOLD) and event_start_index is None:
            print("event detected at:", CURRENT_TIME, "audio level:", audio_level)
            detected_level = audio_level
            event_start_index = index
            save_audio_for_event()
    else:
        print("check_level exited with event flag")

#
# #############################################################
# audio stream callback functions
# ############################################################
#

def callback(indata, frames, time, status):
    global buffer, buffer_index

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
        if EVENT_TIMER and not (EVENT_START <= CURRENT_TIME <= EVENT_END):
            pass
        else:
            check_level(indata, buffer_index) 

    if MODE_PERIOD:
        if PERIOD_TIMER and not (PERIOD_START <= CURRENT_TIME <= PERIOD_END):
            pass
        else:
            check_period(indata, buffer_index) 

    if MODE_VU:
        audio_level = get_level(indata)
        fake_vu_meter(audio_level,'\r')

    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global buffer, buffer_index
    global fft_periodic_plot_proc, continuous_save_thread, period_save_thread, event_save_thread, intercom_proc

    stream = sd.InputStream(device=DEVICE_IN, channels=DEVICE_CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, callback=callback)
    with stream:
        print("Start audio_stream...")

        # Create and start the thread
        if MODE_PERIOD:
            print(f"Starting periodic recording mode, {PERIOD/60:.2f} minutes every {INTERVAL/60:.2f} minutes")
            if PERIOD_TIMER:
                print(f"    Operational between: {PERIOD_START} and {PERIOD_END}")
            else:
                print("    Timer off")
            period_save_thread = threading.Thread(target=save_audio_for_period)
            period_save_thread.start()

        # Create and start the thread
        if MODE_EVENT:
            print(f"Starting event detect mode, threshold trigger: {THRESHOLD}, time before: {SAVE_BEFORE_EVENT} sec, time after: {SAVE_AFTER_EVENT} sec")
            if EVENT_TIMER:
                print(f"    Operational between: {EVENT_START} and {EVENT_END}")
            else:
                print("    Timer off")
            event_save_thread = threading.Thread(target=save_audio_for_event)
            event_save_thread.start()

        while stream.active and not stop_program[0]:
            pass

        stream.stop()
        print("Stopped audio_stream...")


###########################
########## MAIN ###########
###########################

def main():
    global time_of_day_thread, intercom_proc, stop_tod_event, stop_intercom_event

    print("Acoustic Signal Capture\n")
    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/1000000:.2f} megabytes")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FORMAT}; Channels: {DEVICE_CHANNELS}")

    # Create and start the thread for time of day
    time_of_day_thread = threading.Thread(target=get_time_of_day)
    time_of_day_thread.daemon = True 
    time_of_day_thread.start()

    try:
        audio_stream()

        print("\nHopefully we have turned off all the lights...")

    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1) 


if __name__ == "__main__":
    main()

