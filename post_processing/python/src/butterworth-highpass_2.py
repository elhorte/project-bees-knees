#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import platform
import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt, welch
import matplotlib.pyplot as plt


def get_working_dir():
    os_name = platform.system()
    if os_name == 'Windows':    # python compensates for the backslash (Gate's fault)
        return r'E:/git/en/project-bees-knees/beehub/python/src/'
    elif os_name == 'Darwin':
        return r'/Users/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src/'
    elif os_name == 'Linux':
        return r'/home/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src/'
    else:
        return '.' # Default to current directory

def get_audio_file_info(file_path):
    try:
        info = sf.info(file_path)
        return info
    except RuntimeError as e:
        print(f"Error reading file: {e}")
        return None


def high_pass_filter(data, cutoff, fs, order):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def plot_frequency_spectrum(data, fs, label):
    f, Pxx = welch(data, fs, nperseg=1024)
    plt.semilogy(f, Pxx, label=label)

def process_audio_and_plot(input_file, output_file, cutoff_frequency, _dtype, order):
    # Read the FLAC file
    data, fs = sf.read(input_file, dtype=_dtype)

    # Apply high-pass filter
    filtered_data = high_pass_filter(data, cutoff_frequency, fs, order)

    # Plot original and filtered frequency spectrum
    plt.figure()  # Create a new figure
    plot_frequency_spectrum(data, fs, "Original Audio")
    plot_frequency_spectrum(filtered_data, fs, "Filtered Audio")
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('PSD [V²/Hz]')
    plt.title(f'Freq Spectrum Comparison - {order}th-order Butterworth - {cutoff_frequency/1000} kHz cutoff')
    plt.legend()
    plt.grid(True)
    plt.show()  # Show the plot

    # Save the processed audio as WAV
    sf.write(output_file, filtered_data, fs)

def main():
    work_dir = get_working_dir()
    os.chdir(work_dir)

    input_file = 'input.wav'
    output_file = 'output.wav'
    file_path = work_dir + input_file

    info = get_audio_file_info(file_path)

    if info:
        print("Audio file information:")
        print(f" Format: {info.format}")
        print(f" Subtype: {info.subtype}")
        print(f" Channels: {info.channels}")
        print(f" Samplerate: {info.samplerate}")
        print(f" Frames: {info.frames}")
        print(f" Duration: {info.duration} seconds")
    else:
        print("Failed to retrieve audio file information.")
    
    if info.subtype == 'PCM_16': _dtype = 'int16'

    cutoff_frequency = 20000  # 20 kHz

    process_audio_and_plot(input_file, output_file, cutoff_frequency, _dtype, 10)

if __name__ == "__main__":
    main()
