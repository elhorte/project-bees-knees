#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# configuration file for BMARwtm.py

import datetime

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1_4mic"
HIVE_CONFIG = "dual-mic, sensor"

# mode controls
MODE_AUDIO_MONITOR = True                      # recording continuously to mp3 files
MODE_PERIOD = True                              # period recording
MODE_EVENT = False                              # event recording
MODE_FFT_PERIODIC_RECORD = True                 # record fft periodically

# recording types controls:
AUDIO_MONITOR_START = None  ##datetime.time(4, 0, 0)    # time of day to start recording hr, min, sec; None = continuous recording
AUDIO_MONITOR_END = datetime.time(23, 0, 0)     # time of day to stop recording hr, min, sec
AUDIO_MONITOR_RECORD = 1800                     # file size in seconds of continuous recording (default 1800 sec)
AUDIO_MONITOR_INTERVAL = 0                      # seconds between recordings

PERIOD_START = None  ##datetime.time(4, 0, 0)   # 'None' = continuous recording
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = 900                             # seconds of recording (default 900 sec)
PERIOD_INTERVAL = 0                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                          # seconds to save before the event
SAVE_AFTER_EVENT = 30                           # seconds to save after the event
EVENT_THRESHOLD = 20000                         # audio level threshold to be considered an event

# Windows
win_data_drive = "G:"   # D is internal and limited; G is Google Drive, just FYI
win_data_path = "My Drive\eb_beehive_data"
win_data_folders = ["audio", "plots"]  # Fixed syntax - use commas not semicolons
#Macos
mac_data_drive = "~"  
mac_data_path = "data/eb_beehive_data"
mac_data_folders = ["audio", "plots"]  # Fixed syntax - use commas not semicolons
#Linux
linux_data_drive = "~"                          # Use home directory
linux_data_path = "beedata/eb_beehive_data"     # Store in ~/beedata
linux_data_folders = ["audio", "plots"]         # Fixed syntax - use commas not semicolons

# mic location map channel to position
MIC_LOCATION = ['1: upper--front', '2: upper--back', '3: lower w/queen--front', '4: lower w/queen--back']

# mic status
MIC_1 = True
MIC_2 = True
MIC_3 = False
MIC_4 = False

SOUND_IN_CHS = MIC_1 + MIC_2 + MIC_3 + MIC_4    # count of input channels

# input device parameters--linux:
LINUX_MAKE_NAME = ""                                     # Leave empty for Linux default
LINUX_MODEL_NAME = ["pipewire"]                         # Use pipewire as the audio system
LINUX_DEVICE_NAME = "pipewire"                          # Use pipewire device
LINUX_API_NAME = "ALSA"                                 # Use ALSA API for Linux
LINUX_HOSTAPI_NAME = "ALSA"                             # Use ALSA host API
LINUX_HOSTAPI_INDEX = 0                                 # ALSA is typically index 0
LINUX_DEVICE_ID = None                                     # Use pipewire device ID

# input device parameters--windows:
WINDOWS_MAKE_NAME = "Focusrite"                          # Audio interface make
WINDOWS_MODEL_NAME = ["Scarlett"]                        # Audio interface model
WINDOWS_DEVICE_NAME = "Focusrite Scarlett"              # Device name
WINDOWS_API_NAME = "WASAPI"                      # Windows audio API
WINDOWS_HOSTAPI_NAME = "WASAPI"                  # Host API name
WINDOWS_HOSTAPI_INDEX = 0                                # Default host API index
WINDOWS_DEVICE_ID = 12                                   # Device ID for Focusrite

# input device parameters--macos:
MACOS_MAKE_NAME = ""                                    # Leave empty for macOS default
MACOS_MODEL_NAME = ["Built-in"]                        # Built-in audio
MACOS_DEVICE_NAME = "Built-in"                         # Built-in device
MACOS_API_NAME = "CoreAudio"                           # macOS audio API
MACOS_HOSTAPI_NAME = "CoreAudio"                       # Host API name
MACOS_HOSTAPI_INDEX = 0                                # Default host API index
MACOS_DEVICE_ID = 0                                    # Default device ID

# audio parameters:
PRIMARY_SAMPLERATE = 192000                     # Audio sample rate
PRIMARY_BITDEPTH = 16                           # Audio bit depth
PRIMARY_FILE_FORMAT = "FLAC"                    # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

AUDIO_MONITOR_SAMPLERATE = 48000                # For continuous audio
AUDIO_MONITOR_BITDEPTH = 16                     # Audio bit depthv
AUDIO_MONITOR_CHANNELS = 2                      # Number of channels
AUDIO_MONITOR_QUALITY = 0                       # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
AUDIO_MONITOR_FORMAT = "MP3"                    # accepts mp3, flac, or wav

# Windows mme defaults, 2 ch only
SOUND_IN_DEFAULT = 0                          # default input device id              
SOUND_OUT_ID_DEFAULT = 3                        # default output device id
SOUND_OUT_CHS_DEFAULT = 1                       # default number of output channels
SOUND_OUT_SR_DEFAULT = 48000                    # default sample rate

