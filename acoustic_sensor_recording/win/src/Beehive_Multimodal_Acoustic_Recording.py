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
from datetime import datetime
import time
import os
import io
import threading
##import subprocess32 as subprocess
import numpy as np
#from scipy.io import wavfile
#from scipy.io.wavfile import read as wavread
#import resampy
from scipy.signal import resample_poly
##from pydub import AudioSegment


THRESHOLD = 27000            # audio level threshold to be considered an event
BUFFER_SECONDS = 400        # seconds of a circular buffer
SAMPLE_RATE = 192000         # Audio sample rate
DEVICE_IN = 1               # Device ID of input device
DEVICE_OUT = 3              # Device ID of output device
BIT_DEPTH = 16              # Audio bit depth
CHANNELS = 2                # Number of channels
##OUTPUT_DIRECTORY = "."      # for debugging
OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
FORMAT = 'FLAC'             # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

#periodic recording
PERIOD = 60                 # seconds of recording
INTERVAL = 300              # seconds between start of period, must be > period, of course

# init periodic varibles
period_start_index = None
period_save_thread = None

# event recording
SAVE_BEFORE_EVENT = 30   # seconds to save before the event
SAVE_AFTER_EVENT = 30    # seconds to save after the event

# init event variables
event_start_index = None
event_save_thread = None
detected_level = None

_dtype = None
_subtype = None


# Op Mode & ID =====================================================================================
#MODE = "orig_period"       # keeping it around for debugging
#MODE = "period"            # period only
#MODE = "event"             # event only
MODE = "combo"             # period recording with event detection
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"
# ==================================================================================================

### startup housekeeping ###
def initialization():
    global buffer, buffer_index, _dtype, buffer_size, _subtype

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
        if device_CH < CHANNELS:
            print(f"The device only has {device_CH} channel(s) but require {CHANNELS} channels.")
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

    # audio buffers and variables
    buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
    buffer = np.zeros((buffer_size, CHANNELS), dtype=_dtype)
    buffer_index = 0


# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
def fake_vu_meter(value, end):
    normalized_value = int(value / 1000)
    asterisks = '*' * normalized_value
    print(asterisks.ljust(50, ' '), end=end)
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

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}_period_{PERIOD}_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved period audio to {full_path_name}, period: {PERIOD}, interval {INTERVAL} seconds")

    period_save_thread = None
    period_start_index = None


def check_period(audio_data, index):
    global period_start_index, period_save_thread, detected_level

    audio_level = np.max(np.abs(audio_data))
    # if modulo INTERVAL == zero then start of period
    if not int(time.time()) % INTERVAL and period_start_index is None: 
        print("period started at:", datetime.now(), "audio level:", audio_level)
        period_start_index = index 
        period_save_thread = threading.Thread(target=save_audio_for_period)
        period_save_thread.start()
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

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    threshold_tag = int(THRESHOLD/1000)
    output_filename = f"{timestamp}_event_{detected_level}_{SAVE_BEFORE_EVENT}_{SAVE_AFTER_EVENT}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved evemt audio to {full_path_name}, audio threshold level: {detected_level}, duration: {audio_data.shape[0] / SAMPLE_RATE} seconds")

    event_save_thread = None
    event_start_index = None


def check_level(audio_data, index):
    global event_start_index, event_save_thread, detected_level

    audio_level = np.max(np.abs(audio_data))
    if (audio_level > THRESHOLD) and event_start_index is None:
        print("event detected at:", datetime.now(), "audio level:", audio_level)
        detected_level = audio_level
        event_start_index = index
        event_save_thread = threading.Thread(target=save_audio_around_event)
        event_save_thread.start()

    fake_vu_meter(audio_level,'\r')
#
# audio stream callback function
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

    if MODE == "event" or MODE == "combo":
        check_level(indata, buffer_index)   # trigger saving audio if above threshold

    if MODE == "period" or MODE == "combo":
        check_period(indata, buffer_index)  # start saving audio if save period expired

    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global buffer, buffer_index, _dtype

    stream = sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, callback=callback)
    with stream:
        print("Start recording...")
        fake_vu_meter(THRESHOLD, '\n')  # mark audio threshold on the CLI for ref
        while stream.active:
            pass

#
# period recording functions #
#
def period_recording(output_filename, period=PERIOD, interval=INTERVAL, device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, subtype=_subtype, dtype=_dtype):
    try:
        print("* Recording for:",period," waiting for:", interval)
        audio_data = sd.rec(int(period * rate), samplerate=rate, channels=channels, device=device, dtype=dtype)
        for _ in range(int(period * 100)):  # Check every 1/100th of a second
            sd.sleep(10)
            if sd.get_status().input_overflow:
                print('Input overflow detected while recording audio.')
        print("* Finished recording at:      ", datetime.now())

        full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
        sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=subtype)
        print("* Finished saving:", PERIOD, "sec at:", datetime.now())

    except KeyboardInterrupt:
        print('Recording interrupted by user.')


def period_segment_recording():
    while True:
        now = datetime.now()                        # get current date and time
        timestamp = now.strftime("%Y%m%d-%H%M%S")   # convert to string and format for filename
        print("recording from:", timestamp)
        filename = f"{timestamp}_orig-period_{PERIOD}_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}" 
        period_recording(filename)
        print("time sleeping: ", INTERVAL)
        time.sleep(INTERVAL)
        ##play_audio(filename, DEVICE_OUT)  # debugging

###########################
########## MAIN ###########
###########################

if __name__ == "__main__":

    initialization()
    print("Acoustic Signal Capture")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FORMAT}; Channels: {CHANNELS}")
    try:
        if MODE == 'orig_period':
            print("Starting audio stream in original period-only recording mode")
            period_segment_recording()
        elif MODE == 'period':
            print("Starting audio stream in period-only mode")
            audio_stream()
        elif MODE == 'event':
            print("Starting audio stream in event detect-only mode")
            audio_stream()
        elif MODE == 'combo':
            print("Starting audio capture in periodic mode w/event capture")
            audio_stream()
        else:
            print("MODE not recognized")
            quit(-1)
    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')
    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1)         # quit with error



##########################  
# utilities
##########################

# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()
#
# audio sample rate conversion routines
#
