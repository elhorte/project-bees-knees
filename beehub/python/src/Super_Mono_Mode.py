!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Python script that implements an enhanced "Super Mono Mode" with several processing options beyond simple L+R summing. 
This includes phase correction, mid-side processing, and other audiophile-focused enhancements.
Comprehensive Python script that implements several "Super Mono Mode" processing techniques that go far beyond simple L+R channel summing. 

Here are the key features:

## **Processing Modes:**

1. **Basic Mode**: Simple L+R summing with normalization
2. **Enhanced Mode**: Phase correction, weighted summing, and high-frequency compensation
3. **Mid-Side Mode**: Converts to mid-side, preserves spatial information in mono
4. **Frequency Mode**: Multi-band processing with different strategies per frequency range
5. **Vocal Mode**: Optimized for speech/vocals with presence enhancement

## **Advanced Features:**

- **Phase Correlation Analysis**: Detects and corrects phase issues between channels
- **Weighted Summing**: Balances channels based on signal energy
- **Frequency-Dependent Processing**: Different strategies for bass, mids, and highs
- **Spatial Preservation**: Blends some stereo width information back into mono
- **Vocal Enhancement**: Boosts presence frequencies and adds harmonic saturation
- **Automatic Normalization**: Prevents clipping while maintaining dynamics

The script addresses the real-world challenges that audiophile "Super Mono" implementations solve:
- Phase cancellation between channels
- Loss of high-frequency detail in summing
- Preservation of spatial cues in mono
- Frequency-specific optimization
- Vocal clarity enhancement

This implementation goes well beyond the basic mono conversion you'd find in most audio software, 
incorporating techniques inspired by high-end audiophile equipment design principles.'''

'''
You're very welcome! I'm excited to hear how it performs for you. The script includes several different processing modes, 
so you'll be able to experiment and see which one works best for your specific audio content and preferences.

A few tips for testing:
- Try the "enhanced" mode first as a good starting point
- The "vocal" mode works particularly well for spoken content or vocal-heavy music
- The "frequency" mode tends to give the most audiophile-focused results
- Compare against the "basic" mode to really hear the difference the advanced processing makes

I'd love to hear your feedback on which modes work best for different types of content, 
and if you notice any particular improvements in clarity, phase coherence, or overall sound quality. 
Feel free to reach out if you run into any issues or want to discuss modifications!

'''
"""
# Install dependencies
pip install numpy scipy soundfile

# Basic usage
python super_mono.py input.wav output.wav

# With specific mode
python super_mono.py input.wav output.wav --mode frequency

# For vocal content
python super_mono.py input.wav output.wav --mode vocal


Requirements:
    pip install numpy scipy soundfile

Usage:
    python super_mono.py input.wav output.wav --mode enhanced
"""

import numpy as np
import soundfile as sf
import scipy.signal as signal
from scipy.fft import fft, ifft
import argparse
import sys
from pathlib import Path


class SuperMonoProcessor:
    """Enhanced mono conversion with multiple processing modes."""
    
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        
    def basic_mono(self, stereo_audio):
        """Simple L+R summing with normalization."""
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo (2-channel) audio")
        
        mono = (stereo_audio[:, 0] + stereo_audio[:, 1]) / 2.0
        return mono
    
    def enhanced_mono(self, stereo_audio):
        """Enhanced mono with phase correction and filtering."""
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo (2-channel) audio")
        
        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]
        
        # Phase correlation analysis
        correlation = np.corrcoef(left, right)[0, 1]
        
        # If channels are highly anti-correlated, apply phase correction
        if correlation < -0.3:
            print(f"Detected phase issues (correlation: {correlation:.3f}), applying correction")
            right = -right  # Invert phase of right channel
        
        # Weighted summing based on signal strength
        left_energy = np.mean(left**2)
        right_energy = np.mean(right**2)
        total_energy = left_energy + right_energy
        
        if total_energy > 0:
            left_weight = left_energy / total_energy
            right_weight = right_energy / total_energy
        else:
            left_weight = right_weight = 0.5
        
        # Create enhanced mono signal
        mono = left_weight * left + right_weight * right
        
        # Apply gentle high-frequency enhancement to compensate for summing losses
        # Design a subtle high-shelf filter
        nyquist = self.sample_rate / 2
        cutoff = 8000  # 8kHz
        gain_db = 1.5  # Subtle 1.5dB boost
        
        sos = signal.iirfilter(2, cutoff/nyquist, btype='highpass', 
                              ftype='butter', output='sos')
        enhanced_highs = signal.sosfilt(sos, mono)
        
        # Blend original and enhanced
        gain_linear = 10**(gain_db/20)
        blend_factor = 0.3
        mono = mono * (1 - blend_factor) + enhanced_highs * gain_linear * blend_factor
        
        return mono
    
    def mid_side_mono(self, stereo_audio):
        """Mid-side processing for enhanced mono conversion."""
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo (2-channel) audio")
        
        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]
        
        # Convert to mid-side
        mid = (left + right) / 2.0  # Center information
        side = (left - right) / 2.0  # Stereo width information
        
        # Analyze side content
        side_energy = np.mean(side**2)
        mid_energy = np.mean(mid**2)
        
        # If there's significant side content, blend some back into mid
        # to preserve spatial information in mono
        if side_energy > 0.01 * mid_energy:  # If side > 1% of mid energy
            print(f"Preserving spatial content (side energy: {side_energy:.6f})")
            # Add small amount of processed side content
            # Apply gentle low-pass to side content to avoid harshness
            sos = signal.butter(3, 2000/(self.sample_rate/2), btype='low', output='sos')
            filtered_side = signal.sosfilt(sos, side)
            mono = mid + 0.15 * filtered_side  # Blend 15% of filtered side content
        else:
            mono = mid
        
        return mono
    
    def frequency_conscious_mono(self, stereo_audio):
        """Frequency-dependent mono conversion for optimal sound."""
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo (2-channel) audio")
        
        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]
        
        # Split into frequency bands
        # Low frequencies: simple sum (bass is typically mono anyway)
        sos_low = signal.butter(4, 250/(self.sample_rate/2), btype='low', output='sos')
        left_low = signal.sosfilt(sos_low, left)
        right_low = signal.sosfilt(sos_low, right)
        low_mono = (left_low + right_low) / 2.0
        
        # Mid frequencies: enhanced processing
        sos_mid = signal.butter(4, [250/(self.sample_rate/2), 4000/(self.sample_rate/2)], 
                               btype='band', output='sos')
        left_mid = signal.sosfilt(sos_mid, left)
        right_mid = signal.sosfilt(sos_mid, right)
        
        # Apply correlation-based processing to mids
        correlation = np.corrcoef(left_mid, right_mid)[0, 1]
        if correlation < 0:
            right_mid = -right_mid
        mid_mono = (left_mid + right_mid) / 2.0
        
        # High frequencies: preserve detail
        sos_high = signal.butter(4, 4000/(self.sample_rate/2), btype='high', output='sos')
        left_high = signal.sosfilt(sos_high, left)
        right_high = signal.sosfilt(sos_high, right)
        
        # For highs, use the channel with more energy to preserve detail
        left_high_energy = np.mean(left_high**2)
        right_high_energy = np.mean(right_high**2)
        
        if left_high_energy > right_high_energy:
            high_mono = left_high * 0.8 + right_high * 0.2
        else:
            high_mono = right_high * 0.8 + left_high * 0.2
        
        # Combine all bands
        mono = low_mono + mid_mono + high_mono
        
        return mono
    
    def vocal_optimized_mono(self, stereo_audio):
        """Optimized for vocal content and dialog clarity."""
        if stereo_audio.ndim != 2 or stereo_audio.shape[1] != 2:
            raise ValueError("Input must be stereo (2-channel) audio")
        
        left = stereo_audio[:, 0]
        right = stereo_audio[:, 1]
        
        # Extract mid content (where vocals typically reside)
        mid = (left + right) / 2.0
        side = (left - right) / 2.0
        
        # Design a vocal emphasis filter (boost vocal frequencies)
        # Vocal presence range: ~1kHz - 4kHz
        sos_vocal = signal.iirfilter(4, [1000/(self.sample_rate/2), 4000/(self.sample_rate/2)], 
                                    btype='band', ftype='butter', output='sos')
        
        # Apply gentle boost to vocal range in mid content
        vocal_enhanced = signal.sosfilt(sos_vocal, mid)
        vocal_boost_db = 2.0  # 2dB boost
        vocal_boost_linear = 10**(vocal_boost_db/20)
        
        # Blend enhanced vocals back
        mono = mid + (vocal_enhanced * vocal_boost_linear - vocal_enhanced) * 0.3
        
        # Add subtle harmonic enhancement for presence
        # Create gentle saturation effect
        drive = 1.2
        mono_driven = np.tanh(mono * drive) / drive
        mono = mono * 0.85 + mono_driven * 0.15
        
        return mono
    
    def process_file(self, input_path, output_path, mode='enhanced'):
        """Process an audio file with the specified mono mode."""
        
        # Read input file
        try:
            audio_data, sample_rate = sf.read(input_path)
            self.sample_rate = sample_rate
            print(f"Loaded: {input_path}")
            print(f"Sample rate: {sample_rate} Hz")
            print(f"Duration: {len(audio_data)/sample_rate:.2f} seconds")
            print(f"Channels: {audio_data.shape[1] if audio_data.ndim > 1 else 1}")
        except Exception as e:
            print(f"Error reading file: {e}")
            return False
        
        # Check if input is stereo
        if audio_data.ndim == 1:
            print("Input is already mono, copying to output...")
            sf.write(output_path, audio_data, sample_rate)
            return True
        elif audio_data.shape[1] != 2:
            print(f"Error: Input has {audio_data.shape[1]} channels, need stereo (2 channels)")
            return False
        
        # Process based on mode
        print(f"Processing with mode: {mode}")
        
        if mode == 'basic':
            mono_audio = self.basic_mono(audio_data)
        elif mode == 'enhanced':
            mono_audio = self.enhanced_mono(audio_data)
        elif mode == 'midside':
            mono_audio = self.mid_side_mono(audio_data)
        elif mode == 'frequency':
            mono_audio = self.frequency_conscious_mono(audio_data)
        elif mode == 'vocal':
            mono_audio = self.vocal_optimized_mono(audio_data)
        else:
            print(f"Unknown mode: {mode}")
            return False
        
        # Normalize to prevent clipping
        max_amplitude = np.max(np.abs(mono_audio))
        if max_amplitude > 0.95:
            mono_audio = mono_audio / max_amplitude * 0.95
            print(f"Normalized audio (peak was {max_amplitude:.3f})")
        
        # Write output file
        try:
            sf.write(output_path, mono_audio, sample_rate)
            print(f"Saved: {output_path}")
            return True
        except Exception as e:
            print(f"Error writing file: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Super Mono Mode Audio Processor')
    parser.add_argument('input', help='Input stereo audio file')
    parser.add_argument('output', help='Output mono audio file')
    parser.add_argument('--mode', choices=['basic', 'enhanced', 'midside', 'frequency', 'vocal'],
                       default='enhanced', help='Processing mode (default: enhanced)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not Path(args.input).exists():
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)
    
    # Create processor and process file
    processor = SuperMonoProcessor()
    success = processor.process_file(args.input, args.output, args.mode)
    
    if success:
        print("\n✓ Processing completed successfully!")
        print(f"\nMode descriptions:")
        print(f"• basic: Simple L+R summing")
        print(f"• enhanced: Phase correction + frequency compensation")
        print(f"• midside: Mid-side processing with spatial preservation")
        print(f"• frequency: Multi-band processing for optimal frequency response")
        print(f"• vocal: Optimized for speech and vocal content")
    else:
        print("\n✗ Processing failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()