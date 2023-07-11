#!/usr/bin/env python3
# using sounddevice and soundfile to record and save flac files

import sounddevice as sd
import numpy as np
import os
import soundfile as sf
from datetime import datetime
import time
from collections import deque
import scipy.io.wavfile as wav
from collections import deque
from time import sleep
from collections import deque

# Parameters
OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
DEVICE_IN = 1           # OS specific device ID
DEVICE_OUT = 3
CHANNELS = 2            # currently max = 2
SAMPLE_RATE = 44100
BIT_DEPTH_IN = 'PCM_16'
BIT_DEPTH_OUT = 16
FORMAT = 'FLAC'
DURATION = 30           # seconds for continuous recording
INTERVAL = 10           # seconds between recordings
EVENT_TRIGGER = 40      # dBFS threshold for triggering event recording
TIME_BEFORE = 5         # seconds before event trigger to record
TIME_AFTER = 5          # seconds after event trigger to record
MODE = "event"
LOCATION_ID = "Zeev-Berkeley"

def initialization():
    device_info = sd.query_devices(DEVICE_IN)      # Check if the device is mono
    if device_info['max_input_channels'] == 1:
        CHANNELS = 1  
    # Create the output directory if it doesn't exist
    try:
        os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    except Exception as e:    
        print(f"An error occurred while trying to make/find output directory: {e}")
        quit(-1)


# Configure your settings here
FS = 44100  # Sample rate
SECONDS_BEFORE_EVENT = 10  # Number of seconds before the event to save
SECONDS_AFTER_EVENT = 10  # Number of seconds after the event to save
CHANNELS = 2  # Number of channels (2 for stereo)
THRESHOLD = 8  # Audio threshold. Adjust as needed.

# This buffer will hold the last SECONDS_BEFORE_EVENT of audio
buffer = deque(maxlen=FS * SECONDS_BEFORE_EVENT * CHANNELS)
record_buffer = deque(maxlen=FS * SECONDS_AFTER_EVENT * CHANNELS)

# Flags to control the recording state
is_recording = False
start_time = None

def audio_callback(indata, frames, time_info, status):
    global is_recording
    global start_time
    volume_norm = np.linalg.norm(indata) * 10

    if volume_norm > THRESHOLD and not is_recording:
        print('Threshold exceeded, recording...', int(volume_norm))
        is_recording = True
        start_time = time.time()

    if is_recording:
        record_buffer.extend(indata.flatten())
        if (time.time() - start_time) > SECONDS_AFTER_EVENT:
            is_recording = False
            print('Finished recording')

            # Save the audio to a file
            filename = "event.wav"
            complete_buffer = np.array(list(buffer) + list(record_buffer)).reshape((-1, CHANNELS))
            wav.write(filename, FS, complete_buffer)
            # Clear the buffers for the next recording
            buffer.clear()
            record_buffer.clear()
            print('Finished writing to file')
            
    # Only record into the buffer if not currently recording
    if not is_recording:
        buffer.extend(indata.flatten())

# Create a stream and start recording
stream = sd.InputStream(callback=audio_callback, channels=CHANNELS, samplerate=FS)
with stream:
    while True:
        # Keep the script running
        time.sleep(1)
