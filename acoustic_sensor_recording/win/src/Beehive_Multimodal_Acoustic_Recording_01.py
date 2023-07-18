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
import numpy as np
from datetime import datetime
import os
import threading
import time

THRESHOLD = 8000            # audio level threshold to be considered an event
BUFFER_SECONDS = 600        # seconds of a circular buffer
SAMPLE_RATE = 44100         # Audio sample rate
DEVICE_IN = 1               # Device ID of input device
DEVICE_OUT = 3              # Device ID of output device
BIT_DEPTH = 16              # Audio bit depth
CHANNELS = 2                # Number of channels
OUTPUT_DIRECTORY = "."      # for debugging
##OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
FORMAT = 'FLAC'  # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

#continuous recording
DURATION = 10               # seconds of recording
INTERVAL = 10               # seconds between recordings

# event recording
SAVE_DURATION_BEFORE = 10   # seconds to save before the event
SAVE_DURATION_AFTER = 10    # seconds to save after the event

# init event variables
event_start_index = None
save_thread = None
detected_level = None
buffer_index = 0
buffer = None
dtype = None

# Op Mode & ID =====================================================================================
#MODE = "cont"              # "continuous" or "event"
MODE = "event"              # "continuous" or "event"
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"
# ==================================================================================================

### startup housekeeping ###
def initialization():
    global buffer, buffer_index, dtype, buffer_size

    # Check on parms
    if (SAVE_DURATION_BEFORE + SAVE_DURATION_AFTER) * 1.2 > BUFFER_SECONDS:
        print("The buffer is not large enough to hold the maximum amount of audio that can be saved.")
        print("Reduce SAVE_DURATION_BEFORE and/or SAVE_DURATION_AFTER or increase the size of the circular buffer 'BUFFER_SECONDS'")
        quit(-1)

    # Check on input device parms or if input device even exits
    try:
        device_info = sd.query_devices(DEVICE_IN)  
        device_CH = device_info['max_input_channels'] 
        if device_CH < CHANNELS:
            print(f"The device only has {device_CH} channel(s) but require {CHANNELS} channels.")
            quit(-1)
        device_SR = device_info['default_samplerate'] 
        if device_SR != SAMPLE_RATE:
            print(f"The device sample rate {device_SR} is not equal to the required 'SAMPLE_RATE' of {SAMPLE_RATE}")
            quit(-1)
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
        dtype = 'int16'
    elif BIT_DEPTH == 24:
        dtype = 'int24'
    elif BIT_DEPTH == 32:
        dtype = 'int32' 
    else:
        print("The bit depth is not supported: ", BIT_DEPTH)
        quit(-1)

    # prep buffers and variables
    buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
    buffer = np.zeros((buffer_size, CHANNELS), dtype=dtype)


def fake_vu_meter(value):
    # Normalize the value to the range 0-20
    normalized_value = int(value / 1000)
    # Create a string of asterisks corresponding to the normalized value
    asterisks = '*' * normalized_value
    # Print the string of asterisks, ending with a carriage return to overwrite the line
    print(asterisks.ljust(20, ' '), end='\r')

def print_threshold():
    normalized_value = int(THRESHOLD / 1000)
    asterisks = '*' * normalized_value
    print(asterisks.ljust(20, ' '))
#
# event recording functions
#
def save_audio_after_delay():
    global event_start_index
    time.sleep(SAVE_DURATION_AFTER)
    save_audio()


def save_audio():
    global buffer, event_start_index, save_thread, detected_level

    if event_start_index is None:  # if this has been reset already, don't try to save
        return
    save_start_index = (event_start_index - SAVE_DURATION_BEFORE * SAMPLE_RATE) % buffer_size
    save_end_index = (event_start_index + SAVE_DURATION_AFTER * SAMPLE_RATE) % buffer_size

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:
        data = buffer[save_start_index:save_end_index]
    else:
        data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = os.path.join(OUTPUT_DIRECTORY, f"recording_{timestamp}.flac")
    sf.write(filename, data, SAMPLE_RATE, format=FORMAT, subtype=dtype)
    print(f"Saved audio to {filename}, audio threshold level: {detected_level}, duration: {data.shape[0] / SAMPLE_RATE} seconds")

    save_thread = None
    event_start_index = None


def check_level(data, index):
    global event_start_index, save_thread, detected_level

    level = np.max(np.abs(data))
    if (level > THRESHOLD) and event_start_index is None:
        detected_level = level
        event_start_index = index
        save_thread = threading.Thread(target=save_audio_after_delay)
        save_thread.start()
    fake_vu_meter(level)


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

    check_level(indata, buffer_index)
    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global buffer, buffer_index, save_thread

    stream = sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype=dtype, callback=callback)
    with stream:
        print("Start recording...")
        print_threshold()
        while stream.active:
            pass
#
# continuous recording functions #
#
def duration_based_recording(output_filename, duration=DURATION, interval=INTERVAL, device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, subtype=dtype):
    try:
        print("* Recording for:",duration," waiting for:", interval)
        recording = sd.rec(int(duration * rate), samplerate=rate, channels=channels, device=device, dtype='int16')
        for _ in range(int(duration * 100)):  # Check every 1/100th of a second
            sd.sleep(10)
            if sd.get_status().input_overflow:
                print('Input overflow detected while recording audio.')
        print("* Finished recording at:      ", datetime.now())
        output_path = os.path.join(OUTPUT_DIRECTORY, output_filename)
        sf.write(output_path, recording, SAMPLE_RATE, format=FORMAT, subtype=dtype)
        print("* Finished saving:", DURATION, "sec at:", datetime.now())
    except KeyboardInterrupt:
        print('Recording interrupted by user.')


def continuous_recording():
    while True:
        now = datetime.now()                        # get current date and time
        timestamp = now.strftime("%Y%m%d-%H%M%S")   # convert to string and format for filename
        print("recording from:", timestamp)
        filename = f"{timestamp}_{MODE}_{DURATION}_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}" 
        duration_based_recording(filename)
        print("time sleeping: ", INTERVAL)
        time.sleep(INTERVAL)
        ##play_audio(filename, DEVICE_OUT)  # debugging

# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()


if __name__ == "__main__":

    initialization()
    
    try:
        if MODE == 'cont':
            print("Starting audio stream in continuous recording mode")
            continuous_recording()
        elif MODE == 'event':
            print("Starting audio stream in event detect mode")
            audio_stream()
        else:
            print("MODE not recognized")
            quit(-1)
    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')
    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1)         

    print("* Finished playback")
