#!/usr/bin/env python3

import pyaudio
import wave
import os
import numpy as np
from datetime import datetime

OUTPUT_DIRECTORY = "./recordings"
DEVICE_IN = 1
DEVICE_OUT = 3

CHANNELS = 2
SAMPLE_RATE = 192000
BIT_DEPTH_IN = pyaudio.paInt16  # Equivalent to 'PCM_16'
BIT_DEPTH_OUT = 16
FORMAT = 'wav'  # 'wav' because pyaudio does not support 'flac'

LOCATION_ID = "Zeev-Berkeley"
DURATION = 10  # seconds

def record_audio(output_filename, duration=DURATION, device=DEVICE_IN, rate=SAMPLE_RATE, channels=CHANNELS, format=BIT_DEPTH_IN):
    try:
        print("* Recording")
        p = pyaudio.PyAudio()
        stream = p.open(format=format, channels=channels, rate=rate, input=True, frames_per_buffer=1024, input_device_index=device)
        frames = []
        for _ in range(0, int(rate / 1024 * duration)):
            data = stream.read(1024)
            frames.append(data)
        print("* Finished recording at:      ", datetime.now())
        output_path = os.path.join(OUTPUT_DIRECTORY, output_filename)
        wf = wave.open(output_path, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        print("* Finished saving:", DURATION, "sec at:", datetime.now())
        stream.stop_stream()
        stream.close()
        p.terminate()
    except Exception as e:
        print(f"An error occurred while recording audio: {e}")
        quit(-1)

def play_audio(filename, device=DEVICE_OUT, format=BIT_DEPTH_OUT):
    print("* Playing back")
    p = pyaudio.PyAudio()
    wf = wave.open(filename, 'rb')
    stream = p.open(format=format, channels=wf.getnchannels(), rate=wf.getframerate(), output=True, output_device_index=device)
    data = wf.readframes(1024)
    while data != b'':
        stream.write(data)
        data = wf.readframes(1024)
    print("* Finished playback")
    stream.stop_stream()
    stream.close()
    p.terminate()

def main():
    try:
        os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    except Exception as e:    
        print(f"An error occurred while trying to make/find output directory: {e}")
        quit(-1)

    while True:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        print("recording from:", timestamp)
        filename = f"{timestamp}_{DURATION}_{LOCATION_ID}.{FORMAT.lower()}"  # Modify filename here
        record_audio(filename)
        ##play_audio(filename)

if __name__ == "__main__":
    main()
