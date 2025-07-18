"""
BMAR Recording Module
Handles audio recording using PyAudio with configurable file formats.
"""

import logging
import time
import datetime
import os
import numpy as np
import wave
import multiprocessing
from typing import Dict, Optional

def start_recording_process(config: Dict, stop_event: multiprocessing.Event):
    """
    Start recording process with the given configuration and stop event.
    This function is designed to run in a separate process with clean stop control.
    
    Args:
        config: Dictionary containing recording configuration
        stop_event: Multiprocessing event to signal when to stop recording
    """
    try:
        # Import PyAudio here to avoid issues with multiprocessing
        import pyaudio
        
        # Extract configuration
        device_id = config['device_id']
        sample_rate = config['sample_rate']
        channels = config['channels']
        bit_depth = config['bit_depth']
        today_dir = config['today_dir']
        recording_dir = config.get('recording_dir', today_dir)
        file_format = config.get('file_format', 'WAV').upper()  # Get format from config
        
        print(f"Recording process started with device {device_id}")
        print(f"Sample rate: {sample_rate} Hz, Channels: {channels}, Bit depth: {bit_depth}")
        print(f"File format: {file_format}")
        print("Press 'r' again to stop recording")
        
        # Ensure recording directory exists
        os.makedirs(recording_dir, exist_ok=True)
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        
        try:
            # Get device info
            device_info = pa.get_device_info_by_index(device_id)
            print(f"Recording from: {device_info['name']}")
            
            # Calculate audio format
            if bit_depth == 16:
                audio_format = pyaudio.paInt16
                dtype = np.int16
                bytes_per_sample = 2
            elif bit_depth == 24:
                audio_format = pyaudio.paInt24
                dtype = np.int32
                bytes_per_sample = 3
            elif bit_depth == 32:
                audio_format = pyaudio.paFloat32
                dtype = np.float32
                bytes_per_sample = 4
            else:
                audio_format = pyaudio.paInt16
                dtype = np.int16
                bytes_per_sample = 2
                print(f"Unsupported bit depth {bit_depth}, using 16-bit")
            
            # Calculate chunk size (0.1 seconds of audio for responsive stopping)
            chunk_size = int(sample_rate * 0.1)  # 100ms chunks for responsive control
            
            # Generate filename with appropriate extension
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            if file_format == 'FLAC':
                filename = f"recording_{timestamp}.flac"
            else:
                filename = f"recording_{timestamp}.wav"
            
            filepath = os.path.join(recording_dir, filename)
            print(f"Recording to: {filepath}")
            
            # Open audio stream
            stream = pa.open(
                format=audio_format,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=chunk_size
            )
            
            # Collect audio data in memory first
            audio_frames = []
            frames_recorded = 0
            start_time = time.time()
            
            print("Recording started...")
            
            # Main recording loop - check stop_event frequently
            while not stop_event.is_set():
                try:
                    # Read audio data with timeout for responsiveness
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    
                    # Store audio data
                    audio_frames.append(data)
                    
                    frames_recorded += chunk_size
                    duration = frames_recorded / sample_rate
                    
                    # Print progress every 10 seconds
                    if frames_recorded % (sample_rate * 10) < chunk_size:
                        print(f"Recording: {duration:.0f} seconds")
                    
                except Exception as e:
                    print(f"Recording error: {e}")
                    break
            
            # Clean up stream
            stream.stop_stream()
            stream.close()
            
            # Save the recorded audio in the specified format
            if audio_frames:
                save_audio_file(filepath, audio_frames, sample_rate, channels, 
                              bit_depth, file_format, pa)
                
                # Final stats
                duration = frames_recorded / sample_rate
                file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                
                print(f"Recording completed:")
                print(f"  Duration: {duration:.1f} seconds")
                print(f"  File size: {file_size:.1f} MB")
                print(f"  Format: {file_format}")
                print(f"  File: {filepath}")
            else:
                print("No audio data recorded")
            
        finally:
            pa.terminate()
            
    except Exception as e:
        print(f"Recording process error: {e}")
        import traceback
        traceback.print_exc()
        logging.error(f"Recording process error: {e}")

def save_audio_file(filepath, audio_frames, sample_rate, channels, bit_depth, file_format, pa):
    """Save audio data to file in the specified format."""
    try:
        # Combine all audio frames
        audio_data = b''.join(audio_frames)
        
        if file_format == 'FLAC':
            save_flac_file(filepath, audio_data, sample_rate, channels, bit_depth)
        else:
            # Default to WAV format
            save_wav_file(filepath, audio_data, sample_rate, channels, bit_depth, pa)
            
    except Exception as e:
        print(f"Error saving audio file: {e}")
        # Fallback to WAV if FLAC fails
        if file_format == 'FLAC':
            print("FLAC save failed, falling back to WAV...")
            wav_filepath = filepath.replace('.flac', '.wav')
            save_wav_file(wav_filepath, audio_data, sample_rate, channels, bit_depth, pa)

def save_wav_file(filepath, audio_data, sample_rate, channels, bit_depth, pa):
    """Save audio data as WAV file."""
    try:
        # Determine PyAudio format for bytes_per_sample calculation
        if bit_depth == 16:
            audio_format = pyaudio.paInt16
        elif bit_depth == 24:
            audio_format = pyaudio.paInt24
        elif bit_depth == 32:
            audio_format = pyaudio.paFloat32
        else:
            audio_format = pyaudio.paInt16
        
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(pa.get_sample_size(audio_format))
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        
        print(f"WAV file saved: {filepath}")
        
    except Exception as e:
        print(f"Error saving WAV file: {e}")
        raise

def save_flac_file(filepath, audio_data, sample_rate, channels, bit_depth):
    """Save audio data as FLAC file using soundfile."""
    try:
        import soundfile as sf
        import numpy as np
        
        # Convert binary audio data to numpy array
        if bit_depth == 16:
            dtype = np.int16
        elif bit_depth == 24:
            dtype = np.int32  # 24-bit is stored in 32-bit containers
        elif bit_depth == 32:
            dtype = np.float32
        else:
            dtype = np.int16
            print(f"Unsupported bit depth {bit_depth} for FLAC, using 16-bit")
        
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=dtype)
        
        # Reshape for multi-channel audio
        if channels > 1:
            audio_array = audio_array.reshape(-1, channels)
        
        # Normalize if needed (FLAC typically expects float32 in range -1.0 to 1.0)
        if dtype == np.int16:
            audio_array = audio_array.astype(np.float32) / 32768.0
        elif dtype == np.int32:
            audio_array = audio_array.astype(np.float32) / 2147483648.0
        # float32 is already in the right range
        
        # Save as FLAC
        sf.write(filepath, audio_array, sample_rate, format='FLAC')
        print(f"FLAC file saved: {filepath}")
        
    except ImportError:
        print("soundfile library not available for FLAC encoding")
        print("Install with: pip install soundfile")
        raise
    except Exception as e:
        print(f"Error saving FLAC file: {e}")
        raise

def start_simple_recording(device_id, sample_rate=44100, channels=1, duration=None, output_dir=None):
    """
    Simple recording function for immediate use.
    
    Args:
        device_id: Audio device index
        sample_rate: Sample rate in Hz
        channels: Number of channels
        duration: Recording duration in seconds (None for continuous)
        output_dir: Output directory (None for current directory)
    """
    import pyaudio
    
    try:
        # Setup
        if output_dir is None:
            output_dir = os.getcwd()
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
        filepath = os.path.join(output_dir, filename)
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        
        # Audio parameters
        chunk_size = 1024
        audio_format = pyaudio.paInt16
        
        print(f"Starting simple recording to: {filepath}")
        print(f"Device: {device_id}, Rate: {sample_rate}, Channels: {channels}")
        
        # Open stream
        stream = pa.open(
            format=audio_format,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_id,
            frames_per_buffer=chunk_size
        )
        
        # Record
        frames = []
        frames_to_record = int(sample_rate * duration) if duration else None
        frames_recorded = 0
        
        print("Recording... Press Ctrl+C to stop" if duration is None else f"Recording for {duration} seconds...")
        
        try:
            while True:
                data = stream.read(chunk_size, exception_on_overflow=False)
                frames.append(data)
                frames_recorded += chunk_size
                
                if frames_to_record and frames_recorded >= frames_to_record:
                    break
                    
        except KeyboardInterrupt:
            print("\nRecording stopped")
        
        # Save file
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(pa.get_sample_size(audio_format))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))
        
        # Cleanup
        stream.stop_stream()
        stream.close()
        pa.terminate()
        
        duration_actual = frames_recorded / sample_rate
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        
        print(f"Recording saved: {filepath}")
        print(f"Duration: {duration_actual:.1f}s, Size: {file_size:.1f}MB")
        
        return filepath
        
    except Exception as e:
        print(f"Simple recording error: {e}")
        return None

def test_recording_functionality():
    """Test recording functionality with default system device."""
    try:
        from .class_PyAudio import AudioPortManager
        
        print("Testing recording functionality...")
        
        # Get audio manager
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        input_devices = [d for d in devices if d['is_input']]
        
        if not input_devices:
            print("No input devices found for testing")
            return False
        
        # Use first working device
        test_device = None
        for device in input_devices:
            if manager.test_device_configuration(device['index'], 44100, 16, 1):
                test_device = device
                break
        
        if not test_device:
            print("No working input devices found for testing")
            return False
        
        print(f"Testing with device: {test_device['name']}")
        
        # Test 3-second recording
        output_dir = os.path.join(os.getcwd(), 'test_recordings')
        filepath = start_simple_recording(
            device_id=test_device['index'],
            sample_rate=44100,
            channels=1,
            duration=3,
            output_dir=output_dir
        )
        
        if filepath and os.path.exists(filepath):
            print(f"Recording test successful: {filepath}")
            return True
        else:
            print("Recording test failed")
            return False
            
    except Exception as e:
        print(f"Recording test error: {e}")
        return False