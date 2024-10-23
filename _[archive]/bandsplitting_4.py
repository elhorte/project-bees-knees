#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import pywt
import numpy as np
import wave
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

def split_band_wavelet(input_file, output_file_low, output_file_high, cutoff_freq, framerate):
    data, rate = read_wav(input_file)

    # Perform wavelet decomposition to the maximum level
    max_level = pywt.dwt_max_level(data_len=len(data), filter_len=pywt.Wavelet('db1').dec_len)
    coeffs = pywt.wavedec(data, 'db1', level=max_level)

    # Determine the frequency range for each decomposition level
    nyquist_freq = rate / 2
    freq_bands = [nyquist_freq / (2 ** i) for i in range(max_level + 1)]

    # Find the level corresponding to the cutoff frequency
    cutoff_level = next((i for i, freq in enumerate(freq_bands) if freq <= cutoff_freq), max_level)

    # Prepare coefficients for below 20kHz and above 20kHz
    coeffs_low = coeffs.copy()
    coeffs_high = [np.zeros_like(c) for c in coeffs]

    # Zero out coefficients below the cutoff frequency for the 'above 20kHz' band
    for i in range(cutoff_level):
        coeffs_high[i].fill(0)

    # Zero out coefficients above the cutoff frequency for the 'below 20kHz' band
    for i in range(cutoff_level, len(coeffs)):
        coeffs_low[i].fill(0)

    # Reconstruct the audio for both bands
    reconstructed_low = pywt.waverec(coeffs_low, 'db1')
    reconstructed_high = pywt.waverec(coeffs_high, 'db1')

    # Write the output files
    write_wav(output_file_low, reconstructed_low.astype(np.int16), rate)
    write_wav(output_file_high, reconstructed_high.astype(np.int16), rate)


# Example usage
input_wav='E:/git/en/project-bees-knees/beehub/python/src/input.wav'
split_band_wavelet('input_b.wav', 'output_below_20kHz.wav', 'output_above_20kHz.wav', 20000, 192000)
