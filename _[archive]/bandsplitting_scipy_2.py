#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import wave
from scipy.signal import butter, filtfilt
import os

##file_name = "input.wav"
os.chdir(r'E:\git\en\project-bees-knees\beehub\python\src')

def read_wav(filename):
    with wave.open(filename, 'rb') as wav_file:
        nchannels, sampwidth, framerate, nframes, comptype, compname = wav_file.getparams()
        frames = wav_file.readframes(nframes * nchannels)
        out = np.frombuffer(frames, dtype=np.int16)
        out = out.reshape(-1, nchannels)
    return out, framerate

def write_wav(filename, data, framerate, nchannels=1, sampwidth=2):
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(nchannels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(framerate)
        wav_file.writeframes(data.tobytes())

def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low')
    return b, a

def butter_highpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high')
    return b, a

def butter_filter(data, cutoff, fs, order=5, filter_type='low'):
    if filter_type == 'low':
        b, a = butter_lowpass(cutoff, fs, order=order)
    else:
        b, a = butter_highpass(cutoff, fs, order=order)
    y = filtfilt(b, a, data)
    return y

def split_band_filter(input_file, output_file_low, output_file_high, cutoff_freq, framerate):
    data, rate = read_wav(input_file)

    # Apply a low-pass filter for the below 20kHz band
    low_passed = butter_filter(data, cutoff_freq, rate, order=6, filter_type='low')

    # Apply a high-pass filter for the above 20kHz band
    high_passed = butter_filter(data, cutoff_freq, rate, order=6, filter_type='high')

    # Write the output files
    write_wav(output_file_low, low_passed.astype(np.int16), rate)
    write_wav(output_file_high, high_passed.astype(np.int16), rate)

# Example usage
#input_wav='E:/git/en/project-bees-knees/beehub/python/src/input.wav'
split_band_filter('input.wav', 'output_below_20kHz.wav', 'output_above_20kHz.wav', 20000, 192000)
