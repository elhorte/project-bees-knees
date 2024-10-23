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
    # Read the input file
    data, rate = read_wav(input_file)

    # Perform wavelet decomposition
    coeffs = pywt.wavedec(data, 'db1')

    # Determine the total levels of decomposition
    total_levels = len(coeffs) - 1

    # Calculate the level corresponding to the cutoff frequency
    # Note: This calculation may need to be adjusted based on your specific requirements
    level = int(np.floor(np.log2(framerate / (2 * cutoff_freq))))

    # Ensure level is within the valid range
    level = max(0, min(level, total_levels))

    # Create copies of the coefficients for below and above 20kHz
    coeffs_low = [coeff.copy() for coeff in coeffs]
    coeffs_high = [coeff.copy() for coeff in coeffs]

    # Zero out coefficients for the above 20kHz band (low frequencies)
    for i in range(level + 1):
        coeffs_low[i].fill(0)

    # Zero out coefficients for the below 20kHz band (high frequencies)
    for i in range(level + 1, total_levels + 1):
        coeffs_high[i].fill(0)

    # Reconstruct the below and above bands
    reconstructed_low = pywt.waverec(coeffs_low, 'db1')
    reconstructed_high = pywt.waverec(coeffs_high, 'db1')

    # Write the output files
    write_wav(output_file_low, reconstructed_low.astype(np.int16), rate)
    write_wav(output_file_high, reconstructed_high.astype(np.int16), rate)



# Example usage
input_wav='E:/git/en/project-bees-knees/beehub/python/src/input.wav'
split_band_wavelet('input_b.wav', 'output_below_20kHz.wav', 'output_above_20kHz.wav', 20000, 192000)
