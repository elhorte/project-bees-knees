#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 

# Using sounddevice and soundfile libraries, record audio from a device ID and save it to a FLAC file.
# Input audio from a device ID at a defineable sample rate, bit depth, and channel count. 
# Write incoming audio into a circular buffer that is of a definable length. 
# Monitor the incoming audio for levels above a definable threshold for a defineable duration and set a flag when conditions are met. 
# Note the position in the buffer of the event and then continue to record audio until a definable time period after the start of the event. 
# Note the position in the buffer of the end of the time period after the start of the event.
# Continue recording audio into the circular buffer while saving the audio to a FLAC file.
# Save audio in the circular buffer from the start of a defineable time period before the event to the end of the defineable time period after the event.
# Reset the audio threshold level flag and event_start_time after saving audio.

# This flag prevents config values from being printed multiple times in subprocesses
_CONFIG_PRINTED = False

# Check if we're running in the main process or a subprocess
# Subprocesses will have a different parent process ID
def is_main_process():
    import os
    return os.getppid() == 1 or os.getpid() == os.getppid()

import sounddevice as sd
import soundfile as sf
import datetime
import time
import threading
import multiprocessing
import numpy as np
import matplotlib
#matplotlib.use('Agg', force=True)
import matplotlib.pyplot as plt
from scipy.io.wavfile import write
from scipy.signal import resample
from scipy.fft import rfft, rfftfreq
from scipy.signal import resample_poly
from scipy.signal import decimate
from scipy.signal import butter, filtfilt
from pydub import AudioSegment
from sshkeyboard import listen_keyboard
import sys
import platform
import select
import os
import atexit
import signal
import warnings
import traceback
import librosa
import logging
import pyaudio


# Platform-specific imports with error handling
try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None

try:
    import winreg
except ImportError:
    winreg = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

import librosa.display
import resampy
import atexit
import subprocess 
import platform
import pyaudio
import Setup_Pyaudio as set_port
import gc
import psutil
import struct
import logging
#import curses
#import io
#import queue
#import termios
#import fcntl

# Platform-specific modules will be imported after platform detection

import gc
import psutil
import struct
import logging
import atexit
import signal

import BMAR_config as config
##os.environ['NUMBA_NUM_THREADS'] = '1'

class PlatformManager:
    _instance = None
    _initialized = False
    _os_info = None
    _keyboard_info = None
    _msvcrt = None
    _termios = None
    _tty = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlatformManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.initialize()
    
    def is_wsl(self):
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def is_macos(self):
        return sys.platform == 'darwin'
    
    def get_os_info(self):
        if self._os_info is not None:
            return self._os_info
            
        if sys.platform == 'win32':
            if self.is_wsl():
                self._os_info = "Windows Subsystem for Linux (WSL)"
            else:
                try:
                    if winreg is not None:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                        build_number = int(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])
                        product_name = winreg.QueryValueEx(key, "ProductName")[0]
                        
                        if build_number >= 22000:
                            self._os_info = "Windows 11 Pro"
                        else:
                            self._os_info = product_name
                    else:
                        self._os_info = f"Windows {platform.release()}"
                except Exception:
                    self._os_info = f"Windows {platform.release()}"
        elif self.is_macos():
            # Get macOS version information
            try:
                mac_ver = platform.mac_ver()
                macos_version = mac_ver[0]  # Version string like '10.15.7'
                macos_name = self._get_macos_name(macos_version)
                self._os_info = f"macOS {macos_version} ({macos_name})"
            except Exception:
                self._os_info = f"macOS {platform.release()}"
        else:
            self._os_info = f"{platform.system()} {platform.release()}"
        
        return self._os_info
    
    def _get_macos_name(self, version):
        """Get the marketing name for a macOS version"""
        version_dict = {
            '10.15': 'Catalina',
            '11': 'Big Sur',
            '12': 'Monterey',
            '13': 'Ventura',
            '14': 'Sonoma',
        }
        # Get major version for lookup
        major_version = '.'.join(version.split('.')[:2]) if '10.' in version else version.split('.')[0]
        return version_dict.get(major_version, "Unknown")
    
    def initialize(self):
        if not self._initialized:
            self._initialized = True
            print(f"\nDetected operating system: {self.get_os_info()}\r")
            
            if sys.platform == 'win32' and not self.is_wsl():
                if msvcrt is not None:
                    self._msvcrt = msvcrt
                    print("Using Windows keyboard handling (msvcrt)")
                    self._keyboard_info = "Windows"
                else:
                    print("Warning: msvcrt not available")
                    self._keyboard_info = "Limited"
            elif self.is_macos() or (sys.platform != 'win32' and not self.is_wsl()):
                if termios is not None and tty is not None:
                    self._termios = termios
                    self._tty = tty
                    self._fcntl = fcntl
                    print("Using Unix keyboard handling (termios)")
                    self._keyboard_info = "Unix"
                else:
                    print("Warning: termios module not available. Some keyboard functionality may be limited.", end='\r\n', flush=True)
                    self._keyboard_info = "Limited"
            else:
                self._msvcrt = None
                print("Using limited keyboard handling")
                self._keyboard_info = "Limited"
    
    @property
    def msvcrt(self):
        return self._msvcrt
        
    @property
    def termios(self):
        return self._termios
        
    @property
    def tty(self):
        return self._tty

# Create global platform manager instance
##platform_manager = PlatformManager()
# Initialize platform at startup
##platform_manager.initialize()

# #############################################################
# #### BmarApp Class to contain globals #######################
# #############################################################

class BmarApp:
    def __init__(self):
        self.config = config
        self.platform_manager = PlatformManager()
        self.platform_manager.initialize()

        # --- Configuration (mostly static after init) ---
        self.make_name = None
        self.model_name = None
        self.device_name = None
        self.api_name = None
        self.hostapi_name = None
        self.hostapi_index = None
        self.device_id = None
        
        self.data_drive = None
        self.data_path = None
        self.folders = None
        self.PRIMARY_DIRECTORY = None
        self.MONITOR_DIRECTORY = None
        self.PLOT_DIRECTORY = None

        self._dtype = None
        self._subtype = None
        
        self.sound_in_id = 1
        self.sound_in_chs = int(self.config.SOUND_IN_CHS) if hasattr(self.config, 'SOUND_IN_CHS') else 1
        self.sound_out_id = int(self.config.SOUND_OUT_ID_DEFAULT) if hasattr(self.config, 'SOUND_OUT_ID_DEFAULT') else None
        self.sound_out_chs = int(self.config.SOUND_OUT_CHS_DEFAULT) if hasattr(self.config, 'SOUND_OUT_CHS_DEFAULT') else 2                        
        self.sound_out_samplerate = int(self.config.SOUND_OUT_SR_DEFAULT) if hasattr(self.config, 'SOUND_OUT_SR_DEFAULT') else 44100    
        
        # Verify the values are reasonable
        if self.sound_in_chs <= 0 or self.sound_in_chs > 64:  # Sanity check for number of channels
            print(f"Warning: Invalid SOUND_IN_CHS value in config: {self.config.SOUND_IN_CHS}")
            print(f"Setting to default of 1 channel")
            self.sound_in_chs = 1

        # Audio configuration
        self.PRIMARY_IN_SAMPLERATE = self.config.PRIMARY_IN_SAMPLERATE
        self.PRIMARY_SAVE_SAMPLERATE = getattr(self.config, 'PRIMARY_SAVE_SAMPLERATE', None)
        self.PRIMARY_BITDEPTH = self.config.PRIMARY_BITDEPTH
        self.BUFFER_SECONDS = 1000  # Default buffer seconds
        
        # Keyboard/Control Panel mode
        self.KB_or_CP = 'KB'
        
        self.MICS_ACTIVE = [self.config.MIC_1, self.config.MIC_2, self.config.MIC_3, self.config.MIC_4]
        
        # Buffer
        self.buffer = None
        self.buffer_size = 0
        self.buffer_index = 0
        self.blocksize = 8196
        self.monitor_channel = 0
        self.file_offset = 0
        self.stop_program = [False]  # Use list to allow modification by reference
        self.testmode = True

        # init recording varibles
        self.continuous_start_index = None
        self.continuous_end_index = 0        
        self.period_start_index = None
        self.event_start_index = None
        self.detected_level = None

        # Date and time stuff for file naming
        current_date = datetime.datetime.now()
        self.current_year = current_date.strftime('%Y')
        self.current_month = current_date.strftime('%m')
        self.current_day = current_date.strftime('%d')
        
        # Create date components in the correct format
        yy = current_date.strftime('%y')  # 2-digit year (e.g., '23' for 2023)
        mm = current_date.strftime('%m')  # Month (01-12)
        dd = current_date.strftime('%d')  # Day (01-31)
        self.date_folder = f"{yy}{mm}{dd}"     # Format YYMMDD (e.g., '230516')
        
        # --- Dynamic State ---
        self.active_processes = {
            'v': None, 'o': None, 's': None, 'f': None, 
            'i': None, 'p': None, 'P': None
        }
        self.mp_manager = multiprocessing.Manager()
        self.original_terminal_settings = None
        self.keyboard_listener_running = True
        self.keyboard_listener_active = True
        
        # Process and Thread Management
        self.buffer_wrap_event = threading.Event()
        self.stop_recording_event = threading.Event()
        self.stop_intercom_event = threading.Event()
        self.stop_vu_event = threading.Event()
        self.stop_fft_periodic_plot_event = multiprocessing.Event()
        self.stop_performance_monitor_event = threading.Event()
        self.change_ch_event = threading.Event()
        self.buffer_lock = threading.Lock()
        self.blocksize = 0 # Let driver choose optimal block size
        
        self.recording_worker_thread = None
        self.intercom_thread = None

        # Misc
        self.time_diff = self._create_time_diff_func()
        self.fft_interval = 30 # minutes

        # procs
        self.asterisks = None
        self.vu_proc = None
        self.stop_vu_queue = None
        self.intercom_proc = None
        self.oscope_proc = None
        self.fft_periodic_plot_proc = None
        self.one_shot_fft_proc = None
        self.overflow_monitor_proc = None

        # event flags
        self.stop_recording_event = threading.Event()
        self.stop_tod_event = threading.Event()
        self.stop_vu_event = threading.Event()
        self.stop_intercom_event = threading.Event()
        self.stop_fft_periodic_plot_event = threading.Event()
        self.plot_oscope_done = threading.Event()
        self.plot_fft_done = threading.Event()
        self.plot_spectrogram_done = threading.Event()
        self.change_ch_event = threading.Event()


    def _create_time_diff_func(self):
        """Create a time difference function similar to time_between() in BMAR_son.py."""
        # Using a list to store the last called time because lists are mutable and can be modified inside the nested function.
        # This will act like a "nonlocal" variable.
        last_called = [None]
        
        def helper():
            current_time = time.time()
            
            # If the function has never been called before, set last_called to the current time and return a large value
            # to prevent file_offset increment on first call
            if last_called[0] is None:
                last_called[0] = current_time
                return 1800  # Return max value to prevent file_offset increment
            # Calculate the difference and update the last_called time.
            diff = current_time - last_called[0]
            last_called[0] = current_time
            # Cap the difference at 1800 seconds.
            return min(diff, 1800)
        # Return the helper function, NOT A VALUE.
        return helper


    def initialize(self):
        """Run all setup methods to initialize the application state."""
        self._setup_audio_format()
        self._setup_paths_and_devices()
        self.check_and_create_date_folders() # This also sets the initial directory paths
        self.original_terminal_settings = self.save_terminal_settings()
        
        # Print configuration values only in main process
        if is_main_process():
            print(f"\nConfig values:")
            print(f"  data_drive: '{self.data_drive}'")
            print(f"  data_path: '{self.data_path}'")
            print(f"  folders: {self.folders}")
            print(f"  Date folder format: '{self.date_folder}' (YYMMDD)")


    def _setup_audio_format(self):
        """Sets the internal audio data type and subtype based on config."""
        if self.config.PRIMARY_BITDEPTH == 16:
            self._dtype = 'int16'
            self._subtype = 'PCM_16'
        elif self.config.PRIMARY_BITDEPTH == 24:
            self._dtype = 'int24'
            self._subtype = 'PCM_24'
        elif self.config.PRIMARY_BITDEPTH == 32:
            self._dtype = 'int32' 
            self._subtype = 'PCM_32'
        else:
            logging.critical(f"The bit depth is not supported: {self.config.PRIMARY_BITDEPTH}")
            sys.exit(-1)


    def _setup_paths_and_devices(self):
        """Sets up data paths and device names based on the operating system."""
        if self.platform_manager.is_macos():
            self.data_drive = os.path.expanduser(self.config.mac_data_drive)
            self.data_path = self.config.mac_data_path
            self.folders = self.config.mac_data_folders
            self.make_name, self.model_name, self.device_name, self.api_name, self.hostapi_name, self.hostapi_index, self.device_id = \
                self.config.MACOS_MAKE_NAME, self.config.MACOS_MODEL_NAME, self.config.MACOS_DEVICE_NAME, self.config.MACOS_API_NAME, \
                self.config.MACOS_HOSTAPI_NAME, self.config.MACOS_HOSTAPI_INDEX, self.config.MACOS_DEVICE_ID
        elif sys.platform == 'win32':
            self.data_drive = self.config.win_data_drive
            self.data_path = self.config.win_data_path
            self.folders = self.config.win_data_folders
            self.make_name, self.model_name, self.device_name, self.api_name, self.hostapi_name, self.hostapi_index, self.device_id = \
                self.config.WINDOWS_MAKE_NAME, self.config.WINDOWS_MODEL_NAME, self.config.WINDOWS_DEVICE_NAME, self.config.WINDOWS_API_NAME, \
                self.config.WINDOWS_HOSTAPI_NAME, self.config.WINDOWS_HOSTAPI_INDEX, self.config.WINDOWS_DEVICE_ID
        else:  # Linux or other
            self.data_drive = os.path.expanduser(self.config.linux_data_drive)
            self.data_path = self.config.linux_data_path
            self.folders = self.config.linux_data_folders
            self.make_name, self.model_name, self.device_name, self.api_name, self.hostapi_name, self.hostapi_index, self.device_id = \
                self.config.LINUX_MAKE_NAME, self.config.LINUX_MODEL_NAME, self.config.LINUX_DEVICE_NAME, self.config.LINUX_API_NAME, \
                self.config.LINUX_HOSTAPI_NAME, self.config.LINUX_HOSTAPI_INDEX, self.config.LINUX_DEVICE_ID


    def check_and_create_date_folders(self):
        """Checks and creates date-stamped directories for data storage."""
        current_date = datetime.datetime.now()
        date_folder = current_date.strftime('%y%m%d')
        
        logging.info(f"Setting up data directories for date: {date_folder}")
        
        self.PRIMARY_DIRECTORY = os.path.join(self.data_drive, self.data_path, self.config.LOCATION_ID, self.config.HIVE_ID, 
                                        self.folders[0], "raw", date_folder)
        self.MONITOR_DIRECTORY = os.path.join(self.data_drive, self.data_path, self.config.LOCATION_ID, self.config.HIVE_ID, 
                                        self.folders[0], "mp3", date_folder)
        self.PLOT_DIRECTORY = os.path.join(self.data_drive, self.data_path, self.config.LOCATION_ID, self.config.HIVE_ID, 
                                     self.folders[1], date_folder)
        
        # Ensure paths end with a separator for consistency
        self.PRIMARY_DIRECTORY = os.path.join(self.PRIMARY_DIRECTORY, "")
        self.MONITOR_DIRECTORY = os.path.join(self.MONITOR_DIRECTORY, "")
        self.PLOT_DIRECTORY = os.path.join(self.PLOT_DIRECTORY, "")

        logging.info(f"Primary directory set to: {self.PRIMARY_DIRECTORY}")
        logging.info(f"Monitor directory set to: {self.MONITOR_DIRECTORY}")
        logging.info(f"Plot directory set to: {self.PLOT_DIRECTORY}")
        
        required_directories = [self.PRIMARY_DIRECTORY, self.MONITOR_DIRECTORY, self.PLOT_DIRECTORY]
        return ensure_directories_exist(required_directories)
    

    def save_terminal_settings(self):
        """Save current terminal settings for later restoration."""
        try:
            if sys.platform == 'win32' and not self.platform_manager.is_wsl():
                # Windows doesn't need to save terminal settings in the same way
                return None
            elif self.platform_manager.termios is not None:
                # For Unix-like systems
                return self.platform_manager.termios.tcgetattr(sys.stdin)
            else:
                return None
        except Exception as e:
            logging.warning(f"Could not save terminal settings: {e}")
            return None

    def get_subprocess_config(self, **kwargs):
        """
        Create a comprehensive configuration dictionary for subprocess communication.
        This centralizes the configuration creation to avoid code duplication.
        Each subprocess function will use only the keys it needs.
        
        Args:
            **kwargs: Additional parameters to include or override defaults
            
        Returns:
            Dictionary containing all configuration values safe for multiprocessing
        """
        # Comprehensive configuration with all values that any subprocess might need
        config = {
            # Audio device settings
            'sound_in_id': int(self.sound_in_id) if self.sound_in_id is not None else None,
            'sound_in_chs': int(self.sound_in_chs),
            'primary_in_samplerate': int(self.config.PRIMARY_IN_SAMPLERATE),
            'PRIMARY_IN_SAMPLERATE': int(self.PRIMARY_IN_SAMPLERATE),  # VU meter uses this key name
            'primary_bitdepth': int(self.config.PRIMARY_BITDEPTH),
            
            # Directory paths
            'plot_directory': str(self.PLOT_DIRECTORY),
            
            # Location identifiers
            'location_id': str(self.config.LOCATION_ID),
            'hive_id': str(self.config.HIVE_ID),
            
            # Platform information
            'is_wsl': self.platform_manager.is_wsl(),
            'is_macos': self.platform_manager.is_macos(),
            'os_info': self.platform_manager.get_os_info(),
            
            # Oscilloscope settings
            'trace_duration': float(self.config.TRACE_DURATION),
            'oscope_gain_db': float(self.config.OSCOPE_GAIN_DB),
            
            # FFT settings
            'fft_duration': float(self.config.FFT_DURATION),
            'fft_gain': float(getattr(self.config, 'FFT_GAIN', 0)),
            'fft_bw': float(getattr(self.config, 'FFT_BW', 100)),  # Default bucket width
            
            # VU meter settings
            'monitor_channel': int(self.monitor_channel),
        }
        
        # Add any additional kwargs (allows for override or additional values)
        config.update(kwargs)
        
        return config
    
        # end class BmarApp


'''
# audio interface info
make_name = None
model_name = None
device_name = None
api_name = None
hostapi_name = None
hostapi_index = None
device_id = None

# init recording varibles
continuous_start_index = None
continuous_end_index = 0        
period_start_index = None
event_start_index = None
detected_level = None

# threads
recording_worker_thread = None
intercom_thread = None

# misc globals
_dtype = None                   # parms sd lib cares about
_subtype = None
##asterisks = '*'
device_ch = None                # total number of channels from device
current_time = None
timestamp = None
monitor_channel = 0             # '1 of n' mic to monitor by test functions
stop_program = [False]
buffer_size = None
buffer = None
buffer_index = None
file_offset = 0


# #############################################################
# Dictionary to track active processes by key
active_processes = {
    'v': None,  # VU meter
    'o': None,  # Oscilloscope
    's': None,  # Spectrogram 
    'f': None,  # FFT
    'i': None,  # Intercom
    'p': None,  # Performance monitor (one-shot)
    'P': None   # Performance monitor (continuous)
}
'''

# #############################################################
# #### Control Panel ##########################################
# #############################################################

MONITOR_CH = 0                                  # channel to monitor for event (if > number of chs, all channels are monitored)
##TRACE_DURATION = config.TRACE_DURATION          # seconds of audio to show on oscope
##config.OSCOPE_GAIN_DB = 12                             # Gain in dB of audio level for oscope 

# instrumentation parms
FFT_BINS = 800                                  # number of bins for fft
FFT_BW = 1000                                   # bandwidth of each bucket in hertz
##FFT_DURATION = config.FFT_DURATION              # seconds of audio to show on fft
FFT_INTERVAL = 30                               # minutes between ffts

##OSCOPE_DURATION = config.OSCILLOSCOPE_DURATION # seconds of audio to show on oscope
##OSCOPE_GAIN_DB = 12                             # gain in dB for oscope

FULL_SCALE = 2 ** 16                            # just for cli vu meter level reference
BUFFER_SECONDS = 1000                           # time length of circular buffer 

# global: list of mics present in system
##MICS_ACTIVE = [config.MIC_1, config.MIC_2, config.MIC_3, config.MIC_4]

# translate human to machine
if config.PRIMARY_BITDEPTH == 16:
    _dtype = 'int16'
    _subtype = 'PCM_16'
elif config.PRIMARY_BITDEPTH == 24:
    _dtype = 'int24'
    _subtype = 'PCM_24'
elif config.PRIMARY_BITDEPTH == 32:
    _dtype = 'int32' 
    _subtype = 'PCM_32'
else:
    print("The bit depth is not supported: ", config.PRIMARY_BITDEPTH)
    quit(-1)

'''
# Date and time stuff for file naming
current_date = datetime.datetime.now()
current_year = current_date.strftime('%Y')
current_month = current_date.strftime('%m')
current_day = current_date.strftime('%d')

# Create date components in the correct format
# For folder structure we need YY (2-digit year), MM, DD format
yy = current_date.strftime('%y')  # 2-digit year (e.g., '23' for 2023)
mm = current_date.strftime('%m')  # Month (01-12)
dd = current_date.strftime('%d')  # Day (01-31)
date_folder = f"{yy}{mm}{dd}"     # Format YYMMDD (e.g., '230516')
'''

##spectrogram_period = config.PERIOD_SPECTROGRAM

'''
# Select the appropriate data drive and path based on OS
if platform_manager.is_macos():
    data_drive = os.path.expanduser(config.mac_data_drive)  # Expand ~ if present
    data_path = config.mac_data_path
    folders = config.mac_data_folders
    # macOS audio device settings
    make_name = config.MACOS_MAKE_NAME
    model_name = config.MACOS_MODEL_NAME
    device_name = config.MACOS_DEVICE_NAME
    api_name = config.MACOS_API_NAME
    hostapi_name = config.MACOS_HOSTAPI_NAME
    hostapi_index = config.MACOS_HOSTAPI_INDEX
    device_id = config.MACOS_DEVICE_ID
elif sys.platform == 'win32':
    data_drive = config.win_data_drive
    data_path = config.win_data_path
    folders = config.win_data_folders
    # Windows audio device settings
    make_name = config.WINDOWS_MAKE_NAME
    model_name = config.WINDOWS_MODEL_NAME
    device_name = config.WINDOWS_DEVICE_NAME
    api_name = config.WINDOWS_API_NAME
    hostapi_name = config.WINDOWS_HOSTAPI_NAME
    hostapi_index = config.WINDOWS_HOSTAPI_INDEX
    device_id = config.WINDOWS_DEVICE_ID
else:  # Linux or other Unix-like
    data_drive = os.path.expanduser(config.linux_data_drive)  # Expand ~ if present
    data_path = config.linux_data_path
    folders = config.linux_data_folders
    # Linux audio device settings
    make_name = config.LINUX_MAKE_NAME
    model_name = config.LINUX_MODEL_NAME
    device_name = config.LINUX_DEVICE_NAME
    api_name = config.LINUX_API_NAME
    hostapi_name = config.LINUX_HOSTAPI_NAME
    hostapi_index = config.LINUX_HOSTAPI_INDEX
    device_id = config.LINUX_DEVICE_ID

# to be discovered from sounddevice.query_devices()
sound_in_id = 1                             # id of input device, set as default in case none is detected
sound_in_chs = int(config.SOUND_IN_CHS) if hasattr(config, 'SOUND_IN_CHS') else 1  # Ensure it's an integer
sound_out_id = int(config.SOUND_OUT_ID_DEFAULT) if hasattr(config, 'SOUND_OUT_ID_DEFAULT') else None
sound_out_chs = int(config.SOUND_OUT_CHS_DEFAULT) if hasattr(config, 'SOUND_OUT_CHS_DEFAULT') else 2                        
sound_out_samplerate = int(config.SOUND_OUT_SR_DEFAULT) if hasattr(config, 'SOUND_OUT_SR_DEFAULT') else 44100    

# Verify the values are reasonable
if sound_in_chs <= 0 or sound_in_chs > 64:  # Sanity check for number of channels
    print(f"Warning: Invalid SOUND_IN_CHS value in config: {config.SOUND_IN_CHS}")
    print(f"Setting to default of 1 channel")
    app.sound_in_chs = 1

# Construct directory paths using the folders list and including the date subfolder
# Ensure we have proper path joining by using os.path.join
PRIMARY_DIRECTORY = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                folders[0], "raw", date_folder)
MONITOR_DIRECTORY = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                folders[0], "mp3", date_folder)
PLOT_DIRECTORY = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                             folders[1], date_folder)

# Ensure paths end with a separator for consistency
PRIMARY_DIRECTORY = os.path.join(PRIMARY_DIRECTORY, "")
MONITOR_DIRECTORY = os.path.join(MONITOR_DIRECTORY, "")
PLOT_DIRECTORY = os.path.join(PLOT_DIRECTORY, "")
'''

# Config values are now printed from within BmarApp.initialize() method
# No global config printing needed here


testmode = False                            # True = run in test mode with lower than needed sample rate
KB_or_CP = 'KB'                             # use keyboard or control panel (PyQT5) to control program

##########################  
# setup utilities
##########################

lock = threading.Lock()
# Ignore this specific warning
warnings.filterwarnings("ignore", category=UserWarning)

def ensure_directories_exist(directories):
    """
    Check if directories exist and create them if necessary.
    
    Args:
        directories: List of directory paths to check and create
        
    Returns:
        bool: True if all directories exist or were created, False otherwise
    """
    # Expand any home directory tildes
    expanded_dirs = [os.path.expanduser(d) for d in directories]
    
    # Check which directories don't exist
    missing_dirs = [d for d in expanded_dirs if not os.path.exists(d)]
    
    if not missing_dirs:
        print("All required directories exist.")
        return True
    
    print("\nCreating the following directories:")
    for d in missing_dirs:
        print(f"  - {d}")
    
    success = True
    for d in missing_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            
            # Verify directory was created
            if os.path.exists(d):
                print(f"Created directory: {d}")
            else:
                print(f"Failed to create directory: {d} (Unknown error)")
                success = False
        except Exception as e:
            print(f"Error creating directory {d}: {e}")
            success = False
            
            # Additional debugging for permission issues
            if "Permission denied" in str(e):
                print(f"  This appears to be a permissions issue. Current user may not have write access.")
                print(f"  Current working directory: {os.getcwd()}")
                try:
                    parent_dir = os.path.dirname(d)
                    print(f"  Parent directory exists: {os.path.exists(parent_dir)}")
                    if os.path.exists(parent_dir):
                        print(f"  Parent directory permissions: {oct(os.stat(parent_dir).st_mode)[-3:]}")
                except Exception as e2:
                    print(f"  Error checking parent directory: {e2}")
    
    return success



def restore_terminal_settings(app, settings):
    """Restore terminal settings from saved state."""
    try:
        if settings is None:
            return
        if sys.platform == 'win32' and not app.platform_manager.is_wsl():
            # Windows doesn't need terminal restoration in the same way
            return
        elif app.platform_manager.termios is not None:
            app.platform_manager.termios.tcsetattr(sys.stdin, app.platform_manager.termios.TCSADRAIN, settings)
    except Exception as e:
        logging.warning(f"Could not restore terminal settings: {e}")

def safe_stty(command):
    """Safely execute stty command without raising exceptions."""
    try:
        if sys.platform != 'win32':
            os.system(f'stty {command}')
    except Exception as e:
        logging.warning(f"stty command failed: {e}")
        

def stop_all():
    """Stop all processes and threads."""
    # This is a placeholder function that should be implemented based on your application's needs
    pass

def check_and_create_date_folders(app):
    """
    Check if today's date folders exist and create them if necessary.
    This function should be called at startup and periodically during operation.
    
    Args:
        app: BmarApp instance containing configuration and directory paths.
             If None, uses global variables for backward compatibility.
    """

    # Use BmarApp instance
    # Get current date components
    current_date = datetime.datetime.now()
    yy = current_date.strftime('%y')
    mm = current_date.strftime('%m')
    dd = current_date.strftime('%d')
    date_folder = f"{yy}{mm}{dd}"
    
    print(f"\nChecking/creating date folders for {date_folder}...")
    
    # Update directory paths with current date using app properties
    app.PRIMARY_DIRECTORY = os.path.join(app.data_drive, app.data_path, app.config.LOCATION_ID, app.config.HIVE_ID, 
                                    app.folders[0], "raw", date_folder, "")
    app.MONITOR_DIRECTORY = os.path.join(app.data_drive, app.data_path, app.config.LOCATION_ID, app.config.HIVE_ID, 
                                    app.folders[0], "mp3", date_folder, "")
    app.PLOT_DIRECTORY = os.path.join(app.data_drive, app.data_path, app.config.LOCATION_ID, app.config.HIVE_ID, 
                                    app.folders[1], date_folder, "")
    
    print(f"Primary directory: {app.PRIMARY_DIRECTORY}")
    print(f"Monitor directory: {app.MONITOR_DIRECTORY}")
    print(f"Plot directory: {app.PLOT_DIRECTORY}")
    
    # Create directories if they don't exist
    required_directories = [app.PRIMARY_DIRECTORY, app.MONITOR_DIRECTORY, app.PLOT_DIRECTORY]
    return ensure_directories_exist(required_directories)
    

def signal_handler(sig, frame):
    print('\nStopping all threads...\r')
    reset_terminal()  # Reset terminal before stopping
    stop_all()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def reset_terminal(app):
    """Reset terminal settings to default state without clearing the screen."""
    try:
        # Check if we're on Windows
        if sys.platform == 'win32' and not app.platform_manager.is_wsl():
            # Windows-specific terminal reset (no termios needed)
            # Just flush the output
            sys.stdout.flush()
            print("\n[Terminal input mode reset (Windows)]", end='\r\n', flush=True)
            return
            
        # For Unix-like systems (macOS and Linux)
        if app.platform_manager.termios is not None:
            # Reset terminal settings
            app.platform_manager.termios.tcsetattr(sys.stdin, app.platform_manager.termios.TCSADRAIN, app.platform_manager.termios.tcgetattr(sys.stdin))

            # Reset terminal modes without clearing screen
            safe_stty('sane')
            
            # DO NOT clear screen and reset cursor
            # print('\033[2J\033[H', end='')  # Commented out to preserve terminal history
            
            # Reset keyboard mode
            safe_stty('-raw -echo')
            
        # Flush stdout to ensure all output is displayed
        sys.stdout.flush()
        
        print("\n[Terminal input mode reset]", end='\r\n', flush=True)
        
    except Exception as e:
        print(f"Warning: Could not reset terminal: {e}", end='\r\n', flush=True)
        # Try alternative reset method WITHOUT clearing screen
        try:
            # Using stty directly instead of full reset
            safe_stty('sane')
        except:
            pass

def getch(app):
    """Simple getch implementation for Linux."""
    try:
        if app.platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            old = app.platform_manager.termios.tcgetattr(fd)
            new = app.platform_manager.termios.tcgetattr(fd)
            new[3] = new[3] & ~app.platform_manager.termios.ICANON & ~app.platform_manager.termios.ECHO
            new[6][app.platform_manager.termios.VMIN] = 1
            new[6][app.platform_manager.termios.VTIME] = 0
            app.platform_manager.termios.tcsetattr(fd, app.platform_manager.termios.TCSANOW, new)
            try:
                c = os.read(fd, 1)
                return c.decode('utf-8')
            finally:
                app.platform_manager.termios.tcsetattr(fd, app.platform_manager.termios.TCSAFLUSH, old)
        else:
            return input()[:1]
    except:
        return None

def get_key(app):
    """Get a single keypress from the user."""
    if app.platform_manager.msvcrt is not None:
        try:
            return app.platform_manager.msvcrt.getch().decode('utf-8')
        except Exception as e:
            print(f"Error reading key in Windows: {e}")
            return None
    else:
        try:
            if sys.platform == 'win32':
                # If we're on Windows but msvcrt failed, try alternative method
                try:
                    import msvcrt
                    if msvcrt.kbhit():
                        return msvcrt.getch().decode('utf-8')
                except ImportError:
                    print("Warning: msvcrt module not available on this Windows system", end='\r\n', flush=True)
                return None
            elif app.platform_manager.is_macos() or sys.platform.startswith('linux'):
                # Use termios for macOS and Linux
                try:
                    import termios
                    import tty
                    
                    old_settings = termios.tcgetattr(sys.stdin)
                    try:
                        tty.setraw(sys.stdin.fileno())
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            key = sys.stdin.read(1)
                            return key
                        return None
                    finally:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                except ImportError:
                    # Fallback if termios is not available
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        return sys.stdin.read(1)
                    return None
            else:
                # Fallback for other platforms
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    return sys.stdin.read(1)
                return None
        except Exception as e:
            if "termios" in str(e):
                # If termios fails, try alternative method
                try:
                    import msvcrt
                    if msvcrt.kbhit():
                        return msvcrt.getch().decode('utf-8')
                except:
                    pass
            print(f"Error reading key: {e}", end='\r\n', flush=True)
            return None

def get_api_name_for_device(device_id):
    device = sd.query_devices(device_id)
    hostapi_info = sd.query_hostapis(index=device['hostapi'])
    return hostapi_info['name']

def get_windows_sample_rate(device_name):
    """Get the actual sample rate from Windows using PyAudio."""
    try:
        p = pyaudio.PyAudio()
        
        # Find the device index that matches our device name
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:  # Only input devices
                if device_name.lower() in info["name"].lower():
                    sample_rate = int(info["defaultSampleRate"])  # Convert to integer
                    p.terminate()
                    return sample_rate
        
        p.terminate()
        return None
    except Exception as e:
        print(f"Error getting Windows sample rate: {e}")
        return None

def get_current_device_sample_rate(app,device_id):
    """Query the current sample rate of the device from the operating system."""
    try:
        # Get the current device configuration
        device_info = sd.query_devices(device_id, 'input')
        print(f"\nQuerying device {device_id} current sample rate...")
        print(f"Device name: {device_info['name']}")
        
        # Get the host API info
        if 'hostapi' in device_info:
            hostapi_info = sd.query_hostapis(index=device_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
        
        # First try to get the rate from Windows using PyAudio
        if not app.platform_manager.is_wsl():
            windows_rate = get_windows_sample_rate(device_info['name'])
            if windows_rate:
                print(f"Windows reported rate: {windows_rate} Hz")
                return windows_rate
        # Fallback to sounddevice if PyAudio method fails
        try:
            with sd.InputStream(device=device_id, channels=1, samplerate=None) as test_stream:
                current_rate = test_stream.samplerate
                print(f"Stream reported rate: {current_rate} Hz")
                if current_rate:
                    return current_rate
        except Exception as e:
            print(f"Stream creation failed: {e}")
        
        return None
        
    except Exception as e:
        print(f"Error querying device sample rate: {e}")
        return None

def print_all_input_devices():
    print("\nFull input device list (from sounddevice):\r")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            hostapi_info = sd.query_hostapis(index=device['hostapi'])
            api_name = hostapi_info['name']
            print(f"  [{i}] {device['name']} (API: {api_name}) | MaxCh: {device['max_input_channels']} | Default SR: {int(device['default_samplerate'])} Hz")
    print()
    sys.stdout.flush()



# #### version from BMAR_son.py ####

def timed_input(app, prompt, timeout=3, default='n'):
    """
    Get user input with a timeout and default value for headless operation.
    
    Args:
        prompt: The prompt to display to the user
        timeout: Timeout in seconds (default: 3)
        default: Default response if timeout or Enter is pressed (default: 'n')
        
    Returns:
        User input string or default value
    """
    
    # Print the prompt
    print(prompt, end='', flush=True)
    
    # Check if stdin is available (not redirected/piped)
    if not sys.stdin.isatty():
        print(f"[Headless mode] Using default: '{default}'")
        return default
    
    start_time = time.time()
    windows_method_failed = False
    
    # Platform-specific input handling
    if sys.platform == 'win32' and not app.platform_manager.is_wsl():
        # Windows implementation using msvcrt - import directly to avoid module issues
        try:
            import msvcrt as local_msvcrt
            user_input = ""
            while (time.time() - start_time) < timeout:
                try:
                    if local_msvcrt.kbhit():
                        char = local_msvcrt.getch().decode('utf-8', errors='ignore')
                        if char == '\r':  # Enter key
                            print()  # New line
                            return user_input.strip().lower() if user_input.strip() else default
                        elif char == '\b':  # Backspace
                            if user_input:
                                user_input = user_input[:-1]
                                print('\b \b', end='', flush=True)
                        elif char.isprintable():
                            user_input += char
                            print(char, end='', flush=True)
                except Exception as e:
                    # If msvcrt fails, fall back to Unix-style implementation
                    print(f"\n[Windows input failed, using fallback]: {e}")
                    windows_method_failed = True
                    break
                time.sleep(0.01)  # Small delay to prevent high CPU usage
        except ImportError:
            # msvcrt not available, use fallback
            print(f"\n[msvcrt not available, using fallback]")
            windows_method_failed = True
    
    # Unix/Linux/macOS implementation (or Windows fallback)
    if (sys.platform != 'win32' or  app.platform_manager.is_wsl() or windows_method_failed):
        # Reset start time if we're falling back from Windows method
        if windows_method_failed:
            start_time = time.time()
        
        # Check if we can use select on this platform
        try:
            # On Windows (non-WSL), select doesn't work with stdin, so use a different approach
            if sys.platform == 'win32' and not app.platform_manager.is_wsl():
                # Windows fallback - use a different approach since input() blocks
                # We'll use a simple loop that checks for available input without blocking
                print(f"\n[Windows fallback method activated]")
                
                # For Windows, we'll just do a simple timeout since threading with input() 
                # doesn't work properly for timeout scenarios
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    return default
                    
                # We can't implement proper non-blocking input on Windows easily,
                # so we'll just wait for the timeout period
                time.sleep(remaining_time)
                return default
                
            else:
                # Unix/Linux/macOS/WSL - use select
                while (time.time() - start_time) < timeout:
                    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if ready:
                        try:
                            user_input = sys.stdin.readline().strip()
                            return user_input.lower() if user_input else default
                        except:
                            break
        except Exception as e:
            # If select fails, fall back to basic timeout
            print(f"\n[Input method failed, using timeout fallback]: {e}")
            remaining_time = timeout - (time.time() - start_time)
            if remaining_time > 0:
                time.sleep(remaining_time)
    
    # Timeout occurred
    print(f"\n[Timeout after {timeout}s] Using default: '{default}'")
    return default


def set_input_device(app):
    """Find and configure a suitable audio input device based on settings in the app object."""
    logging.info("Scanning for audio input devices...")
    sys.stdout.flush()

    # Initialize testmode to True. It will be set to False upon success.
    app.testmode = True

    print_all_input_devices()

    try:
        # Get all devices
        devices = sd.query_devices()
        
        # First try the specified device_id if it exists
        if app.device_id is not None and app.device_id >= 0:
            try:
                device = sd.query_devices(app.device_id)
                if device['max_input_channels'] > 0:
                    print(f"\nTrying specified device [{app.device_id}]: {device['name']}")
                    print(f"  API: {sd.query_hostapis(index=device['hostapi'])['name']}")
                    print(f"  Max Channels: {device['max_input_channels']}")
                    print(f"  Default Sample Rate: {device['default_samplerate']} Hz")
                    
                    # Check channel compatibility and ask user permission if needed
                    original_channels = app.sound_in_chs
                    user_approved = True
                    
                    if app.sound_in_chs > device['max_input_channels']:
                        print(f"\nChannel mismatch detected:")
                        print(f"  Configuration requires: {original_channels} channels")
                        print(f"  Device supports: {device['max_input_channels']} channels")
                        response = timed_input(app,f"\nWould you like to proceed with {device['max_input_channels']} channel(s) instead? (y/N): ", timeout=3, default='n')

                        if response.lower() != 'y':
                            print("User declined to use fewer channels.")
                            print("Falling back to device search...")
                            user_approved = False
                        else:
                            app.sound_in_chs = device['max_input_channels']
                            print(f"Adjusting channel count from {original_channels} to {app.sound_in_chs}")
                    
                    if user_approved:
                        try:
                            # Try to set the sample rate using PyAudio first
                            if not app.platform_manager.is_wsl():
                                try:
                                    p = pyaudio.PyAudio()
                                    device_info = p.get_device_info_by_index(app.device_id)
                                    print(f"\nCurrent Windows sample rate: {device_info['defaultSampleRate']} Hz")
                                    
                                    # Try to open a stream with our desired sample rate
                                    stream = p.open(format=pyaudio.paInt16,
                                                  channels=app.sound_in_chs,
                                                  rate=app.PRIMARY_IN_SAMPLERATE,
                                                  input=True,
                                                  input_device_index=app.device_id,
                                                  frames_per_buffer=1024)
                                    
                                    # Verify the actual sample rate
                                    actual_rate = stream._get_stream_info()['sample_rate']
                                    print(f"PyAudio stream sample rate: {actual_rate} Hz")
                                    
                                    stream.close()
                                    p.terminate()
                                    
                                    if actual_rate != app.PRIMARY_IN_SAMPLERATE:
                                        print(f"\nWARNING: PyAudio could not set sample rate to {app.PRIMARY_IN_SAMPLERATE} Hz")
                                        print(f"Device is using {actual_rate} Hz instead")
                                        print("This may affect recording quality.")
                                except Exception as e:
                                    print(f"Warning: Could not set sample rate using PyAudio: {e}")
                            
                            # Now try with sounddevice
                            print("\nAttempting to configure device with sounddevice...")
                            sd.default.samplerate = app.PRIMARY_IN_SAMPLERATE
                            
                            with sd.InputStream(device=app.device_id, 
                                              channels=app.sound_in_chs,
                                              samplerate=app.PRIMARY_IN_SAMPLERATE,
                                              dtype=app._dtype,
                                              blocksize=1024) as stream:
                                # Verify the actual sample rate being used
                                actual_rate = stream.samplerate
                                if actual_rate != app.PRIMARY_IN_SAMPLERATE:
                                    print(f"\nWARNING: Requested sample rate {app.PRIMARY_IN_SAMPLERATE} Hz, but device is using {actual_rate} Hz")
                                    print("This may affect recording quality.")
                                
                                # If we get here, the device works with our settings
                                app.sound_in_id = app.device_id
                                print(f"\nSuccessfully configured specified device [{app.device_id}]")
                                print(f"Device Configuration:")
                                print(f"  Sample Rate: {actual_rate} Hz")
                                print(f"  Bit Depth: {app.PRIMARY_BITDEPTH} bits")
                                print(f"  Channels: {app.sound_in_chs}")
                                if original_channels != app.sound_in_chs:
                                    print(f"  Note: Channel count was adjusted from {original_channels} to {app.sound_in_chs}")
                                app.testmode = False
                                return True
                        except Exception as e:
                            print(f"\nERROR: Could not use specified device ID {app.device_id}")
                            print(f"Reason: {str(e)}")
                            response = timed_input(app,"\nThe specified device could not be used. Would you like to proceed with an alternative device? (y/N): ", timeout=3, default='n')
                            if response.lower() != 'y':
                                print("Exiting as requested.")
                                sys.exit(1)
                            print("Falling back to device search...")
                else:
                    print(f"\nERROR: Specified device ID {app.device_id} is not an input device")
                    response = timed_input(app,"\nThe specified device is not an input device. Would you like to proceed with an alternative device? (y/N): ", timeout=3, default='n')
                    if response.lower() != 'y':
                        print("Exiting as requested.")
                        sys.exit(1)
                    print("Falling back to device search...")
            except Exception as e:
                print(f"\nERROR: Could not access specified device ID {app.device_id}")
                print(f"Reason: {str(e)}")
                response = timed_input(app,"\nThe specified device could not be accessed. Would you like to proceed with an alternative device? (y/N): ", timeout=3, default='n')
                if response.lower() != 'y':
                    print("Exiting as requested.")
                    sys.exit(1)
                print("Falling back to device search...")
        else:
            print("\nNo device ID specified, skipping direct device configuration...")
        
        # Create a list of input devices with their IDs
        input_devices = [(i, device) for i, device in enumerate(devices) 
                        if device['max_input_channels'] > 0]
        
        # Sort by device ID in descending order
        input_devices.sort(reverse=True, key=lambda x: x[0])
        
        # If make_name is specified, try those devices first
        if app.make_name and app.make_name.strip():
            print(f"\nLooking for devices matching make name: {app.make_name}")
            matching_devices = [(i, device) for i, device in input_devices 
                              if app.make_name.lower() in device['name'].lower()]
            
            if matching_devices:
                print(f"Found {len(matching_devices)} devices matching make name")
                # Try matching devices first
                for dev_id, device in matching_devices:
                    print(f"\nTrying device [{dev_id}]: {device['name']}")
                    print(f"  API: {sd.query_hostapis(index=device['hostapi'])['name']}")
                    print(f"  Max Channels: {device['max_input_channels']}")
                    print(f"  Default Sample Rate: {device['default_samplerate']} Hz")
                    
                    # Auto-adjust channel count to match device capabilities
                    original_channels = app.sound_in_chs
                    actual_channels = min(app.sound_in_chs, device['max_input_channels'])
                    if actual_channels != app.sound_in_chs:
                        print(f"\nChannel mismatch detected:")
                        print(f"  Configuration requires: {app.sound_in_chs} channels")
                        print(f"  Device supports: {actual_channels} channels")
                        response = timed_input(app,f"\nWould you like to proceed with {actual_channels} channel(s) instead? (y/N): ", timeout=3, default='n')
                        if response.lower() != 'y':
                            print("Skipping this device...")
                            continue
                        app.sound_in_chs = actual_channels
                        print(f"Adjusting channel count from {original_channels} to {app.sound_in_chs}")
                    
                    try:
                        # Try to open a stream with our desired settings
                        with sd.InputStream(device=dev_id, 
                                          channels=app.sound_in_chs,  # Use adjusted channel count
                                          samplerate=app.PRIMARY_IN_SAMPLERATE,
                                          dtype=app._dtype,
                                          blocksize=1024) as stream:
                            # If we get here, the device works with our settings
                            app.sound_in_id = dev_id
                            print(f"\nSuccessfully configured device [{dev_id}]")
                            print(f"Device Configuration:")
                            print(f"  Sample Rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
                            print(f"  Bit Depth: {app.PRIMARY_BITDEPTH} bits")
                            print(f"  Channels: {app.sound_in_chs}")
                            if original_channels != app.sound_in_chs:
                                print(f"  Note: Channel count was auto-adjusted from {original_channels} to {app.sound_in_chs}")
                            app.testmode = False
                            return True
                            
                    except Exception as e:
                        print(f"\nERROR: Could not configure device [{dev_id}]")
                        print(f"  Failed to configure device: {str(e)}")
                        continue
            else:
                print(f"No devices found matching make name: {app.make_name}")
                print("Falling back to trying all devices...")
        
        # Try all devices if no matching devices were found or if make_name was empty
        for dev_id, device in input_devices:
            print(f"\nTrying device [{dev_id}]: {device['name']}")
            print(f"  API: {sd.query_hostapis(index=device['hostapi'])['name']}")
            print(f"  Max Channels: {device['max_input_channels']}")
            print(f"  Default Sample Rate: {device['default_samplerate']} Hz")
            
            # Auto-adjust channel count to match device capabilities
            original_channels = app.sound_in_chs
            actual_channels = min(app.sound_in_chs, device['max_input_channels'])
            if actual_channels != app.sound_in_chs:
                print(f"\nChannel mismatch detected:")
                print(f"  Configuration requires: {app.sound_in_chs} channels")
                print(f"  Device supports: {actual_channels} channels")
                response = timed_input(app,f"\nWould you like to proceed with {actual_channels} channel(s) instead? (y/N): ", timeout=3, default='n')
                if response.lower() != 'y':
                    print("Skipping this device...")
                    continue
                app.sound_in_chs = actual_channels
                print(f"Adjusting channel count from {original_channels} to {app.sound_in_chs}")
            
            try:
                # Try to open a stream with our desired settings
                with sd.InputStream(device=dev_id, 
                                  channels=app.sound_in_chs,  # Use adjusted channel count
                                  samplerate=app.PRIMARY_IN_SAMPLERATE,
                                  dtype=app._dtype,
                                  blocksize=1024) as stream:
                    # If we get here, the device works with our settings
                    app.sound_in_id = dev_id
                    print(f"\nSuccessfully configured device [{dev_id}]")
                    print(f"Device Configuration:")
                    print(f"  Sample Rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
                    print(f"  Bit Depth: {app.PRIMARY_BITDEPTH} bits")
                    print(f"  Channels: {app.sound_in_chs}")
                    if original_channels != app.sound_in_chs:
                        print(f"  Note: Channel count was auto-adjusted from {original_channels} to {app.sound_in_chs}")
                    app.testmode = False
                    return True
                    
            except Exception as e:
                print(f"  Failed to configure device: {str(e)}")
                continue
        
        print("\nNo devices could be configured with acceptable settings.")
        return False

    except Exception as e:
        print(f"\nError during device selection: {str(e)}")
        print("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        return False

# interruptable sleep
def interruptable_sleep(seconds, stop_sleep_event):
    for i in range(seconds*2):
        if stop_sleep_event.is_set():
            return
        time.sleep(0.5)

# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()

# for debugging
def list_all_threads():
    for thread in threading.enumerate():
        print(f"Thread name: {thread.name}, Thread ID: {thread.ident}, Alive: {thread.is_alive()}")


def clear_input_buffer(app):
    """Clear the keyboard input buffer. Handles both Windows and non-Windows platforms."""
    if sys.platform == 'win32' and not app.platform_manager.is_wsl():
        try:
            while app.platform_manager.msvcrt is not None and app.platform_manager.msvcrt.kbhit():
                app.platform_manager.msvcrt.getch()
        except Exception as e:
            print(f"Warning: Could not clear input buffer: {e}")
    else:
        # For macOS and Linux/WSL
        if app.platform_manager.termios is not None and app.platform_manager.tty is not None:
            fd = sys.stdin.fileno()
            try:
                # Save old terminal settings
                old_settings = app.platform_manager.termios.tcgetattr(fd)

                # Set non-blocking mode
                app.platform_manager.tty.setraw(fd, app.platform_manager.termios.TCSANOW)

                # Read all pending input
                while select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.read(1)
                    
                # One more time with a short timeout
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if rlist:
                    sys.stdin.read(len(rlist))
            finally:
                # Restore settings
                try:
                    app.platform_manager.termios.tcsetattr(fd, app.platform_manager.termios.TCSADRAIN, old_settings)
                except Exception as e:
                    print(f"Warning during terminal reset: {e}")
        else:
            # Silent fail or fallback - do NOT use stty on Windows
            if not sys.platform == 'win32':
                try:
                    # Last resort for Unix-like systems
                    safe_stty('-raw echo')
                except:
                    pass


def show_audio_device_info_for_SOUND_IN_OUT(app):
    """Display detailed information about the selected audio input and output devices."""
    print("\nSelected Audio Device Information:")
    print("-" * 50)
    
    # Get and display input device info
    try:
        input_info = sd.query_devices(app.sound_in_id)
        print("\nInput Device:")
        print(f"Name: [{app.sound_in_id}] {input_info['name']}")
        print(f"Default Sample Rate: {int(input_info['default_samplerate'])} Hz")
        print(f"Bit Depth: {app.config.PRIMARY_BITDEPTH} bits")
        print(f"Max Input Channels: {input_info['max_input_channels']}")
        print(f"Current Sample Rate: {int(app.config.PRIMARY_IN_SAMPLERATE)} Hz")
        print(f"Current Channels: {app.sound_in_chs}")
        if 'hostapi' in input_info:
            hostapi_info = sd.query_hostapis(index=input_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting input device info: {e}")
    
    # Get and display output device info
    try:
        output_info = sd.query_devices(app.sound_out_id)
        print("\nOutput Device:")
        print(f"Name: [{app.sound_out_id}] {output_info['name']}")
        print(f"Default Sample Rate: {int(output_info['default_samplerate'])} Hz")
        print(f"Max Output Channels: {output_info['max_output_channels']}")
        if 'hostapi' in output_info:
            hostapi_info = sd.query_hostapis(index=output_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting output device info: {e}")
    
    print("-" * 50)
    sys.stdout.flush()


def show_audio_device_info_for_defaults():
    print("\nsounddevices default device info:")
    default_input_info = sd.query_devices(kind='input')
    default_output_info = sd.query_devices(kind='output')
    print(f"\nDefault Input Device: [{default_input_info['index']}] {default_input_info['name']}")
    print(f"Default Output Device: [{default_output_info['index']}] {default_output_info['name']}\n")


def show_audio_device_list(app):
    """Display detailed information about the selected audio input and output devices."""
    print("\nSelected Audio Device Information:")
    print("-" * 50)
    
    # Get and display input device info
    try:
        input_info = sd.query_devices(app.sound_in_id)
        print("\nInput Device:")
        print(f"Name: [{app.sound_in_id}] {input_info['name']}")
        print(f"Default Sample Rate: {int(input_info['default_samplerate'])} Hz")
        print(f"Bit Depth: {app.config.PRIMARY_BITDEPTH} bits")
        print(f"Max Input Channels: {input_info['max_input_channels']}")
        print(f"Current Sample Rate: {int(app.config.PRIMARY_IN_SAMPLERATE)} Hz")
        print(f"Current Channels: {app.sound_in_chs}")
        if 'hostapi' in input_info:
            app.hostapi_info = sd.query_hostapis(index=input_info['hostapi'])
            print(f"Audio API: {app.hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting input device info: {e}")
    
    # Get and display output device info
    try:
        app.output_info = sd.query_devices(app.sound_out_id)
        print("\nOutput Device:")
        print(f"Name: [{app.sound_out_id}] {app.output_info['name']}")
        print(f"Default Sample Rate: {int(app.output_info['default_samplerate'])} Hz")
        print(f"Max Output Channels: {app.output_info['max_output_channels']}")
        if 'hostapi' in app.output_info:
            app.hostapi_info = sd.query_hostapis(index=app.output_info['hostapi'])
            print(f"Audio API: {app.hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting output device info: {e}")
    
    print("-" * 50)
    sys.stdout.flush()


def show_detailed_device_list(app):
    """Display a detailed list of all audio devices with input/output indicators."""
    print("\nAudio Device List:")
    print("-" * 80)
    
    app.devices = sd.query_devices()
    for i, device in enumerate(app.devices):
        # Get API name
        app.hostapi_info = sd.query_hostapis(index=device['hostapi'])
        api_name = app.hostapi_info['name']

        # Determine if device is input, output, or both
        in_channels = device['max_input_channels']
        out_channels = device['max_output_channels']
        
        # Create prefix based on device type and whether it's the active device
        if i == app.sound_in_id and in_channels > 0:
            prefix = ">"
        elif i == app.sound_out_id and out_channels > 0:
            prefix = "<"
        else:
            prefix = " "
            
        # Format the device name to fit in 40 characters
        app.device_name = device['name']
        if len(app.device_name) > 40:
            app.device_name = app.device_name[:37] + "..."

        # Print the device information
        print(f"{prefix} {i:2d} {app.device_name:<40} {api_name} ({in_channels} in, {out_channels} out)")

    print("-" * 80)
    sys.stdout.flush()


def get_enabled_mic_locations(app):
    """
    Reads microphone enable states (MIC_1 to MIC_4) and maps to their corresponding locations.
    """
    # Define microphone states and corresponding locations
    mic_location_names = [app.config.MIC_LOCATION[i] for i, enabled in enumerate(app.MICS_ACTIVE) if enabled]
    return mic_location_names

##mic_location_names = get_enabled_mic_locations()
def show_mic_locations(app):
    print("Enabled microphone locations:", get_enabled_mic_locations(app))


def is_mic_position_in_bounds(mic_list, position):
  """
  Checks if the mic is present in the hive and powered on.
  Args:
    data: A list of boolean values (True/False) or integers (1/0).
    position: The index of the element to check.
  Returns:
    status of mic at position
  """
  try:
    return bool(mic_list[position])
  except IndexError:
    print(f"Error: mic {position} is out of bounds.")
    return False  


def check_stream_status(app, stream_duration):
    """
    Check the status of a sounddevice input stream for overflows and underflows.
    Parameters:
    - app: BmarApp instance containing audio device configuration
    - stream_duration: Duration for which the stream should be open and checked (in seconds).
    """
    print(f"Checking input stream for overflow. Watching for {stream_duration} seconds")

    # Define a callback function to process the audio stream
    def callback(indata, frames, time, status):
        if status and status.input_overflow:
                print("Input overflow detected at:", datetime.datetime.now())

    # Open an input stream
    with sd.InputStream(callback=callback, device=app.sound_in_id) as stream:
        # Run the stream for the specified duration
        timeout = time.time() + stream_duration
        while time.time() < timeout:
            time.sleep(0.1)  # Sleep for a short duration before checking again

    print("Stream checking finished at", datetime.datetime.now())
    show_audio_device_info_for_SOUND_IN_OUT(app)


# fetch the most recent audio file in the directory
def find_file_of_type_with_offset_1(app, offset=0):
    # Expand path if it contains a tilde
    expanded_dir = os.path.expanduser(app.config.PRIMARY_DIRECTORY)
    
    # Ensure directory exists
    if not os.path.exists(expanded_dir):
        print(f"Directory does not exist: {expanded_dir}")
        return None
        
    try:
        matching_files = [os.path.join(expanded_dir, f) for f in os.listdir(expanded_dir) \
                          if os.path.isfile(os.path.join(expanded_dir, f)) and f.endswith(f".{app.config.PRIMARY_FILE_FORMAT.lower()}")]
        if offset < len(matching_files):
            return matching_files[offset]
    except Exception as e:
        print(f"Error listing files in {expanded_dir}: {e}")
    
    return None

# return the most recent audio file in the directory minus offset (next most recent, etc.)
def find_file_of_type_with_offset(app, offset):
    # Expand path if it contains a tilde
    expanded_dir = os.path.expanduser(app.config.PRIMARY_DIRECTORY)
    
    print(f"\nSearching for {app.config.PRIMARY_FILE_FORMAT} files in: {expanded_dir}")
    
    # Ensure directory exists
    if not os.path.exists(expanded_dir):
        print(f"Directory does not exist: {expanded_dir}")
        return None
        
    try:
        # List all files in the directory first
        all_files = os.listdir(expanded_dir)
        print(f"All files in directory: {all_files}")
        
        # List all files of the specified type in the directory (case-insensitive)
        files_of_type = [f for f in all_files if os.path.isfile(os.path.join(expanded_dir, f)) and f.lower().endswith(f".{app.config.PRIMARY_FILE_FORMAT.lower()}")]
        
        if not files_of_type:
            print(f"No {app.config.PRIMARY_FILE_FORMAT} files found in directory: {expanded_dir}")
            print(f"Looking for files ending with: .{app.config.PRIMARY_FILE_FORMAT.lower()} (case-insensitive)")
            return None
            
        # Sort files alphabetically - most recent first
        files_of_type.sort(reverse=True)
        print(f"Found {len(files_of_type)} {app.config.PRIMARY_FILE_FORMAT} files: {files_of_type}")
        
        if offset < len(files_of_type):
            selected_file = files_of_type[offset]
            print(f"Selected file at offset {offset}: {selected_file}")
            return selected_file
        else:
            print(f"Offset {offset} is out of range. Found {len(files_of_type)} {app.config.PRIMARY_FILE_FORMAT} files.")
            return None
    except Exception as e:
        print(f"Error listing files in {expanded_dir}: {e}")
    
    return None


def time_between():
    # Using a list to store the last called time because lists are mutable and can be modified inside the nested function.
    # This will act like a "nonlocal" variable.
    last_called = [None]
    
    def helper():
        current_time = time.time()
        if last_called[0] is None:
            last_called[0] = current_time
            return 1800
        diff = current_time - last_called[0]
        last_called[0] = current_time
        return min(diff, 1800)
    # Return the helper function, NOT A VALUE.
    return helper

# Initialize the function 'time_diff()', which will return a value.
time_diff = time_between()
# wlh: why does this print on the cli when keyboard 's' iniates plot spectrogram?
###print("time diff from the outter script", time_diff())   # 0

# #############################################################
# Audio conversion functions
# #############################################################

# convert audio to mp3 and save to file using downsampled data
def pcm_to_mp3_write(np_array, full_path):
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
            if config.AUDIO_MONITOR_QUALITY >= 64 and config.AUDIO_MONITOR_QUALITY <= 320:    # use constant bitrate, 64k would be the min, 320k the best
                cbr = str(config.AUDIO_MONITOR_QUALITY) + "k"
                audio_segment.export(full_path, format="mp3", bitrate=cbr)
            elif config.AUDIO_MONITOR_QUALITY < 10:                      # use variable bitrate, 0 to 9, 0 is highest quality
                audio_segment.export(full_path, format="mp3", parameters=["-q:a", "0"])
            else:
                print("Don't know of a mp3 mode with parameter:", config.AUDIO_MONITOR_QUALITY)
                quit(-1)
        except Exception as e:
            if "ffmpeg" in str(e).lower():
                print("\nError: ffmpeg not found. Please install ffmpeg:")
                print("1. Download ffmpeg from https://www.gyan.dev/ffmpeg/builds/")
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


# downsample audio to a lower sample rate
def downsample_audio(audio_data, orig_sample_rate, target_sample_rate):
    # Convert audio to float for processing
    audio_float = audio_data.astype(np.float32) / np.iinfo(np.int16).max
    downsample_ratio = int(orig_sample_rate / target_sample_rate)

    # Define an anti-aliasing filter
    nyq = 0.5 * orig_sample_rate
    low = 0.5 * target_sample_rate
    low = low / nyq
    b, a = butter(5, low, btype='low')

    # If audio is stereo, split channels
    if audio_float.shape[1] == 2:
        left_channel = audio_float[:, 0]
        right_channel = audio_float[:, 1]
    else:
        # If not stereo, duplicate the mono channel
        left_channel = audio_float.ravel()
        right_channel = audio_float.ravel()

    # Apply the Nyquist filter for each channel
    left_filtered = filtfilt(b, a, left_channel)
    right_filtered = filtfilt(b, a, right_channel)
    # and downsample each channel 
    left_downsampled = left_filtered[::downsample_ratio]
    right_downsampled = right_filtered[::downsample_ratio]
    # Combine the two channels back into a stereo array
    downsampled_audio_float = np.column_stack((left_downsampled, right_downsampled))
    # Convert back to int16
    downsampled_audio = (downsampled_audio_float * np.iinfo(np.int16).max).astype(np.int16)
    return downsampled_audio


# #############################################################
# signal display functions
# #############################################################


def get_default_output_device():
    devices = sd.query_devices()
    for device in devices:
        if device['max_output_channels'] > 0:
            return device['name']
    return None

def create_progress_bar(current, total, bar_length=50):
    """Create a progress bar string.
    Args:
        current: Current progress value
        total: Total value
        bar_length: Length of the progress bar (default 50)
    Returns:
        String representation of progress bar like [######     ]
    """
    if total == 0:
        return f"[{'#' * bar_length}] 100%"
    
    # Ensure current doesn't exceed total
    current = min(current, total)
    
    # Calculate percentage (0-100)
    percent = int(current * 100 / total)
    
    # Calculate filled length, ensuring it can reach full bar_length
    if current >= total:
        filled_length = bar_length  # Force full bar when complete
    else:
        filled_length = int(bar_length * current / total)
    
    bar = '#' * filled_length + ' ' * (bar_length - filled_length)
    
    return f"[{bar}] {percent}%"


def _record_audio_pyaudio(duration, sound_in_id, sound_in_chs, stop_queue, task_name="audio recording"):
    """
    Helper function to record a chunk of audio using PyAudio and return it as a numpy array.
    This function encapsulates the PyAudio stream setup, callback, and teardown.
    """
    p = pyaudio.PyAudio()
    recording = None
    try:
        device_info = p.get_device_info_by_index(sound_in_id)
        max_channels = int(device_info['maxInputChannels'])
        
        actual_channels = min(sound_in_chs, max_channels)
        actual_channels = max(1, actual_channels)

        logging.info(f"Starting {task_name} for {duration:.1f}s on {actual_channels} channel(s).")

        num_frames = int(config.PRIMARY_IN_SAMPLERATE * duration)
        chunk_size = 4096
        
        recording_array = np.zeros((num_frames, actual_channels), dtype=np.float32)
        frames_recorded = 0
        recording_complete = False

        def callback(indata, frame_count, time_info, status):
            nonlocal frames_recorded, recording_complete
            try:
                if status:
                    logging.warning(f"PyAudio stream status: {status}")
                if frames_recorded < num_frames and not recording_complete:
                    data = np.frombuffer(indata, dtype=np.float32)
                    if len(data) > 0:
                        start_idx = frames_recorded
                        end_idx = min(start_idx + len(data) // actual_channels, num_frames)
                        data = data.reshape(-1, actual_channels)
                        recording_array[start_idx:end_idx] = data[:(end_idx - start_idx)]
                        frames_recorded += len(data) // actual_channels
                        if frames_recorded >= num_frames:
                            recording_complete = True
                            return (None, pyaudio.paComplete)
                return (None, pyaudio.paContinue)
            except Exception as e:
                logging.error(f"Error in PyAudio callback: {e}", exc_info=True)
                recording_complete = True
                return (None, pyaudio.paAbort)

        stream = p.open(format=pyaudio.paFloat32,
                        channels=actual_channels,
                        rate=int(config.PRIMARY_IN_SAMPLERATE),
                        input=True,
                        input_device_index=sound_in_id,
                        frames_per_buffer=chunk_size,
                        stream_callback=callback)
        
        stream.start_stream()
        
        start_time = time.time()
        timeout = duration + 10
        
        while not recording_complete and stop_queue.empty() and (time.time() - start_time) < timeout:
            progress_bar = create_progress_bar(frames_recorded, num_frames)
            print(f"Recording progress: {progress_bar}", end='\r')
            time.sleep(0.1)
        
        # Ensure we show 100% completion when done
        if recording_complete or frames_recorded >= num_frames:
            progress_bar = create_progress_bar(num_frames, num_frames)  # Force 100%
            print(f"Recording progress: {progress_bar}", end='\r')
        
        stream.stop_stream()
        stream.close()
        
        print() # Newline after progress bar
        if frames_recorded < num_frames * 0.9:
            logging.warning(f"Recording incomplete: only got {frames_recorded}/{num_frames} frames.")
            return None, 0
        
        logging.info(f"Finished {task_name}.")
        return recording_array, actual_channels

    except Exception as e:
        logging.error(f"Failed to record audio with PyAudio for {task_name}", exc_info=True)
        return None, 0
    finally:
        if p:
            try:
                p.terminate()
                time.sleep(0.1) # Allow time for resources to be released
            except Exception as e:
                logging.error(f"Error terminating PyAudio instance for {task_name}", exc_info=True)

# #############################################################
# Plotting functions    
# #############################################################

def cleanup_process(app, command):
    """Clean up a specific command's process."""
    try:
        # Check if the command key exists in active_processes
        if command in app.active_processes:
            process = app.active_processes[command]
            if process is not None:
                try:
                    # Check if it's still alive without raising an exception
                    if hasattr(process, 'is_alive') and process.is_alive():
                        try:
                            process.terminate()
                            process.join(timeout=1)
                            if process.is_alive():
                                process.kill()
                        except Exception as e:
                            print(f"Error terminating process for command '{command}': {e}")
                except Exception as e:
                    # Process may no longer exist or be accessible
                    print(f"Warning: Could not check process status for command '{command}': {e}")
                
                # Reset the process reference
                app.active_processes[command] = None
                print(f"Process for command '{command}' has been cleaned up")
        else:
            # The command doesn't exist in our tracking dictionary
            print(f"Warning: No process tracking for command '{command}'")
    except Exception as e:
        print(f"Error in cleanup_process for command '{command}': {e}")


# single-shot plot of 'n' seconds of audio of each channels for an oscope view
def plot_oscope(app_config, queue): 
    try:
        # Force garbage collection before starting
        gc.collect()
        
        # Ensure clean matplotlib state for this process
        import matplotlib
        matplotlib.use('Agg', force=True)
        import matplotlib.pyplot as plt
        plt.close('all')  # Close any existing figures
        
        # Brief delay to ensure clean audio device state
        time.sleep(0.1)
        
        # Extract configuration from app_config dictionary
        sound_in_id = app_config['sound_in_id']
        sound_in_chs = app_config['sound_in_chs']
        trace_duration = app_config['trace_duration']
        oscope_gain_db = app_config['oscope_gain_db']
        primary_in_samplerate = app_config['primary_in_samplerate']
        plot_directory = app_config['plot_directory']
        primary_bitdepth = app_config['primary_bitdepth']
        location_id = app_config['location_id']
        hive_id = app_config['hive_id']
        is_wsl = app_config['is_wsl']
        is_macos = app_config['is_macos']
            
        recording, actual_channels = _record_audio_pyaudio(
            trace_duration, sound_in_id, sound_in_chs, queue, "oscilloscope traces"
        )
        
        if recording is None:
            logging.error("Failed to record audio for oscilloscope.")
            return

        # Apply gain if needed
        if oscope_gain_db > 0:
            gain = 10 ** (oscope_gain_db / 20)      
            logging.info(f"Applying gain of: {gain:.1f}") 
            recording *= gain

        logging.info("Creating oscilloscope plot...")
        # Create figure with reduced DPI for better performance
        fig = plt.figure(figsize=(10, 3 * actual_channels), dpi=80)
        
        # Optimize plotting by downsampling for display
        downsample_factor = max(1, len(recording) // 5000)  # Limit points to ~5k for better performance
        time_points = np.arange(0, len(recording), downsample_factor) / primary_in_samplerate
        
        # Plot each channel
        for i in range(actual_channels):
            ax = plt.subplot(actual_channels, 1, i+1)
            ax.plot(time_points, recording[::downsample_factor, i], linewidth=0.5)
            ax.set_title(f"Oscilloscope Traces w/{oscope_gain_db}dB Gain--Ch{i+1}")
            ax.set_xlabel('Time (seconds)')
            ax.set_ylim(-1.0, 1.0)
            
            # Add graticule
            # Horizontal line at 0
            ax.axhline(y=0, color='gray', linewidth=0.5, alpha=0.7)
            
            # Vertical lines at each second
            max_time = time_points[-1]
            for t in range(0, int(max_time) + 1):
                ax.axvline(x=t, color='gray', linewidth=0.5, alpha=0.5)
            
            # Add minor vertical lines at 0.5 second intervals
            for t in np.arange(0.5, max_time, 0.5):
                ax.axvline(x=t, color='gray', linewidth=0.3, alpha=0.3, linestyle='--')
            
            # Configure grid and ticks
            ax.set_xticks(range(0, int(max_time) + 1))
            ax.set_yticks([-1.0, -0.5, 0, 0.5, 1.0])
            ax.tick_params(axis='both', which='both', labelsize=8)
        
        plt.tight_layout()

        # Save the plot
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        plotname = os.path.join(plot_directory, f"{timestamp}_oscope_{int(primary_in_samplerate/1000)}_kHz_{primary_bitdepth}_{location_id}_{hive_id}.png")
        logging.info(f"Saving oscilloscope plot to: {plotname}")
        
        # Make sure the directory exists
        os.makedirs(os.path.dirname(plotname), exist_ok=True)
        
        # Display the expanded path
        expanded_path = os.path.abspath(os.path.expanduser(plotname))
        logging.info(f"Absolute path: {expanded_path}")
        
        # Save with optimized settings
        logging.info("Saving figure...")
        plt.savefig(expanded_path, dpi=80, bbox_inches='tight', pad_inches=0.1, format='png')
        logging.info("Plot saved successfully")
        plt.close('all')  # Close all figures

        # Open the saved image based on OS
        try:
            if is_wsl:
                logging.info("Opening image in WSL...")
                try:
                    subprocess.Popen(['xdg-open', expanded_path])
                except FileNotFoundError:
                    subprocess.Popen(['wslview', expanded_path])
                logging.info("Image viewer command executed")
            elif is_macos:
                logging.info("Opening image in macOS...")
                subprocess.Popen(['open', expanded_path])
                logging.info("Image viewer command executed")
            elif sys.platform == 'win32':
                logging.info("Opening image in Windows...")
                os.startfile(expanded_path)
                logging.info("Image viewer command executed")
            else:
                logging.info("Opening image in Linux...")
                subprocess.Popen(['xdg-open', expanded_path])
                logging.info("Image viewer command executed")

        except Exception as e:
            logging.error(f"Could not open image viewer: {e}")
            logging.info(f"Image saved at: {expanded_path}")
            
    except Exception as e:
        logging.error(f"Error in oscilloscope recording: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure cleanup happens
        try:
            plt.close('all')
            gc.collect()
        except:
            pass


def trigger_oscope(app):
    """Trigger oscilloscope plot generation with proper cleanup."""
    try:
        # Clean up any existing process
        cleanup_process(app,'o')
        clear_input_buffer(app)

        # Create a queue for communication
        stop_queue = multiprocessing.Queue()
        
        # Get configuration dictionary for oscilloscope subprocess
        app_config = app.get_subprocess_config()
        
        # Create and configure the process
        app.oscope_process = multiprocessing.Process(
            target=plot_oscope, 
            args=(app_config, stop_queue)
        )
        
        # Set process as daemon
        app.oscope_process.daemon = True
        
        # Store in active processes
        app.active_processes['o'] = app.oscope_process
        
        print("Starting oscilloscope process...")
        # Start the process
        app.oscope_process.start()

        # Wait for completion with timeout
        timeout = app.config.TRACE_DURATION + 30  # Reduced timeout to be more responsive
        app.oscope_process.join(timeout=timeout)

        # Check if process is still running
        if app.oscope_process.is_alive():
            print("\nOscilloscope process taking too long, terminating...")
            try:
                # Signal the process to stop
                stop_queue.put(True)
                # Give it a moment to clean up
                time.sleep(1)
                # Then terminate if still running
                if app.oscope_process.is_alive():
                    app.oscope_process.terminate()
                    app.oscope_process.join(timeout=2)
                    if app.oscope_process.is_alive():
                        app.oscope_process.kill()
            except Exception as e:
                print(f"Error terminating oscilloscope process: {e}")
        
    except Exception as e:
        print(f"Error in trigger_oscope: {e}")
        traceback.print_exc()
    finally:
        # Always ensure cleanup
        cleanup_process(app,'o')
        clear_input_buffer(app)
        print("Oscilloscope process completed")





# Global variables for buffer management
buffer_wrap_event = threading.Event()


def callback(app, indata, frames, time, status):
    """Callback function for audio input stream."""
    if status:
        print("Callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    data_len = len(indata)

    # managing the circular buffer
    if app.buffer_index + data_len <= app.buffer_size:
        app.buffer[app.buffer_index:app.buffer_index + data_len] = indata
        buffer_wrap_event.clear()
    else:
        overflow = (app.buffer_index + data_len) - app.buffer_size
        app.buffer[app.buffer_index:] = indata[:-overflow]
        app.buffer[:overflow] = indata[-overflow:]
        buffer_wrap_event.set()

    app.buffer_index = (app.buffer_index + data_len) % app.buffer_size


def setup_audio_circular_buffer(app):
    """Set up the circular buffer for audio recording."""
    # Calculate buffer size and initialize buffer
    app.buffer_size = int(app.BUFFER_SECONDS * app.PRIMARY_IN_SAMPLERATE)
    app.buffer = np.zeros((app.buffer_size, app.sound_in_chs), dtype=app._dtype)
    app.buffer_index = 0
    app.buffer_wrap = False
    app.blocksize = 8196
    buffer_wrap_event.clear()
    
    print(f"\naudio buffer size: {sys.getsizeof(app.buffer)}\n")
    sys.stdout.flush()


def recording_worker_thread(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
    """Worker thread for recording audio to files."""
    
    if start_tod is None:
        print(f"{thread_id} is recording continuously\r")

    samplerate = app.PRIMARY_IN_SAMPLERATE

    while not app.stop_recording_event.is_set():
        try:
            current_time = datetime.datetime.now().time()
            
            if start_tod is None or (start_tod <= current_time <= end_tod):        
                print(f"{app.thread_id} started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec\n\r")

                app.period_start_index = app.buffer_index 
                # wait PERIOD seconds to accumulate audio
                interruptable_sleep(record_period, app.stop_recording_event)

                # Check if we're shutting down before saving
                if app.stop_recording_event.is_set():
                    break

                period_end_index = app.buffer_index 
                save_start_index = app.period_start_index % app.buffer_size
                save_end_index = app.period_end_index % app.buffer_size

                # saving from a circular buffer so segments aren't necessarily contiguous
                if save_end_index > save_start_index:   # indexing is contiguous
                    audio_data = app.buffer[save_start_index:save_end_index]
                else:                                   # ain't contiguous so concatenate to make it contiguous
                    audio_data = np.concatenate((app.buffer[save_start_index:], app.buffer[:save_end_index]))

                # Determine the sample rate to use for saving
                save_sample_rate = app.PRIMARY_SAVE_SAMPLERATE if app.PRIMARY_SAVE_SAMPLERATE is not None else app.PRIMARY_IN_SAMPLERATE
                
                # Resample if needed
                if save_sample_rate < app.PRIMARY_IN_SAMPLERATE:
                    # resample to lower sample rate
                    audio_data = downsample_audio(audio_data, app.PRIMARY_IN_SAMPLERATE, save_sample_rate)
                    print(f"Resampling from {app.PRIMARY_IN_SAMPLERATE}Hz to {save_sample_rate}Hz for saving")

                # Check if we're shutting down before saving
                if app.stop_recording_event.is_set():
                    break

                # Check and create new date folders if needed
                if not check_and_create_date_folders(app):
                    print(f"Warning: Could not create/verify date folders for {thread_id}")
                    continue

                # Calculate the saving sample rate for the filename
                filename_sample_rate = int(save_sample_rate)
                
                # Generate timestamp and filename
                timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"{timestamp}_{filename_sample_rate}_{app.PRIMARY_BITDEPTH}_{thread_id}_{app.config.LOCATION_ID}_{app.config.HIVE_ID}.{file_format.lower()}"
                
                # Choose directory based on thread type
                if "Audio_monitor" in thread_id:
                    file_path = os.path.join(app.MONITOR_DIRECTORY, filename)
                else:
                    file_path = os.path.join(app.PRIMARY_DIRECTORY, filename)

                try:
                    # Save the audio data
                    if file_format.upper() == 'FLAC':
                        sf.write(file_path, audio_data, int(save_sample_rate), subtype=app._subtype)
                    elif file_format.upper() == 'WAV':
                        sf.write(file_path, audio_data, int(save_sample_rate), subtype=app._subtype)
                    elif file_format.upper() == 'MP3':
                        # Convert to MP3 using pydub
                        pcm_to_mp3_write(audio_data, file_path)
                    else:
                        logging.error(f"Unsupported file format: {file_format}")
                        continue
                        
                    logging.info(f"{thread_id} saved: {filename}\r")
                    
                except Exception as e:
                    logging.error(f"Error saving {filename}: {e}")
                    continue

                # Wait for the next recording interval
                if not app.stop_recording_event.is_set():
                    interruptable_sleep(interval, app.stop_recording_event)
            else:
                # Not in recording time window, wait briefly and check again
                interruptable_sleep(10, app.stop_recording_event)
                
        except Exception as e:
            logging.error(f"Error in {thread_id}: {e}")
            if not app.stop_recording_event.is_set():
                interruptable_sleep(30, app.stop_recording_event)  # Wait before retrying


def ensure_directories_exist(directories):
    """
    Check if directories exist and create them if necessary.
    Args:
        directories: List of directory paths to check and create
    Returns:
        bool: True if all directories exist or were created, False otherwise
    """
    # Expand any home directory tildes
    expanded_dirs = [os.path.expanduser(d) for d in directories]
    
    # Check which directories don't exist
    missing_dirs = [d for d in expanded_dirs if not os.path.exists(d)]
    
    if not missing_dirs:
        return True
    
    print("\nCreating the following directories:")
    for d in missing_dirs:
        print(f"  - {d}")
    
    success = True
    for d in missing_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            
            # Verify directory was created
            if os.path.exists(d):
                logging.info(f"Created directory: {d}")
            else:
                logging.error(f"Failed to create directory: {d} (Unknown error)")
                success = False
        except Exception as e:
            logging.error(f"Error creating directory {d}: {e}")
            success = False
            # Additional debugging for permission issues
            if "Permission denied" in str(e):
                logging.error(f"  This appears to be a permissions issue. Current user may not have write access.")
                logging.error(f"  Current working directory: {os.getcwd()}")
                try:
                    parent_dir = os.path.dirname(d)
                    logging.info(f"  Parent directory exists: {os.path.exists(parent_dir)}")
                    if os.path.exists(parent_dir):
                        logging.info(f"  Parent directory permissions: {oct(os.stat(parent_dir).st_mode)[-3:]}")
                except Exception as e2:
                    logging.error(f"  Error checking parent directory: {e2}")
        return success


def reset_terminal_settings(app):
    """Reset terminal settings to default state without clearing the screen."""
    try:
        if app.platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            old_settings = app.platform_manager.termios.tcgetattr(fd)
            app.platform_manager.termios.tcsetattr(fd, app.platform_manager.termios.TCSANOW, old_settings)
    except Exception as e:
        logging.warning(f"Could not reset terminal settings: {e}")


def audio_stream(app):
    """Main audio streaming function."""
    
    # Reset terminal settings before printing
    reset_terminal_settings(app)

    # Print initialization info with forced output
    logging.info("Initializing audio stream...")
    logging.info(f"Device ID: [{app.sound_in_id}]")
    logging.info(f"Channels: {app.sound_in_chs}")
    logging.info(f"Sample Rate: {int(app.PRIMARY_IN_SAMPLERATE)} Hz")
    logging.info(f"Bit Depth: {app.PRIMARY_BITDEPTH} bits")
    logging.info(f"Data Type: {app._dtype}")

    try:
        # First verify the device configuration
        device_info = sd.query_devices(app.sound_in_id)
        logging.info("Selected device info:")
        logging.info(f"Name: [{app.sound_in_id}] {device_info['name']}")
        logging.info(f"Max Input Channels: {device_info['max_input_channels']}")
        logging.info(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz")

        if device_info['max_input_channels'] < app.sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {app.sound_in_chs} channels are required")

        # Set the device's sample rate to match our configuration
        sd.default.samplerate = app.PRIMARY_IN_SAMPLERATE
        
        # Create a partial function to pass app to the callback
        app_callback = lambda indata, frames, time, status: callback(app, indata, frames, time, status)
        
        # Initialize the stream with the configured sample rate and bit depth
        stream = sd.InputStream(
            device=app.sound_in_id,
            channels=app.sound_in_chs,
            samplerate=app.PRIMARY_IN_SAMPLERATE,
            dtype=app._dtype,
            blocksize=app.blocksize,
            callback=app_callback
        )

        logging.info("Audio stream initialized successfully")
        logging.info(f"Stream sample rate: {stream.samplerate} Hz")
        logging.info(f"Stream bit depth: {app.PRIMARY_BITDEPTH} bits")

        with stream:
            # start the recording worker threads
            if hasattr(app.config, 'MODE_AUDIO_MONITOR') and app.config.MODE_AUDIO_MONITOR:
                logging.info("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...")
                threading.Thread(target=app.recording_worker_thread, args=(
                    app,  # Pass app as first parameter
                    app.config.AUDIO_MONITOR_RECORD,
                    app.config.AUDIO_MONITOR_INTERVAL,
                    "Audio_monitor",
                    app.config.AUDIO_MONITOR_FORMAT,
                    app.config.AUDIO_MONITOR_SAMPLERATE,
                    getattr(app.config, 'AUDIO_MONITOR_START', None),
                    getattr(app.config, 'AUDIO_MONITOR_END', None)
                )).start()

            if hasattr(app.config, 'MODE_PERIOD') and app.config.MODE_PERIOD and not app.testmode:
                logging.info("Starting recording_worker_thread for caching period audio at primary sample rate and all channels...")
                threading.Thread(target=app.recording_worker_thread, args=(
                    app,  # Pass app as first parameter
                    app.config.PERIOD_RECORD,
                    app.config.PERIOD_INTERVAL,
                    "Period_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'PERIOD_START', None),
                    getattr(app.config, 'PERIOD_END', None)
                )).start()

            if hasattr(app.config, 'MODE_EVENT') and app.config.MODE_EVENT and not app.testmode:
                logging.info("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
                threading.Thread(target=app.recording_worker_thread, args=(
                    app,  # Pass app as first parameter
                    app.config.SAVE_BEFORE_EVENT,
                    app.config.SAVE_AFTER_EVENT,
                    "Event_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'EVENT_START', None),
                    getattr(app.config, 'EVENT_END', None)
                )).start()

            # Wait for keyboard input to stop
            while not app.stop_program[0]:
                time.sleep(0.1)
            
            # Normal exit - return True
            logging.info("Audio stream stopped normally")
            return True

    except Exception as e:
        logging.error(f"Error in audio stream: {e}")
        logging.info("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        return False

    return True  # Normal exit path


def stop_all(app):
    """Stop all processes and threads."""

    logging.info("Stopping all processes and threads...")

    # Set stop flags
    app.stop_program[0] = True
    app.keyboard_listener_running = False
    
    # Stop recording events
    if hasattr(app, 'stop_recording_event'):
        app.stop_recording_event.set()
    
    # Stop other events
    if hasattr(app, 'stop_tod_event'):
        app.stop_tod_event.set()
    if hasattr(app, 'stop_vu_event'):
        app.stop_vu_event.set()
    if hasattr(app, 'stop_intercom_event'):
        app.stop_intercom_event.set()
    if hasattr(app, 'stop_fft_periodic_plot_event'):
        app.stop_fft_periodic_plot_event.set()
    
    # Stop performance monitor
    ##global stop_performance_monitor_event
    app.stop_performance_monitor_event.set()
    
    # Signal buffer wrap event to unblock any waiting threads
    buffer_wrap_event.set()
    
    # Clean up active processes
    if app.active_processes is not None:
        for key in app.active_processes:
            cleanup_process(app, key)
    
    # Give threads a moment to finish
    time.sleep(0.5)
    
    print("All processes stopped.")


def cleanup(app):
    """Clean up and exit."""
    ##global original_terminal_settings
    
    print("\nPerforming cleanup...")
    
    # Stop all processes first (but don't print duplicate messages)
    global buffer_wrap_event
    
    # Set stop flags
    app.stop_program[0] = True
    app.keyboard_listener_running = False
    
    # Stop recording events
    if hasattr(app, 'stop_recording_event'):
        app.stop_recording_event.set()
    
    # Stop other events  
    if hasattr(app, 'stop_tod_event'):
        app.stop_tod_event.set()
    if hasattr(app, 'stop_vu_event'):
        app.stop_vu_event.set()
    if hasattr(app, 'stop_intercom_event'):
        app.stop_intercom_event.set()
    if hasattr(app, 'stop_fft_periodic_plot_event'):
        app.stop_fft_periodic_plot_event.set()
    
    # Stop performance monitor
    ##global stop_performance_monitor_event
    app.stop_performance_monitor_event.set()
    
    # Signal buffer wrap event to unblock any waiting threads
    buffer_wrap_event.set()
    
    # Clean up active processes
    if app.active_processes is not None:
        for key in app.active_processes:
            cleanup_process(app, key)

    # Force close any remaining sounddevice streams
    try:
        sd.stop()  # Stop all sounddevice streams
        time.sleep(0.1)
    except Exception as e:
        logging.warning(f"Note: Error stopping sounddevice streams: {e}")

    # Restore terminal settings
    if app.original_terminal_settings:
        restore_terminal_settings(app.original_terminal_settings)
    else:
        reset_terminal_settings(app)
    
    logging.info("Cleanup completed.")
    
    # Force exit to prevent hanging
    import os
    os._exit(0)


def keyboard_listener(app):
    """Main keyboard listener loop."""
    global change_ch_event, intercom_proc
    
    # Reset terminal settings before starting
    reset_terminal_settings(app)
    
    print("\nKeyboard listener started. Press 'h' for help.", end='\n\n', flush=True)
    
    while app.keyboard_listener_running:
        try:
            key = get_key(app)
            if key is not None:
                if key == "^":  # Toggle listening
                    toggle_listening(app)
                elif app.keyboard_listener_active:
                    if key.isdigit():
                        # Handle direct channel changes when in VU meter or Intercom mode
                        if app.vu_proc is not None or app.intercom_proc is not None:
                            key_int = int(key) - 1  # Convert to 0-based index
                            
                            # Validate channel number is within range
                            if key_int < 0 or key_int >= app.sound_in_chs:
                                logging.warning(f"\nInvalid channel selection: Device has only {app.sound_in_chs} channel(s) (1-{app.sound_in_chs})")
                                continue
                                
                            app.monitor_channel = key_int
                            if app.intercom_proc is not None:
                                app.change_ch_event.set()
                            print(f"\nNow monitoring channel: {app.monitor_channel+1} (of {app.sound_in_chs})", end='\n', flush=True)
                            # Restart VU meter if running
                            if app.vu_proc is not None:
                                print(f"Restarting VU meter on channel: {app.monitor_channel+1}", end='\n', flush=True)
                                toggle_vu_meter(app)
                                time.sleep(0.1)
                                toggle_vu_meter(app)
                        else:
                            if key == "0":
                                print("Exiting channel change", end='\n', flush=True)
                            else:
                                print(f"Unknown command: {key}", end='\n', flush=True)
                    elif key == "a": 
                        check_stream_status(app, 10)
                    elif key == "c":  
                        change_monitor_channel(app)
                    elif key == "d":  
                        show_audio_device_list(app)
                    elif key == "D":  
                        show_detailed_device_list(app)
                    elif key == "f":  
                        try:
                            trigger_fft(app)
                        except Exception as e:
                            logging.error(f"Error in FFT trigger: {e}")
                            cleanup_process(app, 'f')
                    elif key == "i":  
                        toggle_intercom_m()  # Note: This function doesn't take app parameter yet
                    elif key == "m":  
                        show_mic_locations(app)
                    elif key == "o":  
                        trigger_oscope(app) 
                    elif key == "p":
                        run_performance_monitor_once(app)
                    elif key == "P":
                        toggle_continuous_performance_monitor(app)                              
                    elif key == "q":  
                        print("\nQuitting...", end='\n', flush=True)
                        app.keyboard_listener_running = False
                        stop_all(app)
                    elif key == "s":  
                        trigger_spectrogram(app)
                    elif key == "t":  
                        list_all_threads()  # Note: This function doesn't take app parameter        
                    elif key == "v":  
                        try:
                            toggle_vu_meter(app)
                        except Exception as e:
                            logging.error(f"Error in VU meter toggle: {e}")
                            print(f"\nError starting VU meter: {e}")
                            # Clean up any partial state
                            if hasattr(app, 'vu_proc') and app.vu_proc is not None:
                                try:
                                    if app.vu_proc.is_alive():
                                        app.vu_proc.terminate()
                                        app.vu_proc.join(timeout=1)
                                except:
                                    pass
                                app.vu_proc = None
                            cleanup_process(app, 'v')      
                    elif key == "h" or key =="?":  
                        show_list_of_commands()
                
        except Exception as e:
            logging.error(f"Error in keyboard listener: {e}")
            continue
            
        time.sleep(0.01)  # Small delay to prevent high CPU usage

def toggle_listening(app):
    """Toggle keyboard listener active state."""
    app.keyboard_listener_active = not app.keyboard_listener_active
    if app.keyboard_listener_active:
        print("\nKeyboard listener activated. Listening for commands...")
        show_list_of_commands()
    else:
        print("\nKeyboard listener deactivated. Press '^' to reactivate.")
        stop_vu()
        stop_intercom_m()


def show_list_of_commands():
    print("\na  audio pathway--check for over/underflows")
    print("c  channel--select channel to monitor, either before or during use of vu or intercom, '0' to exit")
    print("d  selected devices in use data")
    print("D  show all devices with active input/output indicator")
    print("f  fft--show plot")
    print("q  quit--stop all processes and exit")
    print("s  spectrogram--plot of last recording")
    print("t  threads--see list of all threads")
    print("v  vu meter--toggle--show vu meter on cli")
    print()
    print("1-'n' - Direct channel selection")
    print("^  toggle keyboard listener on/off")
    print("h or ?  show list of commands\n")


def change_monitor_channel(app):
    """Change the monitor channel."""
    print(f"\nCurrent monitor channel: {app.monitor_channel + 1}")
    print(f"Device has {app.sound_in_chs} channel(s) available")
    print("Enter new channel number (1-{}) or 0 to cancel: ".format(app.sound_in_chs), end='', flush=True)
    
    try:
        choice = input()
        if choice == "0":
            print("Channel change cancelled")
            return
        
        new_channel = int(choice) - 1  # Convert to 0-based
        if 0 <= new_channel < app.sound_in_chs:
            app.monitor_channel = new_channel
            print(f"Monitor channel changed to: {app.monitor_channel + 1}")
        else:
            print(f"Invalid channel. Must be 1-{app.sound_in_chs}")
    except ValueError:
        print("Invalid input. Please enter a number.")


def check_wsl_audio():
    """Check WSL audio configuration and provide setup instructions."""
    try:       
        # Set PulseAudio server to use TCP
        os.environ['PULSE_SERVER'] = 'tcp:localhost'
        
        # Check if PulseAudio is running
        result = subprocess.run(['pulseaudio', '--check'], capture_output=True, text=True)
        if result.returncode != 0:
            logging.info("\nPulseAudio is not running. Starting it...")
            subprocess.run(['pulseaudio', '--start'], capture_output=True)
        
        # Check if ALSA is configured
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        print("\nALSA devices:")
        print(result.stdout)
        
        # Check if PulseAudio is configured
        result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
        print("\nPulseAudio info:")
        print(result.stdout)
        
        # Check if we can list audio devices through PulseAudio
        result = subprocess.run(['pactl', 'list', 'sources'], capture_output=True, text=True)
        print("\nPulseAudio sources:")
        print(result.stdout)
        
        return True
    except Exception as e:
        print(f"\nError checking audio configuration: {e}")
        print("\nPlease ensure your WSL audio is properly configured:")
        print("1. Install required packages:")
        print("   sudo apt-get update")
        print("   sudo apt-get install -y pulseaudio libasound2-plugins")
        print("\n2. Configure PulseAudio:")
        print("   echo 'export PULSE_SERVER=tcp:localhost' >> ~/.bashrc")
        print("   source ~/.bashrc")
        print("\n3. Create PulseAudio configuration:")
        print("   mkdir -p ~/.config/pulse")
        print("   echo 'load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1' > ~/.config/pulse/default.pa")
        print("\n4. Start PulseAudio:")
        print("   pulseaudio --start")
        print("\n5. Test audio:")
        print("   speaker-test -t sine -f 1000 -l 1")
        return False


def vu_meter(app_instance, app_config):
    """VU meter function for displaying audio levels using BmarApp configuration."""
    # Note: app_instance is None when called from subprocess to avoid pickling issues
    sound_in_id = app_config['sound_in_id']
    sound_in_chs = app_config['sound_in_chs']
    channel = app_config['monitor_channel']
    sample_rate = app_config['PRIMARY_IN_SAMPLERATE']
    is_wsl = app_config['is_wsl']
    is_macos = app_config['is_macos']
    os_info = app_config['os_info']
    debug_verbose = app_config.get('DEBUG_VERBOSE', False)

    # Debug: Print incoming parameter types
    if debug_verbose:
        print(f"\n[VU Debug] Parameter types:")
        print(f"  sound_in_id: {sound_in_id} (type: {type(sound_in_id)})")
        print(f"  sample_rate: {sample_rate} (type: {type(sample_rate)})")
        print(f"  sound_in_chs: {sound_in_chs} (type: {type(sound_in_chs)})")
        print(f"  channel: {channel} (type: {type(channel)})")
        print(f"  is_wsl: {is_wsl}")
        print(f"  is_macos: {is_macos}")
    
    # Ensure sample rate is an integer for buffer size calculation
    buffer_size = int(sample_rate)
    buffer = np.zeros(buffer_size)
    last_print = ""
    
    # Validate the channel is valid for the device
    if channel >= sound_in_chs:
        print(f"\nError: Selected channel {channel+1} exceeds available channels ({sound_in_chs})", end='\r\n')
        print(f"Defaulting to channel 1", end='\r\n')
        channel = 0  # Default to first channel

    def callback_input(indata, frames, time, status):
        nonlocal last_print
        try:
            # Debug first callback
            if debug_verbose and last_print == "":
                print(f"\n[VU Debug] First callback: frames={frames}, indata.shape={indata.shape}")
            
            # Always validate channel before accessing the data
            selected_channel = int(min(channel, indata.shape[1] - 1))
            
            channel_data = indata[:, selected_channel]
            # Ensure frames is an integer for array slicing
            frames_int = int(frames)
            buffer[:frames_int] = channel_data
            audio_level = np.max(np.abs(channel_data))
            normalized_value = int((audio_level / 1.0) * 50)
            
            asterisks = '*' * normalized_value
            current_print = ' ' * 11 + asterisks.ljust(50, ' ')
            
            # Only print if the value has changed
            if current_print != last_print:
                print(current_print, end='\r')
                last_print = current_print
                sys.stdout.flush()  # Ensure output is displayed immediately
        except Exception as e:
            # Log the error but don't crash
            print(f"\rVU meter callback error: {e}", end='\r\n')
            if debug_verbose:
                print(f"Error details: channel={channel}, frames={frames}, indata.shape={indata.shape}", end='\r\n')
                import traceback
                traceback.print_exc()
            time.sleep(0.1)  # Prevent too many messages

    try:
        # Debug platform detection
        if debug_verbose:
            print(f"\n[VU Debug] Platform detection:")
            print(f"  sys.platform: {sys.platform}")
            print(f"  is_wsl: {is_wsl}")
            print(f"  is_macos: {is_macos}")
            print(f"  os_info: {os_info}")

        # In WSL, we need to use different stream parameters
        if is_wsl:
            if debug_verbose:
                print("[VU Debug] Using WSL audio configuration")
            # Check audio configuration first
            if not check_wsl_audio():
                raise Exception("Audio configuration check failed")
            
            # Try with minimal configuration
            try:
                with sd.InputStream(callback=callback_input,
                                  device=None,  # Use system default
                                  channels=1,   # Use mono
                                  samplerate=48000,  # Use standard rate
                                  blocksize=1024,    # Use smaller block size
                                  latency='low'):
                    # Simple loop - run until process is terminated externally
                    while True:
                        sd.sleep(100)  # Sleep for 100ms
            except Exception as e:
                print(f"\nError with default configuration: {e}")
                print("\nPlease ensure your WSL audio is properly configured.")
                raise
        else:
            if debug_verbose:
                print("[VU Debug] Using standard audio configuration (non-WSL)")
            # Make sure we request at least as many channels as our selected channel
            # Ensure all parameters are integers for compatibility
            try:
                # Simple approach - just ensure the critical parameters are integers
                with sd.InputStream(callback=callback_input,
                                  device=int(sound_in_id) if sound_in_id is not None else None,
                                  channels=int(sound_in_chs),
                                  samplerate=int(sample_rate),
                                  blocksize=1024,
                                  latency='low'):
                    # Simple loop - run until process is terminated externally
                    while True:
                        sd.sleep(100)  # Sleep for 100ms
            except Exception as e:
                print(f"\nError in VU meter InputStream: {e}")
                print(f"Debug info:")
                print(f"  sound_in_id={sound_in_id} (type: {type(sound_in_id)})")
                print(f"  sound_in_chs={sound_in_chs} (type: {type(sound_in_chs)})")
                print(f"  sample_rate={sample_rate} (type: {type(sample_rate)})")
                import traceback
                traceback.print_exc()
                raise
    except Exception as e:
        print(f"\nError in VU meter: {e}")
    finally:
        print("\nStopping VU meter...")


def toggle_vu_meter(app):
    """Toggle VU meter display using BmarApp instance."""
    ##global vu_proc, asterisks
    
    # Clear any buffered input before toggling
    clear_input_buffer(app)

    if app.vu_proc is None:
        cleanup_process(app,'v')  # Clean up any existing process
        
        # Validate channel before starting process
        if app.monitor_channel >= app.sound_in_chs:
            print(f"\nError: Selected channel {app.monitor_channel+1} exceeds available channels ({app.sound_in_chs})")
            print(f"Defaulting to channel 1")
            app.monitor_channel = 0  # Default to first channel
            
        print(f"\nVU meter monitoring channel: {app.monitor_channel+1}")
        
        # Create shared values for display (but don't use them in subprocess to avoid pickling issues)
        vu_manager = multiprocessing.Manager()
        app.asterisks = vu_manager.Value(str, '*' * 50)

        # Print initial state once
        print("fullscale:", app.asterisks.value.ljust(50, ' '))

        if hasattr(app.config, 'MODE_EVENT') and app.config.MODE_EVENT:
            normalized_value = int(app.config.EVENT_THRESHOLD / 1000)
            app.asterisks.value = '*' * normalized_value
            print("threshold:", app.asterisks.value.ljust(50, ' '))
            
        # Debug and validate parameters before creating process
        debug_verbose = hasattr(app.config, 'DEBUG_VERBOSE') and app.config.DEBUG_VERBOSE
        if debug_verbose:
            print(f"\n[Toggle VU Debug] Parameter validation:")
            print(f"  sound_in_id: {app.sound_in_id} (type: {type(app.sound_in_id)})")
            print(f"  PRIMARY_IN_SAMPLERATE: {app.PRIMARY_IN_SAMPLERATE} (type: {type(app.PRIMARY_IN_SAMPLERATE)})")
            print(f"  sound_in_chs: {app.sound_in_chs} (type: {type(app.sound_in_chs)})")
            print(f"  monitor_channel: {app.monitor_channel} (type: {type(app.monitor_channel)})")
        
        # Get configuration dictionary for VU meter subprocess
        app_config = app.get_subprocess_config(DEBUG_VERBOSE=debug_verbose)
            
        # Create the VU meter process
        app.vu_proc = multiprocessing.Process(
            target=vu_meter, 
            args=(None, app_config)  # Don't pass the app object - it may contain unpicklable items
        )
        
        # Set the process to start in a clean environment
        app.vu_proc.daemon = True
            
        app.active_processes['v'] = app.vu_proc
        app.vu_proc.start()
    else:
        stop_vu(app)
    
    # Clear input buffer after toggling
    clear_input_buffer(app)


def stop_vu(app):
    """Stop VU meter."""
    ##global vu_proc
    
    if app.vu_proc is not None:
        try:
            # Try to get the stop_vu_queue and stop_vu_event that were created in toggle_vu_meter
            # For now, we'll terminate the process directly since we need better process management
            
            # Give the process a short time to stop gracefully
            app.vu_proc.join(timeout=1)
            
            if app.vu_proc.is_alive():
                # If still running after timeout, terminate
                app.vu_proc.terminate()
                app.vu_proc.join(timeout=1)
                if app.vu_proc.is_alive():
                    app.vu_proc.kill()  # Force kill if still alive

            print("\nvu stopped")
        except Exception as e:
            print(f"\nError stopping VU meter: {e}")
        finally:
            app.vu_proc = None
            cleanup_process(app, 'v')
            clear_input_buffer(app)

def toggle_intercom_m():
    """Toggle intercom functionality - PLACEHOLDER."""
    print("Intercom toggle placeholder - full implementation pending")


def stop_intercom_m():
    """Stop intercom - PLACEHOLDER."""
    print("Stop intercom placeholder - full implementation pending")


def plot_fft(app_config, sound_in_id, sound_in_chs, channel, stop_queue):
    """Single-shot FFT plot of audio."""
    try:
        # Force garbage collection before starting
        gc.collect()
        
        # Ensure clean matplotlib state for this process
        import matplotlib
        matplotlib.use('Agg', force=True)
        import matplotlib.pyplot as plt
        plt.close('all')  # Close any existing figures
        
        # Brief delay to ensure clean audio device state
        time.sleep(0.1)
        
        # Extract configuration from app_config dictionary
        fft_duration = app_config['fft_duration']
        fft_gain = app_config.get('fft_gain', 0)
        primary_in_samplerate = app_config['primary_in_samplerate']
        plot_directory = app_config['plot_directory']
        primary_bitdepth = app_config['primary_bitdepth']
        location_id = app_config['location_id']
        hive_id = app_config['hive_id']
        fft_bw = app_config['fft_bw']
        is_wsl = app_config['is_wsl']
        is_macos = app_config['is_macos']
        
        recording, actual_channels = _record_audio_pyaudio(
            fft_duration, sound_in_id, sound_in_chs, stop_queue, "FFT analysis"
        )
        
        if recording is None:
            logging.error("Failed to record audio for FFT.")
            return

        # Ensure channel index is valid
        if channel >= actual_channels:
            logging.warning(f"Channel {channel+1} not available for FFT, using channel 1.")
            monitor_channel = 0
        else:
            monitor_channel = channel
            
        # Extract the requested channel
        single_channel_audio = recording[:, monitor_channel]
        
        # Apply gain if needed
        if fft_gain > 0:
            gain = 10 ** (fft_gain / 20)
            logging.info(f"Applying FFT gain of: {gain:.1f}")
            single_channel_audio *= gain

        logging.info("Performing FFT...")
        # Perform FFT
        from scipy.fft import rfft, rfftfreq
        yf = rfft(single_channel_audio.flatten())
        xf = rfftfreq(len(single_channel_audio), 1 / primary_in_samplerate)

        # Define bucket width
        bucket_width = fft_bw  # Hz
        bucket_size = int(bucket_width * len(single_channel_audio) / primary_in_samplerate)  # Number of indices per bucket

        # Calculate the number of complete buckets
        num_buckets = len(yf) // bucket_size
        
        # Average buckets - ensure both arrays have the same length
        buckets = []
        bucket_freqs = []
        for i in range(num_buckets):
            start_idx = i * bucket_size
            end_idx = start_idx + bucket_size
            buckets.append(yf[start_idx:end_idx].mean())
            bucket_freqs.append(xf[start_idx:end_idx].mean())
        
        buckets = np.array(buckets)
        bucket_freqs = np.array(bucket_freqs)

        logging.info("Creating FFT plot...")
        # Create figure with reduced DPI for better performance
        fig = plt.figure(figsize=(10, 6), dpi=80)
        plt.plot(bucket_freqs, np.abs(buckets), linewidth=1.0)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title(f'FFT Plot monitoring ch: {monitor_channel + 1} of {actual_channels} channels')
        plt.grid(True)

        # Save the plot
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        plotname = os.path.join(plot_directory, f"{timestamp}_fft_{int(primary_in_samplerate/1000)}_kHz_{primary_bitdepth}_{location_id}_{hive_id}.png")
        logging.info(f"Saving FFT plot to: {plotname}")
        
        # Make sure the directory exists
        os.makedirs(os.path.dirname(plotname), exist_ok=True)
        
        # Display the expanded path
        expanded_path = os.path.abspath(os.path.expanduser(plotname))
        logging.info(f"Absolute path: {expanded_path}")
        
        # Save with optimized settings
        logging.info("Saving figure...")
        plt.savefig(expanded_path, dpi=80, bbox_inches='tight', pad_inches=0.1, format='png')
        logging.info("Plot saved successfully")
        plt.close('all')  # Close all figures

        # Open the saved image based on OS
        try:
            # First verify the file exists
            if not os.path.exists(expanded_path):
                logging.error(f"Plot file does not exist at: {expanded_path}")
                return
                
            logging.info(f"Plot file exists, size: {os.path.getsize(expanded_path)} bytes")
            
            if is_wsl:
                logging.info("Opening image in WSL...")
                try:
                    proc = subprocess.Popen(['xdg-open', expanded_path])
                    logging.info(f"xdg-open launched with PID: {proc.pid}")
                except FileNotFoundError:
                    logging.info("xdg-open not found, trying wslview...")
                    proc = subprocess.Popen(['wslview', expanded_path])
                    logging.info(f"wslview launched with PID: {proc.pid}")
            elif is_macos:
                logging.info("Opening image in macOS...")
                proc = subprocess.Popen(['open', expanded_path])
                logging.info(f"open command launched with PID: {proc.pid}")
            elif sys.platform == 'win32':
                logging.info("Opening image in Windows...")
                os.startfile(expanded_path)
                logging.info("Image viewer command executed")
            else:
                logging.info("Opening image in Linux...")
                proc = subprocess.Popen(['xdg-open', expanded_path])
                logging.info(f"xdg-open launched with PID: {proc.pid}")
                
            logging.info("Image viewer command executed successfully")
            
            # Give the process a moment to start
            time.sleep(0.5)
            
            # Also print the command that can be run manually
            print(f"\nIf the image didn't open, you can manually run:")
            if is_wsl or not sys.platform == 'win32':
                print(f"  xdg-open '{expanded_path}'")
            elif is_macos:
                print(f"  open '{expanded_path}'")
                
        except Exception as e:
            logging.error("Could not open image viewer", exc_info=True)
            try:
                # Try with shell=True as a fallback
                subprocess.Popen(f"xdg-open '{expanded_path}'", shell=True)
                logging.info("Alternative method executed")
            except Exception as e2:
                logging.error("Alternative open method also failed", exc_info=True)
            logging.info(f"Image saved at: {expanded_path}")
            logging.info("You can manually open this file with your image viewer")
            
    except Exception as e:
        logging.error("Error in FFT recording", exc_info=True)
    finally:
        # Ensure cleanup happens
        try:
            plt.close('all')
            gc.collect()
        except:
            pass

def trigger_fft(app):
    """Trigger FFT plot generation with proper cleanup."""
    try:
        # Clean up any existing FFT process
        cleanup_process(app,'f')
        clear_input_buffer(app)

        # Get current app instance parameters
        monitor_channel = app.monitor_channel
        sound_in_chs = app.sound_in_chs
        sound_in_id = app.sound_in_id
        
        # Create a queue for communication
        stop_queue = multiprocessing.Queue()
        
        # Get configuration dictionary for FFT subprocess
        app_config = app.get_subprocess_config()
        
        # Create new process
        fft_process = multiprocessing.Process(
            target=plot_fft,
            args=(app_config, sound_in_id, sound_in_chs, monitor_channel, stop_queue)
        )
        
        # Set process as daemon
        fft_process.daemon = True
        
        # Store process reference
        app.active_processes['f'] = fft_process
        
        print("Starting FFT analysis process...")
        # Start process
        fft_process.start()
        
        # Wait for completion with timeout
        timeout = app.config.FFT_DURATION + 30  # Recording duration plus extra time for processing
        fft_process.join(timeout=timeout)
        
        # Check if process is still running
        if fft_process.is_alive():
            print("\nFFT process taking too long, terminating...")
            try:
                # Signal the process to stop
                stop_queue.put(True)
                # Give it a moment to clean up
                time.sleep(1)
                # Then terminate if still running
                if fft_process.is_alive():
                    fft_process.terminate()
                    fft_process.join(timeout=2)
                    if fft_process.is_alive():
                        fft_process.kill()
            except Exception as e:
                print(f"Error terminating FFT process: {e}")
        
    except Exception as e:
        print(f"Error in trigger_fft: {e}")
        traceback.print_exc()
    finally:
        # Always clean up
        cleanup_process(app,'f')
        clear_input_buffer(app)
        print("FFT process completed")

def plot_spectrogram(app, channel, y_axis_type, file_offset, period):
    """
    Generate a spectrogram from an audio file and display/save it as an image.
    Parameters:
    - app: BmarApp instance
    - channel: Channel to use for multi-channel audio files
    - y_axis_type: Type of Y axis for the spectrogram ('log' or 'linear')
    - file_offset: Offset for finding the audio file
    - period: Duration limit for spectrogram analysis
    """
    # Store original matplotlib backend to restore later
    original_backend = None
    plt_imported = False
    
    try:
        # Force garbage collection before starting
        gc.collect()
        
        # Force non-interactive backend before any plotting
        import matplotlib
        original_backend = matplotlib.get_backend()
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt_imported = True
        
        # Clear any existing figures to prevent interference
        plt.close('all')
        
        next_spectrogram = find_file_of_type_with_offset(app, file_offset)
        
        if next_spectrogram is None:
            print("No data available to see?")
            return
            
        full_audio_path = os.path.join(app.PRIMARY_DIRECTORY, next_spectrogram)
        print("Spectrogram source:", full_audio_path)

        print("Loading audio file with librosa...")
        # Variables to ensure cleanup
        y = None
        sr = None
        D_db = None
        
        try:
            # For spectrogram display, limit duration to avoid memory issues
            max_duration = min(app.config.PERIOD_RECORD, period)  # Max duration for display
            
            # Load the audio file with duration limit
            # Using mono=False to preserve channels, keeping native sample rate
            y, sr = librosa.load(full_audio_path, sr=None, duration=max_duration, mono=False)
            print(f"Audio loaded: shape={y.shape if hasattr(y, 'shape') else 'scalar'}, sample_rate={sr} Hz, duration={max_duration}s")
            
            # Keep the native sample rate to preserve high-frequency information
            print(f"Using sample rate of {sr} Hz from native sample rate of {config.PRIMARY_IN_SAMPLERATE} Hz")
        except Exception as e:
            print(f"Error loading audio file: {e}")
            return
        
        # If multi-channel audio, select the specified channel
        if len(y.shape) > 1:
            y = y[channel]
            print(f"Selected channel {channel+1}")
            
        print("Computing spectrogram...")
        try:
            # Use larger hop length for long files or high sample rates to reduce spectrogram size
            duration_seconds = len(y) / sr
            
            # Adaptive parameters based on duration and sample rate
            if sr > 96000:  # Very high sample rate
                if duration_seconds > 60:
                    hop_length = 4096  # Very large hop for high SR + long duration
                    n_fft = 8192
                else:
                    hop_length = 2048
                    n_fft = 4096
            elif duration_seconds > 60:  # Normal sample rate, long file
                hop_length = 2048
                n_fft = 4096
            else:  # Normal sample rate, short file
                hop_length = 512
                n_fft = 2048
                
            # Compute the spectrogram with specified parameters
            D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
            D_db = librosa.amplitude_to_db(abs(D), ref=np.max)
            print(f"Spectrogram computed: shape={D_db.shape}, hop_length={hop_length}, n_fft={n_fft}")
            print(f"Frequency resolution: {sr/n_fft:.1f} Hz/bin, Time resolution: {hop_length/sr*1000:.1f} ms/frame")
        except Exception as e:
            print(f"Error computing spectrogram: {e}")
            return
        finally:
            # Clean up intermediate variables
            try:
                if 'D' in locals():
                    del D
                gc.collect()
            except:
                pass
        
        # Plot the spectrogram
        fig = None
        try:
            fig = plt.figure(figsize=(12, 6))

            if y_axis_type == 'log':
                librosa.display.specshow(D_db, sr=sr, x_axis='time', y_axis='log', hop_length=hop_length)
                y_decimal_places = 3
            elif y_axis_type == 'lin':
                librosa.display.specshow(D_db, sr=sr, x_axis='time', y_axis='linear', hop_length=hop_length)
                y_decimal_places = 0
            else:
                raise ValueError("y_axis_type must be 'log' or 'linear'")
            
            # Adjust y-ticks to be in kilohertz and have the specified number of decimal places
            y_ticks = plt.gca().get_yticks()
            plt.gca().set_yticklabels(['{:.{}f} kHz'.format(tick/1000, y_decimal_places) for tick in y_ticks])
            
            # Extract filename from the audio path
            filename = os.path.basename(full_audio_path)
            root, _ = os.path.splitext(filename)
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            plotname = os.path.join(app.PLOT_DIRECTORY, f"{timestamp}_{root}_spectrogram.png")

            # Set title to include filename and channel
            mic_location = app.config.MIC_LOCATION[channel] if channel < len(app.config.MIC_LOCATION) else f"Ch{channel+1}"
            plt.title(f'Spectrogram from {app.config.LOCATION_ID}, hive:{app.config.HIVE_ID}, Mic Loc:{mic_location}\nfile:{filename}, Ch:{channel+1}')
            plt.colorbar(format='%+2.0f dB')
            plt.tight_layout()
            print("\nSaving spectrogram to:", plotname)
            
            # Make sure the directory exists
            os.makedirs(os.path.dirname(plotname), exist_ok=True)
            
            # Display the expanded path
            expanded_path = os.path.abspath(os.path.expanduser(plotname))
            print(f"Absolute path: {expanded_path}")
            
            print("Attempting to save plot...")
            try:
                # For large spectrograms, use rasterization to speed up saving
                if D_db.shape[1] > 10000:  # If more than 10k time frames
                    print("Using rasterized format for large spectrogram...")
                    plt.gca().set_rasterized(True)
                    
                plt.savefig(expanded_path, dpi=72, format='png', bbox_inches='tight')  # Lower DPI for very large plots
                print("Plot saved successfully")
            except Exception as e:
                print(f"Error saving plot: {e}")
                return
            finally:
                # Always close the figure, even if save failed
                if fig is not None:
                    plt.close(fig)
                    
            # Open the saved image based on OS
            try:
                if app.platform_manager.is_wsl():
                    print("Opening image in WSL...")
                    try:
                        subprocess.Popen(['xdg-open', expanded_path])
                    except FileNotFoundError:
                        subprocess.Popen(['wslview', expanded_path])
                elif app.platform_manager.is_macos():
                    print("Opening image in macOS...")
                    subprocess.Popen(['open', expanded_path])
                elif sys.platform == 'win32':
                    print("Opening image in Windows...")
                    os.startfile(expanded_path)
                else:
                    print("Opening image in Linux...")
                    subprocess.Popen(['xdg-open', expanded_path])
                print("Image viewer command executed")
            except Exception as e:
                print(f"Could not open image viewer: {e}")
                print(f"Image saved at: {expanded_path}")
                if not os.path.exists(expanded_path):
                    print("Warning: The saved image file does not exist!")
        except Exception as e:
            print(f"Error in plotting: {e}")
            if fig is not None:
                plt.close(fig)
            raise
        
    except Exception as e:
        print(f"Error in plot_spectrogram: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Force cleanup of all matplotlib and librosa resources
        try:
            if plt_imported:
                plt.close('all')
                # Clear matplotlib's internal state
                plt.clf()
                plt.cla()
            
            # Restore original matplotlib backend if it was changed
            if original_backend is not None and plt_imported:
                try:
                    import matplotlib
                    matplotlib.use(original_backend)
                    print(f"Restored matplotlib backend to: {original_backend}")
                except Exception as e:
                    print(f"Warning: Could not restore matplotlib backend: {e}")
            
            # Force garbage collection to free memory
            gc.collect()
            
            # Clear any remaining variables to free memory
            try:
                # Set large variables to None to help garbage collection
                y = None
                sr = None
                D_db = None
            except:
                pass
            
            # Final garbage collection
            gc.collect()
        except Exception as e:
            print(f"Warning during cleanup: {e}")
            pass

def trigger_spectrogram(app):
    """Trigger spectrogram generation."""
    try:
        # Clean up any existing spectrogram process
        cleanup_process(app,'s')
        
        # Clear input buffer before starting
        clear_input_buffer(app)
        
        # Get file offset and time difference
        ##global file_offset, monitor_channel, time_diff
        time_since_last = time_diff()  # Store the time difference
        
        # Only increment offset if we're within the recording period
        if time_since_last < (config.PERIOD_RECORD + config.PERIOD_INTERVAL):
            app.file_offset = min(app.file_offset + 1, 0)  # Cap at 0 to prevent going negative
        else:
            app.file_offset = 0  # Reset to first file

        print(f"Time since last file: {time_since_last:.1f}s, using file offset: {app.file_offset}")

        # Create and start the spectrogram process
        app.active_processes['s'] = multiprocessing.Process(
            target=plot_spectrogram,
            args=(app, app.monitor_channel, 'lin', app.file_offset, app.config.spectrogram_period)
        )
        app.active_processes['s'].daemon = True  # Make it a daemon process
        app.active_processes['s'].start()

        # Brief delay to allow the spectrogram process to initialize properly
        # and prevent interference with subsequent audio operations
        time.sleep(0.2)
        
        print("Plotting spectrogram...")
        clear_input_buffer(app)

        # Wait for completion with timeout
        app.active_processes['s'].join(timeout=240)  # Increased timeout for spectrogram generation

        # Cleanup if process is still running
        if app.active_processes['s'].is_alive():
            print("Spectrogram process taking too long, terminating...")
            try:
                app.active_processes['s'].terminate()
                app.active_processes['s'].join(timeout=1)
                if app.active_processes['s'].is_alive():
                    # Force kill if still running
                    app.active_processes['s'].kill()
                    app.active_processes['s'].join(timeout=1)
            except Exception as e:
                print(f"Warning during process termination: {e}")
        
    except Exception as e:
        print(f"Error in trigger_spectrogram: {e}")
    finally:
        # Always clean up
        try:
            cleanup_process(app,'s')
        except Exception as e:
            print(f"Warning during cleanup: {e}")
        clear_input_buffer(app)
        print("Spectrogram process completed")


def get_system_performance():
    """Get a single snapshot of system performance."""
    # Get CPU usage for each core
    cpu_percents = psutil.cpu_percent(interval=1, percpu=True)
    
    # Get memory usage
    memory = psutil.virtual_memory()
    
    # Build the output string
    output = "\n=== System Performance Monitor ===\n"
    
    # Add CPU information
    output += "CPU Usage by Core:\n"
    for i, percent in enumerate(cpu_percents):
        output += f"Core {i}: {percent:5.1f}%\n"
    
    # Add memory information
    output += "\nMemory Usage:\n"
    output += f"Total: {memory.total / (1024**3):5.1f} GB\n"
    output += f"Used:  {memory.used / (1024**3):5.1f} GB\n"
    output += f"Free:  {memory.available / (1024**3):5.1f} GB\n"
    output += f"Used%: {memory.percent}%\n"
    output += "=" * 30 + "\n"
    
    return output

def monitor_system_performance_once():
    """Display a single snapshot of system performance."""
    try:
        output = get_system_performance()
        print(output, flush=True)
    except Exception as e:
        print(f"\nError in performance monitor: {e}", end='\r')

def monitor_system_performance_continuous(app):
    """Continuously monitor and display CPU and RAM usage."""
    ##global stop_performance_monitor_event
    
    try:
        while not app.stop_performance_monitor_event.is_set():
            output = get_system_performance()
            print(output, flush=True)
            
            # Use event wait with timeout instead of sleep for better responsiveness
            if app.stop_performance_monitor_event.wait(timeout=2):
                break
    except Exception as e:
        print(f"\nError in performance monitor: {e}", end='\r')
    finally:
        print("\nPerformance monitor stopped.", end='\r')

def run_performance_monitor_once(app):
    """Run the performance monitor once."""
    cleanup_process(app,'p')  # Clean up any existing process
    proc = multiprocessing.Process(target=monitor_system_performance_once)
    proc.daemon = True
    app.active_processes['p'] = proc
    proc.start()
    proc.join()  # Wait for it to complete
    cleanup_process(app,'p')

def toggle_continuous_performance_monitor(app):
    """Toggle the continuous performance monitor on/off."""
    ##global performance_monitor_proc, stop_performance_monitor_event

    if app.performance_monitor_proc is None or not app.performance_monitor_proc.is_alive():
        cleanup_process(app,'P')  # Clean up any existing process
        print("\nStarting continuous performance monitor...", end='\r')
        
        # Reset the event before starting
        app.stop_performance_monitor_event.clear()

        app.performance_monitor_proc = multiprocessing.Process(target=monitor_system_performance_continuous)
        app.performance_monitor_proc.daemon = True
        app.active_processes['P'] = app.performance_monitor_proc
        app.performance_monitor_proc.start()
    else:
        print("\nStopping performance monitor...", end='\r')
        app.stop_performance_monitor_event.set()
        if app.performance_monitor_proc.is_alive():
            app.performance_monitor_proc.join(timeout=3)
            if app.performance_monitor_proc.is_alive():
                app.performance_monitor_proc.terminate()
                app.performance_monitor_proc.join(timeout=1)
                if app.performance_monitor_proc.is_alive():
                    app.performance_monitor_proc.kill()
        app.performance_monitor_proc = None
        cleanup_process(app,'P')
        print("Performance monitor stopped", end='\r')

def emergency_cleanup(signum, frame):
    """Emergency cleanup handler for signals."""
    print(f"\nEmergency cleanup triggered by signal {signum}")
    # Note: app instance not available in signal handler context
    # TODO: Implement global cleanup for signal handlers
    sys.exit(0)


# ###################################################
# # Main function to initialize and run the BmarApp
# ###################################################

def main():
    """Main function to initialize and run the BmarApp."""
    
    # Create and initialize the application
    app = BmarApp()
    app.initialize()
    
    logging.info("BmarApp initialized successfully!")
    logging.info(f"Primary directory: {app.PRIMARY_DIRECTORY}")
    logging.info(f"Monitor directory: {app.MONITOR_DIRECTORY}")
    logging.info(f"Plot directory: {app.PLOT_DIRECTORY}")

    # Set up audio device
    if not set_input_device(app):
        logging.error("Failed to configure audio input device. Exiting.")
        sys.exit(1)
    
    # Display selected device information
    show_audio_device_info_for_SOUND_IN_OUT(app)
    
    # Set monitor channel with validation
    if app.monitor_channel >= app.sound_in_chs:
        app.monitor_channel = 0
        logging.info(f"Setting monitor channel to {app.monitor_channel+1}")

    # Set up audio circular buffer
    setup_audio_circular_buffer(app)

    logging.info(f"Buffer size: {app.BUFFER_SECONDS} seconds, {app.buffer.size/500000:.2f} megabytes")
    logging.info(f"Sample Rate: {int(app.PRIMARY_IN_SAMPLERATE)} Hz; File Format: {app.config.PRIMARY_FILE_FORMAT}; Channels: {app.sound_in_chs}")

    # Check and create date-based directories
    if not check_and_create_date_folders(app):
        logging.error("Critical directories could not be created. Exiting.")
        sys.exit(1)
    
    # Print directories for verification
    logging.info("Directory setup:")
    logging.info(f"  Primary recordings: {app.PRIMARY_DIRECTORY}")
    logging.info(f"  Monitor recordings: {app.MONITOR_DIRECTORY}")
    logging.info(f"  Plot files: {app.PLOT_DIRECTORY}")

    # Register cleanup handlers
    atexit.register(lambda: cleanup(app))
    signal.signal(signal.SIGINT, emergency_cleanup)
    signal.signal(signal.SIGTERM, emergency_cleanup)
    
    # Start keyboard listener in a separate thread
    if hasattr(app, 'KB_or_CP') and app.KB_or_CP == 'KB':
        time.sleep(1)  # Give a small delay to ensure prints are visible
        keyboard_thread = threading.Thread(target=keyboard_listener, args=(app,))
        keyboard_thread.daemon = True
        keyboard_thread.start()
        logging.info("Keyboard listener started successfully!")
    try:
        # Start the audio stream
        result = audio_stream(app)
        if not result:
            logging.error("Audio stream failed to start properly.")
            sys.exit(1)
        else:
            logging.info("Program exited normally")

    except KeyboardInterrupt:
        logging.info('Ctrl-C: Recording process stopped by user.')
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure cleanup happens
        try:
            cleanup(app)
        except SystemExit:
            pass  # Allow os._exit() to work
        except Exception as e:
            logging.error(f"Error during final cleanup: {e}")
            import os
            os._exit(1)

if __name__ == "__main__":
    main()

