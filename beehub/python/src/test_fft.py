import numpy as np
import matplotlib.pyplot as plt

# Test the FFT computation to verify it's working correctly
def test_fft_computation():
    """Test FFT computation with synthetic data to verify correct frequency domain plotting."""
    
    # Generate test signal similar to synthetic audio
    samplerate = 44100
    duration = 2.0
    t = np.linspace(0, duration, int(samplerate * duration))
    
    # Create signal with known frequencies
    freq1 = 440  # A4 note
    freq2 = 880  # A5 note  
    freq3 = 1320 # E6 note
    freq4 = 100  # Low frequency
    
    signal = (0.6 * np.sin(2 * np.pi * freq1 * t) +
             0.3 * np.sin(2 * np.pi * freq2 * t) +
             0.2 * np.sin(2 * np.pi * freq3 * t) +
             0.1 * np.sin(2 * np.pi * freq4 * t))
    
    # Apply window
    windowed_data = signal * np.hanning(len(signal))
    
    # Compute FFT
    fft_size = len(windowed_data)
    fft = np.fft.fft(windowed_data)
    freqs = np.fft.fftfreq(fft_size, 1/samplerate)
    
    # Take only positive frequencies
    positive_freqs = freqs[:fft_size//2]
    magnitude = np.abs(fft[:fft_size//2])
    
    # Convert to dB
    magnitude_db = 20 * np.log10(magnitude + 1e-10)
    
    # Find peaks at expected frequencies
    print("Expected peaks:")
    for freq in [100, 440, 880, 1320]:
        # Find closest frequency bin
        freq_idx = np.argmin(np.abs(positive_freqs - freq))
        actual_freq = positive_freqs[freq_idx]
        actual_mag = magnitude_db[freq_idx]
        print(f"  {freq}Hz -> {actual_freq:.1f}Hz: {actual_mag:.1f}dB")
    
    # Create plot
    plt.figure(figsize=(12, 6))
    plt.plot(positive_freqs, magnitude_db)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude (dB)')
    plt.title('Test FFT - Expected peaks at 100, 440, 880, 1320 Hz')
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 5000)  # Focus on low frequencies where peaks should be
    plt.ylim(-100, 20)  # Reasonable dB range
    
    # Mark expected frequencies
    for freq in [100, 440, 880, 1320]:
        plt.axvline(x=freq, color='red', linestyle='--', alpha=0.5, label=f'{freq}Hz')
    
    plt.legend()
    plt.show()
    
    print("If you see clear peaks at the marked frequencies, FFT is working correctly!")

if __name__ == "__main__":
    test_fft_computation()
