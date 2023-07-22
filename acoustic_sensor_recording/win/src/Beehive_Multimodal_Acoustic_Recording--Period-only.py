#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 

# Using sounddevice and soundfile libraries, record audio from a device ID and save it to a FLAC file.
# Input audio from a device ID at a defineable sample rate, bit depth, and channel count. 
# Write incoming audio into a circular buffer that is of a definable length. 
# Start a recoding period at a defineable interval
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
import numpy as np

THRESHOLD = 27000            # audio level threshold to be considered an event
BUFFER_SECONDS = 400        # seconds of a circular buffer
SAMPLE_RATE = 192000         # Audio sample rate
DEVICE_IN = 1               # Device ID of input device
DEVICE_OUT = 3              # Device ID of output device
BIT_DEPTH = 16              # Audio bit depth
CHANNELS = 2                # Number of channels
OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
FORMAT = 'FLAC'             # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

#periodic recording
PERIOD = 60                 # seconds of recording
INTERVAL = 300              # seconds between start of period, must be > period, of course

_dtype = None
_subtype = None


# Op Mode & ID =====================================================================================
MODE = "period"            # period only
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
    # sleep for the period while recording into circular buffer
    time.sleep(PERIOD)
    save_period_audio() # now save the audio


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

# this is called from the callback function everytime a new sample arrives
def check_period(audio_data, index):
    global period_start_index, period_save_thread, detected_level
    # check for start of INTERVAL which is the modulo in seconds of wall time
    if not int(time.time()) % INTERVAL and period_start_index is None: 
        print("period started at:", datetime.now())
        period_start_index = index 
        period_save_thread = threading.Thread(target=save_audio_for_period)
        period_save_thread.start()
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

    check_period(indata, buffer_index)  
    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global buffer, buffer_index, _dtype

    stream = sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, callback=callback)
    with stream:
        print("Start recording...")
        while stream.active:
            pass

###########################
########## MAIN ###########
###########################

if __name__ == "__main__":

    initialization()
    print("Acoustic Signal Capture")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FORMAT}; Channels: {CHANNELS}")
    try:
        if MODE == 'period':
            print("Starting audio stream in period-only mode")
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

