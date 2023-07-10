#!/usr/bin/env python3

import pyaudio
import wave
import threading
import time
import os
from datetime import datetime

CHUNK_SIZE = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 192000
RECORD_DURATION = 30  # seconds
INPUT_DEVICE_INDEX = 7  # Set the USB audio source index here

class AudioRecorder:
    def __init__(self, output_directory):
        self.output_directory = output_directory
        self.current_file = None
        self.should_stop = False
        self.frames = []

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  input_device_index=INPUT_DEVICE_INDEX,  # Set the USB audio source index here
                                  frames_per_buffer=CHUNK_SIZE)

    def record_audio(self):
        while not self.should_stop:
            data = self.stream.read(CHUNK_SIZE)
            self.frames.append(data)

    def save_audio(self):
        while not self.should_stop:
            if len(self.frames) >= RATE * RECORD_DURATION:
                current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                output_file = f"{self.output_directory}/audio_{current_time}.wav"

                wf = wave.open(output_file, "wb")
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b"".join(self.frames[:RATE * RECORD_DURATION]))
                wf.close()

                self.frames = self.frames[RATE * RECORD_DURATION:]
                print("Recording saved to:", output_file)

            time.sleep(1)

    def start_recording(self):
        record_thread = threading.Thread(target=self.record_audio)
        save_thread = threading.Thread(target=self.save_audio)

        record_thread.start()
        save_thread.start()

        record_thread.join()
        save_thread.join()

    def stop_recording(self):
        self.should_stop = True

        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

# Set the output directory where the recordings will be saved
OUTPUT_DIRECTORY = "./recordings"
# Create the output directory if it doesn't exist
os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

# Create an instance of AudioRecorder
recorder = AudioRecorder(OUTPUT_DIRECTORY)

# Start the recording thread
recording_thread = threading.Thread(target=recorder.start_recording)
recording_thread.start()

# Wait for user input to stop the recording
input("Press Enter to stop recording...")

# Stop the recording thread
recorder.stop_recording()
recording_thread.join()
