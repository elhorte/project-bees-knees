#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import platform
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft

import librosa
import librosa.display

from scipy.io import wavfile
from scipy.signal.windows import blackman, hamming, hann, triang, boxcar
from scipy.linalg import toeplitz, solve


def get_working_dir():
    os_name = platform.system()
    if os_name == 'Windows':
        return r'E:/git/en/project-bees-knees/beehub/python/src/'
    elif os_name == 'Darwin':
        return r'/Users/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src/'
    elif os_name == 'Linux':
        return r'/home/elhorte/dev/GitHub/en/project-bees-knees/beehub/python/src/'
    else:
        return '.' # Do nothing'

def get_audio_file_info(file_path):
    try:
        info = sf.info(file_path)
        return info
    except RuntimeError as e:
        print(f"Error reading file: {e}")
        return None


def perform_fft_on_audio(file_path, time_offset_ms, sample_rate=8000, duration_ms=150, buckets=35):
    """
    Perform FFT on a segment of an audio file and plot the results with 35 bars.

    :param file_path: Path to the audio file.
    :param time_offset_ms: Time offset in milliseconds from the start of the file.
    :param sample_rate: Sampling rate of the audio file in Hz.
    :param duration_ms: Duration of the audio to be analyzed in milliseconds.
    :param buckets: Number of buckets to use for FFT.
    :return: None
    """
    # Calculate the number of samples for the given duration
    num_samples = int(duration_ms * sample_rate / 1000)

    # Read the audio file
    rate, data = wavfile.read(file_path)

    # Check if stereo and take only one channel
    if len(data.shape) > 1:
        data = data[:, 0]

    # Calculate start and end sample indices
    start_sample = int(time_offset_ms * sample_rate / 1000)
    end_sample = start_sample + num_samples

    # Extract the segment of the audio
    segment = data[start_sample:end_sample]

    # Perform FFT
    fft_result = fft(segment, n=buckets * 2)  # doubling the number of points for FFT
    fft_magnitude = np.abs(fft_result)[:buckets]  # taking only the first half (35 buckets)

    # Frequency bins
    freq_bins = np.linspace(0, sample_rate / 2, buckets)  # half the sampling rate for Nyquist frequency

    # Plotting the FFT result
    plt.figure(figsize=(12, 6))
    plt.bar(freq_bins, fft_magnitude, width=freq_bins[1] - freq_bins[0])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('FFT of Audio Segment')
    plt.show()

def perform_fft_on_audio_with_blackman_window(file_path, time_offset_ms, sample_rate=8000, duration_ms=150, buckets=35):
    """
    Perform FFT on a segment of an audio file using Blackman windowing, and plot the results with 35 bars.

    :param file_path: Path to the audio file.
    :param time_offset_ms: Time offset in milliseconds from the start of the file.
    :param sample_rate: Sampling rate of the audio file in Hz.
    :param duration_ms: Duration of the audio to be analyzed in milliseconds.
    :param buckets: Number of buckets to use for FFT.
    :return: None
    """
    # Calculate the number of samples for the given duration
    num_samples = int(duration_ms * sample_rate / 1000)

    # Read the audio file
    rate, data = wavfile.read(file_path)

    # Check if stereo and take only one channel
    if len(data.shape) > 1:
        data = data[:, 0]

    # Calculate start and end sample indices
    start_sample = int(time_offset_ms * sample_rate / 1000)
    end_sample = start_sample + num_samples

    # Extract the segment of the audio
    segment = data[start_sample:end_sample]

    # Apply Blackman window
    blackman_window = blackman(num_samples)
    windowed_segment = segment * blackman_window

    # Perform FFT
    fft_result = fft(windowed_segment, n=buckets * 2)  # doubling the number of points for FFT
    fft_magnitude = np.abs(fft_result)[:buckets]  # taking only the first half (35 buckets)

    # Frequency bins
    freq_bins = np.linspace(0, sample_rate / 2, buckets)  # half the sampling rate for Nyquist frequency

    # Plotting the FFT result
    plt.figure(figsize=(12, 6))
    plt.bar(freq_bins, fft_magnitude, width=freq_bins[1] - freq_bins[0])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('FFT with Blackman Windowing of Audio Segment')
    plt.show()

def perform_fft_on_audio_with_wola(file_path, time_offset_ms, sample_rate=8000, window_duration_ms=100, overlap_percent=50, buckets=35):
    """
    Perform FFT on a segment of an audio file using Weighted Overlap-Add (WOLA) with a Blackman window, 
    and plot the aggregated results with 35 bars.

    :param file_path: Path to the audio file.
    :param time_offset_ms: Time offset in milliseconds from the start of the file.
    :param sample_rate: Sampling rate of the audio file in Hz.
    :param window_duration_ms: Duration of each window in milliseconds.
    :param overlap_percent: Percentage of overlap between windows.
    :param buckets: Number of buckets to use for FFT.
    :return: None
    """
    # Calculate the number of samples per window and overlap
    window_size_samples = int(window_duration_ms * sample_rate / 1000)
    overlap_samples = int(window_size_samples * overlap_percent / 100)

    # Read the audio file
    rate, data = wavfile.read(file_path)

    # Check if stereo and take only one channel
    if len(data.shape) > 1:
        data = data[:, 0]

    # Start processing from the offset
    start_sample = int(time_offset_ms * sample_rate / 1000)
    data = data[start_sample:]

    # Initialize variables for FFT aggregation
    aggregate_fft_magnitude = np.zeros(buckets)

    # Apply WOLA
    for i in range(0, len(data) - window_size_samples, window_size_samples - overlap_samples):
        segment = data[i:i + window_size_samples]

        # Apply Blackman window
        blackman_window = blackman(window_size_samples)
        windowed_segment = segment * blackman_window

        # Perform FFT
        fft_result = fft(windowed_segment, n=buckets * 2)  # doubling the number of points for FFT
        fft_magnitude = np.abs(fft_result)[:buckets]  # taking only the first half (35 buckets)

        # Aggregate FFT magnitudes
        aggregate_fft_magnitude += fft_magnitude

    # Average the FFT magnitudes
    aggregate_fft_magnitude /= (len(data) / (window_size_samples - overlap_samples))

    # Frequency bins
    freq_bins = np.linspace(0, sample_rate / 2, buckets)  # half the sampling rate for Nyquist frequency

    # Plotting the FFT result
    plt.figure(figsize=(12, 6))
    plt.bar(freq_bins, aggregate_fft_magnitude, width=freq_bins[1] - freq_bins[0])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('FFT with WOLA of Audio Segment')
    plt.show()

def perform_fft_with_wola_b(file_path, time_offset_ms, sample_rate=8000, window_ms=100, overlap_factor=0.5, buckets=35):
    """
    Perform FFT on a segment of an audio file using Weighted Overlap-Add (WOLA) with Blackman windowing.

    :param file_path: Path to the audio file.
    :param time_offset_ms: Time offset in milliseconds from the start of the file.
    :param sample_rate: Sampling rate of the audio file in Hz.
    :param window_ms: Window duration in milliseconds for each FFT.
    :param overlap_factor: Overlap factor between consecutive windows.
    :param buckets: Number of buckets to use for FFT.
    :return: None
    """
    # Calculate the number of samples for the given window duration
    window_samples = int(window_ms * sample_rate / 1000)
    overlap_samples = int(window_samples * overlap_factor)

    # Read the audio file
    rate, data = wavfile.read(file_path)

    # Check if stereo and take only one channel
    if len(data.shape) > 1:
        data = data[:, 0]

    # Calculate start sample index
    start_sample = int(time_offset_ms * sample_rate / 1000)

    # Initialize variables for FFT accumulation
    fft_accumulated = np.zeros(buckets)
    count = 0

    # Perform WOLA
    while start_sample + window_samples <= len(data):
        # Extract windowed segment
        segment = data[start_sample:start_sample + window_samples]

        # Apply Blackman window
        blackman_window = blackman(window_samples)
        windowed_segment = segment * blackman_window

        # Perform FFT and accumulate
        fft_result = fft(windowed_segment, n=buckets * 2)  # doubling the number of points for FFT
        fft_magnitude = np.abs(fft_result)[:buckets]  # taking only the first half (35 buckets)
        fft_accumulated += fft_magnitude

        # Update for next window
        start_sample += window_samples - overlap_samples
        count += 1

    # Average the FFT result
    fft_average = fft_accumulated / count if count > 0 else fft_accumulated

    # Frequency bins
    freq_bins = np.linspace(0, sample_rate / 2, buckets)

    # Plotting the FFT result
    plt.figure(figsize=(12, 6))
    plt.bar(freq_bins, fft_average, width=freq_bins[1] - freq_bins[0])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('WOLA FFT of Audio Segment')
    plt.show()

def plot_fft_with_wola_c(file_path, time_offset_ms, sample_rate=8000, window_ms=100, overlap_factor=0.5, buckets=35):
    """
    Plot the FFT of a 100ms block of audio with 50% overlap at a given time offset using WOLA and Blackman windowing.

    :param file_path: Path to the audio file.
    :param time_offset_ms: Time offset in milliseconds from the start of the file.
    :param sample_rate: Sampling rate of the audio file in Hz.
    :param window_ms: Window duration in milliseconds for the FFT.
    :param overlap_factor: Overlap factor between consecutive windows.
    :param buckets: Number of buckets to use for FFT.
    :return: None
    """
    # Calculate the number of samples for the given window duration and overlap
    window_samples = int(window_ms * sample_rate / 1000)
    overlap_samples = int(window_samples * overlap_factor)

    # Read the audio file
    rate, data = wavfile.read(file_path)

    # Check if stereo and take only one channel
    if len(data.shape) > 1:
        data = data[:, 0]

    # Calculate start and end sample indices for the desired block
    start_sample = int(time_offset_ms * sample_rate / 1000)
    end_sample = start_sample + window_samples + overlap_samples

    # Extract the block of audio
    audio_block = data[start_sample:end_sample]

    # Apply Blackman window
    blackman_window = blackman(len(audio_block))
    windowed_audio_block = audio_block * blackman_window

    # Perform FFT
    fft_result = fft(windowed_audio_block, n=buckets * 2)  # doubling the number of points for FFT
    fft_magnitude = np.abs(fft_result)[:buckets]  # taking only the first half (35 buckets)

    # Frequency bins
    freq_bins = np.linspace(0, sample_rate / 2, buckets)

    # Plotting the FFT result
    plt.figure(figsize=(12, 6))
    plt.bar(freq_bins, fft_magnitude, width=freq_bins[1] - freq_bins[0])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('FFT with Blackman Windowing and WOLA of Audio Segment')
    plt.show()



def plot_lpc_with_wola(file_path, time_offset_ms, window_type, sample_rate=8000, window_ms=100, overlap_factor=0.5, order=35):
    """
    Plot the LPC of a 100ms block of audio with 50% overlap at a given time offset.

    :param file_path: Path to the audio file.
    :param time_offset_ms: Time offset in milliseconds from the start of the file.
    :param sample_rate: Sampling rate of the audio file in Hz.
    :param window_ms: Window duration in milliseconds.
    :param overlap_factor: Overlap factor between consecutive windows.
    :param order: Order of LPC (number of coefficients).
    :param window_type: Type of window to apply ('blackman', 'hamming', 'hann', 'triangular', 'rectangular').
    :return: None
    """
    # Calculate the number of samples for the given window duration and overlap
    window_samples = int(window_ms * sample_rate / 1000)
    overlap_samples = int(window_samples * overlap_factor)

    # Read the audio file
    rate, data = wavfile.read(file_path)

    # Check if stereo and take only one channel
    if len(data.shape) > 1:
        data = data[:, 0]

    # Calculate start and end sample indices for the desired block
    start_sample = int(time_offset_ms * sample_rate / 1000)
    end_sample = start_sample + window_samples + overlap_samples

    # Extract the block of audio
    audio_block = data[start_sample:end_sample]

    # Apply selected window
    if window_type == 'blackman':
        window = blackman(len(audio_block))
    elif window_type == 'hamming':
        window = hamming(len(audio_block))
    elif window_type == 'hann':
        window = hann(len(audio_block))
    elif window_type == 'triangular':
        window = triang(len(audio_block))
    elif window_type == 'boxcar':
        window = boxcar(len(audio_block))
    else:
        raise ValueError("Invalid window type. Choose 'blackman', 'hamming', 'hann', 'triangular', or 'boxcar'.")
    
    if 0:
        # Plotting the window function
        plt.figure(figsize=(12, 6))
        plt.plot(window, marker='o')
        plt.xlabel('Window Index')
        plt.ylabel('Window Value')
        plt.title('Window Shape')
        plt.show()

    windowed_audio_block = audio_block * window

    # Perform LPC using Levinson-Durbin algorithm
    autocorr = np.correlate(windowed_audio_block, windowed_audio_block, mode='full')
    autocorr = autocorr[autocorr.size // 2:]
    R = autocorr[:order + 1]
    R_matrix = toeplitz(R[:-1])
    lpc_coefficients = solve(R_matrix, R[1:])

    if 0:
        # Plotting the LPC coefficients
        plt.figure(figsize=(12, 6))
        plt.plot(lpc_coefficients, marker='o')
        plt.xlabel('Coefficient Index')
        plt.ylabel('Coefficient Value')
        plt.title('LPC Coefficients of Audio Segment')
        plt.show()

    return lpc_coefficients


def euclidean_distance(vec1, vec2):
    """
    Calculate the Euclidean distance between two vectors.

    :param vec1: First vector (list of 35 elements)
    :param vec2: Second vector (list of 35 elements)
    :return: Euclidean distance between vec1 and vec2
    """
    if len(vec1) != 35 or len(vec2) != 35:
        raise ValueError("Both vectors must have exactly 35 elements.")

    distance = sum((p - q) ** 2 for p, q in zip(vec1, vec2)) ** 0.5
    return distance


def main():
    work_dir = get_working_dir()
    os.chdir(work_dir)

    cutoff_frequency = 8000  # 8kHz

    input_file = 'GMA-TV--8khz16b.wav'
    ##output_file = 'output.wav'
    file_path = work_dir + input_file

    info = get_audio_file_info(file_path)

    if info and 0:
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
    
    ##perform_fft_on_audio(file_path, 550)  # Analyze 150ms of audio starting at 500ms
    ##perform_fft_on_audio_with_blackman_window(file_path, 550)
    ##plot_fft_with_wola_c(file_path, 600)
    print(euclidean_distance(plot_lpc_with_wola(file_path, 600, window_type='boxcar'), plot_lpc_with_wola(file_path, 100650, window_type='boxcar')))


if __name__ == "__main__":
    main()

# Example usage
# plot_lpc_with_wola("path_to_audio.wav", 500, window_type='hamming')