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
platform_manager = PlatformManager()
# Initialize platform at startup
platform_manager.initialize()

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
        self.stop_program = False
        self.testmode = True

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
        
        self.blocksize = 0 # Let driver choose optimal block size
        
        # Misc
        self.time_diff = self._create_time_diff_func()
        self.fft_interval = 30 # minutes

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
        self.original_terminal_settings = save_terminal_settings()

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

# procs
vu_proc = None
stop_vu_queue = None
oscope_proc = None
intercom_proc = None
fft_periodic_plot_proc = None
one_shot_fft_proc = None  
overflow_monitor_proc = None

# event flags
stop_recording_event = threading.Event()
stop_tod_event = threading.Event()
stop_vu_event = threading.Event()
stop_intercom_event = threading.Event()
stop_fft_periodic_plot_event = threading.Event()

plot_oscope_done = threading.Event()
plot_fft_done = threading.Event()
plot_spectrogram_done = threading.Event()
change_ch_event = threading.Event()

# queues
stop_vu_queue = None

# misc globals
_dtype = None                   # parms sd lib cares about
_subtype = None
asterisks = '*'
device_ch = None                # total number of channels from device
current_time = None
timestamp = None
monitor_channel = 0             # '1 of n' mic to monitor by test functions
stop_program = [False]
buffer_size = None
buffer = None
buffer_index = None
file_offset = 0

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
MICS_ACTIVE = [config.MIC_1, config.MIC_2, config.MIC_3, config.MIC_4]

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

spectrogram_period = config.PERIOD_SPECTROGRAM

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
    sound_in_chs = 1

# Only print config values in the main process, not in subprocesses
# This ensures they don't show up when starting the VU meter or intercom
if is_main_process():
    print(f"\nConfig values:")
    print(f"  data_drive: '{data_drive}'")
    print(f"  data_path: '{data_path}'")
    print(f"  folders: {folders}")
    print(f"  Date folder format: '{date_folder}' (YYMMDD)")

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

def save_terminal_settings():
    """Save current terminal settings for later restoration."""
    try:
        if sys.platform == 'win32' and not platform_manager.is_wsl():
            # Windows doesn't need to save terminal settings in the same way
            return None
        elif platform_manager.termios is not None:
            # For Unix-like systems
            return platform_manager.termios.tcgetattr(sys.stdin)
        else:
            return None
    except Exception as e:
        logging.warning(f"Could not save terminal settings: {e}")
        return None

def restore_terminal_settings(settings):
    """Restore terminal settings from saved state."""
    try:
        if settings is None:
            return
        if sys.platform == 'win32' and not platform_manager.is_wsl():
            # Windows doesn't need terminal restoration in the same way
            return
        elif platform_manager.termios is not None:
            platform_manager.termios.tcsetattr(sys.stdin, platform_manager.termios.TCSADRAIN, settings)
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

def check_and_create_date_folders():
    """
    Check if today's date folders exist and create them if necessary.
    This function should be called at startup and periodically during operation.
    """
    global PRIMARY_DIRECTORY, MONITOR_DIRECTORY, PLOT_DIRECTORY
    
    # Get current date components
    current_date = datetime.datetime.now()
    yy = current_date.strftime('%y')
    mm = current_date.strftime('%m')
    dd = current_date.strftime('%d')
    date_folder = f"{yy}{mm}{dd}"
    
    print(f"\nChecking/creating date folders for {date_folder}...")
    
    # Update directory paths with current date
    PRIMARY_DIRECTORY = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                    folders[0], "raw", date_folder, "")
    MONITOR_DIRECTORY = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                    folders[0], "mp3", date_folder, "")
    PLOT_DIRECTORY = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                 folders[1], date_folder, "")
    
    print(f"Primary directory: {PRIMARY_DIRECTORY}")
    print(f"Monitor directory: {MONITOR_DIRECTORY}")
    print(f"Plot directory: {PLOT_DIRECTORY}")
    
    # Create directories if they don't exist
    required_directories = [PRIMARY_DIRECTORY, MONITOR_DIRECTORY, PLOT_DIRECTORY]
    return ensure_directories_exist(required_directories)

def signal_handler(sig, frame):
    print('\nStopping all threads...\r')
    reset_terminal()  # Reset terminal before stopping
    stop_all()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def reset_terminal():
    """Reset terminal settings to default state without clearing the screen."""
    try:
        # Check if we're on Windows
        if sys.platform == 'win32' and not platform_manager.is_wsl():
            # Windows-specific terminal reset (no termios needed)
            # Just flush the output
            sys.stdout.flush()
            print("\n[Terminal input mode reset (Windows)]", end='\r\n', flush=True)
            return
            
        # For Unix-like systems (macOS and Linux)
        if platform_manager.termios is not None:
            # Reset terminal settings
            platform_manager.termios.tcsetattr(sys.stdin, platform_manager.termios.TCSADRAIN, platform_manager.termios.tcgetattr(sys.stdin))
            
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

def getch():
    """Simple getch implementation for Linux."""
    try:
        if platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            old = platform_manager.termios.tcgetattr(fd)
            new = platform_manager.termios.tcgetattr(fd)
            new[3] = new[3] & ~platform_manager.termios.ICANON & ~platform_manager.termios.ECHO
            new[6][platform_manager.termios.VMIN] = 1
            new[6][platform_manager.termios.VTIME] = 0
            platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSANOW, new)
            try:
                c = os.read(fd, 1)
                return c.decode('utf-8')
            finally:
                platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSAFLUSH, old)
        else:
            return input()[:1]
    except:
        return None

def get_key():
    """Get a single keypress from the user."""
    if platform_manager.msvcrt is not None:
        try:
            return platform_manager.msvcrt.getch().decode('utf-8')
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
            elif platform_manager.is_macos() or sys.platform.startswith('linux'):
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

def get_current_device_sample_rate(device_id):
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
        if not platform_manager.is_wsl():
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

def timed_input(prompt, timeout=3, default='n'):
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
    if sys.platform == 'win32' and not platform_manager.is_wsl():
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
    if (sys.platform != 'win32' or platform_manager.is_wsl() or windows_method_failed):
        # Reset start time if we're falling back from Windows method
        if windows_method_failed:
            start_time = time.time()
        
        # Check if we can use select on this platform
        try:
            # On Windows (non-WSL), select doesn't work with stdin, so use a different approach
            if sys.platform == 'win32' and not platform_manager.is_wsl():
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
                        response = timed_input(f"\nWould you like to proceed with {device['max_input_channels']} channel(s) instead? (y/N): ", timeout=3, default='n')

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
                            if not platform_manager.is_wsl():
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
                            response = timed_input("\nThe specified device could not be used. Would you like to proceed with an alternative device? (y/N): ", timeout=3, default='n')
                            if response.lower() != 'y':
                                print("Exiting as requested.")
                                sys.exit(1)
                            print("Falling back to device search...")
                else:
                    print(f"\nERROR: Specified device ID {app.device_id} is not an input device")
                    response = timed_input("\nThe specified device is not an input device. Would you like to proceed with an alternative device? (y/N): ", timeout=3, default='n')
                    if response.lower() != 'y':
                        print("Exiting as requested.")
                        sys.exit(1)
                    print("Falling back to device search...")
            except Exception as e:
                print(f"\nERROR: Could not access specified device ID {app.device_id}")
                print(f"Reason: {str(e)}")
                response = timed_input("\nThe specified device could not be accessed. Would you like to proceed with an alternative device? (y/N): ", timeout=3, default='n')
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
                        response = timed_input(f"\nWould you like to proceed with {actual_channels} channel(s) instead? (y/N): ", timeout=3, default='n')
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
                response = timed_input(f"\nWould you like to proceed with {actual_channels} channel(s) instead? (y/N): ", timeout=3, default='n')
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


def clear_input_buffer():
    """Clear the keyboard input buffer. Handles both Windows and non-Windows platforms."""
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        try:
            while platform_manager.msvcrt is not None and platform_manager.msvcrt.kbhit():
                platform_manager.msvcrt.getch()
        except Exception as e:
            print(f"Warning: Could not clear input buffer: {e}")
    else:
        # For macOS and Linux/WSL
        if platform_manager.termios is not None and platform_manager.tty is not None:
            fd = sys.stdin.fileno()
            try:
                # Save old terminal settings
                old_settings = platform_manager.termios.tcgetattr(fd)
                
                # Set non-blocking mode
                platform_manager.tty.setraw(fd, platform_manager.termios.TCSANOW)
                
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
                    platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSADRAIN, old_settings)
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


def show_audio_device_info_for_SOUND_IN_OUT():
    """Display detailed information about the selected audio input and output devices."""
    print("\nSelected Audio Device Information:")
    print("-" * 50)
    
    # Get and display input device info
    try:
        input_info = sd.query_devices(sound_in_id)
        print("\nInput Device:")
        print(f"Name: [{sound_in_id}] {input_info['name']}")
        print(f"Default Sample Rate: {int(input_info['default_samplerate'])} Hz")
        print(f"Bit Depth: {config.PRIMARY_BITDEPTH} bits")
        print(f"Max Input Channels: {input_info['max_input_channels']}")
        print(f"Current Sample Rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz")
        print(f"Current Channels: {sound_in_chs}")
        if 'hostapi' in input_info:
            hostapi_info = sd.query_hostapis(index=input_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting input device info: {e}")
    
    # Get and display output device info
    try:
        output_info = sd.query_devices(sound_out_id)
        print("\nOutput Device:")
        print(f"Name: [{sound_out_id}] {output_info['name']}")
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


def show_audio_device_list():
    """Display detailed information about the selected audio input and output devices."""
    print("\nSelected Audio Device Information:")
    print("-" * 50)
    
    # Get and display input device info
    try:
        input_info = sd.query_devices(sound_in_id)
        print("\nInput Device:")
        print(f"Name: [{sound_in_id}] {input_info['name']}")
        print(f"Default Sample Rate: {int(input_info['default_samplerate'])} Hz")
        print(f"Bit Depth: {config.PRIMARY_BITDEPTH} bits")
        print(f"Max Input Channels: {input_info['max_input_channels']}")
        print(f"Current Sample Rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz")
        print(f"Current Channels: {sound_in_chs}")
        if 'hostapi' in input_info:
            hostapi_info = sd.query_hostapis(index=input_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting input device info: {e}")
    
    # Get and display output device info
    try:
        output_info = sd.query_devices(sound_out_id)
        print("\nOutput Device:")
        print(f"Name: [{sound_out_id}] {output_info['name']}")
        print(f"Default Sample Rate: {int(output_info['default_samplerate'])} Hz")
        print(f"Max Output Channels: {output_info['max_output_channels']}")
        if 'hostapi' in output_info:
            hostapi_info = sd.query_hostapis(index=output_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting output device info: {e}")
    
    print("-" * 50)
    sys.stdout.flush()


def get_enabled_mic_locations():
    """
    Reads microphone enable states (MIC_1 to MIC_4) and maps to their corresponding locations.
    """
    # Define microphone states and corresponding locations
    mic_location_names = [config.MIC_LOCATION[i] for i, enabled in enumerate(MICS_ACTIVE) if enabled]
    return mic_location_names

##mic_location_names = get_enabled_mic_locations()
def show_mic_locations():
    print("Enabled microphone locations:", get_enabled_mic_locations())


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


def check_stream_status(stream_duration):
    """
    Check the status of a sounddevice input stream for overflows and underflows.
    Parameters:
    - stream_duration: Duration for which the stream should be open and checked (in seconds).
    """
    global sound_in_id
    print(f"Checking input stream for overflow. Watching for {stream_duration} seconds")

    # Define a callback function to process the audio stream
    def callback(indata, frames, time, status):
        if status and status.input_overflow:
                print("Input overflow detected at:", datetime.datetime.now())

    # Open an input stream
    with sd.InputStream(callback=callback, device=sound_in_id) as stream:
        # Run the stream for the specified duration
        timeout = time.time() + stream_duration
        while time.time() < timeout:
            time.sleep(0.1)  # Sleep for a short duration before checking again

    print("Stream checking finished at", datetime.datetime.now())
    show_audio_device_info_for_SOUND_IN_OUT()


# fetch the most recent audio file in the directory
def find_file_of_type_with_offset_1(directory=PRIMARY_DIRECTORY, file_type=config.PRIMARY_FILE_FORMAT, offset=0):
    # Expand path if it contains a tilde
    expanded_dir = os.path.expanduser(directory)
    
    # Ensure directory exists
    if not os.path.exists(expanded_dir):
        print(f"Directory does not exist: {expanded_dir}")
        return None
        
    try:
        matching_files = [os.path.join(expanded_dir, f) for f in os.listdir(expanded_dir) \
                          if os.path.isfile(os.path.join(expanded_dir, f)) and f.endswith(f".{file_type.lower()}")]
        if offset < len(matching_files):
            return matching_files[offset]
    except Exception as e:
        print(f"Error listing files in {expanded_dir}: {e}")
    
    return None

# return the most recent audio file in the directory minus offset (next most recent, etc.)
def find_file_of_type_with_offset(offset, directory=PRIMARY_DIRECTORY, file_type=config.PRIMARY_FILE_FORMAT):
    # Expand path if it contains a tilde
    expanded_dir = os.path.expanduser(directory)
    
    print(f"\nSearching for {file_type} files in: {expanded_dir}")
    
    # Ensure directory exists
    if not os.path.exists(expanded_dir):
        print(f"Directory does not exist: {expanded_dir}")
        return None
        
    try:
        # List all files in the directory first
        all_files = os.listdir(expanded_dir)
        print(f"All files in directory: {all_files}")
        
        # List all files of the specified type in the directory (case-insensitive)
        files_of_type = [f for f in all_files if os.path.isfile(os.path.join(expanded_dir, f)) and f.lower().endswith(f".{file_type.lower()}")]
        
        if not files_of_type:
            print(f"No {file_type} files found in directory: {expanded_dir}")
            print(f"Looking for files ending with: .{file_type.lower()} (case-insensitive)")
            return None
            
        # Sort files alphabetically - most recent first
        files_of_type.sort(reverse=True)
        print(f"Found {len(files_of_type)} {file_type} files: {files_of_type}")
        
        if offset < len(files_of_type):
            selected_file = files_of_type[offset]
            print(f"Selected file at offset {offset}: {selected_file}")
            return selected_file
        else:
            print(f"Offset {offset} is out of range. Found {len(files_of_type)} {file_type} files.")
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
        return f"[{'#' * bar_length}]"
    
    
    percent = min(100, int(current * 100 / total))
    filled_length = int(bar_length * current // total)
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

# single-shot plot of 'n' seconds of audio of each channels for an oscope view
def plot_oscope(sound_in_id, sound_in_chs, queue): 
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
            
        recording, actual_channels = _record_audio_pyaudio(
            config.TRACE_DURATION, sound_in_id, sound_in_chs, queue, "oscilloscope traces"
        )
        
        if recording is None:
            logging.error("Failed to record audio for oscilloscope.")
            return

        # Apply gain if needed
        if config.OSCOPE_GAIN_DB > 0:
            gain = 10 ** (config.OSCOPE_GAIN_DB / 20)      
            logging.info(f"Applying gain of: {gain:.1f}") 
            recording *= gain

        logging.info("Creating oscilloscope plot...")
        # Create figure with reduced DPI for better performance
        fig = plt.figure(figsize=(10, 3 * actual_channels), dpi=80)
        
        # Optimize plotting by downsampling for display
        downsample_factor = max(1, len(recording) // 5000)  # Limit points to ~5k for better performance
        time_points = np.arange(0, len(recording), downsample_factor) / config.PRIMARY_IN_SAMPLERATE
        
        # Plot each channel
        for i in range(actual_channels):
            ax = plt.subplot(actual_channels, 1, i+1)
            ax.plot(time_points, recording[::downsample_factor, i], linewidth=0.5)
            ax.set_title(f"Oscilloscope Traces w/{config.OSCOPE_GAIN_DB}dB Gain--Ch{i+1}")
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
        plotname = os.path.join(PLOT_DIRECTORY, f"{timestamp}_oscope_{int(config.PRIMARY_IN_SAMPLERATE/1000)}_kHz_{config.PRIMARY_BITDEPTH}_{config.LOCATION_ID}_{config.HIVE_ID}.png")
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
            if platform_manager.is_wsl():
                logging.info("Opening image in WSL...")
                try:
                    subprocess.Popen(['xdg-open', expanded_path])
                except FileNotFoundError:
                    subprocess.Popen(['wslview', expanded_path])
                logging.info("Image viewer command executed")
            elif platform_manager.is_macos():
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

def trigger_oscope():
    """Trigger oscilloscope plot generation with proper cleanup."""
    try:
        # Clean up any existing process
        cleanup_process('o')
        clear_input_buffer()
        
        # Create a queue for communication
        stop_queue = multiprocessing.Queue()
        
        # Create and configure the process
        oscope_process = multiprocessing.Process(
            target=plot_oscope, 
            args=(sound_in_id, sound_in_chs, stop_queue)
        )
        
        # Set process as daemon
        oscope_process.daemon = True
        
        # Store in active processes
        active_processes['o'] = oscope_process
        
        print("Starting oscilloscope process...")
        # Start the process
        oscope_process.start()
        
        # Wait for completion with timeout
        timeout = config.TRACE_DURATION + 30  # Reduced timeout to be more responsive
        oscope_process.join(timeout=timeout)
        
        # Check if process is still running
        if oscope_process.is_alive():
            print("\nOscilloscope process taking too long, terminating...")
            try:
                # Signal the process to stop
                stop_queue.put(True)
                # Give it a moment to clean up
                time.sleep(1)
                # Then terminate if still running
                if oscope_process.is_alive():
                    oscope_process.terminate()
                    oscope_process.join(timeout=2)
                    if oscope_process.is_alive():
                        oscope_process.kill()
            except Exception as e:
                print(f"Error terminating oscilloscope process: {e}")
        
    except Exception as e:
        print(f"Error in trigger_oscope: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always ensure cleanup
        cleanup_process('o')
        clear_input_buffer()
        print("Oscilloscope process completed")

def cleanup_process(command):
    """Clean up a specific command's process."""
    try:
        # Check if the command key exists in active_processes
        if command in active_processes:
            process = active_processes[command]
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
                active_processes[command] = None
                print(f"Process for command '{command}' has been cleaned up")
        else:
            # The command doesn't exist in our tracking dictionary
            print(f"Warning: No process tracking for command '{command}'")
    except Exception as e:
        print(f"Error in cleanup_process for command '{command}': {e}")

# Global variables for buffer management
buffer_wrap_event = threading.Event()

def callback(indata, frames, time, status):
    """Callback function for audio input stream."""
    global buffer, buffer_index, buffer_size
    if status:
        print("Callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    data_len = len(indata)

    # managing the circular buffer
    if buffer_index + data_len <= buffer_size:
        buffer[buffer_index:buffer_index + data_len] = indata
        buffer_wrap_event.clear()
    else:
        overflow = (buffer_index + data_len) - buffer_size
        buffer[buffer_index:] = indata[:-overflow]
        buffer[:overflow] = indata[-overflow:]
        buffer_wrap_event.set()

    buffer_index = (buffer_index + data_len) % buffer_size

def setup_audio_circular_buffer():
    """Set up the circular buffer for audio recording."""
    global buffer_size, buffer, buffer_index, buffer_wrap, blocksize
    
    # Get values from app instance
    buffer_size = int(app.BUFFER_SECONDS * app.PRIMARY_IN_SAMPLERATE)
    buffer = np.zeros((buffer_size, app.sound_in_chs), dtype=app._dtype)
    buffer_index = 0
    buffer_wrap = False
    blocksize = 8196
    buffer_wrap_event.clear()
    
    # Update app instance with buffer info
    app.buffer_size = buffer_size
    app.buffer = buffer
    app.buffer_index = buffer_index
    app.blocksize = blocksize
    
    print(f"\naudio buffer size: {sys.getsizeof(buffer)}\n")
    sys.stdout.flush()

def recording_worker_thread(record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
    """Worker thread for recording audio to files."""
    global buffer, buffer_size, buffer_index, stop_recording_event
    
    if start_tod is None:
        print(f"{thread_id} is recording continuously\r")

    samplerate = app.PRIMARY_IN_SAMPLERATE

    while not stop_recording_event.is_set():
        try:
            current_time = datetime.datetime.now().time()
            
            if start_tod is None or (start_tod <= current_time <= end_tod):        
                print(f"{thread_id} started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec\r")

                period_start_index = buffer_index 
                # wait PERIOD seconds to accumulate audio
                interruptable_sleep(record_period, stop_recording_event)

                # Check if we're shutting down before saving
                if stop_recording_event.is_set():
                    break

                period_end_index = buffer_index 
                save_start_index = period_start_index % buffer_size
                save_end_index = period_end_index % buffer_size

                # saving from a circular buffer so segments aren't necessarily contiguous
                if save_end_index > save_start_index:   # indexing is contiguous
                    audio_data = buffer[save_start_index:save_end_index]
                else:                                   # ain't contiguous so concatenate to make it contiguous
                    audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

                # Determine the sample rate to use for saving
                save_sample_rate = app.PRIMARY_SAVE_SAMPLERATE if app.PRIMARY_SAVE_SAMPLERATE is not None else app.PRIMARY_IN_SAMPLERATE
                
                # Resample if needed
                if save_sample_rate < app.PRIMARY_IN_SAMPLERATE:
                    # resample to lower sample rate
                    audio_data = downsample_audio(audio_data, app.PRIMARY_IN_SAMPLERATE, save_sample_rate)
                    print(f"Resampling from {app.PRIMARY_IN_SAMPLERATE}Hz to {save_sample_rate}Hz for saving")

                # Check if we're shutting down before saving
                if stop_recording_event.is_set():
                    break

                # Check and create new date folders if needed
                if not check_and_create_date_folders():
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
                        print(f"Unsupported file format: {file_format}")
                        continue
                        
                    print(f"{thread_id} saved: {filename}\r")
                    
                except Exception as e:
                    print(f"Error saving {filename}: {e}")
                    continue

                # Wait for the next recording interval
                if not stop_recording_event.is_set():
                    interruptable_sleep(interval, stop_recording_event)
            else:
                # Not in recording time window, wait briefly and check again
                interruptable_sleep(10, stop_recording_event)
                
        except Exception as e:
            print(f"Error in {thread_id}: {e}")
            if not stop_recording_event.is_set():
                interruptable_sleep(30, stop_recording_event)  # Wait before retrying

def check_and_create_date_folders():
    """Check and create date-based folders if needed."""
    global app
    
    try:
        current_date = datetime.datetime.now().strftime("%y%m%d")
        
        # Check if date has changed and update folder paths if needed
        if current_date != app.date_folder:
            print(f"Date changed from {app.date_folder} to {current_date}, updating directory paths...")
            app.date_folder = current_date
            
            # Update directory paths
            app.PRIMARY_DIRECTORY = os.path.join(app.data_drive, app.data_path, app.config.LOCATION_ID, app.config.HIVE_ID,
                                                app.folders[0], "raw", app.date_folder)
            app.MONITOR_DIRECTORY = os.path.join(app.data_drive, app.data_path, app.config.LOCATION_ID, app.config.HIVE_ID,
                                                app.folders[0], "mp3", app.date_folder)
            app.PLOT_DIRECTORY = os.path.join(app.data_drive, app.data_path, app.config.LOCATION_ID, app.config.HIVE_ID,
                                             app.folders[1], app.date_folder)
            
            # Ensure paths end with separator
            app.PRIMARY_DIRECTORY = os.path.join(app.PRIMARY_DIRECTORY, "")
            app.MONITOR_DIRECTORY = os.path.join(app.MONITOR_DIRECTORY, "")
            app.PLOT_DIRECTORY = os.path.join(app.PLOT_DIRECTORY, "")
            
            # Update global variables for backward compatibility
            # update_globals_from_app()  # TODO: Implement this function
        
        # Ensure directories exist
        return ensure_directories_exist([app.PRIMARY_DIRECTORY, app.MONITOR_DIRECTORY, app.PLOT_DIRECTORY])
        
    except Exception as e:
        print(f"Error in check_and_create_date_folders: {e}")
        return False

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
def reset_terminal_settings():
    """Reset terminal settings to default state without clearing the screen."""
    try:
        if platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            old_settings = platform_manager.termios.tcgetattr(fd)
            platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSANOW, old_settings)
    except Exception as e:
        print(f"Warning: Could not reset terminal settings: {e}")

def audio_stream():
    """Main audio streaming function."""
    global app, stop_program, buffer, buffer_size, buffer_index
    
    # Reset terminal settings before printing
    reset_terminal_settings()

    # Print initialization info with forced output
    print("Initializing audio stream...", flush=True)
    print(f"Device ID: [{app.sound_in_id}]", end='\r', flush=True)
    print(f"Channels: {app.sound_in_chs}", end='\r', flush=True)
    print(f"Sample Rate: {int(app.PRIMARY_IN_SAMPLERATE)} Hz", end='\r', flush=True)
    print(f"Bit Depth: {app.PRIMARY_BITDEPTH} bits", end='\r', flush=True)
    print(f"Data Type: {app._dtype}", end='\r', flush=True)

    try:
        # First verify the device configuration
        device_info = sd.query_devices(app.sound_in_id)
        print("\nSelected device info:", flush=True)
        print(f"Name: [{app.sound_in_id}] {device_info['name']}", end='\r', flush=True)
        print(f"Max Input Channels: {device_info['max_input_channels']}", end='\r', flush=True)
        print(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz", end='\r', flush=True)

        if device_info['max_input_channels'] < app.sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {app.sound_in_chs} channels are required")

        # Set the device's sample rate to match our configuration
        sd.default.samplerate = app.PRIMARY_IN_SAMPLERATE
        
        # Initialize the stream with the configured sample rate and bit depth
        stream = sd.InputStream(
            device=app.sound_in_id,
            channels=app.sound_in_chs,
            samplerate=app.PRIMARY_IN_SAMPLERATE,
            dtype=app._dtype,
            blocksize=app.blocksize,
            callback=callback
        )

        print("\nAudio stream initialized successfully\r", flush=True)
        print(f"Stream sample rate: {stream.samplerate} Hz", end='\r', flush=True)
        print(f"Stream bit depth: {app.PRIMARY_BITDEPTH} bits", end='\r', flush=True)

        with stream:
            # start the recording worker threads
            if hasattr(app.config, 'MODE_AUDIO_MONITOR') and app.config.MODE_AUDIO_MONITOR:
                print("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...\r")
                threading.Thread(target=recording_worker_thread, args=(
                    app.config.AUDIO_MONITOR_RECORD,
                    app.config.AUDIO_MONITOR_INTERVAL,
                    "Audio_monitor",
                    app.config.AUDIO_MONITOR_FORMAT,
                    app.config.AUDIO_MONITOR_SAMPLERATE,
                    getattr(app.config, 'AUDIO_MONITOR_START', None),
                    getattr(app.config, 'AUDIO_MONITOR_END', None)
                )).start()

            if hasattr(app.config, 'MODE_PERIOD') and app.config.MODE_PERIOD and not app.testmode:
                print("Starting recording_worker_thread for caching period audio at primary sample rate and all channels...\r")
                threading.Thread(target=recording_worker_thread, args=(
                    app.config.PERIOD_RECORD,
                    app.config.PERIOD_INTERVAL,
                    "Period_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'PERIOD_START', None),
                    getattr(app.config, 'PERIOD_END', None)
                )).start()

            if hasattr(app.config, 'MODE_EVENT') and app.config.MODE_EVENT and not app.testmode:
                print("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...\r")
                threading.Thread(target=recording_worker_thread, args=(
                    app.config.SAVE_BEFORE_EVENT,
                    app.config.SAVE_AFTER_EVENT,
                    "Event_recording",
                    app.config.PRIMARY_FILE_FORMAT,
                    app.PRIMARY_IN_SAMPLERATE,
                    getattr(app.config, 'EVENT_START', None),
                    getattr(app.config, 'EVENT_END', None)
                )).start()

            # Wait for keyboard input to stop
            while not stop_program[0]:
                time.sleep(0.1)

    except Exception as e:
        print(f"\nError initializing audio stream: {str(e)}")
        print("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        return False

    return True

def stop_all():
    """Stop all processes and threads."""
    global stop_program, keyboard_listener_running, app, buffer_wrap_event
    
    print("\nStopping all processes and threads...")
    
    # Set stop flags
    stop_program[0] = True
    keyboard_listener_running = False
    
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
    
    # Signal buffer wrap event to unblock any waiting threads
    buffer_wrap_event.set()
    
    # Clean up active processes
    if 'active_processes' in globals():
        for key in active_processes:
            cleanup_process(key)
    
    # Give threads a moment to finish
    time.sleep(0.5)
    
    print("All processes stopped.")

def cleanup():
    """Clean up and exit."""
    global original_terminal_settings
    
    print("\nPerforming cleanup...")
    
    # Stop all processes first (but don't print duplicate messages)
    global stop_program, keyboard_listener_running, app, buffer_wrap_event
    
    # Set stop flags
    stop_program[0] = True
    keyboard_listener_running = False
    
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
    
    # Signal buffer wrap event to unblock any waiting threads
    buffer_wrap_event.set()
    
    # Clean up active processes
    if 'active_processes' in globals():
        for key in active_processes:
            cleanup_process(key)
    
    # Force close any remaining sounddevice streams
    try:
        sd.stop()  # Stop all sounddevice streams
        time.sleep(0.1)
    except Exception as e:
        print(f"Note: Error stopping sounddevice streams: {e}")
    
    # Restore terminal settings
    if original_terminal_settings:
        restore_terminal_settings(original_terminal_settings)
    else:
        reset_terminal_settings()
    
    print("Cleanup completed.")
    
    # Force exit to prevent hanging
    import os
    os._exit(0)

def keyboard_listener():
    """Main keyboard listener loop."""
    global app, keyboard_listener_running, keyboard_listener_active, monitor_channel
    global change_ch_event, vu_proc, intercom_proc
    
    # Reset terminal settings before starting
    reset_terminal_settings()
    
    print("\nKeyboard listener started. Press 'h' for help.", end='\n', flush=True)
    
    while keyboard_listener_running:
        try:
            key = get_key()
            if key is not None:
                if key == "^":  # Toggle listening
                    toggle_listening()
                elif keyboard_listener_active:
                    if key.isdigit():
                        # Handle direct channel changes when in VU meter or Intercom mode
                        if vu_proc is not None or intercom_proc is not None:
                            key_int = int(key) - 1  # Convert to 0-based index
                            
                            # Validate channel number is within range
                            if key_int < 0 or key_int >= app.sound_in_chs:
                                print(f"\nInvalid channel selection: Device has only {app.sound_in_chs} channel(s) (1-{app.sound_in_chs})", end='\n', flush=True)
                                continue
                                
                            monitor_channel = key_int
                            if intercom_proc is not None:
                                change_ch_event.set()
                            print(f"\nNow monitoring channel: {monitor_channel+1} (of {app.sound_in_chs})", end='\n', flush=True)
                            # Restart VU meter if running
                            if vu_proc is not None:
                                print(f"Restarting VU meter on channel: {monitor_channel+1}", end='\n', flush=True)
                                toggle_vu_meter()
                                time.sleep(0.1)
                                toggle_vu_meter()
                        else:
                            if key == "0":
                                print("Exiting channel change", end='\n', flush=True)
                            else:
                                print(f"Unknown command: {key}", end='\n', flush=True)
                    elif key == "a": 
                        check_stream_status(10)
                    elif key == "c":  
                        change_monitor_channel()
                    elif key == "d":  
                        show_audio_device_list()
                    elif key == "f":  
                        try:
                            trigger_fft()
                        except Exception as e:
                            print(f"Error in FFT trigger: {e}", end='\n', flush=True)
                            cleanup_process('f')
                    elif key == "i":  
                        toggle_intercom_m()
                    elif key == "m":  
                        show_mic_locations()
                    elif key == "o":  
                        trigger_oscope()        
                    elif key == "q":  
                        print("\nQuitting...", end='\n', flush=True)
                        keyboard_listener_running = False
                        stop_all()
                    elif key == "s":  
                        trigger_spectrogram()
                    elif key == "t":  
                        list_all_threads()        
                    elif key == "v":  
                        toggle_vu_meter()      
                    elif key == "h" or key =="?":  
                        show_list_of_commands()
                
        except Exception as e:
            print(f"Error in keyboard listener: {e}", end='\n', flush=True)
            continue
            
        time.sleep(0.01)  # Small delay to prevent high CPU usage

def toggle_listening():
    """Toggle keyboard listener active state."""
    global keyboard_listener_active
    keyboard_listener_active = not keyboard_listener_active
    if keyboard_listener_active:
        print("\nKeyboard listener activated. Listening for commands...")
        show_list_of_commands()
    else:
        print("\nKeyboard listener deactivated. Press '^' to reactivate.")
        stop_vu()
        stop_intercom_m()

def show_list_of_commands():
    """Display available keyboard commands."""
    print("\nAvailable Commands:")
    print("  a - Check audio stream status")
    print("  c - Change monitor channel")
    print("  d - Show audio device list")
    print("  f - Generate FFT plot")
    print("  h/? - Show this help")
    print("  i - Toggle intercom")
    print("  m - Show microphone locations")
    print("  o - Generate oscilloscope plot")
    print("  q - Quit application")
    print("  s - Generate spectrogram")
    print("  t - List active threads")
    print("  v - Toggle VU meter")
    print("  ^ - Toggle keyboard listener")
    print("  1-4 - Direct channel selection")

def change_monitor_channel():
    """Change the monitor channel."""
    global monitor_channel
    print(f"\nCurrent monitor channel: {monitor_channel + 1}")
    print(f"Device has {app.sound_in_chs} channel(s) available")
    print("Enter new channel number (1-{}) or 0 to cancel: ".format(app.sound_in_chs), end='', flush=True)
    
    try:
        choice = input()
        if choice == "0":
            print("Channel change cancelled")
            return
        
        new_channel = int(choice) - 1  # Convert to 0-based
        if 0 <= new_channel < app.sound_in_chs:
            monitor_channel = new_channel
            print(f"Monitor channel changed to: {monitor_channel + 1}")
        else:
            print(f"Invalid channel. Must be 1-{app.sound_in_chs}")
    except ValueError:
        print("Invalid input. Please enter a number.")

def toggle_vu_meter():
    """Toggle VU meter display - PLACEHOLDER."""
    print("VU meter toggle placeholder - full implementation pending")

def toggle_intercom_m():
    """Toggle intercom functionality - PLACEHOLDER."""
    print("Intercom toggle placeholder - full implementation pending")

def stop_vu():
    """Stop VU meter - PLACEHOLDER."""
    print("Stop VU meter placeholder - full implementation pending")

def stop_intercom_m():
    """Stop intercom - PLACEHOLDER."""
    print("Stop intercom placeholder - full implementation pending")

def trigger_fft():
    """Trigger FFT plot generation - PLACEHOLDER."""
    print("FFT trigger placeholder - full implementation pending")

def trigger_spectrogram():
    """Trigger spectrogram generation - PLACEHOLDER."""
    print("Spectrogram trigger placeholder - full implementation pending")

def emergency_cleanup(signum, frame):
    """Emergency cleanup handler for signals."""
    print(f"\nEmergency cleanup triggered by signal {signum}")
    cleanup()
    sys.exit(0)

# Global variables for application control
app = None
fft_periodic_plot_proc = None
oscope_proc = None
one_shot_fft_proc = None
monitor_channel = 0
keyboard_listener_running = True
keyboard_listener_active = True
original_terminal_settings = None
stop_program = [False]

# Global variables for buffer management
buffer = None
buffer_size = None
buffer_index = None
buffer_wrap_event = threading.Event()

# Global variables for processes and events
vu_proc = None
intercom_proc = None
change_ch_event = threading.Event()

def main():
    """Main function to initialize and run the BmarApp."""
    global app, fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel
    global keyboard_listener_running, original_terminal_settings, stop_program
    
    # Create and initialize the application
    app = BmarApp()
    app.initialize()
    
    print("BmarApp initialized successfully!")
    print(f"Primary directory: {app.PRIMARY_DIRECTORY}")
    print(f"Monitor directory: {app.MONITOR_DIRECTORY}")
    print(f"Plot directory: {app.PLOT_DIRECTORY}")
    
    # Set up audio device
    if not set_input_device(app):
        print("Failed to configure audio input device. Exiting.")
        sys.exit(1)
    
    # Display selected device information
    show_audio_device_info_for_SOUND_IN_OUT()
    
    # Set monitor channel with validation
    if monitor_channel >= app.sound_in_chs:
        monitor_channel = 0
        print(f"Setting monitor channel to {monitor_channel+1}")

    # Set up audio circular buffer
    setup_audio_circular_buffer()
    
    print(f"Buffer size: {app.BUFFER_SECONDS} seconds, {buffer.size/500000:.2f} megabytes")
    print(f"Sample Rate: {int(app.PRIMARY_IN_SAMPLERATE)} Hz; File Format: {app.config.PRIMARY_FILE_FORMAT}; Channels: {app.sound_in_chs}")

    # Check and create date-based directories
    if not check_and_create_date_folders():
        print("Critical directories could not be created. Exiting.")
        sys.exit(1)
    
    # Print directories for verification
    print("Directory setup:")
    print(f"  Primary recordings: {app.PRIMARY_DIRECTORY}")
    print(f"  Monitor recordings: {app.MONITOR_DIRECTORY}")
    print(f"  Plot files: {app.PLOT_DIRECTORY}")
    
    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, emergency_cleanup)
    signal.signal(signal.SIGTERM, emergency_cleanup)
    
    # Start keyboard listener in a separate thread
    if hasattr(app, 'KB_or_CP') and app.KB_or_CP == 'KB':
        time.sleep(1)  # Give a small delay to ensure prints are visible
        keyboard_thread = threading.Thread(target=keyboard_listener)
        keyboard_thread.daemon = True
        keyboard_thread.start()
        print("Keyboard listener started successfully!")
    
    print("Application ready for use.")
    print("Press 'h' for help with keyboard commands.")
    
    try:
        # Start the audio stream
        result = audio_stream()
        if not result:
            print("Audio stream failed to start properly.")
    except KeyboardInterrupt:
        print('\nCtrl-C: Recording process stopped by user.')
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure cleanup happens
        try:
            cleanup()
        except SystemExit:
            pass  # Allow os._exit() to work
        except Exception as e:
            print(f"Error during final cleanup: {e}")
            import os
            os._exit(1)

if __name__ == "__main__":
    main()

