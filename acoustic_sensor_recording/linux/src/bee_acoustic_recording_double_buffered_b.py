#!/usr/bin/env python3

import pyaudio
import wave
import threading
from datetime import datetime

CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
RECORD_DURATION = 300  # 5 minutes
USB_INDEX = 7

class AudioRecorder:
    def __init__(self, output_directory):
        self.output_directory = output_directory
        self.current_file = None
        self.should_stop = False

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=USB_INDEX,  # Set the USB audio source index here
            frames_per_buffer=CHUNK_SIZE)

    def record_audio(self):
        frames = []
        samples = int(RATE / CHUNK_SIZE * RECORD_DURATION)
        c = 0
        for _ in range(0, samples):
            if self.should_stop:
                break
            data = self.stream.read(CHUNK_SIZE)
            frames.append(data)
            c += 1
        print("count: ", c)
        return frames

    def save_audio(self, frames, output_file):
        wf = wave.open(output_file, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wf.close()

    def start_recording(self):
        while not self.should_stop:
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.current_file = f"{self.output_directory}/audio_{current_time}.wav"

            frames = self.record_audio()
            self.save_audio(frames, self.current_file)
            print("Recording saved to:", self.current_file)

    def stop_recording(self):
        self.should_stop = True

        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

# Set the output directory where the recordings will be saved
output_directory = "."

# Create an instance of AudioRecorder
recorder = AudioRecorder(output_directory)

# Start the recording thread
recording_thread = threading.Thread(target=recorder.start_recording)
recording_thread.start()

# Wait for user input to stop the recording
input("Press Enter to stop recording...")

# Stop the recording thread
recorder.stop_recording()
recording_thread.join()
