#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# configuration file for BMARwtm.py

import datetime

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1_4mic"
HIVE_CONFIG = "dual-mic, sensor"

# mode controls
MODE_AUDIO_MONITOR = False                       # recording continuously to mp3 files
MODE_PERIOD = True                              # period recording
MODE_EVENT = False                              # event recording
MODE_FFT_PERIODIC_RECORD = True                 # record fft periodically

# recording types controls:
AUDIO_MONITOR_START = None  ##datetime.time(4, 0, 0)    # time of day to start recording hr, min, sec; None = continuous recording
AUDIO_MONITOR_END = datetime.time(23, 0, 0)     # time of day to stop recording hr, min, sec
AUDIO_MONITOR_RECORD = 1800                     # file size in seconds of continuous recording
AUDIO_MONITOR_INTERVAL = 0                      # seconds between recordings

PERIOD_START = None  ##datetime.time(4, 0, 0)   # 'None' = continuous recording
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = 300                             # seconds of recording
PERIOD_INTERVAL = 0                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                          # seconds to save before the event
SAVE_AFTER_EVENT = 30                           # seconds to save after the event
EVENT_THRESHOLD = 20000                         # audio level threshold to be considered an event
MIC_LOCATION = ["lower w/queen--front", "upper--front", "upper--back", "lower w/queen--back", "upper--back"]

data_drive = "G:"
data_directory = "My Drive/en_beehive_data"
##data_drive = "C:"
##data_directory = "temp"

# input device parameters:
MAKE_NAME = "Focusrite"                         # 'Behringer' or 'Zoom or Scarlett'
MODEL_NAME = ["UMC404HD", "Analogue 1 + 2", "Zoom", "Volt"]
DEVICE_NAME = 'UAC'                             # 'UAC' or 'USB'
API_NAME = "WASAPI"                             # 'MME' or 'WASAPI' or 'ASIO' or 'DS'  
HOSTAPI_NAME = "Windows"                        # 'Windows' or 'ASIO' or 'DS' or 'WDM-KS'
HOSTAPI_INDEX = 3                               # 0 = Windows, 1 = ASIO, 2 = DS, 3 = WASAPI, 4 = WDM-KS
SOUND_IN_CHS = 4

# windows mme defaults, 2 ch only
SOUND_IN_DEFAULT = 0                          # default input device id              
SOUND_OUT_ID_DEFAULT = 14                        # default output device id
SOUND_OUT_CHS_DEFAULT = 2                       # default number of output channels
SOUND_OUT_SR_DEFAULT = 44100                    # default sample rate