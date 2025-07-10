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

import BMAR_config_lmw as config
##os.environ['NUMBA_NUM_THREADS'] = '1'

# Near the top of the file, after the imports
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
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                    build_number = int(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])
                    product_name = winreg.QueryValueEx(key, "ProductName")[0]
                    
                    if build_number >= 22000:
                        self._os_info = "Windows 11 Pro"
                    else:
                        self._os_info = product_name
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
            if multiprocessing.current_process().name == 'MainProcess':
                logging.info(f"Detected operating system: {self.get_os_info()}")
            
            if sys.platform == 'win32' and not self.is_wsl():
                import msvcrt
                self._msvcrt = msvcrt
                if multiprocessing.current_process().name == 'MainProcess':
                    logging.info("Using Windows keyboard handling (msvcrt)")
                self._keyboard_info = "Windows"
            elif self.is_macos() or (sys.platform != 'win32' and not self.is_wsl()):
                try:
                    import termios
                    import tty
                    import fcntl
                    self._termios = termios
                    self._tty = tty
                    self._fcntl = fcntl
                    if multiprocessing.current_process().name == 'MainProcess':
                        logging.info("Using Unix keyboard handling (termios)")
                    self._keyboard_info = "Unix"
                except ImportError:
                    if multiprocessing.current_process().name == 'MainProcess':
                        logging.warning("termios module not available. Some keyboard functionality may be limited.")
                    self._keyboard_info = "Limited"
            else:
                self._msvcrt = None
                if multiprocessing.current_process().name == 'MainProcess':
                    logging.info("Using limited keyboard handling")
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
        
        self.MICS_ACTIVE = [self.config.MIC_1, self.config.MIC_2, self.config.MIC_3, self.config.MIC_4]
        
        # --- Dynamic State ---
        self.monitor_channel = 0
        self.file_offset = 0
        self.stop_program = False
        self.testmode = True

        # Buffer
        self.buffer = None
        self.buffer_size = 0
        self.buffer_index = 0
        
        # Process and Thread Management
        self.active_processes = {
            'v': None, 'o': None, 's': None, 'f': None, 
            'i': None, 'p': None, 'P': None
        }
        self.mp_manager = multiprocessing.Manager()
        self.original_terminal_settings = None
        self.keyboard_listener_running = True
        self.keyboard_listener_active = True
        
        # Events
        self.buffer_wrap_event = threading.Event()
        self.stop_recording_event = threading.Event()
        self.stop_intercom_event = threading.Event()
        self.stop_vu_event = threading.Event()
        self.stop_fft_periodic_plot_event = multiprocessing.Event()
        self.stop_performance_monitor_event = threading.Event()
        self.change_ch_event = threading.Event()
        self.buffer_lock = threading.Lock()
        self.blocksize = 0 # Let driver choose optimal block size
        
        # Misc
        self.time_diff = self._create_time_diff_func()
        self.fft_interval = 30 # minutes

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

    def setup_audio_circular_buffer(self):
        """Initializes the main audio circular buffer."""
        BUFFER_SECONDS = 1000 
        self.buffer_size = int(BUFFER_SECONDS * self.config.PRIMARY_IN_SAMPLERATE)
        self.buffer = np.zeros((self.buffer_size, self.sound_in_chs), dtype=self._dtype)
        self.buffer_index = 0
        self.buffer_wrap_event.clear()
        logging.info(f"Audio buffer created: {self.buffer.nbytes / 1e6:.2f} MB")

    def _create_time_diff_func(self):
        last_called = [None]
        def helper():
            current_time = time.time()
            if last_called[0] is None:
                last_called[0] = current_time
                return 1800
            diff = current_time - last_called[0]
            last_called[0] = current_time
            return min(diff, 1800)
        return helper

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
#buffer_size = None
#buffer = None
#buffer_index = None
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
#FFT_INTERVAL = 30                               # minutes between ffts

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



def get_api_name_for_device(device_id):
    device = sd.query_devices(device_id)
    hostapi_info = sd.query_hostapis(index=device['hostapi'])
    return hostapi_info['name']

def get_windows_sample_rate(device_name):
    """Get the actual sample rate from Windows using PyAudio."""
    try:
        import pyaudio
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

def prompt_with_timeout(prompt, timeout=3, default='n'):
    """
    Prompts the user for input with a timeout. Returns the default value if the timeout is reached 
    or if the user just presses Enter.
    """
    print(prompt, end='', flush=True)
    
    # For Unix-like systems (macOS, Linux, WSL)
    if platform_manager.termios:
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            response = sys.stdin.readline().strip()
            return response if response else default
        else:
            print() # Newline for clarity
            return default

    # For Windows
    elif platform_manager.msvcrt:
        import msvcrt
        start_time = time.time()
        input_buffer = []
        while True:
            if time.time() - start_time > timeout:
                print() # Newline
                return default
            if msvcrt.kbhit():
                char_byte = msvcrt.getch()
                # Handle Enter
                if char_byte in (b'\r', b'\n'):
                    print()
                    return "".join(input_buffer) if input_buffer else default
                # Handle Backspace
                elif char_byte == b'\x08':
                    if input_buffer:
                        input_buffer.pop()
                        # Erase character from console
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                else:
                    try:
                        char = char_byte.decode()
                        input_buffer.append(char)
                        sys.stdout.write(char)
                        sys.stdout.flush()
                    except UnicodeDecodeError:
                        pass # Ignore non-decodeable characters
            time.sleep(0.01)
    
    # Fallback for unsupported platforms where timed input is not possible.
    else:
        try:
            response = input()
            return response if response else default
        except EOFError:
            return default

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

def dummy_callback(indata, frames, time, status):
    """A dummy callback that does nothing, to force non-blocking mode."""
    pass

def set_input_device(app):
    """Find and configure a suitable audio input device based on settings in the app object."""
    logging.info("Scanning for audio input devices...")
    sys.stdout.flush()

    # Initialize testmode to True. It will be set to False upon success.
    app.testmode = True

    print_all_input_devices()

    devices = sd.query_devices()
    devices_to_try = []

    # If a specific device ID is provided, try it first.
    if app.device_id is not None and app.device_id >= 0:
        try:
            device_info = sd.query_devices(app.device_id)
            if device_info['max_input_channels'] > 0:
                devices_to_try.append((app.device_id, device_info))
            else:
                logging.error(f"Specified device ID {app.device_id} is not an input device.")
        except Exception as e:
            logging.error(f"Could not access specified device ID {app.device_id}: {e}")

    # If no specific device or it failed, create a sorted list of all input devices.
    if not devices_to_try:
        logging.info("No valid device ID specified or device not found, scanning all available devices.")
        preferred_apis = ['Windows WASAPI', 'Windows WDM-KS', 'MME', 'Windows DirectSound', 'ASIO']
        all_devices = sorted(
            [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0],
            key=lambda item: preferred_apis.index(sd.query_hostapis(index=item[1]['hostapi'])['name']) if sd.query_hostapis(index=item[1]['hostapi'])['name'] in preferred_apis else len(preferred_apis)
        )
        devices_to_try = all_devices

    # Now, iterate through the list of devices and probe each one sequentially.
    for dev_id, device in devices_to_try:
        api_name = sd.query_hostapis(index=device['hostapi'])['name']
        logging.info(f"--- Probing Device [{dev_id}]: {device['name']} (API: {api_name}) ---")

        original_channels = app.sound_in_chs
        actual_channels = min(app.sound_in_chs, device['max_input_channels'])
        
        if actual_channels < original_channels:
            logging.warning(f"Channel count mismatch for device [{dev_id}]: Config wants {original_channels}, but device only supports {actual_channels}.")
            response = prompt_with_timeout(f"Proceed with {actual_channels} channel(s)? (y/N): ", timeout=3, default='n')
            if response.lower() != 'y':
                logging.info("User declined or timeout expired. Skipping device.")
                continue
        
        # --- Attempt 1: Configured Sample Rate ---
        sr1 = app.config.PRIMARY_IN_SAMPLERATE
        logging.info(f"  > Attempt 1: Probing with configured SR {sr1} Hz...")
        try:
            with sd.InputStream(device=dev_id, channels=actual_channels, samplerate=sr1, dtype=app._dtype, blocksize=0, callback=dummy_callback):
                pass # Success if this block executes without error
            logging.info(f"*** SUCCESS with configured rate {sr1} Hz ***")
            app.sound_in_id = dev_id
            app.sound_in_chs = actual_channels
            app.config.PRIMARY_IN_SAMPLERATE = sr1
            app.testmode = False
            return True
        except sd.PortAudioError as e:
            logging.warning(f"    > FAILED. Reason: {str(e).strip()}")
        except Exception as e:
            logging.error(f"    > FAILED with unexpected error.", exc_info=True)

        time.sleep(0.1) # Small delay for stability

        # --- Attempt 2: Device Default Sample Rate ---
        sr2 = int(device['default_samplerate'])
        if sr2 != sr1:
            logging.info(f"  > Attempt 2: Probing with device default SR {sr2} Hz...")
            try:
                with sd.InputStream(device=dev_id, channels=actual_channels, samplerate=sr2, dtype=app._dtype, blocksize=0, callback=dummy_callback):
                    pass
                logging.info(f"*** SUCCESS with device default rate {sr2} Hz ***")
                app.sound_in_id = dev_id
                app.sound_in_chs = actual_channels
                app.config.PRIMARY_IN_SAMPLERATE = sr2
                app.testmode = False
                return True
            except sd.PortAudioError as e:
                logging.warning(f"    > FAILED. Reason: {str(e).strip()}")
            except Exception as e:
                logging.error(f"    > FAILED with unexpected error.", exc_info=True)
        else:
            logging.info(f"  > Skipping Attempt 2: Default rate is same as configured rate.")

        time.sleep(0.1)

        # --- Attempt 3: Universal Fallback Rate ---
        sr3 = 44100
        if sr3 not in [sr1, sr2]:
            logging.info(f"  > Attempt 3: Probing with universal fallback SR {sr3} Hz...")
            try:
                with sd.InputStream(device=dev_id, channels=actual_channels, samplerate=sr3, dtype=app._dtype, blocksize=0, callback=dummy_callback):
                    pass
                logging.info(f"*** SUCCESS with fallback rate {sr3} Hz ***")
                app.sound_in_id = dev_id
                app.sound_in_chs = actual_channels
                app.config.PRIMARY_IN_SAMPLERATE = sr3
                app.testmode = False
                return True
            except sd.PortAudioError as e:
                logging.warning(f"    > FAILED. Reason: {str(e).strip()}")
            except Exception as e:
                logging.error(f"    > FAILED with unexpected error.", exc_info=True)
        else:
            logging.info(f"  > Skipping Attempt 3: Fallback rate already tried.")

    # If all devices and rates have been tried and failed
    logging.critical("No suitable audio input device could be configured.")
    logging.critical("Please check your audio device connections, drivers, and configuration.")
    sys.exit(1)
    return False # Should be unreachable due to sys.exit

# interruptable sleep
def interruptable_sleep(seconds, stop_sleep_event):
    start_time = time.time()
    while time.time() - start_time < seconds:
        if stop_sleep_event.is_set():
            return
        # Sleep for a short duration before checking again
        time.sleep(0.1)

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
    if audio_data.shape[1] == 2:
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

        def callback(in_data, frame_count, time_info, status):
            nonlocal frames_recorded, recording_complete
            try:
                if status:
                    logging.warning(f"PyAudio stream status: {status}")
                if frames_recorded < num_frames and not recording_complete:
                    data = np.frombuffer(in_data, dtype=np.float32)
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
        import time
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

def trigger_oscope(app):
    """Trigger oscilloscope plot generation with proper cleanup."""
    try:
        cleanup_process('o', app)
        clear_input_buffer()
        
        stop_queue = multiprocessing.Queue()
        
        oscope_process = multiprocessing.Process(
            target=plot_oscope, 
            args=(app.sound_in_id, app.sound_in_chs, stop_queue)
        )
        
        oscope_process.daemon = True
        app.active_processes['o'] = oscope_process
        
        print("Starting oscilloscope process...")
        oscope_process.start()
        
        timeout = app.config.TRACE_DURATION + 30
        oscope_process.join(timeout=timeout)
        
        if oscope_process.is_alive():
            print("\nOscilloscope process taking too long, terminating...")
            try:
                stop_queue.put(True)
                time.sleep(1)
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
        cleanup_process('o', app)
        clear_input_buffer()
        print("Oscilloscope process completed")

def cleanup_process(command, app):
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


# single-shot fft plot of audio
def plot_fft(sound_in_id, sound_in_chs, channel, stop_queue):
    try:
        # Force garbage collection before starting
        gc.collect()
        
        # Ensure clean matplotlib state for this process
        import matplotlib
        matplotlib.use('Agg', force=True)
        import matplotlib.pyplot as plt
        plt.close('all')  # Close any existing figures
        
        # Brief delay to ensure clean audio device state
        import time
        time.sleep(0.1)
        
        recording, actual_channels = _record_audio_pyaudio(
            config.FFT_DURATION, sound_in_id, sound_in_chs, stop_queue, "FFT analysis"
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
        if config.FFT_GAIN > 0:
            gain = 10 ** (config.FFT_GAIN / 20)
            logging.info(f"Applying FFT gain of: {gain:.1f}")
            single_channel_audio *= gain

        logging.info("Performing FFT...")
        # Perform FFT
        yf = rfft(single_channel_audio.flatten())
        xf = rfftfreq(len(single_channel_audio), 1 / config.PRIMARY_IN_SAMPLERATE)

        # Define bucket width
        bucket_width = FFT_BW  # Hz
        bucket_size = int(bucket_width * len(single_channel_audio) / config.PRIMARY_IN_SAMPLERATE)  # Number of indices per bucket

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
        plotname = os.path.join(PLOT_DIRECTORY, f"{timestamp}_fft_{int(config.PRIMARY_IN_SAMPLERATE/1000)}_kHz_{config.PRIMARY_BITDEPTH}_{config.LOCATION_ID}_{config.HIVE_ID}.png")
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
            
            if platform_manager.is_wsl():
                logging.info("Opening image in WSL...")
                try:
                    proc = subprocess.Popen(['xdg-open', expanded_path])
                    logging.info(f"xdg-open launched with PID: {proc.pid}")
                except FileNotFoundError:
                    logging.info("xdg-open not found, trying wslview...")
                    proc = subprocess.Popen(['wslview', expanded_path])
                    logging.info(f"wslview launched with PID: {proc.pid}")
            elif platform_manager.is_macos():
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
            if platform_manager.is_wsl() or not sys.platform == 'win32':
                print(f"  xdg-open '{expanded_path}'")
            elif platform_manager.is_macos():
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
        cleanup_process('f', app)
        
        stop_queue = multiprocessing.Queue()
        
        fft_process = multiprocessing.Process(
            target=plot_fft,
            args=(app.sound_in_id, app.sound_in_chs, app.monitor_channel, stop_queue)
        )
        
        app.active_processes['f'] = fft_process
        
        fft_process.start()
        
        timeout = app.config.FFT_DURATION + 30
        fft_process.join(timeout=timeout)
        
        if fft_process.is_alive():
            print("\nFFT process taking too long, terminating...")
            try:
                stop_queue.put(True)
                time.sleep(1)
                if fft_process.is_alive():
                    fft_process.terminate()
                    fft_process.join(timeout=2)
                    if fft_process.is_alive():
                        fft_process.kill()
            except Exception as e:
                print(f"Error terminating FFT process: {e}")
        
    except Exception as e:
        print(f"Error in trigger_fft: {e}")
    finally:
        try:
            cleanup_process('f', app)
        except Exception as e:
            print(f"Warning during cleanup: {e}")
        clear_input_buffer()
        print("FFT process completed")

def trigger_spectrogram(app):
    """Trigger spectrogram generation."""
    try:
        cleanup_process('s', app)
        clear_input_buffer()
        
        time_since_last = app.time_diff()
        
        if time_since_last < (app.config.PERIOD_RECORD + app.config.PERIOD_INTERVAL):
            app.file_offset = min(app.file_offset + 1, 0)
        else:
            app.file_offset = 0
            
        print(f"Time since last file: {time_since_last:.1f}s, using file offset: {app.file_offset}")
            
        spectrogram_process = multiprocessing.Process(
            target=plot_spectrogram, 
            args=(app.monitor_channel, 'lin', app.file_offset, app.config.PERIOD_SPECTROGRAM)
        )
        app.active_processes['s'] = spectrogram_process
        spectrogram_process.daemon = True
        spectrogram_process.start()
        
        time.sleep(0.2)
        
        print("Plotting spectrogram...")
        clear_input_buffer()
        
        spectrogram_process.join(timeout=240)
        
        if spectrogram_process.is_alive():
            print("Spectrogram process taking too long, terminating...")
            try:
                spectrogram_process.terminate()
                spectrogram_process.join(timeout=1)
                if spectrogram_process.is_alive():
                    spectrogram_process.kill()
                    spectrogram_process.join(timeout=1)
            except Exception as e:
                print(f"Warning during process termination: {e}")
        
    except Exception as e:
        print(f"Error in trigger_spectrogram: {e}")
    finally:
        try:
            cleanup_process('s', app)
        except Exception as e:
            print(f"Warning during cleanup: {e}")
        clear_input_buffer()
        print("Spectrogram process completed")
        

def plot_spectrogram(channel, y_axis_type, file_offset, period):
    """
    Generate a spectrogram from an audio file and display/save it as an image.
    Parameters:
    - channel: Channel to use for multi-channel audio files
    - y_axis_type: Type of Y axis for the spectrogram ('log' or 'linear')
    - file_offset: Offset for finding the audio file
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
        
        next_spectrogram = find_file_of_type_with_offset(file_offset)
        
        if next_spectrogram is None:
            print("No data available to see?")
            return
            
        full_audio_path = os.path.join(PRIMARY_DIRECTORY, next_spectrogram)
        print("Spectrogram source:", full_audio_path)

        print("Loading audio file with librosa...")
        # Variables to ensure cleanup
        y = None
        sr = None
        D_db = None
        
        try:
            # For spectrogram display, limit duration to avoid memory issues
            max_duration = min(config.PERIOD_RECORD, period)  # Max 5 minutes for display
            
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
            plotname = os.path.join(PLOT_DIRECTORY, f"{timestamp}_{root}_spectrogram.png")

            # Set title to include filename and channel
            plt.title(f'Spectrogram from {config.LOCATION_ID}, hive:{config.HIVE_ID}, Mic Loc:{config.MIC_LOCATION[channel]}\nfile:{filename}, Ch:{channel+1}')
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
                if platform_manager.is_wsl():
                    print("Opening image in WSL...")
                    try:
                        subprocess.Popen(['xdg-open', expanded_path])
                    except FileNotFoundError:
                        subprocess.Popen(['wslview', expanded_path])
                elif platform_manager.is_macos():
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

def check_wsl_audio():
    """Check WSL audio configuration and provide setup instructions."""
    try:
        import subprocess
        import os
        
        # Set PulseAudio server to use TCP
        os.environ['PULSE_SERVER'] = 'tcp:localhost'
        
        # Check if PulseAudio is running
        result = subprocess.run(['pulseaudio', '--check'], capture_output=True, text=True)
        if result.returncode != 0:
            print("\nPulseAudio is not running. Starting it...")
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
        return False

def vu_meter(sound_in_id, sound_in_chs, channel, stop_vu_queue, asterisks_proxy, debug_verbose, primary_samplerate, is_wsl):
    """Process target function for displaying a VU meter."""
    if debug_verbose:
        logging.debug(f"[VU Debug] Process started. Params: sound_in_id={sound_in_id}, sound_in_chs={sound_in_chs}, channel={channel}")

    buffer_size = int(primary_samplerate)
    last_print = ""
    
    # Validate the channel is valid for the device
    if channel >= sound_in_chs:
        logging.warning(f"VU Meter: Selected channel {channel+1} exceeds available channels ({sound_in_chs}). Defaulting to channel 1.")
        channel = 0

    def callback_input(indata, frames, time_info, status):
        nonlocal last_print
        if status:
            logging.warning(f"VU meter stream status: {status}")
        try:
            selected_channel = int(min(channel, indata.shape[1] - 1))
            channel_data = indata[:, selected_channel]
            audio_level = np.max(np.abs(channel_data))
            normalized_value = int((audio_level / 1.0) * 50)
            
            # Use the manager proxy to share the value
            asterisks_proxy.value = '*' * normalized_value
            current_print = ' ' * 11 + asterisks_proxy.value.ljust(50, ' ')
            
            if current_print != last_print:
                print(current_print, end='\r')
                last_print = current_print
                sys.stdout.flush()
        except Exception as e:
            logging.error(f"VU meter callback error: {e}", exc_info=True)
            time.sleep(0.1)

    try:
        if is_wsl:
            logging.warning("VU meter may not be fully supported on WSL. Using fallback settings.")
            if not check_wsl_audio():
                raise Exception("WSL audio configuration check failed.")
            
            # Use minimal settings for WSL
            stream_params = {
                'device': None, 'channels': 1, 'samplerate': 48000,
                'blocksize': 1024, 'latency': 'low', 'callback': callback_input
            }
        else:
            # Standard settings for Windows/macOS/Linux
            stream_params = {
                'device': int(sound_in_id) if sound_in_id is not None else None,
                'channels': int(sound_in_chs),
                'samplerate': int(primary_samplerate),
                'blocksize': 1024, 'latency': 'low', 'callback': callback_input
            }

        with sd.InputStream(**stream_params):
            while not stop_vu_queue.get():
                sd.sleep(100)
    except Exception as e:
        logging.error(f"Error in VU meter process: {e}", exc_info=True)
    finally:
        logging.info("VU meter process shutting down...")

def toggle_vu_meter(app):
    """Toggles the VU meter on and off."""
    clear_input_buffer()

    vu_process_info = app.active_processes.get('v')
    is_running = vu_process_info and vu_process_info[0].is_alive()

    if not is_running:
        # Clean up any zombie process entry before starting a new one
        cleanup_process('v', app)
        
        # Validate channel before starting process
        if app.monitor_channel >= app.sound_in_chs:
            logging.warning(f"Selected channel {app.monitor_channel+1} exceeds available channels ({app.sound_in_chs}). Defaulting to channel 1.")
            app.monitor_channel = 0
            
        logging.info(f"Starting VU meter on channel: {app.monitor_channel+1}")
        
        stop_vu_queue = multiprocessing.Queue()
        stop_vu_queue.put(False)
        asterisks_proxy = app.mp_manager.Value('c', '*' * 50)

        logging.info(f"Channel {app.monitor_channel + 1} audio:")
        print("fullscale:", asterisks_proxy.value.ljust(50, ' '))

        if app.config.MODE_EVENT:
            normalized_value = int(app.config.EVENT_THRESHOLD / 1000)
            print("threshold:", ('*' * normalized_value).ljust(50, ' '))
            
        # Create and start the new process
        debug_verbose = app.config.DEBUG_VERBOSE if hasattr(app.config, 'DEBUG_VERBOSE') else False
        primary_samplerate = app.config.PRIMARY_IN_SAMPLERATE
        is_wsl = app.platform_manager.is_wsl()
        
        vu_proc = multiprocessing.Process(
            target=vu_meter, 
            args=(app.sound_in_id, app.sound_in_chs, app.monitor_channel, stop_vu_queue, asterisks_proxy, debug_verbose, primary_samplerate, is_wsl),
            name="VUMeterProcess"
        )
        vu_proc.daemon = True
        vu_proc.start()
            
        # Store the new process and its queue in our tracking dictionary
        app.active_processes['v'] = (vu_proc, stop_vu_queue, asterisks_proxy)
    else:
        # If it is running, stop it
        stop_vu(app)
    
    clear_input_buffer()

def stop_vu(app):
    """Stops the VU meter process if it's running."""
    vu_process_info = app.active_processes.get('v')
    if not vu_process_info:
        return

    # The process and its queue are stored as a tuple
    vu_proc, stop_vu_queue, _ = vu_process_info
    if vu_proc and vu_proc.is_alive():
        try:
            app.stop_vu_event.set()
            stop_vu_queue.put(True)
            
            vu_proc.join(timeout=1)
            
            if vu_proc.is_alive():
                vu_proc.terminate()
                vu_proc.join(timeout=1)
                if vu_proc.is_alive():
                    vu_proc.kill()
            
            print("\nvu stopped")
        except Exception as e:
            print(f"\nError stopping VU meter: {e}")
        finally:
            # Clear the process from our tracking dictionary
            app.active_processes['v'] = None
            clear_input_buffer()

#
# ############ intercom using multiprocessing #############
#

def intercom_m_downsampled(sound_in_id, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel):

    # Create a buffer to hold the audio data
    buffer_size = config.PRIMARY_IN_SAMPLERATE // 4      # For 48,000 samples per second
    buffer = np.zeros((buffer_size,))
    channel = monitor_channel

    # Callback function to handle audio input
    def callback_input(indata, frames, time, status):
        # Only process audio from the designated channel
        channel_data = indata[:, channel]
        # Downsample the audio using resampy
        downsampled_data = resampy.resample(channel_data, config.PRIMARY_IN_SAMPLERATE, 44100)
        buffer[:len(downsampled_data)] = downsampled_data

    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        # Play back the audio from the buffer
        outdata[:, 0] = buffer[:frames]         # Play back on the first channel
        ##outdata[:, 1] = buffer[:frames]         # Play back on the second channel

    # Open an input stream and an output stream with the callback function
    with sd.InputStream(callback=callback_input, device=sound_in_id, channels=sound_in_chs, samplerate=config.PRIMARY_IN_SAMPLERATE), \
        sd.OutputStream(callback=callback_output, device=sound_out_id, channels=sound_out_chs, samplerate=sound_out_samplerate): 
        # The streams are now open and the callback function will be called every time there is audio input and output
        while not stop_intercom_event.is_set():
            sd.sleep(1000)  # Changed from 1 to 1000 milliseconds
        print("Stopping intercom...")


def intercom_m(sound_in_id, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel):
    print(f"[Intercom] Monitoring channel: {monitor_channel+1}", end='\r\n')
    # Create a buffer to hold the audio data at input sample rate
    buffer = np.zeros((int(config.PRIMARY_IN_SAMPLERATE),))
    
    # Validate the channel is valid for the device
    if monitor_channel >= sound_in_chs:
        print(f"\nError: Selected channel {monitor_channel+1} exceeds available channels ({sound_in_chs})", end='\r\n')
        print(f"Defaulting to channel 1", end='\r\n')
        channel = 0  # Default to first channel
    else:
        channel = monitor_channel
        
    last_error_time = 0
    error_count = 0

    # Callback function to handle audio input
    def callback_input(indata, frames, time, status):
        nonlocal channel, last_error_time, error_count
        if status:
            current_time = time.time()
            if current_time - last_error_time > 1:  # Only print errors once per second
                print(f"Input status: {status}")
                last_error_time = current_time
                error_count += 1
                
        # Only process audio from the designated channel
        try:
            channel_data = indata[:, channel]
            # Downsample the audio using linear interpolation (simple and fast)
            num_samples = len(channel_data)
            x = np.linspace(0, 1, num=num_samples)
            xp = np.linspace(0, 1, num=int(num_samples * sound_out_samplerate / config.PRIMARY_IN_SAMPLERATE))
            downsampled_data = np.interp(xp, x, channel_data)
            
            # Fill the buffer with the downsampled audio data
            buffer_len = len(buffer)
            data_len = len(downsampled_data)
            
            if data_len > buffer_len:
                buffer[:] = downsampled_data[-buffer_len:]
            else:
                buffer[-data_len:] = downsampled_data
        except IndexError:
            if time.time() - last_error_time > 1:
                print(f"\nError: Channel index {channel} is out of bounds for the input data.", end='\r\n')
                last_error_time = time.time()
                channel = 0 # Fallback to first channel
        except Exception as e:
            if time.time() - last_error_time > 1:
                print(f"\nError in input callback: {e}", end='\r\n')
                last_error_time = time.time()
    
    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        nonlocal last_error_time
        if status:
            current_time = time.time()
            if current_time - last_error_time > 1:
                print(f"Output status: {status}")
                last_error_time = current_time
                
        # Play back the audio from the buffer
        buffer_len = len(buffer)
        if frames <= buffer_len:
            playback_data = buffer[-frames:]
        else:
            playback_data = np.concatenate((np.zeros(frames - buffer_len), buffer))
            
        # Ensure correct shape for output
        outdata[:] = playback_data.reshape(-1, 1)

    # Open an input stream and an output stream with the callback function
    try:
        with sd.InputStream(device=sound_in_id, channels=sound_in_chs, samplerate=config.PRIMARY_IN_SAMPLERATE, callback=callback_input, latency='low'), \
             sd.OutputStream(device=sound_out_id, channels=sound_out_chs, samplerate=sound_out_samplerate, callback=callback_output, latency='low'):
            # The streams are now open and the callback function will be called every time there is audio input and output
            while not stop_intercom_event.is_set():
                sd.sleep(100)  # Sleep for a short duration
            print("Stopping intercom...")
    except Exception as e:
        print(f"Error starting intercom stream: {e}", end='\r\n')


def stop_intercom_m(app):
    """Stop the intercom process."""
    if app.active_processes.get('i'):
        print("Stopping intercom...")
        app.stop_intercom_event.set()
        process = app.active_processes['i']
        if process.is_alive():
            process.join(timeout=1)
            if process.is_alive():
                process.terminate()
        app.active_processes['i'] = None

def toggle_intercom_m(app):
    """Toggle the intercom on and off."""
    if app.active_processes.get('i') and app.active_processes['i'].is_alive():
        stop_intercom_m(app)
        return

    # Cleanup before starting a new one
    cleanup_process('i', app)
    
    app.stop_intercom_event.clear()
    
    # Default to first channel if current monitor channel is out of bounds
    if app.monitor_channel >= app.sound_in_chs:
        logging.warning(f"Intercom: Selected channel {app.monitor_channel+1} exceeds available channels ({app.sound_in_chs}). Defaulting to channel 1.")
        monitor_channel = 0
    else:
        monitor_channel = app.monitor_channel
        
    print("Starting intercom...")
    intercom_process = multiprocessing.Process(
        target=intercom_m, 
        args=(
            app.sound_in_id, 
            app.sound_in_chs, 
            app.sound_out_id, 
            app.sound_out_samplerate, 
            app.sound_out_chs, 
            monitor_channel
        )
    )
    intercom_process.daemon = True
    app.active_processes['i'] = intercom_process
    intercom_process.start()

def change_monitor_channel(app):
    """
    Prompts the user to enter a new monitor channel and updates it.
    """
    global monitor_channel
    print("\n------------------------------")
    print(f"Current monitor channel is: {app.monitor_channel + 1}")
    print("------------------------------\n")
    
    # Print the enabled microphone locations
    mic_locations = get_enabled_mic_locations()
    if mic_locations:
        print("Enabled Microphone Locations:")
        for i, location in enumerate(mic_locations):
            # We add 1 to i to make it 1-based for the user
            print(f"  Channel {i + 1}: {location}")
        print()
    else:
        print("No microphones enabled in config.\n")
    
    # Create a list of currently active channels
    active_channels = [i + 1 for i, enabled in enumerate(app.MICS_ACTIVE) if enabled]
    
    if not active_channels:
        print("No active microphone channels to switch to.")
        return
        
    # Ask the user for the new channel
    try:
        new_channel_str = input(f"Enter new monitor channel (1-{len(active_channels)}): ")
        if not new_channel_str:
            print("No input received. Aborting.")
            return
            
        new_channel = int(new_channel_str)
        
        # Validate the user's input
        if new_channel not in active_channels:
            print(f"Invalid channel. Please choose from {active_channels}.")
            return
            
        # Update the monitor channel (adjusting for 0-based index)
        app.monitor_channel = new_channel - 1
        
        print(f"\nMonitor channel changed to: {app.monitor_channel + 1}")
        
        # Restart the VU meter if it's active
        if app.active_processes.get('v') and app.active_processes['v'][0].is_alive():
            print("Restarting VU meter for new channel...")
            toggle_vu_meter(app) # Stop it
            time.sleep(0.5) # Give it a moment to stop
            toggle_vu_meter(app) # Start it again
        
        # Restart the intercom if it's active
        if app.active_processes.get('i') and app.active_processes['i'].is_alive():
            print("Restarting intercom for new channel...")
            toggle_intercom_m(app) # Stop it
            time.sleep(0.5) # Give it a moment to stop
            toggle_intercom_m(app) # Start it again
            
    except ValueError:
        print("Invalid input. Please enter a number.")
    except Exception as e:
        print(f"An error occurred: {e}")

#
# ############ periodic functions #############
#
def plot_and_save_fft(stop_event, config):
    """
    This function will be run in a separate thread.
    It will periodically record audio, generate an FFT plot, and save it to a file.
    """
    while not stop_event.is_set():
        try:
            # Record audio for a specified duration
            print("Recording audio for FFT...")
            audio_data = sd.rec(int(config.FFT_DURATION * config.PRIMARY_IN_SAMPLERATE),
                                samplerate=config.PRIMARY_IN_SAMPLERATE,
                                channels=config.SOUND_IN_CHS,
                                dtype='int16')
            sd.wait()
            print("Recording finished.")

            # Perform FFT on the recorded audio
            print("Performing FFT...")
            fft_data = rfft(audio_data[:, 0].flatten())
            fft_freq = rfftfreq(len(audio_data), 1 / config.PRIMARY_IN_SAMPLERATE)

            # Define bucket width
            bucket_width = FFT_BW  # Hz
            bucket_size = int(bucket_width * len(audio_data) / config.PRIMARY_IN_SAMPLERATE)
            
            # Calculate the number of complete buckets
            num_buckets = len(fft_data) // bucket_size
            
            # Average buckets - ensure both arrays have the same length
            buckets = []
            bucket_freqs = []
            for i in range(num_buckets):
                start_idx = i * bucket_size
                end_idx = start_idx + bucket_size
                buckets.append(np.mean(fft_data[start_idx:end_idx]))
                bucket_freqs.append(np.mean(fft_freq[start_idx:end_idx]))

            # Create plot
            print("Creating plot...")
            plt.figure(figsize=(10, 6))
            plt.plot(bucket_freqs, np.abs(buckets))
            plt.xlabel('Frequency (Hz)')
            plt.ylabel('Amplitude')
            plt.title('FFT Plot')
            plt.grid(True)

            # Save the plot
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            plotname = f"{timestamp}_fft_{int(config.PRIMARY_IN_SAMPLERATE/1000)}_kHz_{config.PRIMARY_BITDEPTH}_{config.LOCATION_ID}_{config.HIVE_ID}.png"
            full_plot_path = os.path.join(PLOT_DIRECTORY, plotname)
            plt.savefig(full_plot_path)
            plt.close()
            print(f"Plot saved to {full_plot_path}")

        except Exception as e:
            print(f"An error occurred in the FFT thread: {e}")

        # Wait for the specified interval before the next run
        print(f"Waiting for {config.FFT_INTERVAL} minutes...")
        stop_event.wait(timeout=config.FFT_INTERVAL * 60)

def keyboard_listener(app):
    """
    This function will be run in a separate thread.
    It will listen for keyboard input and trigger actions accordingly.
    """
    
    # Save the original terminal settings
    if sys.platform != 'win32' or platform_manager.is_wsl():
        original_terminal_settings = save_terminal_settings()

    while app.keyboard_listener_running:
        try:
            # Check if listening is active
            if not app.keyboard_listener_active:
                time.sleep(0.1)
                continue

            # Check for keyboard input
            key = get_key()

            if key:
                if key.lower() == 'q':
                    print("Quitting...\r")
                    app.stop_program = True
                    stop_all(app)
                    break
                elif key.lower() == 'v':
                    toggle_vu_meter(app)
                elif key.lower() == 'i':
                    toggle_intercom_m(app)
                elif key.lower() == 'c':
                    change_monitor_channel(app)
                elif key.lower() == 's':
                    trigger_spectrogram(app)
                elif key.lower() == 'o':
                    trigger_oscope(app)
                elif key.lower() == 'f':
                    trigger_fft(app)
                elif key.lower() == 'p':
                    run_performance_monitor_once(app)
                elif key.lower() == 'l':
                    show_list_of_commands()
                elif key.isdigit():
                    new_channel = int(key)
                    set_monitor_channel(app, new_channel -1)
                else:

                    print(f"Unknown command: '{key}'\r")
                    show_list_of_commands()
            
            time.sleep(0.01) # Small sleep to prevent busy-waiting
            
        except Exception as e:
            print(f"Error in keyboard listener: {e}\r")
            
    # Restore terminal settings before exiting
    if sys.platform != 'win32' or platform_manager.is_wsl():
        restore_terminal_settings(original_terminal_settings)

def setup_raw_terminal():
    """Put terminal in raw mode for character-by-character input."""
    if platform_manager.termios is not None and platform_manager.tty is not None:
        fd = sys.stdin.fileno()
        old_settings = platform_manager.termios.tcgetattr(fd)
        try:
            platform_manager.tty.setraw(fd)
        except Exception as e:
            print(f"Could not set raw terminal mode: {e}")
        return old_settings
    return None

def restore_canonical_terminal(old_settings):
    """Restore terminal to its original canonical mode."""
    if platform_manager.termios is not None and old_settings is not None:
        fd = sys.stdin.fileno()
        platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSADRAIN, old_settings)


##########################
# recording worker thread
##########################

def recording_worker_thread(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod, startup_event=None):

    try:
        logging.info(f"Worker thread {thread_id} started. Mode: PERIODIC, Record: {record_period}s, Interval: {interval}s")
        
        # Signal that this thread's startup is complete
        if startup_event:
            startup_event.set()
        
        while not app.stop_recording_event.is_set():
            
            # Check if current time is within the allowed Time of Day (TOD) window
            now = datetime.datetime.now().time()
            if start_tod and end_tod:
                if not (start_tod <= now <= end_tod):
                    # Outside the recording window, sleep for a minute and check again
                    app.stop_recording_event.wait(60)
                    continue

            # Record a chunk of audio
            logging.info(f"Thread {thread_id}: Starting recording of {record_period} seconds.")
            
            # Using sd.rec to record a block of audio
            try:
                audio_data = sd.rec(int(record_period * app.config.PRIMARY_IN_SAMPLERATE),
                                    samplerate=app.config.PRIMARY_IN_SAMPLERATE,
                                    channels=app.sound_in_chs,
                                    dtype=app._dtype)
                sd.wait() # Wait for the recording to complete
            except Exception as e:
                logging.error(f"Error during audio recording in thread {thread_id}: {e}", exc_info=True)
                app.stop_recording_event.wait(10) # Wait before retrying
                continue
                
            logging.info(f"Thread {thread_id}: Recording finished.")

            # Create filename
            current_time = datetime.datetime.now()
            timestamp = current_time.strftime("%y%m%d_%H%M%S")
            filename = f"{timestamp}_{app.config.LOCATION_ID}_{app.config.HIVE_ID}_{int(app.config.PRIMARY_IN_SAMPLERATE/1000)}k.{file_format.lower()}"
            full_path = os.path.join(app.PRIMARY_DIRECTORY, filename)

            logging.info(f"Thread {thread_id}: Writing to file: {full_path}")
            
            # Write to file in a separate thread to avoid blocking
            write_thread = threading.Thread(
                target=sf.write,
                args=(full_path, audio_data, app.config.PRIMARY_IN_SAMPLERATE),
                kwargs={'subtype': app._subtype}
            )
            write_thread.start()
            
            # If a lower sample rate is specified for monitoring, downsample and save
            if target_sample_rate and target_sample_rate < app.config.PRIMARY_IN_SAMPLERATE:
                try:
                    logging.info(f"Thread {thread_id}: Downsampling audio to {target_sample_rate} Hz...")
                    downsampled_audio = downsample_audio(audio_data, app.config.PRIMARY_IN_SAMPLERATE, target_sample_rate)
                    
                    # Create MP3 filename for the monitor file
                    monitor_filename = f"{timestamp}_{app.config.LOCATION_ID}_{app.config.HIVE_ID}_{int(target_sample_rate/1000)}k.mp3"
                    monitor_full_path = os.path.join(app.MONITOR_DIRECTORY, monitor_filename)
                    
                    # Write downsampled audio to MP3
                    logging.info(f"Thread {thread_id}: Writing monitor file to: {monitor_full_path}")
                    pcm_to_mp3_write(downsampled_audio, monitor_full_path)
                except Exception as e:
                    logging.error(f"Error during downsampling/MP3 conversion in thread {thread_id}: {e}", exc_info=True)

            # Wait for the primary file write to complete
            write_thread.join(timeout=60)
            if write_thread.is_alive():
                logging.error(f"Thread {thread_id}: File write for {full_path} timed out.")
            else:
                logging.info(f"Thread {thread_id}: File write completed.")
                
            # Wait for the specified interval
            logging.info(f"Thread {thread_id}: Waiting for {interval} seconds...")
            app.stop_recording_event.wait(interval)

    except Exception as e:
        logging.critical(f"Unhandled exception in worker thread {thread_id}: {e}", exc_info=True)
    finally:
        logging.info(f"Worker thread {thread_id} is shutting down.")


def audio_stream(app):
    """Main audio stream handler using a callback."""
    
    # Callback function to process audio from the input stream
    def callback(indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        try:
            if status:
                logging.warning(f"Stream status: {status}")
            
            # --- Continuous Recording Logic ---
            if app.config.MODE_CONTINUOUS and not app.testmode:
                # This mode is simpler: just write the incoming data to the circular buffer.
                # The worker thread handles writing from the buffer to files.
                
                # Check for available space in the buffer
                remaining_space = app.buffer_size - app.buffer_index
                
                # If the incoming data fits, append it
                if frames <= remaining_space:
                    app.buffer[app.buffer_index : app.buffer_index + frames] = indata
                    app.buffer_index += frames
                else:
                    # If not, fill the remaining space and wrap around
                    app.buffer[app.buffer_index:] = indata[:remaining_space]
                    app.buffer[:frames - remaining_space] = indata[remaining_space:]
                    app.buffer_index = frames - remaining_space
                    
                    # Signal that the buffer has wrapped
                    app.buffer_wrap_event.set()
            
            # --- Periodic Recording Logic ---
            elif app.config.MODE_PERIOD and not app.testmode:
                # In this mode, a separate worker thread handles all recording and writing.
                # The main stream callback does nothing.
                pass
                
            # --- Event-based Recording Logic ---
            elif app.config.MODE_EVENT and not app.testmode:
                # This mode is more complex, involving level detection and pre/post-trigger recording.
                # (Implementation for this mode would go here)
                pass

        except Exception as e:
            logging.critical(f"Error in audio callback: {e}", exc_info=True)

    # Main stream logic
    try:
        logging.info("Starting audio stream...")
        
        # For PERIODIC mode, we don't need a continuously running stream here,
        # as the worker thread handles recording via sd.rec().
        if app.config.MODE_PERIOD and not app.testmode:
            logging.info("Periodic mode enabled. Main audio stream will idle.")
            # Keep the function alive to allow other threads to run
            while not app.stop_recording_event.is_set():
                app.stop_recording_event.wait(1)
            logging.info("Main audio stream function exiting.")
            return

        # For CONTINUOUS or EVENT modes, open the stream with the callback
        with sd.InputStream(
                samplerate=app.config.PRIMARY_IN_SAMPLERATE,
                device=app.sound_in_id,
                channels=app.sound_in_chs,
                dtype=app._dtype,
                latency='low',
                callback=callback):
            
            logging.info("Audio stream is active. Listening...")
            # Keep the stream open until the stop event is set
            app.stop_recording_event.wait()
            
    except Exception as e:
        logging.critical("Error initializing audio stream", exc_info=True)
    finally:
        logging.info("Audio stream has been stopped.")


def kill_worker_threads():
    """
    Stops and joins all running worker threads.
    """
    global recording_worker_thread, intercom_thread
    
    stop_recording_event.set()
    
    if recording_worker_thread and recording_worker_thread.is_alive():
        print("Stopping recording worker thread...")
        recording_worker_thread.join(timeout=2)
        if recording_worker_thread.is_alive():
            print("Warning: Recording worker thread did not exit gracefully.")
            
    if intercom_thread and intercom_thread.is_alive():
        print("Stopping intercom thread...")
        stop_intercom_event.set()
        intercom_thread.join(timeout=2)
        if intercom_thread.is_alive():
            print("Warning: Intercom thread did not exit gracefully.")

def toggle_listening(app):
    """Toggles the keyboard listener's active state."""
    app.keyboard_listener_active = not app.keyboard_listener_active
    if app.keyboard_listener_active:
        print("\nKeyboard listener is now ON.")
    else:
        print("\nKeyboard listener is now OFF. Press 'k' to re-enable.")

def stop_keyboard_listener(app):
    """Stops the keyboard listener thread."""
    global keyboard_listener_thread
    
    if keyboard_listener_thread and keyboard_listener_thread.is_alive():
        print("Stopping keyboard listener...")
        
        # Stop the listener's main loop
        app.keyboard_listener_running = False
        
        # Wait for the thread to finish
        keyboard_listener_thread.join(timeout=1)
        
        if keyboard_listener_thread.is_alive():
            print("Warning: Keyboard listener did not stop gracefully.")
        else:
            print("Keyboard listener stopped.")
    else:
        print("Keyboard listener is not running.")

##########################
# user info
##########################

def show_detailed_device_list():
    """Display a detailed list of all available audio devices."""
    print("\n--------------------------------------------------")
    print("Available Audio Devices:")
    print("--------------------------------------------------")
    
    devices = sd.query_devices()
    host_apis = sd.query_hostapis()
    
    for i, device in enumerate(devices):
        is_input = device['max_input_channels'] > 0
        is_output = device['max_output_channels'] > 0
        
        # Determine device type
        if is_input and is_output:
            device_type = "Input/Output"
        elif is_input:
            device_type = "Input"
        elif is_output:
            device_type = "Output"
        else:
            device_type = "Unknown"
            
        # Get API name
        api_name = host_apis[device['hostapi']]['name']
        
        print(f"\nDevice ID: {i} ({device_type})")
        print(f"  Name: {device['name']}")
        print(f"  API: {api_name}")
        print(f"  Max Input Channels: {device['max_input_channels']}")
        print(f"  Max Output Channels: {device['max_output_channels']}")
        print(f"  Default Sample Rate: {int(device['default_samplerate'])} Hz")
    
    print("\n--------------------------------------------------")

def show_list_of_commands():
    # define text to be displayed
    print("\n----------------------------------")
    print("Enter a command:")
    print("----------------------------------")
    print("'l': list of commands")
    print("'c': change monitor channel")
    print("'i': intercom")
    print("'v': vu meter")
    print("'s': spectrogram")
    print("'o': o-scope")
    print("'f': FFT")
    print("'p': System performance")
    print("'L': list detailed audio devices")
    print("'q': quit")
    print("----------------------------------")

# Check for required packages and dependencies
def check_dependencies(app):
    """
    Check if required Python packages and external dependencies (like ffmpeg) are installed.
    """
    print("\nChecking Python dependencies:")
    print("-" * 50)
    
    required_packages = {
        'sounddevice': '0.4.6', 
        'soundfile': '0.12.1', 
        'numpy': '1.23.5',
        'matplotlib': '3.7.1',
        'scipy': '1.10.1',
        'pydub': '0.25.1',
        'librosa': '0.10.0',
        'resampy': '0.4.2',
        'pyaudio': '0.2.13'
    }
    
    all_found = True
    
    for package, min_version in required_packages.items():
        try:
            # Use importlib.metadata to check for installed package version
            from importlib import metadata
            version = metadata.version(package)
            print(f"✓ {package:<15} found (version {version})")
        except metadata.PackageNotFoundError:
            print(f"✗ {package:<15} NOT FOUND")
            all_found = False
        except Exception as e:
            print(f"? {package:<15} found (version unknown)")

    print("-" * 50)
    
    # Check for ffmpeg
    print("\nChecking for external dependencies:")
    try:
        # Use 'ffmpeg -version' to check if it's installed and in PATH
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=True)
        print("✓ ffmpeg found at: ffmpeg")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ ffmpeg NOT FOUND in system PATH")
        print("  Please install ffmpeg and ensure it's in your system's PATH.")
        all_found = False
        
    print("-" * 50)

    if all_found:
        print("\nAll required packages and dependencies are installed and up to date!")
    else:
        print("\nSome dependencies are missing. Please install them to ensure full functionality.")
        
    print()
    return all_found


#=== Main() ============================================================

def main():
    # --- Setup Logging ---
    # NOTE: This temporary setup is for initializing the logger before the app object exists.
    # The final log path will be determined by the app state.
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    # Initialize the main application object
    app = BmarApp()
    app.initialize()

    # Set up final logging path now that directories are confirmed
    log_file_path = os.path.join(app.PRIMARY_DIRECTORY, "BMAR.log")
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)

    # Re-register cleanup with app instance
    atexit.register(cleanup, app)
    signal.signal(signal.SIGINT, lambda s, f: emergency_cleanup(s, f, app))
    signal.signal(signal.SIGTERM, lambda s, f: emergency_cleanup(s, f, app))

    # Check directories and dependencies
    if not ensure_directories_exist([app.PRIMARY_DIRECTORY, app.MONITOR_DIRECTORY, app.PLOT_DIRECTORY]):
        logging.critical("Could not create necessary directories. Exiting.")
        sys.exit(1)
    
    check_dependencies(app)
    
    # Configure the audio device
    if not set_input_device(app):
        logging.critical("Application failed to start due to audio device configuration issues.")
        return # Exit main if no device is found

    # Setup circular buffer for continuous recording modes
    #if app.config.MODE_CONTINUOUS or app.config.MODE_EVENT:
    app.setup_audio_circular_buffer()
        
    # Start the keyboard listener thread
    global keyboard_listener_thread
    keyboard_listener_thread = threading.Thread(target=keyboard_listener, args=(app,), name="KeyboardListener")
    keyboard_listener_thread.daemon = True
    keyboard_listener_thread.start()

    # --- Start Worker Threads based on Recording Mode ---
    worker_threads = []
    startup_events = []
    
    if app.config.MODE_PERIOD and not app.testmode:
        logging.info("Starting in PERIODIC mode...")
        # Create a single worker for periodic recording
        startup_event = threading.Event()
        startup_events.append(startup_event)
        
        worker = threading.Thread(
            target=recording_worker_thread,
            args=(
                app,
                app.config.PERIOD_RECORD,
                app.config.PERIOD_INTERVAL,
                1, # thread_id
                app.config.PRIMARY_FILE_FORMAT,
                app.config.AUDIO_MONITOR_SAMPLERATE,
                app.config.AUDIO_MONITOR_START,
                app.config.AUDIO_MONITOR_END,
                startup_event
            ),
            name="PeriodicRecorder"
        )
        worker_threads.append(worker)
    
    # Start all created worker threads
    for t in worker_threads:
        t.daemon = True
        t.start()

    # Wait for all worker threads to signal they have completed their startup
    if startup_events:
        logging.info("Main thread waiting for worker threads to complete startup...")
        for event in startup_events:
            event.wait(timeout=10) # 10-second timeout for each thread startup
        logging.info("All worker threads have started.")

    # Show the list of commands to the user
    show_list_of_commands()

    # Start the main audio stream (which may just idle in periodic mode)
    try:
        audio_stream(app)
    except Exception as e:
        logging.critical(f"Fatal error in main audio stream loop: {e}", exc_info=True)
    finally:
        # When audio_stream exits, it means stop_program was triggered
        stop_all(app)
        
        # Wait for all worker threads to finish
        for t in worker_threads:
            if t.is_alive():
                t.join(timeout=5)

        # Final cleanup
        cleanup(app)
        logging.info("Application has shut down gracefully.")


def stop_all(app):
    """Gracefully stop all running processes and threads."""
    logging.info("Initiating shutdown sequence...")
    
    # Stop the main audio stream and worker threads
    app.stop_recording_event.set()
    
    # Stop all subprocesses
    for command in list(app.active_processes.keys()):
        cleanup_process(command, app)
        
    # Stop the keyboard listener
    if hasattr(app, 'keyboard_listener_running'):
        app.keyboard_listener_running = False
        
    logging.info("Shutdown sequence complete.")

def cleanup(app):
    """
    Final cleanup function to be called at exit.
    Ensures all resources are released.
    """
    print("\nPerforming final cleanup...")
    
    # Ensure all threads and processes are stopped
    stop_all(app)
    
    # Ensure terminal settings are restored
    if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
        restore_terminal_settings(app.original_terminal_settings)
        print("Terminal settings restored.")

    # Close the multiprocessing manager
    try:
        if app.mp_manager:
            app.mp_manager.shutdown()
            print("Multiprocessing manager shut down.")
    except Exception as e:
        print(f"Warning: Could not shut down multiprocessing manager: {e}")

    # Force garbage collection
    gc.collect()
    
    print("Cleanup finished. Exiting.")
    # Use os._exit to force exit without hanging
    os._exit(0)

def safe_stty(command):
    """Run stty command safely, ignoring errors if it's not available."""
    try:
        subprocess.run(['stty', command], check=True, stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # stty is not available or failed, which is expected on some systems (like Git Bash on Windows)
        pass

def force_kill_child_processes():
    """Forcefully kills all child processes of the current process."""
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                print(f"Forcefully terminating child process {child.pid}...")
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        print(f"Error during force kill of child processes: {e}")

def emergency_cleanup(signum=None, frame=None, app=None):
    """
    An emergency cleanup function for SIGINT/SIGTERM.
    Tries to clean up as much as possible and then forcefully exits.
    """
    print("\nEMERGENCY SHUTDOWN ACTIVATED (Ctrl+C detected)")
    
    # --- Attempt Graceful Shutdown First ---
    if app:
        try:
            # 1. Stop all event loops and threads
            if hasattr(app, 'stop_recording_event'): app.stop_recording_event.set()
            if hasattr(app, 'keyboard_listener_running'): app.keyboard_listener_running = False
            
            # 2. Terminate all child processes
            for command in list(app.active_processes.keys()):
                cleanup_process(command, app)
                
            # 3. Restore terminal
            if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
                restore_terminal_settings(app.original_terminal_settings)
                
        except Exception as e:
            print(f"Error during graceful shutdown: {e}")

    # --- Force Kill Any Remaining Children ---
    print("Force-killing any remaining child processes...")
    force_kill_child_processes()
    
    # --- Final Exit ---
    print("Exiting application immediately.")
    # Use os._exit() for a hard exit that doesn't hang
    os._exit(1)


def save_terminal_settings():
    """Save the current terminal settings."""
    if platform_manager.termios is not None:
        try:
            return platform_manager.termios.tcgetattr(sys.stdin)
        except Exception as e:
            # This can happen if not run in a real terminal (e.g., in some IDEs)
            return None
    return None

def restore_terminal_settings(old_settings):
    """Restore saved terminal settings."""
    if platform_manager.termios is not None and old_settings is not None:
        try:
            platform_manager.termios.tcsetattr(sys.stdin, platform_manager.termios.TCSADRAIN, old_settings)
        except Exception as e:
            # Suppress errors if the file descriptor is no longer valid
            pass


def get_system_performance():
    """Get current CPU and memory usage."""
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory_info = psutil.virtual_memory()
    
    # Try to get process-specific memory usage
    try:
        process = psutil.Process(os.getpid())
        process_memory_mb = process.memory_info().rss / (1024 * 1024)
    except psutil.NoSuchProcess:
        process_memory_mb = 0

    return {
        "cpu_percent": cpu_usage,
        "total_memory_gb": memory_info.total / (1024**3),
        "available_memory_gb": memory_info.available / (1024**3),
        "used_memory_percent": memory_info.percent,
        "process_memory_mb": process_memory_mb
    }

def monitor_system_performance_once():
    """Print system performance stats once."""
    stats = get_system_performance()
    print("\n--- System Performance ---")
    print(f"  CPU Usage: {stats['cpu_percent']:.1f}%")
    print(f"  Memory Usage: {stats['used_memory_percent']:.1f}% ({stats['available_memory_gb']:.2f} GB available)")
    print(f"  This Process Memory: {stats['process_memory_mb']:.2f} MB")
    print("--------------------------")

def monitor_system_performance_continuous():
    """Continuously monitor and print system performance."""
    print("Starting continuous performance monitoring... (Press any key to stop)")
    stop_event = threading.Event()

    def monitor_loop():
        while not stop_event.is_set():
            stats = get_system_performance()
            output = (
                f"CPU: {stats['cpu_percent']:.1f}% | "
                f"Mem: {stats['used_memory_percent']:.1f}% | "
                f"ProcMem: {stats['process_memory_mb']:.2f}MB"
            )
            print(output, end='\r')
            time.sleep(1)

    monitor_thread = threading.Thread(target=monitor_loop)
    monitor_thread.daemon = True
    monitor_thread.start()

    # Wait for any key press to stop
    get_key()
    stop_event.set()
    monitor_thread.join()
    print("\nStopped continuous performance monitoring.")

def run_performance_monitor_once(app):
    """Wrapper to run the performance monitor."""
    cleanup_process('p', app)
    
    perf_proc = multiprocessing.Process(target=monitor_system_performance_once)
    app.active_processes['p'] = perf_proc
    perf_proc.start()
    perf_proc.join()
    
    cleanup_process('p', app)

def toggle_continuous_performance_monitor():
    """Toggles the continuous performance monitor."""
    global continuous_perf_proc
    
    if continuous_perf_proc and continuous_perf_proc.is_alive():
        print("Stopping continuous performance monitor...")
        continuous_perf_proc.terminate()
        continuous_perf_proc.join()
        continuous_perf_proc = None
    else:
        continuous_perf_proc = multiprocessing.Process(target=monitor_system_performance_continuous)
        continuous_perf_proc.start()

def get_key():
    """Gets a single character from standard input, works on Windows and Unix-like systems."""
    if platform_manager.msvcrt:
        if platform_manager.msvcrt.kbhit():
            return platform_manager.msvcrt.getch().decode(errors='ignore')
        return None
    elif platform_manager.termios and platform_manager.tty:
        fd = sys.stdin.fileno()
        old_settings = save_terminal_settings()
        if not old_settings: return None
        
        try:
            platform_manager.tty.setraw(fd)
            # Use select for non-blocking read with a very short timeout
            if select.select([sys.stdin], [], [], 0.01)[0]:
                return sys.stdin.read(1)
        finally:
            restore_terminal_settings(old_settings)
    return None

def set_monitor_channel(app, new_channel_index):
    """
    Sets the monitor channel to a new index and restarts relevant processes.
    """
    if new_channel_index < 0 or new_channel_index >= app.sound_in_chs:
        print(f"Invalid channel index: {new_channel_index + 1}. Must be between 1 and {app.sound_in_chs}.")
        return

    app.monitor_channel = new_channel_index
    print(f"\nMonitor channel changed to: {app.monitor_channel + 1}")

    # Restart the VU meter if it's active
    if app.active_processes.get('v') and app.active_processes['v'][0].is_alive():
        print("Restarting VU meter for new channel...")
        toggle_vu_meter(app) # Stop it
        time.sleep(0.2) # Give it a moment to stop
        toggle_vu_meter(app) # Start it again
    
    # Restart the intercom if it's active
    if app.active_processes.get('i') and app.active_processes['i'].is_alive():
        print("Restarting intercom for new channel...")
        toggle_intercom_m(app) # Stop it
        time.sleep(0.2) # Give it a moment to stop
        toggle_intercom_m(app) # Start it again

def change_monitor_channel(app):
    """
    Prompts the user to enter a new monitor channel and updates it.
    """
    print("\n------------------------------")
    print(f"Current monitor channel is: {app.monitor_channel + 1}")
    print(f"Available channels: 1 to {app.sound_in_chs}")
    print("------------------------------\n")
    
    # Temporarily enable keyboard listener if it was off
    original_state = app.keyboard_listener_active
    app.keyboard_listener_active = True
    
    try:
        new_channel_str = input(f"Enter new monitor channel (1-{app.sound_in_chs}): ")
        if not new_channel_str:
            print("No input received. Aborting.")
            return
            
        new_channel = int(new_channel_str)
        set_monitor_channel(app, new_channel - 1)
            
    except ValueError:
        print("Invalid input. Please enter a number.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Restore original listener state
        app.keyboard_listener_active = original_state


if __name__ == '__main__':
    main()