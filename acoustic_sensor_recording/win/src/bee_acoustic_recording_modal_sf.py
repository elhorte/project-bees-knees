#!/usr/bin/env python3
# using sounddevice and soundfile to record and save flac files
import sounddevice as sd
import numpy as np
import os
import soundfile as sf
from datetime import datetime
import time

OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"

DEVICE_IN = 1
DEVICE_OUT = 3

CHANNELS = 2
SAMPLE_RATE = 192000
BIT_DEPTH_IN = 'PCM_16'
BIT_DEPTH_OUT = 16
FORMAT = 'FLAC'  # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

DURATION = 600   # seconds
INTERVAL = 0 # seconds between recordings
EVENT_TRIGGER = -20 # dBFS threshold for recording
TIME_BEFORE = 5 # seconds before event trigger to record
TIME_AFTER = 5 # seconds after event trigger to record

MODE = "continuous" # "continuous" or "event"

LOCATION_ID = "Zeev-Berkeley"

def record_audio(output_filename, duration=DURATION, interval=INTERVAL, device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, subtype='PCM_16'):
    try:
        print("* Recording")
        # Check if the device is mono
        device_info = sd.query_devices(device)
        if device_info['max_input_channels'] == 1:
            channels = 1  # Set to mono if the device only supports 1 channel
        recording = sd.rec(int(duration * rate), samplerate=rate, channels=channels, device=device, dtype='int16')
        sd.wait()
        print("* Finished recording at:      ", datetime.now())
        output_path = os.path.join(OUTPUT_DIRECTORY, output_filename)
        sf.write(output_path, recording, rate, format=FORMAT, subtype=subtype)
        print("* Finished saving:", DURATION, "sec at:", datetime.now())
    except Exception as e:
        print(f"An error occurred while attempting to record audio: {e}")
        print("These are the available devices: \n", sd.query_devices())
        quit(-1)

def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()
    print("* Finished playback")

def main():
    # Create the output directory if it doesn't exist
    try:
        os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    except Exception as e:    
        print(f"An error occurred while trying to make/find output directory: {e}")
        quit(-1)

    # exit loop with ctrl+c
    while True:
        now = datetime.now()                        # get current date and time
        timestamp = now.strftime("%Y%m%d-%H%M%S")   # convert to string and format for filename
        print("recording from:", timestamp)

        filename = f"{timestamp}_{DURATION}_{INTERVAL}_{LOCATION_ID}.{FORMAT.lower()}" 

        if MODE == "continuous":
            record_audio(filename)
            print("time sleeping: ", INTERVAL)
            time.sleep(INTERVAL)
        elif MODE == "event":
            pass
        else:
            print("MODE not recognized")
            quit(-1)

        ##play_audio(filename, DEVICE_OUT)  # debugging

if __name__ == "__main__":
    main()