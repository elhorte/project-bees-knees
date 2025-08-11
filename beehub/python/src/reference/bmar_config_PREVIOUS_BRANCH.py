"""
BMAR Configuration Module
Contains global constants, settings, and configuration validation.
"""

import os
import datetime
import platform

# #############################################################
# #### Control Panel ##########################################
# #############################################################

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1_4mic"
HIVE_CONFIG = "dual-mic, sensor"

# mode controls
MODE_AUDIO_MONITOR = True                       # recording continuously to mp3 files
MODE_PERIOD = True                              # period recording
MODE_EVENT = False                              # event recording
MODE_FFT_PERIODIC_RECORD = True                 # record fft periodically

# circular buffer size
BUFFER_SECONDS = 900                            # time length of circular buffer 

# recording types controls:
AUDIO_MONITOR_START = None  ##datetime.time(4, 0, 0)    # time of day to start recording hr, min, sec; None = continuous recording
AUDIO_MONITOR_END = datetime.time(23, 0, 0)     # time of day to stop recording hr, min, sec
AUDIO_MONITOR_RECORD = BUFFER_SECONDS           # duration of continuous recording in seconds, must be <= BUFFER_SECONDS (default BUFFER_SECONDS)
AUDIO_MONITOR_INTERVAL = 0.1                    # seconds between recordings

PERIOD_START = None  ##datetime.time(4, 0, 0)   # 'None' = continuous recording
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = BUFFER_SECONDS                  # duration of period recording in seconds, must be <= BUFFER_SECONDS (default BUFFER_SECONDS)
PERIOD_SPECTROGRAM = 120                        # spectrogram duration for saved png images
PERIOD_INTERVAL = 0.1                           # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                          # seconds to save before the event
SAVE_AFTER_EVENT = 30                           # seconds to save after the event
EVENT_THRESHOLD = 20000                         # audio level threshold to be considered an event

MONITOR_CH = 0                                  # channel to monitor for event (if > number of chs, all channels are monitored)

# Audio input configuration
MIC_1 = True
MIC_2 = True
MIC_3 = False
MIC_4 = False

SOUND_IN_CHS = MIC_1 + MIC_2 + MIC_3 + MIC_4    # count of input channels

# instrumentation parms
FFT_INTERVAL = 30                               # minutes between ffts

LOG_AUDIO_CALLBACK = False  # set True to see per-callback audio stats

# Global flags
DEBUG_VERBOSE = False                           # Enable verbose debug output (set to True for troubleshooting)

# Enhanced audio configuration
ENABLE_ENHANCED_AUDIO = True                    # Enable sounddevice-based enhanced audio device testing
AUDIO_API_PREFERENCE = ["WASAPI", "DirectSound", "MME"]  # Preferred audio APIs in order
AUDIO_FALLBACK_ENABLED = False                   # Allow fallback to default device if specified device fails

# input device parameters--linux:
LINUX_MAKE_NAME = ""                             # Leave empty for Linux default
LINUX_MODEL_NAME = ["pipewire"]                  # Use pipewire as the audio system
LINUX_DEVICE_NAME = "pipewire"                   # Use pipewire device
LINUX_API_NAME = "ALSA"                          # Use ALSA API for Linux
LINUX_HOSTAPI_NAME = "ALSA"                      # Use ALSA host API
LINUX_HOSTAPI_INDEX = 0                          # ALSA is typically index 0
LINUX_DEVICE_ID = None                           # Use pipewire device ID

# input device parameters--windows:
WINDOWS_MAKE_NAME = "Behringer"                 # Audio interface make
WINDOWS_MODEL_NAME = "UMC204HD"                 # Audio interface model
WINDOWS_DEVICE_NAME = "UMC204HD"                # Device name
WINDOWS_API_NAME = "WASAPI"                     # Windows audio API
WINDOWS_HOSTAPI_NAME = "WASAPI"                 # Host API name
WINDOWS_HOSTAPI_INDEX = 21                      # Default host API index
WINDOWS_DEVICE_ID = None                        # Device ID for Focusrite

# input device parameters--macos:
MACOS_MAKE_NAME = ""                            # Leave empty for macOS default
MACOS_MODEL_NAME = ["Built-in"]                 # Built-in audio
MACOS_DEVICE_NAME = "Built-in"                  # Built-in device
MACOS_API_NAME = "CoreAudio"                    # macOS audio API
MACOS_HOSTAPI_NAME = "CoreAudio"                # Host API name
MACOS_HOSTAPI_INDEX = 0                         # Default host API index
MACOS_DEVICE_ID = 0                             # Default device ID

# audio parameters:
PRIMARY_IN_SAMPLERATE = 192000                  # Audio sample rate
PRIMARY_BITDEPTH = 16                           # Audio bit depth
PRIMARY_SAVE_SAMPLERATE = 96000                 # if None then save at Input Samplerate
PRIMARY_FILE_FORMAT = "FLAC"                    # 'WAV' or 'FLAC'

# Apply pre-write attenuation to avoid clipping in saved files (dB)
# 0 = no attenuation; try 3 for a little headroom
SAVE_HEADROOM_DB = 0.0

AUDIO_MONITOR_SAMPLERATE = 48000                # For continuous audio
AUDIO_MONITOR_BITDEPTH = 16                     # Audio bit depth
AUDIO_MONITOR_CHANNELS = 2                      # Number of channels
AUDIO_MONITOR_QUALITY = 256                       # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
AUDIO_MONITOR_FORMAT = "MP3"                    # accepts mp3, flac, or wav

# Windows
win_data_drive = "G:\\"   # D is internal and limited; G is Google Drive, just FYI
win_data_path = "My Drive\\eb_beehive_data"
win_data_folders = ["audio", "plots"]
# macOS
mac_data_drive = "~"  
mac_data_path = "data/eb_beehive_data"
mac_data_folders = ["audio", "plots"]
# Linux
linux_data_drive = "~"                          # Use home directory
linux_data_path = "beedata/eb_beehive_data"     # Store in ~/beedata
linux_data_folders = ["audio", "plots"]

# mic location map channel to position
MIC_LOCATION = ['1: upper--front', '2: upper--back', '3: lower w/queen--front', '4: lower w/queen--back']

# Windows mme defaults
SOUND_IN_DEFAULT = 0                            # default input device id              
SOUND_OUT_ID_DEFAULT = 3                        # default output device id
SOUND_OUT_CHS_DEFAULT = 1                       # default number of output channels
SOUND_OUT_SR_DEFAULT = 48000                    # default sample rate

# Intercom (local monitor) parameters
INTERCOM_SAMPLERATE = 48000                     # Sample rate for local monitoring playback

# audio display parameters:
TRACE_DURATION = 10.0                            # seconds
OSCOPE_GAIN_DB = 12                             # Gain in dB of audio level for oscilloscope

FFT_DURATION = 10.0                             # seconds
FFT_GAIN = 12                                   # Gain in dB of audio level for fft
# FFT frequency axis limits (Hz). Set max to None to use Nyquist (samplerate/2)
FFT_FREQ_MIN_HZ = 0.0
FFT_FREQ_MAX_HZ = 10000.0  # 10 kHz max for audio

SPECTROGRAM_DURATION = 10.0                     # seconds
SPECTROGRAM_GAIN = 12                           # Gain in dB of audio level for spectrogram

# Spectrogram display scaling (dBFS)
SPECTROGRAM_DB_MIN = -70.0
SPECTROGRAM_DB_MAX = 0.0

def get_platform_audio_config(platform_manager, config):
    """Get platform-specific audio configuration."""
    if platform_manager.is_macos():
        return {
            'data_drive': os.path.expanduser(config.mac_data_drive),
            'data_path': config.mac_data_path,
            'folders': config.mac_data_folders,
            'make_name': config.MACOS_MAKE_NAME,
            'model_name': config.MACOS_MODEL_NAME,
            'device_name': config.MACOS_DEVICE_NAME,
            'api_name': config.MACOS_API_NAME,
            'hostapi_name': config.MACOS_HOSTAPI_NAME,
            'hostapi_index': config.MACOS_HOSTAPI_INDEX,
            'device_id': config.MACOS_DEVICE_ID
        }
    elif platform_manager.is_windows():
        return {
            'data_drive': config.win_data_drive,
            'data_path': config.win_data_path,
            'folders': config.win_data_folders,
            'make_name': config.WINDOWS_MAKE_NAME,
            'model_name': config.WINDOWS_MODEL_NAME,
            'device_name': config.WINDOWS_DEVICE_NAME,
            'api_name': config.WINDOWS_API_NAME,
            'hostapi_name': config.WINDOWS_HOSTAPI_NAME,
            'hostapi_index': config.WINDOWS_HOSTAPI_INDEX,
            'device_id': config.WINDOWS_DEVICE_ID
        }
    else:  # Linux or other Unix-like
        return {
            'data_drive': os.path.expanduser(config.linux_data_drive),
            'data_path': config.linux_data_path,
            'folders': config.linux_data_folders,
            'make_name': config.LINUX_MAKE_NAME,
            'model_name': config.LINUX_MODEL_NAME,
            'device_name': config.LINUX_DEVICE_NAME,
            'api_name': config.LINUX_API_NAME,
            'hostapi_name': config.LINUX_HOSTAPI_NAME,
            'hostapi_index': config.LINUX_HOSTAPI_INDEX,
            'device_id': config.LINUX_DEVICE_ID
        }

def get_platform_config():
    """Get platform-specific configuration information."""
    config = {
        'name': platform.system(),
        'version': platform.version(),
        'machine': platform.machine()
    }
    
    return config
