#!/usr/bin/env python3
# using sounddevice and soundfile to record and save flac files

import sounddevice as sd
import numpy as np
import os
import soundfile as sf
from datetime import datetime
import time
from collections import deque

OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"

DEVICE_IN = 1   # 1 is the microphone
DEVICE_OUT = 3  # 3 is the speakers

CHANNELS = 2
SAMPLE_RATE = 192000
BIT_DEPTH_IN = 'PCM_16'
BIT_DEPTH_OUT = 16
FORMAT = 'FLAC'  # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

DURATION = 30       # seconds
INTERVAL = 10       # seconds between recordings
EVENT_TRIGGER = 10 # dBFS threshold for recording
TIME_BEFORE = 5     # seconds before event trigger to record
TIME_AFTER = 5      # seconds after event trigger to record
threshold = 0       # linear scale calculated from EVENT_TRIGGER
vol_counter = 0         # number of times around the loop

MODE = "continuous" # "continuous" or "event"
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

def duration_based_recording(output_filename, duration=DURATION, interval=INTERVAL, device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, subtype='PCM_16'):
    try:
        print("* Recording")
        recording = sd.rec(int(duration * rate), samplerate=rate, channels=channels, device=device, dtype='int16')
        for _ in range(int(duration * 100)):  # Check every 1/100th of a second
            sd.sleep(10)
            if sd.get_status().input_overflow:
                print('Input overflow detected while recording audio.')
        print("* Finished recording at:      ", datetime.now())
        output_path = os.path.join(OUTPUT_DIRECTORY, output_filename)
        sf.write(output_path, recording, rate, format=FORMAT, subtype=subtype)
        print("* Finished saving:", DURATION, "sec at:", datetime.now())
    except KeyboardInterrupt:
        print('Recording interrupted by user.')
    except Exception as e:
        print(f"An error occurred while attempting to record audio: {e}")
        print("These are the available devices: \n", sd.query_devices())
        quit(-1)

def event_based_recording(device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, duration=TIME_BEFORE+TIME_AFTER):
    print('* Monitoring for events...')
    buffer = deque(maxlen=int((TIME_BEFORE+TIME_AFTER) * rate))  # A rolling buffer for the past 'duration' seconds
    threshold = 10**(EVENT_TRIGGER/20)  # Convert dBFS to linear scale
    triggered = False
    stream = sd.InputStream(device=device, channels=channels, samplerate=rate, callback=callback)
    stream.start()
    try:
        while True:
            time.sleep(0.1)  # Sleep a bit to reduce CPU usage
            if triggered:
                print('Event detected, writing to file...')
                output_filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{LOCATION_ID}.{FORMAT.lower()}"
                output_path = os.path.join(OUTPUT_DIRECTORY, output_filename)
                sf.write(output_path, np.array(buffer), rate, format=FORMAT, subtype=BIT_DEPTH_IN)
                print('* Finished saving')
                triggered = False  # Reset the trigger
    except KeyboardInterrupt:
        print('Monitoring process stopped by user.')
    except Exception as e:
        print(f"An error occurred while attempting to record audio: {e}")
        print("These are the available devices: \n", sd.query_devices())
        quit(-1)
    finally:
        stream.stop()
        stream.close()

def callback(indata, frames, time, status):
    if status.input_overflow:
        print('Input overflow detected while monitoring audio.')
    volume_norm = np.linalg.norm(indata) * 10
    if vol_counter % 100 == 0:
        print("vol, thresh:", int(volume_norm),":", int(threshold))
    if volume_norm > threshold:
        triggered = True  # Set the trigger if the volume is above the threshold

def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()
    print("* Finished playback")

def continuous_recording():
    while True:
        now = datetime.now()                        # get current date and time
        timestamp = now.strftime("%Y%m%d-%H%M%S")   # convert to string and format for filename
        print("recording from:", timestamp)
        filename = f"{timestamp}_{DURATION}_{INTERVAL}_{LOCATION_ID}.{FORMAT.lower()}" 
        duration_based_recording(filename)
        print("time sleeping: ", INTERVAL)
        time.sleep(INTERVAL)
        ##play_audio(filename, DEVICE_OUT)  # debugging

if __name__ == "__main__":
    initialization()
    try:
        if MODE == 'continuous':
            continuous_recording()
        elif MODE == 'event':
            event_based_recording()
        else:
            print("MODE not recognized")
            quit(-1)
    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')


# ==================================================================================================
