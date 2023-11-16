#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 


import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt, welch
import matplotlib.pyplot as plt
import os

##file_name = "input.wav"
os.chdir('/Users/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src')

def high_pass_filter(data, cutoff, fs, order=9):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def plot_frequency_spectrum(data, fs, title="Frequency Spectrum"):
    f, Pxx = welch(data, fs, nperseg=1024)
    plt.figure()  # Create a new figure
    plt.semilogy(f, Pxx)
    plt.ylim([1e-8, 1e2])
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('PSD [V²/Hz]')
    plt.title(title)
    plt.grid(True)
    plt.show()  # Show the plot
    plt.pause(1)  # Pause for a moment to ensure the plot is rendered

def process_audio(input_file, output_file, cutoff_frequency):
    # Read the FLAC file
    data, fs = sf.read(input_file, dtype='int16')

    # Plot original frequency spectrum
    plot_frequency_spectrum(data, fs, "Original Audio")

    # Apply high-pass filter
    filtered_data = high_pass_filter(data, cutoff_frequency, fs)

    # Plot filtered frequency spectrum
    plot_frequency_spectrum(filtered_data, fs, "Filtered Audio")

    # Save the processed audio as WAV
    sf.write(output_file, filtered_data, fs)

# Usage example
input_file = 'input.wav'
output_file = 'output.wav'
cutoff_frequency = 20000  # 20 kHz

process_audio(input_file, output_file, cutoff_frequency)
