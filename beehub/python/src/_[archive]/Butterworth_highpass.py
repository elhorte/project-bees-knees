#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 

import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt
from pydub import AudioSegment
import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt
from pydub import AudioSegment
import os

##file_name = "input.wav"
os.chdir('/Users/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src')

def high_pass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def process_audio(input_file, output_file, cutoff_frequency):
    # Read the FLAC file
    data, fs = sf.read(input_file, dtype='float32')

    # Apply high-pass filter
    filtered_data = high_pass_filter(data, cutoff_frequency, fs)

    # Save the processed audio as WAV
    sf.write(output_file, filtered_data, fs)

# Usage example
input_file = 'input.wav'
output_file = 'output.wav'
cutoff_frequency = 20000  # 20 kHz

process_audio(input_file, output_file, cutoff_frequency)

def high_pass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def process_audio(input_file, output_file, cutoff_frequency):
    # Read the FLAC file
    data, fs = sf.read(input_file, dtype='int16')

    # Apply high-pass filter
    filtered_data = high_pass_filter(data, cutoff_frequency, fs)

    # Save the processed audio as WAV
    sf.write(output_file, filtered_data, fs)

# Usage example
input_file = 'input.wav'
output_file = 'output.wav'
cutoff_frequency = 20000  # 20 kHz

process_audio(input_file, output_file, cutoff_frequency)
