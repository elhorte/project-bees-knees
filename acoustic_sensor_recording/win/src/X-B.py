#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import queue
import threading
import time
from scipy.signal import resample_poly
import os

# Parameters
sample_rate = 192000
blocksize = 1024  # Number of frames processed at a time
duration_1 = 300  # Duration for the first thread
duration_2 = 100  # Duration for the second thread
wait_2 = 400  # Waiting time for the second thread
downsample_rate = 48000  # Downsample rate for the first thread

# Audio queue
audio_queue = queue.Queue()

# Callback function to feed the queue
def callback(indata, frames, time, status):
    # Cast to int16 for 16-bit audio
    audio_queue.put(indata.astype(np.int16).copy())

# Worker thread function to save audio
def worker(duration, wait, thread_id, downsample=False):
    while True:
        audio_data = []
        for _ in range(int(duration * sample_rate / blocksize)):
            audio_data.extend(audio_queue.get())
        audio_data = np.array(audio_data)

        if downsample:
            # Select the first two channels
            audio_data = audio_data[:, :2]
            # Downsample
            audio_data = resample_poly(audio_data, up=1, down=int(sample_rate / downsample_rate))
            # Save as WAV
            wav_file = f'output_{thread_id}_{int(time.time())}.wav'
            write(wav_file, downsample_rate, audio_data)
            # Convert to MP3 with lame
            os.system(f'lame --quiet -b 192 {wav_file} output_{thread_id}_{int(time.time())}.mp3')
            os.remove(wav_file)  # Remove the temporary WAV file
        else:
            write(f'output_{thread_id}_{int(time.time())}.wav', sample_rate, audio_data)
        if wait > 0:
            time.sleep(wait)

# Start recording
with sd.InputStream(callback=callback, channels=4, samplerate=sample_rate, blocksize=blocksize):
    # Worker threads
    threading.Thread(target=worker, args=(duration_1, 0, 1, True)).start()  # The first thread downsamples and saves as MP3
    threading.Thread(target=worker, args=(duration_2, wait_2 - duration_2, 2)).start()
