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
AUDIO_MONITOR_RECORD = 35                     # file size in seconds of continuous recording (default 1800 sec)
AUDIO_MONITOR_INTERVAL = 0                      # seconds between recordings

PERIOD_START = None  ##datetime.time(4, 0, 0)   # 'None' = continuous recording
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = 30                             # seconds of recording (default 900 sec)
PERIOD_INTERVAL = 0                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                          # seconds to save before the event
SAVE_AFTER_EVENT = 30                           # seconds to save after the event
EVENT_THRESHOLD = 20000                         # audio level threshold to be considered an event

# Windows
win_data_drive = "G:"   # D is internal and limited; G is Google Drive, just FYI
win_data_path = "My Drive/eb_beehive_data"
win_data_folders = ["audio", "plots"]  # Fixed syntax - use commas not semicolons
#Macos
mac_data_drive = "~"  
mac_data_path = "data/eb_beehive_data"
mac_data_folders = ["audio", "plots"]  # Fixed syntax - use commas not semicolons
#Linux
linux_data_drive = "/mnt/beedata" 
linux_data_path = "eb_beehive_data"
linux_data_folders = ["audio", "plots"]  # Fixed syntax - use commas not semicolons

# mic location map channel to position
MIC_LOCATION = ['1: upper--front', '2: upper--back', '3: lower w/queen--front', '4: lower w/queen--back']

# mic status
MIC_1 = True
MIC_2 = True
MIC_3 = False
MIC_4 = False

SOUND_IN_CHS = MIC_1 + MIC_2 + MIC_3 + MIC_4    # count of input channels

# input device parameters:
MAKE_NAME = "Focusrite"                         # 'Behringer' or 'Zoom or Scarlett'
MODEL_NAME = ["UMC404HD", "Analogue 1 + 2", "Zoom", "Volt"]
DEVICE_NAME = 'UAC'                             # 'UAC' or 'USB'
API_NAME = "WASAPI"                             # 'MME' or 'WASAPI' or 'ASIO' or 'DS'  
HOSTAPI_NAME = "Windows"                        # 'Windows' or 'ASIO' or 'DS' or 'WDM-KS'
HOSTAPI_INDEX = 3                               # 0 = Windows, 1 = ASIO, 2 = DS, 3 = WASAPI, 4 = WDM-KS

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

