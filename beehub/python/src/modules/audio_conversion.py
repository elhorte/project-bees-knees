"""
BMAR Audio Conversion Module
Handles audio format conversion, downsampling, and encoding operations.
"""

import numpy as np
from scipy.signal import butter, filtfilt
from pydub import AudioSegment

def pcm_to_mp3_write(np_array, full_path, config):
    """
    Convert PCM audio to MP3 and save to file using downsampled data.
    
    Args:
        np_array: NumPy array containing audio data
        full_path: Full path where to save the MP3 file
        config: Configuration object containing audio settings
    """
    try:
        # The input np_array should already be int16 from the buffer
        # No need to convert again - this was causing double scaling
        int_array = np_array.astype(np.int16)
        byte_array = int_array.tobytes()

        # Create an AudioSegment instance from the byte array
        audio_segment = AudioSegment(
            data=byte_array,
            sample_width=2,
            frame_rate=config.AUDIO_MONITOR_SAMPLERATE,
            channels=config.AUDIO_MONITOR_CHANNELS
        )
        
        # Try to export with ffmpeg first
        try:
            if config.AUDIO_MONITOR_QUALITY >= 64 and config.AUDIO_MONITOR_QUALITY <= 320:
                # Use bitrate for quality between 64-320 kbps
                audio_segment.export(full_path, format="mp3", bitrate=f"{config.AUDIO_MONITOR_QUALITY}k")
            elif config.AUDIO_MONITOR_QUALITY < 10:
                # Use quality setting for values 0-9
                audio_segment.export(full_path, format="mp3", parameters=["-q:a", str(config.AUDIO_MONITOR_QUALITY)])
            else:
                # Default to 128 kbps for other values
                audio_segment.export(full_path, format="mp3", bitrate="128k")
                
        except Exception as e:
            if "ffmpeg" in str(e).lower():
                print("\nError: ffmpeg not found or not working properly.")
                print("Please install ffmpeg:")
                print("1. Download from https://ffmpeg.org/download.html")
                print("2. Extract the zip file")
                print("3. Add the bin folder to your system PATH")
                print("\nOr install using pip:")
                print("pip install ffmpeg-python")
                raise
            else:
                raise
                
    except Exception as e:
        print(f"Error converting audio to MP3: {str(e)}")
        raise

def downsample_audio(audio_data, orig_sample_rate, target_sample_rate):
    """
    Downsample audio to a lower sample rate with anti-aliasing filter.
    
    Args:
        audio_data: Input audio data as NumPy array (should be int16 from buffer)
        orig_sample_rate: Original sample rate
        target_sample_rate: Target sample rate
        
    Returns:
        NumPy array: Downsampled audio data as int16
    """
    # Convert audio to float for processing
    # The input should be int16 data from the buffer, so convert to float range [-1.0, 1.0]
    if audio_data.dtype == np.int16:
        audio_float = audio_data.astype(np.float32) / 32767.0  # Use 32767 to preserve scaling
    else:
        # If already float, assume it's in proper range
        audio_float = audio_data.astype(np.float32)
    downsample_ratio = int(orig_sample_rate / target_sample_rate)

    # Define an anti-aliasing filter
    nyq = 0.5 * orig_sample_rate
    low = 0.5 * target_sample_rate
    low = low / nyq
    b, a = butter(5, low, btype='low')

    # If audio is stereo, split channels
    if len(audio_float.shape) > 1 and audio_float.shape[1] == 2:
        left_channel = audio_float[:, 0]
        right_channel = audio_float[:, 1]
    else:
        # If not stereo, duplicate the mono channel
        left_channel = audio_float.ravel()
        right_channel = audio_float.ravel()

    # Apply the Nyquist filter for each channel
    left_filtered = filtfilt(b, a, left_channel)
    right_filtered = filtfilt(b, a, right_channel)
    
    # Downsample each channel 
    left_downsampled = left_filtered[::downsample_ratio]
    right_downsampled = right_filtered[::downsample_ratio]
    
    # Combine the two channels back into a stereo array
    downsampled_audio_float = np.column_stack((left_downsampled, right_downsampled))
    
    # Convert back to int16 preserving the original scaling
    # Convert float range [-1.0, 1.0] back to int16 range [-32767, 32767]
    downsampled_audio = (downsampled_audio_float * 32767.0).astype(np.int16)
    return downsampled_audio
