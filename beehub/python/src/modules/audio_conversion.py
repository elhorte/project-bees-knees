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
        audio_data: Input audio data as NumPy array
        orig_sample_rate: Original sample rate
        target_sample_rate: Target sample rate
        
    Returns:
        NumPy array: Downsampled audio data
    """
    # Convert audio to float for processing
    audio_float = audio_data.astype(np.float32) / np.iinfo(np.int16).max
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
    
    # Convert back to int16
    downsampled_audio = (downsampled_audio_float * np.iinfo(np.int16).max).astype(np.int16)
    return downsampled_audio

def resample_audio(audio_data, orig_sample_rate, target_sample_rate):
    """
    Resample audio data to a different sample rate.
    
    Args:
        audio_data: Input audio data as NumPy array
        orig_sample_rate: Original sample rate
        target_sample_rate: Target sample rate
        
    Returns:
        NumPy array: Resampled audio data
    """
    if orig_sample_rate == target_sample_rate:
        return audio_data
    
    try:
        import librosa
        # Use librosa for high-quality resampling
        resampled = librosa.resample(audio_data.T, 
                                   orig_sr=orig_sample_rate, 
                                   target_sr=target_sample_rate)
        return resampled.T
    except ImportError:
        # Fallback to simple downsampling if librosa not available
        if target_sample_rate < orig_sample_rate:
            return downsample_audio(audio_data, orig_sample_rate, target_sample_rate)
        else:
            # For upsampling without librosa, just repeat samples (not ideal)
            ratio = target_sample_rate / orig_sample_rate
            new_length = int(len(audio_data) * ratio)
            return np.interp(np.linspace(0, len(audio_data)-1, new_length), 
                           np.arange(len(audio_data)), audio_data)

def convert_bit_depth(audio_data, target_bit_depth):
    """
    Convert audio data to a different bit depth.
    
    Args:
        audio_data: Input audio data as NumPy array
        target_bit_depth: Target bit depth (16, 24, or 32)
        
    Returns:
        NumPy array: Converted audio data with appropriate dtype
    """
    if target_bit_depth == 16:
        if audio_data.dtype != np.int16:
            # Normalize to [-1, 1] then scale to int16 range
            if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                return (audio_data * np.iinfo(np.int16).max).astype(np.int16)
            else:
                # Convert from other integer types
                max_val = np.iinfo(audio_data.dtype).max
                normalized = audio_data.astype(np.float64) / max_val
                return (normalized * np.iinfo(np.int16).max).astype(np.int16)
        return audio_data
        
    elif target_bit_depth == 24:
        # 24-bit is usually stored in 32-bit containers
        if audio_data.dtype != np.int32:
            if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                return (audio_data * (2**23 - 1)).astype(np.int32)
            else:
                max_val = np.iinfo(audio_data.dtype).max
                normalized = audio_data.astype(np.float64) / max_val
                return (normalized * (2**23 - 1)).astype(np.int32)
        return audio_data
        
    elif target_bit_depth == 32:
        if audio_data.dtype != np.float32:
            if audio_data.dtype == np.int16:
                return audio_data.astype(np.float32) / np.iinfo(np.int16).max
            elif audio_data.dtype == np.int32:
                return audio_data.astype(np.float32) / np.iinfo(np.int32).max
            else:
                max_val = np.iinfo(audio_data.dtype).max
                return audio_data.astype(np.float32) / max_val
        return audio_data
        
    else:
        raise ValueError(f"Unsupported bit depth: {target_bit_depth}")

def normalize_audio(audio_data, target_level_db=-6.0):
    """
    Normalize audio to a target level in dB.
    
    Args:
        audio_data: Input audio data as NumPy array
        target_level_db: Target level in dB (default: -6.0 dB)
        
    Returns:
        NumPy array: Normalized audio data
    """
    # Calculate current RMS level
    rms = np.sqrt(np.mean(audio_data**2))
    
    if rms == 0:
        return audio_data  # Avoid division by zero for silence
    
    # Calculate target level (linear scale)
    target_level_linear = 10**(target_level_db / 20.0)
    
    # Calculate gain needed
    gain = target_level_linear / rms
    
    # Apply gain
    normalized = audio_data * gain
    
    # Ensure we don't clip
    max_val = np.max(np.abs(normalized))
    if max_val > 1.0:
        normalized = normalized / max_val
    
    return normalized
