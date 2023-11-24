#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import soundfile as sf
import pywt
from scipy.signal import butter, filtfilt, welch
import matplotlib.pyplot as plt
import os


def get_audio_file_info(file_path):
    try:
        info = sf.info(file_path)
        return info
    except RuntimeError as e:
        print(f"Error reading file: {e}")
        return None
    
overlay = 1
if overlay:
    def plot_frequency_spectrum(data, fs, label):
        f, Pxx = welch(data, fs, nperseg=1024)
        plt.semilogy(f, Pxx, label=label)

    def plot_spectrum_overlay(data, filtered_data, fs):
        # Plot original and filtered frequency spectrum
        plt.figure()  # Create a new figure
        plot_frequency_spectrum(data, fs, "Original Audio")
        plot_frequency_spectrum(filtered_data, fs, "Filtered Audio")
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('PSD [V²/Hz]')
        plt.title('Frequency Spectrum Comparison')
        plt.legend()
        plt.grid(True)
else:
    def plot_frequency_spectrum(data, fs, title="Frequency Spectrum"):
        f, Pxx = welch(data, fs, nperseg=1024)
        plt.figure()  # Create a new figure
        plt.semilogy(f, Pxx)
        plt.ylim([1e-4, 1e2])
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('PSD [V²/Hz]')
        plt.title(title)
        plt.grid(True)


def high_pass_filter_butterworth(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = filtfilt(b, a, data)
    return filtered_data


def high_pass_filter_wavelet(data, cutoff, fs, wavelet='db8'):
    # Determine the maximum decomposition level
    max_level = pywt.dwt_max_level(data_len=len(data), filter_len=pywt.Wavelet(wavelet).dec_len)

    # Perform Discrete Wavelet Transform (DWT)
    coeffs = pywt.wavedec(data, wavelet, level=max_level)

    # Calculate the cutoff level for desired frequency
    cutoff_level = int(np.floor(np.log2(fs/cutoff)))

    # Zeroing coefficients below the cutoff level
    for i in range(1, max_level - cutoff_level + 1):
        coeffs[i] = np.zeros_like(coeffs[i])

    # Reconstruct the signal from modified coefficients
    filtered_data = pywt.waverec(coeffs, wavelet)[:len(data)]
    return filtered_data


def process_audio(input_file, output_file, cutoff_frequency, _dtype, _ftype):
    # Read the FLAC file
    data, fs = sf.read(input_file, dtype=_dtype)

    if _ftype == 'wavelet':
        # Apply high-pass filter using wavelet
        filtered_data = high_pass_filter_wavelet(data, cutoff_frequency, fs)
    else:
        # Apply high-pass filter using wavelet
        filtered_data = high_pass_filter_butterworth(data, cutoff_frequency, fs)

    # Plot original frequency spectrum
    plot_frequency_spectrum(data, fs, "Original Audio")

    # Plot filtered frequency spectrum
    plot_frequency_spectrum(filtered_data, fs, "Filtered Audio")

    plot_spectrum_overlay(data, filtered_data, fs)

    plt.show()  # Show the plot
    
    # Save the processed audio as WAV
    sf.write(output_file, filtered_data, fs)


def main():
    
    work_dir = '/Users/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src/'
    os.chdir(work_dir)

    cutoff_frequency = 20000  # 20 kHz

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

    _ftype = 'butterworth'
    process_audio(input_file, output_file, cutoff_frequency, _dtype, _ftype)

if __name__ == "__main__":
    main()
