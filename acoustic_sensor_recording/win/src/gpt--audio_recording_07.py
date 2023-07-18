#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 

# Using sounddevice and soundfile libraries, record audio from a device ID and save it to a FLAC file.
# Input audio from a device ID at a defineable sample rate, bit depth, and channel count. 
# Write incoming audio into a circular buffer that is of a definable length. 
# Monitor the incoming audio for levels above a definable threshold for a defineable duration and set a flag when conditions are met. 
# Note the point in the buffer of the event and then continue to record audio until a definable time period after the start of the event. 
# Note the point in the buffer of the end of the time period after the start of the event.
# Continue recording audio into the circular buffer
# Save to a FLAC file the audio in the circular buffer from the start of a defineable time period before the event to the end of the time period after the event.
# Reset the audio threshold level flag.
# Reset event_start_time back to None after saving audio.


import sounddevice as sd
import soundfile as sf
import numpy as np
import datetime
import os
import threading
import time

THRESHOLD = 8000            # audio level threshold to be considered an event
BUFFER_SECONDS = 600        # seconds of a circular buffer
SAMPLE_RATE = 44100         # Audio sample rate
DEVICE_IN = 1               # Device ID
BIT_DEPTH = 16              # Audio bit depth
CHANNELS = 2                # Number of channels
SAVE_DURATION_BEFORE = 10   # seconds to save before the event
SAVE_DURATION_AFTER = 10    # seconds to save after the event
OUTPUT_DIRECTORY = "."
##OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"

buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
buffer = np.zeros((buffer_size, CHANNELS), dtype=f'int{BIT_DEPTH}')
buffer_index = 0

event_start_index = None
save_thread = None
detected_level = None

### startup housekeeping ###

# Check on parms
if (SAVE_DURATION_BEFORE + SAVE_DURATION_AFTER) * 1.2 > BUFFER_SECONDS:
    print("The buffer is not large enough to hold the maximum amount of audio that can be saved.")
    print("Reduce SAVE_DURATION_BEFORE and/or SAVE_DURATION_AFTER or increase the size of the circular buffer 'BUFFER_SECONDS'")
    quit(-1)

# Check on input device parms or if input device even exits
try:
    device_info = sd.query_devices(DEVICE_IN)  
    device_CH = device_info['max_input_channels'] 
    if device_CH != CHANNELS:
        print("The device does not have the number of channels required by 'CHANNELS': ", device_CH)
        quit(-1)
    device_SR = device_info['default_samplerate'] 
    if device_SR != SAMPLE_RATE:
        print("The device sample rate is not equal to the required 'SAMPLE_RATE': ", device_SR)
        quit(-1)
except Exception as e:
    print(f"An error occurred while attempting to access the input device: {e}")
    print("These are the available devices: \n", sd.query_devices())
    quit(-1)
#print(sd.query_devices())

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

### end housekeeping ###

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

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = os.path.join(OUTPUT_DIRECTORY, f"recording_{timestamp}.flac")
    sf.write(filename, data, SAMPLE_RATE, format='FLAC')

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

    stream = sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype='int16', callback=callback)

    with stream:
        print("Start recording...")
        print_threshold()
        while stream.active:
            pass

if __name__ == '__main__':
    audio_stream()


# ==================================================================================================
# scratch area


