#!/usr/bin/env python3
# using sounddevice and soundfile to record and save flac files

import sounddevice as sd
import numpy as np
import os
import soundfile as sf
from datetime import datetime
import time
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

class EventRecorder:
    def __init__(self, device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, duration=TIME_BEFORE + TIME_AFTER):
        self.device = device
        self.rate = rate
        self.channels = channels
        self.duration = duration
        self.buffer = deque(maxlen=int((TIME_BEFORE + TIME_AFTER) * rate))  # A rolling buffer for the past 'duration' seconds
        self.threshold = 10**(EVENT_TRIGGER/20)  # Convert dBFS to linear scale
        self.triggered = False
        self.time_of_trigger = None
        self.stream = sd.InputStream(device=self.device, channels=self.channels, samplerate=self.rate, callback=self.callback)

    def callback(self, indata, frames, time_info, status):
        self.buffer.extend(indata[:, :self.channels])  # store the incoming data into the buffer
        if status.input_overflow:
            print('Input overflow detected while monitoring audio.')
        volume_norm = np.linalg.norm(indata) * 10

        if volume_norm > self.threshold:
            self.triggered = True  # Set the trigger if the volume is above the threshold
            print('Event detected above threshold', volume_norm, self.threshold, 'at:', datetime.now())

    def start_recording(self):
        print('* Monitoring for events...')
        debounce = False
        self.stream.start()
        try:
            while True:
                time.sleep(0.1)  # Sleep a bit to reduce CPU usage
                if self.triggered:
                    if debounce == False:
                        self.time_of_trigger = time.time()
                        print('datetime of trigger:', self.time_of_trigger)
                        debounce = True
                        print('Event detected, writing to file BEFORE...')
                        output_filename_before = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{'EVENT_BEFORE'}_{LOCATION_ID}.{FORMAT.lower()}"
                        output_path_before = os.path.join(OUTPUT_DIRECTORY, output_filename_before).replace("\\", "/")  # Replacing "\\" with "/"
                        sf.write(output_path_before, np.array(list(self.buffer)), self.rate, format=FORMAT, subtype=BIT_DEPTH_IN)
                        print('* Finished saving BEFORE')
                    if self.time_of_trigger < (time.time() - TIME_AFTER):
                        self.triggered = False  # Reset the trigger
                        debounce = False
                        print('Event detected, writing to file AFTER...')
                        output_filename_after = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{'EVENT_AFTER'}_{LOCATION_ID}.{FORMAT.lower()}"
                        output_path_after = os.path.join(OUTPUT_DIRECTORY, output_filename_after).replace("\\", "/")  # Replacing "\\" with "/"
                        sf.write(output_path_after, np.array(list(self.buffer)), self.rate, format=FORMAT, subtype=BIT_DEPTH_IN)
                        print('* Finished saving AFTER')

        except KeyboardInterrupt:
            print('Monitoring process stopped by user.')
        except Exception as e:
            print(f"An error occurred while attempting to record audio: {e}")
            quit(-1)
        finally:
            self.stream.stop()
            self.stream.close()

if __name__ == "__main__":
    initialization()
    try:
        if MODE == 'continuous':
            continuous_recording()
        elif MODE == 'event':
            recorder = EventRecorder()
            recorder.start_recording()
        else:
            print("MODE not recognized")
            quit(-1)
    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')
