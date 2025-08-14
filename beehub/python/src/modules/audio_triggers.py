"""
BMAR Audio Triggers Module
Contains spectral analysis and audio trigger functions based on amplitude and duration.
This module is part of the BMAR (Biometric Monitoring and Analysis for Research) project.
This code is released under the GNU General Public License v3.0.
"""

import numpy as np
import time
import sounddevice as sd
import sys

def audio_trigger(amplitude_threshold, duration_threshold, sample_rate=44100):
    """
    Monitors audio input and triggers an action when the amplitude exceeds a threshold for a specified duration.
    
    Parameters:
    - amplitude_threshold: float, the minimum amplitude to trigger the action.
    - duration_threshold: float, the minimum duration (in seconds) the amplitude must exceed the threshold.
    - sample_rate: int, the sample rate of the audio input (default is 44100 Hz).
    
    Returns:
    - None
    """
    print("Starting audio trigger monitoring...")
    
    start_time = None
    
    def callback(indata, frames, time, status):
        nonlocal start_time
        if status:
            print(status, file=sys.stderr)
        
        amplitude = np.max(np.abs(indata))
        
        if amplitude > amplitude_threshold:
            if start_time is None:
                start_time = time.inputBufferAdcTime
            elif time.inputBufferAdcTime - start_time >= duration_threshold:
                print("Trigger activated!")
                start_time = None  # Reset after triggering
        else:
            start_time = None  # Reset if below threshold
    
    with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate):
        print("Press Ctrl+C to stop.")
        while True:
            time.sleep(0.1)  # Keep the stream alive   
            # The callback will handle the audio processing in real-time
        print("Audio trigger monitoring stopped.")
