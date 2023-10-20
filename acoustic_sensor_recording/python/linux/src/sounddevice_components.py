#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sounddevice as sd
import numpy as np

DEVICE_IN = 'device_in'    # Replace with your device id or name
CHANNELS = 2              # Number of channels
SAMPLE_RATE = 44100       # Sample rate
DTYPE = 'float32'         # Data type

# Buffer to store the channel data
left_channel_data = []

def callback(indata, frames, time, status):
    global left_channel_data
    # `indata` is a numpy array containing the input data.
    # If your stream has two channels, `indata` has shape (frames, 2).
    # You can simply index into this array to get one channel:
    left_channel = indata[:, 0]
    # Now, save this to your other variable:
    left_channel_data.append(left_channel)

with sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype=DTYPE, callback=callback):
    print("Recording started...")
    sd.sleep(5000)  # Record audio for 5 seconds
    print("Recording finished.")

# Convert the list of arrays to a single numpy array for further processing
left_channel_data = np.concatenate(left_channel_data)
