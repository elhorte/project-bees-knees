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
print(f"\n--- SCRIPT EXECUTING FROM: {os.path.abspath(__file__)} ---\n")
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
                if error_count > 10:  # If too many errors, raise an exception
                    raise RuntimeError("Too many audio input errors")

        try:
            # Safely check if channel is in bounds
            if channel < indata.shape[1]:
                channel_data = indata[:, channel]
                buffer[:frames] = channel_data
            else:
                # Handle case where channel is out of bounds
                print(f"Channel {channel+1} not available. Device has {indata.shape[1]} channels.")
                # Use the first channel as fallback
                buffer[:frames] = indata[:, 0]
        except Exception as e:
            print(f"Error in callback_input: {e}")
            print(f"Channel: {channel}, Frames: {frames}, Buffer shape: {buffer.shape}, Input shape: {indata.shape}")
            # Attempt graceful recovery without raising
            buffer[:frames] = 0  # Fill with silence

    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        if status:
            print(f"Output status: {status}")
        try:
            # Calculate how many input samples we need based on the output frames
            input_frames = int(frames * config.PRIMARY_IN_SAMPLERATE / sound_out_samplerate)
            
            # Get the input samples and resample them to output rate
            input_samples = buffer[:input_frames]
            if len(input_samples) > 0:
                # Resample the audio data to match output sample rate
                output_samples = resample(input_samples, frames)
                outdata[:, 0] = output_samples  # Play back on the first channel
                if outdata.shape[1] > 1:
                    outdata[:, 1] = output_samples  # Play back on the second channel if available
            else:
                outdata.fill(0)  # Fill with silence if no input data
        except Exception as e:
            print(f"Error in callback_output: {e}")
            print(f"Frames: {frames}, Buffer shape: {buffer.shape}, Output shape: {outdata.shape}")
            raise

    print("Starting audio streams...", end='\r\n')
    try:
        # Open an input stream and an output stream with the callback function
        with sd.InputStream(callback=callback_input, 
                          device=sound_in_id, 
                          channels=sound_in_chs, 
                          samplerate=config.PRIMARY_IN_SAMPLERATE,
                          blocksize=1024,
                          latency='low'), \
             sd.OutputStream(callback=callback_output, 
                           device=sound_out_id, 
                           channels=sound_out_chs, 
                           samplerate=sound_out_samplerate,
                           blocksize=1024,
                           latency='low'):
            print("Audio streams opened successfully", end='\r\n')
            
            # Only show device information in the main process
            if is_main_process():
                print(f"Input device: {sd.query_devices(sound_in_id)['name']} ({config.PRIMARY_IN_SAMPLERATE} Hz)")
                print(f"Output device: {sd.query_devices(sound_out_id)['name']} ({sound_out_samplerate} Hz)")
            
            # The streams are now open and the callback function will be called every time there is audio input and output
            while not stop_intercom_event.is_set():
                if change_ch_event.is_set():
                    channel = monitor_channel
                    print(f"\nIntercom changing to channel: {monitor_channel+1}", end='\r\n')
                    # Clear the buffer when changing channels to avoid audio artifacts
                    buffer.fill(0)
                    change_ch_event.clear()
                sd.sleep(10000)  # Changed from 10 to 10000 milliseconds (10 seconds)
            print("Stopping intercom...")
    except Exception as e:
        print(f"Error in intercom_m: {e}")
        print("Device configuration:")
        print(f"Input device: {sd.query_devices(sound_in_id)}")
        print(f"Output device: {sd.query_devices(sound_out_id)}")
        raise

def stop_intercom_m(app):
    if app.active_processes['i'] is not None:
        logging.info("\nStopping intercom...")
        app.stop_intercom_event.set()
        intercom_proc = app.active_processes['i']
        if intercom_proc.is_alive():
            intercom_proc.join(timeout=2)
            if intercom_proc.is_alive():
                intercom_proc.terminate()
                intercom_proc.join(timeout=1)
        app.active_processes['i'] = None
        app.stop_intercom_event.clear()
        logging.info("Intercom stopped")

def toggle_intercom_m(app):
    if app.active_processes['i'] is None:
        if app.monitor_channel >= app.sound_in_chs:
            logging.warning(f"\nError: Selected channel {app.monitor_channel+1} exceeds available channels ({app.sound_in_chs})")
            logging.warning(f"Defaulting to channel 1")
            app.monitor_channel = 0
            
        logging.info(f"Starting intercom on channel: {app.monitor_channel + 1}")
        try:
            if not hasattr(app.change_ch_event, 'set'):
                app.change_ch_event = multiprocessing.Event()
            
            input_device = sd.query_devices(app.sound_in_id)
            output_device = sd.query_devices(app.sound_out_id)
            
            if is_main_process():
                logging.info("\nDevice configuration:")
                logging.info(f"Input device: [{app.sound_in_id}] {input_device['name']}")
                logging.info(f"Input channels: {input_device['max_input_channels']}")
                logging.info(f"Input sample rate: {int(app.config.PRIMARY_IN_SAMPLERATE)} Hz")
                logging.info(f"Output device: [{app.sound_out_id}] {output_device['name']}")
                logging.info(f"Output channels: {output_device['max_output_channels']}")
                logging.info(f"Output sample rate: {int(app.sound_out_samplerate)} Hz")
            
            intercom_proc = multiprocessing.Process(
                target=intercom_m, 
                args=(app.sound_in_id, app.sound_in_chs, 
                      app.sound_out_id, app.sound_out_samplerate, app.sound_out_chs, 
                      app.monitor_channel)
            )
            intercom_proc.daemon = True
            intercom_proc.start()
            app.active_processes['i'] = intercom_proc
            logging.info("Intercom process started successfully")
        except Exception as e:
            logging.error("Error starting intercom process", exc_info=True)
            app.active_processes['i'] = None
    else:
        stop_intercom_m(app)
        logging.info("\nIntercom stopped")

def change_monitor_channel(app):
    clear_input_buffer()
    
    logging.info(f"\nAvailable channels: 1-{app.sound_in_chs}")
    logging.info("Press channel number (1-9) to monitor, or 0/q to exit:")
    
    while True:
        try:
            key = get_key()
            if key is None:
                time.sleep(0.01)
                continue
                
            if key == '0' or key.lower() == 'q':
                logging.info("\nExiting channel change")
                clear_input_buffer()
                return
                
            if key.isdigit() and int(key) > 0:
                key_int = int(key) - 1
                
                if key_int < app.sound_in_chs:
                    app.monitor_channel = key_int
                    logging.info(f"\nNow monitoring channel: {app.monitor_channel+1} (of {app.sound_in_chs})")
                    
                    if app.active_processes['i'] is not None:
                        app.change_ch_event.set()
                    
                    if app.active_processes['v'] is not None:
                        logging.info(f"Restarting VU meter on channel: {app.monitor_channel+1}")
                        toggle_vu_meter(app)
                        time.sleep(0.1)
                        toggle_vu_meter(app)
                    
                    clear_input_buffer()
                    return
                else:
                    logging.warning(f"\nInvalid channel selection: Device has only {app.sound_in_chs} channel(s) (1-{app.sound_in_chs})")
            else:
                if key.isprintable() and key != '0' and key.lower() != 'q':
                    logging.warning(f"\nInvalid input: '{key}'. Use 1-{app.sound_in_chs} for channels or 0/q to exit.")
                    
        except Exception as e:
            logging.error(f"\nError reading input: {e}")
            continue

def keyboard_listener(app):
    """Main keyboard listener loop."""
    ##reset_terminal_settings()
    logging.info("\nstarted. Press 'h' for help.")
    
    while app.keyboard_listener_running:
        try:
            key = get_key()
            if key is not None:
                if key == "^":
                    toggle_listening(app)
                elif app.keyboard_listener_active:
                    # This section for numeric keys needs more refactoring, will address later
                    if key.isdigit() and int(key) > 0:
                        logging.warning(f"Direct channel switching with number keys is temporarily disabled during refactor.")
                    elif key == "a": 
                        check_stream_status(10) # TODO: Refactor
                    elif key == "c":  
                        change_monitor_channel(app)
                    elif key == "d":  
                        show_audio_device_list() # TODO: Refactor
                    elif key == "D":  
                        show_detailed_device_list() # TODO: Refactor
                    elif key == "f":  
                        trigger_fft(app)
                    elif key == "i":  
                        toggle_intercom_m(app)
                    elif key == "m":  
                        show_mic_locations() # TODO: Refactor
                    elif key == "o":  
                        trigger_oscope(app)        
                    elif key == "p":
                        run_performance_monitor_once(app)
                    elif key == "P":
                        toggle_continuous_performance_monitor(app)
                    elif key == "q":  
                        logging.info("\nQuitting...")
                        app.keyboard_listener_running = False
                        stop_all(app)
                    elif key == "s":  
                        trigger_spectrogram(app)
                    elif key == "t":  
                        list_all_threads()        
                    elif key == "v":  
                        toggle_vu_meter(app)      
                    elif key == "h" or key =="?":  
                        show_list_of_commands()
                
        except Exception as e:
            logging.error("Error in keyboard listener", exc_info=True)
            continue
            
        time.sleep(0.01)

#
# continuous fft plot of audio in a separate background process
#

def plot_and_save_fft(stop_event, config):
    """
    Periodically records audio, generates an FFT plot, and saves it to a file.
    This function is designed to run in a separate process.
    """
    # Import necessary libraries inside the new process
    import matplotlib.pyplot as plt
    import numpy as np
    import datetime
    import os
    from scipy.fft import rfft, rfftfreq
    import sounddevice as sd
    import logging

    interval = config.get('interval', 1800)
    n_samples = config.get('n_samples')
    gain = config.get('gain', 1.0)
    samplerate = config.get('samplerate')
    channel = config.get('channel', 0)
    total_channels = config.get('total_channels', 1)
    bucket_width = config.get('bucket_width', 1000)
    plot_directory = config.get('plot_directory')
    filename_parts = config.get('filename_parts', {})

    if not all([n_samples, samplerate, plot_directory]):
        logging.error("Periodic FFT process missing required configuration.")
        return

    while not stop_event.is_set():
        try:
            logging.info(f"Periodic FFT will record in {interval / 60:.1f} minutes...")
            # Use event.wait() which is an interruptable sleep
            if stop_event.wait(timeout=interval):
                break  # Stop if event is set during wait

            logging.info(f"Periodic FFT: Recording {n_samples / samplerate:.1f}s of audio...")
            
            myrecording = sd.rec(n_samples, samplerate=samplerate, channels=total_channels, blocking=True)
            
            # Select the correct channel data
            channel_audio = myrecording[:, channel] if myrecording.ndim > 1 else myrecording.flatten()
            
            if gain != 1.0:
                channel_audio *= gain
            
            logging.info("Periodic FFT: Recording finished. Processing FFT...")

            # Perform FFT
            yf = rfft(channel_audio)
            xf = rfftfreq(n_samples, 1 / samplerate)

            # Average into buckets
            bucket_size = int(bucket_width * n_samples / samplerate)
            if bucket_size == 0:
                bucket_size = 1
            num_buckets = len(yf) // bucket_size
            
            buckets = [np.mean(np.abs(yf[i:i + bucket_size])) for i in range(0, num_buckets * bucket_size, bucket_size)]
            bucket_freqs = [np.mean(xf[i:i + bucket_size]) for i in range(0, num_buckets * bucket_size, bucket_size)]

            # Plot results in a new figure
            fig, ax = plt.subplots()
            ax.plot(bucket_freqs, buckets)
            ax.set_xlabel('Frequency (Hz)')
            ax.set_ylabel('Amplitude')
            ax.set_title(f'FFT Plot (Ch: {channel + 1}/{total_channels})')
            ax.grid(True)
            
            # Save plot to disk
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            fname_parts = filename_parts
            fname = f"{timestamp}_fft_{fname_parts.get('samplerate_khz', '??')}k_{fname_parts.get('bitdepth', '??')}b_ch{channel+1}_{fname_parts.get('location', 'L')}_{fname_parts.get('hive', 'H')}.png"
            full_path_name = os.path.join(plot_directory, fname)
            
            os.makedirs(os.path.dirname(full_path_name), exist_ok=True)
            fig.savefig(full_path_name)
            plt.close(fig) # Free memory
            logging.info(f"Saved periodic FFT plot to: {full_path_name}")

        except Exception as e:
            logging.error(f"Error in periodic FFT process: {e}", exc_info=True)
            if stop_event.wait(timeout=60):
                break

    logging.info("Periodic FFT process exiting.")


def keyboard_listener(app):
    """Main keyboard listener loop."""
    
    # Platform-specific terminal setup
    if platform_manager.termios and platform_manager.tty:
        # Unix-like systems (Linux, macOS)
        fd = sys.stdin.fileno()
        old_settings = platform_manager.termios.tcgetattr(fd)
        try:
            platform_manager.tty.setcbreak(sys.stdin.fileno())
            logging.info("\nstarted. Press 'h' for help.")
            
            while app.keyboard_listener_running:
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    key = sys.stdin.read(1)
                    if key is not None:
                        if key == "^":
                            toggle_listening(app)
                        elif app.keyboard_listener_active:
                            if key.isdigit() and int(key) > 0:
                                logging.warning(f"Direct channel switching with number keys is temporarily disabled during refactor.")
                            elif key == "a": 
                                check_stream_status(10)
                            elif key == "c":  
                                change_monitor_channel(app)
                            elif key == "d":  
                                show_audio_device_list()
                            elif key == "D":  
                                show_detailed_device_list()
                            elif key == "f":  
                                trigger_fft(app)
                            elif key == "i":  
                                toggle_intercom_m(app)
                            elif key == "m":  
                                show_mic_locations()
                            elif key == "o":  
                                trigger_oscope(app)        
                            elif key == "p":
                                run_performance_monitor_once(app)
                            elif key == "P":
                                toggle_continuous_performance_monitor(app)
                            elif key == "q":  
                                logging.info("\nQuitting...")
                                app.keyboard_listener_running = False
                                stop_all(app)
                            elif key == "s":  
                                trigger_spectrogram(app)
                            elif key == "t":  
                                list_all_threads()        
                            elif key == "v":  
                                toggle_vu_meter(app)      
                            elif key == "h" or key =="?":  
                                show_list_of_commands()
        except Exception as e:
            logging.error("Error in keyboard listener", exc_info=True)
        finally:
            platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSADRAIN, old_settings)
            print("\n[Terminal restored]", end='\r\n', flush=True)

    elif platform_manager.msvcrt:
        # Windows
        logging.info("\nstarted. Press 'h' for help.")
        while app.keyboard_listener_running:
            if platform_manager.msvcrt.kbhit():
                try:
                    key = platform_manager.msvcrt.getch().decode('utf-8')
                    if key is not None:
                        if key == "^":
                            toggle_listening(app)
                        elif app.keyboard_listener_active:
                            if key.isdigit() and int(key) > 0:
                                logging.warning(f"Direct channel switching with number keys is temporarily disabled during refactor.")
                            elif key == "a": 
                                check_stream_status(10)
                            elif key == "c":  
                                change_monitor_channel(app)
                            elif key == "d":  
                                show_audio_device_list()
                            elif key == "D":  
                                show_detailed_device_list()
                            elif key == "f":  
                                trigger_fft(app)
                            elif key == "i":  
                                toggle_intercom_m(app)
                            elif key == "m":  
                                show_mic_locations()
                            elif key == "o":  
                                trigger_oscope(app)        
                            elif key == "p":
                                run_performance_monitor_once(app)
                            elif key == "P":
                                toggle_continuous_performance_monitor(app)
                            elif key == "q":  
                                logging.info("\nQuitting...")
                                app.keyboard_listener_running = False
                                stop_all(app)
                            elif key == "s":  
                                trigger_spectrogram(app)
                            elif key == "t":  
                                list_all_threads()        
                            elif key == "v":  
                                toggle_vu_meter(app)      
                            elif key == "h" or key =="?":  
                                show_list_of_commands()
                except Exception as e:
                    logging.error("Error in keyboard listener", exc_info=True)
            time.sleep(0.01)
    else:
        logging.warning("No keyboard input method available for this OS. The application will be unresponsive.")
        while app.keyboard_listener_running:
            time.sleep(1)


def setup_raw_terminal():
    """Setup terminal for immediate keypress detection on Unix-like systems."""
    global original_terminal_settings
    
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        return  # Windows doesn't need this
        
    if platform_manager.termios is not None:
        try:
            fd = sys.stdin.fileno()
            # Save current settings for cleanup later
            original_terminal_settings = platform_manager.termios.tcgetattr(fd)
            print("[Terminal ready for immediate keypress detection]", end='\r\n', flush=True)
        except Exception as e:
            print(f"Warning: Could not prepare terminal: {e}", end='\r\n', flush=True)

def restore_canonical_terminal():
    """Restore terminal to canonical mode (normal line-buffered mode)."""
    global original_terminal_settings
    
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        return  # Windows doesn't need this
        
    if platform_manager.termios is not None and original_terminal_settings is not None:
        try:
            fd = sys.stdin.fileno()
            platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSADRAIN, original_terminal_settings)
            print("\n[Terminal restored to canonical mode]", end='\r\n', flush=True)
        except Exception as e:
            print(f"Warning: Could not restore terminal settings: {e}", end='\r\n', flush=True)

#
# #############################################################
# audio stream & callback functions
# ############################################################
#
'''
def setup_audio_circular_buffer():
    """Set up the circular buffer for audio recording."""
    global buffer_size, buffer, buffer_index, buffer_wrap, blocksize, buffer_wrap_event

    # Create a buffer to hold the audio data
    buffer_size = int(BUFFER_SECONDS * config.PRIMARY_IN_SAMPLERATE)
    buffer = np.zeros((buffer_size, sound_in_chs), dtype=_dtype)
    buffer_index = 0
    buffer_wrap = False
    blocksize = 8196
    buffer_wrap_event = threading.Event()
    print(f"\naudio buffer size: {sys.getsizeof(buffer)}\n")
    sys.stdout.flush()
'''
def recording_worker_thread(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod, startup_event=None):
    if start_tod is None:
        logging.info(f"{thread_id} is recording continuously")

    # If the interval is 0, this would cause a tight loop. Log a warning and exit the thread.
    if interval == 0:
        config_name = "an interval setting"
        if thread_id == "Period_recording":
            config_name = "PERIOD_INTERVAL"
        elif thread_id == "Audio_monitor":
            config_name = "AUDIO_MONITOR_INTERVAL"
        elif thread_id == "Event_recording":
            config_name = "SAVE_AFTER_EVENT"
            
        logging.warning(f"'{thread_id}' has an interval of 0, which would cause an infinite loop. The thread will not run.")
        logging.warning(f"Please check '{config_name}' in your config file.")
        return
    
    while not app.stop_recording_event.is_set():
        try:
            current_time = datetime.datetime.now().time()
            
            if start_tod is None or (start_tod <= current_time <= end_tod):        
                logging.info(f"{thread_id} started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec")

                if startup_event and not startup_event.is_set():
                    startup_event.set()

                with app.buffer_lock:
                    period_start_index = app.buffer_index 
                interruptable_sleep(record_period, app.stop_recording_event)

                if app.stop_recording_event.is_set():
                    break

                with app.buffer_lock:
                    period_end_index = app.buffer_index 
                    save_start_index = period_start_index % app.buffer_size
                    save_end_index = period_end_index % app.buffer_size

                    if save_end_index > save_start_index:
                        audio_data = app.buffer[save_start_index:save_end_index].copy()
                    else:
                        audio_data = np.concatenate((app.buffer[save_start_index:], app.buffer[:save_end_index])).copy()

                save_sample_rate = app.config.PRIMARY_SAVE_SAMPLERATE if app.config.PRIMARY_SAVE_SAMPLERATE is not None else app.config.PRIMARY_IN_SAMPLERATE
                
                if save_sample_rate < app.config.PRIMARY_IN_SAMPLERATE:
                    audio_data = downsample_audio(audio_data, app.config.PRIMARY_IN_SAMPLERATE, save_sample_rate)
                    logging.info(f"Resampling from {app.config.PRIMARY_IN_SAMPLERATE}Hz to {save_sample_rate}Hz for saving")

                if app.stop_recording_event.is_set():
                    break

                app.check_and_create_date_folders()

                current_date = datetime.datetime.now()
                date_folder = current_date.strftime('%y%m%d')

                if file_format.upper() == 'MP3':
                    if target_sample_rate in [44100, 48000]:
                        full_path_name = os.path.join(app.MONITOR_DIRECTORY, 
                                                    f"{current_date.strftime('%H%M%S')}_{thread_id}_{record_period}_{interval}_{app.config.LOCATION_ID}_{app.config.HIVE_ID}.{file_format.lower()}")
                        logging.info(f"\nAttempting to save MP3 file: {full_path_name}")
                        try:
                            pcm_to_mp3_write(audio_data, full_path_name)
                            logging.info(f"Successfully saved: {full_path_name}")
                        except Exception as e:
                            logging.error(f"Error saving MP3 file: {e}")
                    else:
                        logging.error(f"MP3 only supports 44.1k and 48k sample rates, got {target_sample_rate}")
                elif file_format.upper() in ['FLAC', 'WAV']:
                    full_path_name = os.path.join(app.PRIMARY_DIRECTORY,
                                                f"{current_date.strftime('%H%M%S')}_{thread_id}_{record_period}_{interval}_{app.config.LOCATION_ID}_{app.config.HIVE_ID}.{file_format.lower()}")
                    logging.info(f"\nAttempting to save {file_format.upper()} file: {full_path_name}")
                    try:
                        sf.write(full_path_name, audio_data, int(save_sample_rate), 
                                format=file_format.upper(), 
                                subtype=app._subtype)
                        logging.info(f"Successfully saved: {full_path_name}")
                    except Exception as e:
                        logging.error(f"Error saving {file_format.upper()} file: {e}")
                else:
                    logging.critical(f"Unsupported file format: {file_format}. Supported: MP3, FLAC, WAV")
                
                if not app.stop_recording_event.is_set():
                    logging.info(f"Saved {thread_id} audio to {full_path_name}, period: {record_period}, interval {interval} seconds")
                
                interruptable_sleep(interval, app.stop_recording_event)
            
        except Exception as e:
            logging.error("Error in recording_worker_thread", exc_info=True)
            app.stop_recording_event.set()


def audio_stream(app):
    """Initializes and manages the main audio input stream."""

    def callback(indata, frames, time, status):
        """Callback function for audio input stream. Captures 'app' from outer scope."""
        if status:
            logging.warning(f"Callback status: {status}")
            if status.input_overflow:
                logging.warning(f"Sounddevice input overflow at: {datetime.datetime.now()}")
        
        with app.buffer_lock:
            data_len = len(indata)

            if app.buffer_index + data_len <= app.buffer_size:
                app.buffer[app.buffer_index:app.buffer_index + data_len] = indata
                app.buffer_wrap_event.clear()
            else:
                overflow = (app.buffer_index + data_len) - app.buffer_size
                app.buffer[app.buffer_index:] = indata[:-overflow]
                app.buffer[:overflow] = indata[-overflow:]
                app.buffer_wrap_event.set()

            app.buffer_index = (app.buffer_index + data_len) % app.buffer_size

    #reset_terminal_settings()

    logging.info("Initializing audio stream...")
    logging.info(f"Device ID: [{app.sound_in_id}]")
    logging.info(f"Channels: {app.sound_in_chs}")
    logging.info(f"Sample Rate: {int(app.config.PRIMARY_IN_SAMPLERATE)} Hz")
    logging.info(f"Bit Depth: {app.config.PRIMARY_BITDEPTH} bits")
    logging.info(f"Data Type: {app._dtype}")

    try:
        device_info = sd.query_devices(app.sound_in_id)
        logging.info("\nSelected device info:")
        logging.info(f"Name: [{app.sound_in_id}] {device_info['name']}")
        logging.info(f"Max Input Channels: {device_info['max_input_channels']}")
        logging.info(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz")

        if device_info['max_input_channels'] < app.sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {app.sound_in_chs} are required")

        sd.default.samplerate = app.config.PRIMARY_IN_SAMPLERATE
        
        stream = sd.InputStream(
            device=app.sound_in_id,
            channels=app.sound_in_chs,
            samplerate=app.config.PRIMARY_IN_SAMPLERATE,
            dtype=app._dtype,
            blocksize=app.blocksize,
            callback=callback
        )

        logging.info("\nAudio stream initialized successfully")
        logging.info(f"Stream sample rate: {stream.samplerate} Hz")
        logging.info(f"Stream bit depth: {app.config.PRIMARY_BITDEPTH} bits")

        with stream:
            startup_events = []

            if app.config.MODE_AUDIO_MONITOR:
                logging.info("Starting audio_monitor worker thread...")
                event = threading.Event()
                startup_events.append(event)
                threading.Thread(target=recording_worker_thread, args=(app, 
                                                                        app.config.AUDIO_MONITOR_RECORD,
                                                                        app.config.AUDIO_MONITOR_INTERVAL,
                                                                        "Audio_monitor",
                                                                        app.config.AUDIO_MONITOR_FORMAT,
                                                                        app.config.AUDIO_MONITOR_SAMPLERATE,
                                                                        app.config.AUDIO_MONITOR_START,
                                                                        app.config.AUDIO_MONITOR_END,
                                                                        event)).start()

            if app.config.MODE_PERIOD and not app.testmode:
                logging.info("Starting period_recording worker thread...")
                event = threading.Event()
                startup_events.append(event)
                threading.Thread(target=recording_worker_thread, args=(app, 
                                                                        app.config.PERIOD_RECORD,
                                                                        app.config.PERIOD_INTERVAL,
                                                                        "Period_recording",
                                                                        app.config.PRIMARY_FILE_FORMAT,
                                                                        app.config.PRIMARY_IN_SAMPLERATE,
                                                                        app.config.PERIOD_START,
                                                                        app.config.PERIOD_END,
                                                                        event)).start()

            if app.config.MODE_EVENT and not app.testmode:
                logging.info("Starting event_recording worker thread...")
                event = threading.Event()
                startup_events.append(event)
                threading.Thread(target=recording_worker_thread, args=(app, 
                                                                        app.config.SAVE_BEFORE_EVENT,
                                                                        app.config.SAVE_AFTER_EVENT,
                                                                        "Event_recording",
                                                                        app.config.PRIMARY_FILE_FORMAT,
                                                                        app.config.PRIMARY_IN_SAMPLERATE,
                                                                        app.config.EVENT_START,
                                                                        app.config.EVENT_END,
                                                                        event)).start()
                
            for event in startup_events:
                event.wait(timeout=5.0)

            logging.info("\n\nStartup complete. Press 'h' to see a list of available commands..\n")
            
            while not app.stop_program:
                time.sleep(0.1)

    except Exception as e:
        logging.critical("Error initializing audio stream", exc_info=True)
        return False

    return True

def kill_worker_threads():
    for t in threading.enumerate():
        print("thread name:", t)

        if "recording_worker_thread" in t.name:
            if t.is_alive():
                stop_recording_event.set()
                t.join
                print("recording_worker_thread stopped ***")  


# Add this near the top with other global variables
keyboard_listener_running = True
keyboard_listener_active = True  # New variable to track if keyboard listener is active
emergency_cleanup_in_progress = False  # Add this to prevent recursion
original_terminal_settings = None  # Store original terminal settings for cleanup

def toggle_listening(app):
    app.keyboard_listener_active = not app.keyboard_listener_active
    if app.keyboard_listener_active:
        print("\nKeyboard listener activated. Listening for commands...")
        show_list_of_commands()
    else:
        print("\nKeyboard listener deactivated. Press '^' to reactivate.")
        stop_vu(app)
        stop_intercom_m(app)

def stop_keyboard_listener():
    """Stop the keyboard listener and restore terminal settings without clearing screen."""
    global keyboard_listener_running
    keyboard_listener_running = False
    
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        # Windows-specific cleanup
        try:
            # Clear any pending input
            if platform_manager.msvcrt is not None:
                while platform_manager.msvcrt.kbhit():
                    platform_manager.msvcrt.getch()
            sys.stdout.flush()
        except Exception as e:
            print(f"Warning: Error during Windows keyboard cleanup: {e}")
    else:
        # Unix/macOS terminal reset
        try:
            # Reset terminal settings without clearing screen
            safe_stty('sane')
            safe_stty('-raw -echo')
            
            # Clear any pending input
            try:
                # Get current terminal settings
                import termios, tty
                old_settings = termios.tcgetattr(sys.stdin)
                # Set terminal to raw mode temporarily
                tty.setraw(sys.stdin.fileno())
                # Read any pending input
                while sys.stdin.read(1):
                    pass
                # Restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except Exception as e:
                print(f"Warning: Could not clear input buffer: {e}")
        except Exception as e:
            print(f"Warning: Could not reset terminal settings: {e}")
    
    # Print a message instead of resetting the terminal
    print("\n[Keyboard listener stopped]")



def show_detailed_device_list():
    """Display a detailed list of all audio devices with input/output indicators."""
    print("\nAudio Device List:")
    print("-" * 80)
    
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        # Get API name
        hostapi_info = sd.query_hostapis(index=device['hostapi'])
        api_name = hostapi_info['name']
        
        # Determine if device is input, output, or both
        in_channels = device['max_input_channels']
        out_channels = device['max_output_channels']
        
        # Create prefix based on device type and whether it's the active device
        if i == sound_in_id and in_channels > 0:
            prefix = ">"
        elif i == sound_out_id and out_channels > 0:
            prefix = "<"
        else:
            prefix = " "
            
        # Format the device name to fit in 40 characters
        device_name = device['name']
        if len(device_name) > 40:
            device_name = device_name[:37] + "..."
            
        # Print the device information
        print(f"{prefix} {i:2d} {device_name:<40} {api_name} ({in_channels} in, {out_channels} out)")
    
    print("-" * 80)
    sys.stdout.flush()

def show_list_of_commands():
    print("\na  audio pathway--check for over/underflows")
    print("c  channel--select channel to monitor, either before or during use of vu or intercom, '0' to exit")
    print("d  selected devices in use data")
    print("D  show all devices with active input/output indicator")
    print("f  fft--show plot")
    print("i  intercom: press i then press 1, 2, 3, ... to listen to that channel")
    print("m  mic--show active positions")
    print("o  oscilloscope--show trace of each active channel")
    print("p  performance monitor--show CPU and RAM usage (one-shot)")
    print("P  performance monitor--show CPU and RAM usage (continuous)")
    print("q  quit--stop all processes and exit")
    print("s  spectrogram--plot of last recording")
    print("t  threads--see list of all threads")
    print("v  vu meter--toggle--show vu meter on cli")
    print("^  toggle keyboard listener on/off")
    print("h or ?  show list of commands\n")

###########################
########## MAIN ###########
###########################

def check_dependencies(app):
    """Check for required Python libraries and their versions."""
    required_packages = {
        'sounddevice': '0.4.6',
        'soundfile': '0.12.1',
        'numpy': '1.24.0',
        'matplotlib': '3.7.0',
        'scipy': '1.10.0',
        'pydub': '0.25.1',
        'librosa': '0.10.0',
        'resampy': '0.4.2',
        'pyaudio': '0.2.13'  # Added PyAudio requirement
    }
    
    missing_packages = []
    outdated_packages = []
    missing_system_deps = []
    
    print("\nChecking Python dependencies:")
    print("-" * 50)
    
    # Check Python packages
    for package, min_version in required_packages.items():
        try:
            # Try to import the package
            module = __import__(package)
            # Get the version
            version = getattr(module, '__version__', 'unknown')
            print(f"✓ {package:<15} found (version {version})")
            
            # Check if version meets minimum requirement
            if version != 'unknown':
                from packaging import version as pkg_version
                if pkg_version.parse(version) < pkg_version.parse(min_version):
                    outdated_packages.append(f"{package} (current: {version}, required: {min_version})")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package:<15} not found")
    
    print("-" * 50)
    
    # Check for ffmpeg
    try:
        import subprocess
        if sys.platform == 'win32':
            # Try multiple possible ffmpeg locations in Windows
            ffmpeg_paths = [
                'ffmpeg',  # If it's in PATH
                'C:\\ffmpeg\\bin\\ffmpeg.exe',  # Common installation path
                'C:\\ffmpeg\\ffmpeg.exe',  # Alternative path
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'ffmpeg\\bin\\ffmpeg.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'ffmpeg\\bin\\ffmpeg.exe')
            ]
            
            ffmpeg_found = False
            for path in ffmpeg_paths:
                try:
                    result = subprocess.run([path, '-version'], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"\n✓ ffmpeg found at: {path}")
                        ffmpeg_found = True
                        break
                except:
                    continue
            
            if not ffmpeg_found:
                missing_system_deps.append('ffmpeg')
                print("\n✗ ffmpeg not found in common locations")
        elif app.platform_manager.is_macos():
            # For macOS, check common Homebrew and MacPorts locations
            ffmpeg_paths = [
                '/usr/local/bin/ffmpeg',  # Homebrew default
                '/opt/homebrew/bin/ffmpeg',  # Apple Silicon Homebrew 
                '/opt/local/bin/ffmpeg',  # MacPorts
                'ffmpeg'  # System PATH
            ]
            
            ffmpeg_found = False
            for path in ffmpeg_paths:
                try:
                    result = subprocess.run([path, '-version'], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"\n✓ ffmpeg found at: {path}")
                        ffmpeg_found = True
                        break
                except:
                    continue
            
            if not ffmpeg_found:
                missing_system_deps.append('ffmpeg')
                print("\n✗ ffmpeg not found in common macOS locations")
        else:
            # For Linux/WSL, use which command
            result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            if result.returncode == 0:
                print("\n✓ ffmpeg found")
            else:
                missing_system_deps.append('ffmpeg')
                print("\n✗ ffmpeg not found")
    except Exception as e:
        missing_system_deps.append('ffmpeg')
        print(f"\n✗ Error checking for ffmpeg: {e}")
    
    print("-" * 50)
    
    if missing_packages:
        print("\nMissing required Python packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nTo install missing packages, run:")
        print("pip install " + " ".join(missing_packages))
    
    if outdated_packages:
        print("\nOutdated packages:")
        for package in outdated_packages:
            print(f"  - {package}")
        print("\nTo update packages, run:")
        print("pip install --upgrade " + " ".join(pkg.split()[0] for pkg in outdated_packages))
    
    if missing_system_deps:
        print("\nMissing system dependencies:")
        for dep in missing_system_deps:
            print(f"  - {dep}")
        print("\nTo install system dependencies:")
        if app.platform_manager.is_wsl():
            print("Run these commands in WSL:")
            print("sudo apt-get update")
            print("sudo apt-get install ffmpeg")
        elif app.platform_manager.is_macos():
            print("For macOS:")
            print("1. Install Homebrew if not already installed:")
            print("   /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            print("2. Install ffmpeg:")
            print("   brew install ffmpeg")
        else:
            print("For Windows:")
            print("1. Download ffmpeg from https://www.gyan.dev/ffmpeg/builds/")
            print("2. Extract the zip file")
            print("3. Add the bin folder to your system PATH")
            print("   (e.g., add 'C:\\ffmpeg\\bin' to your PATH environment variable)")
    
    if not missing_packages and not outdated_packages and not missing_system_deps:
        print("\nAll required packages and dependencies are installed and up to date!\n")
    
    return len(missing_packages) == 0 and len(outdated_packages) == 0 and len(missing_system_deps) == 0

#=== Main() ============================================================

def main():

    # --- Setup Logging ---
    # NOTE: This temporary setup is for initializing the logger before the app object exists.
    # The final log path will be determined by the app state.
    try:
        temp_data_drive = config.win_data_drive if sys.platform == 'win32' else os.path.expanduser(config.mac_data_drive)
        temp_data_path = config.win_data_path if sys.platform == 'win32' else config.mac_data_path
        log_file_path = os.path.join(temp_data_drive, temp_data_path, 'BMAR.log')
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    except Exception as e:
        print(f"CRITICAL: Could not create log file path. Error: {e}")
        # Fallback to a local log file
        log_file_path = 'BMAR_fallback.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(processName)s - %(threadName)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("--- Starting Beehive Multichannel Acoustic-Signal Recorder ---")

    app = BmarApp()
    app.initialize()

    # Register cleanup handlers
    atexit.register(cleanup, app)
    # Partial functions are needed to pass the app object to the signal handler
    from functools import partial
    signal.signal(signal.SIGINT, partial(emergency_cleanup, app=app))
    signal.signal(signal.SIGTERM, partial(emergency_cleanup, app=app))
    if sys.platform != 'win32':
        signal.signal(signal.SIGHUP, partial(emergency_cleanup, app=app))
        signal.signal(signal.SIGQUIT, partial(emergency_cleanup, app=app))

    # --- Audio format validation ---
    allowed_primary_formats = ["FLAC", "WAV"]
    allowed_monitor_formats = ["MP3", "FLAC", "WAV"]
    if app.config.PRIMARY_FILE_FORMAT.upper() not in allowed_primary_formats:
        logging.warning(f"PRIMARY_FILE_FORMAT '{app.config.PRIMARY_FILE_FORMAT}' is not allowed. Must be one of: {allowed_primary_formats}")
    if app.config.AUDIO_MONITOR_FORMAT.upper() not in allowed_monitor_formats:
        logging.warning(f"AUDIO_MONITOR_FORMAT '{app.config.AUDIO_MONITOR_FORMAT}' is not allowed. Must be one of: {allowed_monitor_formats}")

    logging.info("Beehive Multichannel Acoustic-Signal Recorder")
   
    # Display platform-specific messages
    if sys.platform == 'win32' and not app.platform_manager.is_wsl():
        logging.info("Running on Windows - some terminal features will be limited.")
        logging.info("Note: You can safely ignore the 'No module named termios' warning.")
   
    # Check dependencies
    if not check_dependencies(app):
        logging.warning("Some required packages are missing or outdated.")
        logging.warning("The script may not function correctly.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    logging.info(f"Saving data to: {app.PRIMARY_DIRECTORY}")

    # Try to set up the input device
    if not set_input_device(app):
        logging.critical("Exiting due to no suitable audio input device found.")
        sys.exit(1)

    # Validate and adjust monitor_channel after device setup
    if app.monitor_channel >= app.sound_in_chs:
        logging.warning(f"Monitor channel {app.monitor_channel+1} exceeds available channels ({app.sound_in_chs})")
        app.monitor_channel = 0  # Default to first channel
        logging.info(f"Setting monitor channel to {app.monitor_channel+1}")
    
    app.setup_audio_circular_buffer()

    logging.info(f"Sample Rate: {int(app.config.PRIMARY_IN_SAMPLERATE)} Hz; File Format: {app.config.PRIMARY_FILE_FORMAT}; Channels: {app.sound_in_chs}")
    
    # Create and start the process
    if app.config.MODE_FFT_PERIODIC_RECORD:
        # Create a pickle-able config dictionary for the new process
        fft_config = {
            'interval': app.fft_interval * 60,
            'n_samples': int(app.config.PRIMARY_IN_SAMPLERATE * app.config.FFT_DURATION),
            'gain': 10 ** (app.config.FFT_GAIN / 20) if app.config.FFT_GAIN > 0 else 1.0,
            'samplerate': app.config.PRIMARY_IN_SAMPLERATE,
            'channel': app.monitor_channel,
            'total_channels': app.sound_in_chs,
            'bucket_width': 1000, # Corresponds to the old FFT_BW global
            'plot_directory': app.PLOT_DIRECTORY,
            'filename_parts': {
                'samplerate_khz': int(app.config.PRIMARY_IN_SAMPLERATE / 1000),
                'bitdepth': app.config.PRIMARY_BITDEPTH,
                'location': app.config.LOCATION_ID,
                'hive': app.config.HIVE_ID,
            }
        }

        app.active_processes['f_periodic'] = multiprocessing.Process(
            target=plot_and_save_fft, 
            args=(app.stop_fft_periodic_plot_event, fft_config),
            name="PeriodicFFTProcess"
        )
        app.active_processes['f_periodic'].daemon = True
        logging.info("Starting periodic FFT plot process...")
        app.active_processes['f_periodic'].start()

    try:
        # NOTE: KB_or_CP seems to be an undefined global, assuming 'KB' for now
        if 'KB_or_CP' not in globals() or globals().get('KB_or_CP') == 'KB':
            # Give a small delay to ensure prints are visible before starting keyboard listener
            time.sleep(1)
            # Start keyboard listener in a separate thread
            keyboard_thread = threading.Thread(target=keyboard_listener, args=(app,), name="KeyboardListener")
            keyboard_thread.daemon = True
            keyboard_thread.start()
            
        # Start the audio stream
        audio_stream(app)
            
    except KeyboardInterrupt: # ctrl-c in windows
        logging.info('Ctrl-C received. Stopping...')
        # The atexit handler will call cleanup
        sys.exit(0)

    except Exception as e:
        logging.critical("An unhandled error occurred in main", exc_info=True)
    finally:
        # Ensure terminal is reset even if an error occurs
        restore_terminal_settings(app.original_terminal_settings)

def stop_all(app):
    """Stop all processes and threads."""
    logging.info("Stopping all processes...")
    
    try:
        # Set all stop events
        app.stop_program = True
        app.stop_recording_event.set()
        app.stop_fft_periodic_plot_event.set()
        app.stop_vu_event.set()
        app.stop_intercom_event.set()
        app.stop_performance_monitor_event.set()
        app.keyboard_listener_running = False

        # Clean up all active processes
        for command in list(app.active_processes.keys()):
            cleanup_process(command, app)

        # Stop VU meter
        stop_vu(app)

        # Stop intercom
        stop_intercom_m(app)

        # List and stop all worker threads
        logging.info("Stopping worker threads...")
        current_thread = threading.current_thread()
        for thread in threading.enumerate():
            if thread != threading.main_thread() and thread != current_thread:
                logging.info(f"Stopping thread: {thread.name}")
                if thread.is_alive():
                    try:
                        thread.join(timeout=1)
                    except RuntimeError:
                        pass
    except Exception:
        logging.critical("Error during stop_all", exc_info=True)

    logging.info("All processes and threads commanded to stop.")

def cleanup(app):
    """Clean up and exit."""
    logging.info("Cleaning up resources...")
    
    try:
        # Set stop flags to prevent any new recordings
        app.stop_program = True
        app.stop_recording_event.set()
        
        # Stop all processes and threads
        stop_all(app)
        
        # Platform-specific terminal cleanup
        try:
            restore_canonical_terminal()
        except Exception:
            logging.error("Error resetting terminal during cleanup", exc_info=True)
            # Try alternative terminal reset
            try:
                if sys.platform != 'win32':
                    os.system('stty sane; stty echo')
            except:
                pass
    except Exception:
        logging.critical("Error during cleanup", exc_info=True)
    
    # Give threads a moment to clean up
    time.sleep(0.5)
    
    # Force kill any remaining processes
    force_kill_child_processes()
    
    # Final terminal reset attempt
    try:
        if sys.platform != 'win32':
            os.system('stty sane; stty echo')
            sys.stdout.write('\n')
            sys.stdout.flush()
    except:
        pass
    
    # Force exit after cleanup
    logging.info("Cleanup complete. Exiting.")
    os._exit(0)

def safe_stty(command):
    """
    Safely execute stty command only on platforms that support it.
    Will silently do nothing on Windows.
    """
    if sys.platform != 'win32' or platform_manager.is_wsl():
        try:
            os.system(f'stty {command}')
        except Exception as e:
            # Silent fail - this is OK on platforms where stty fails
            pass

def force_kill_child_processes():
    """Force kill all child processes of the current process."""
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        print(f"Error killing child processes: {e}")

def emergency_cleanup(signum=None, frame=None, app=None):
    """Emergency cleanup function for handling signals and abnormal termination."""
    # This function should have a global flag to prevent recursion,
    # but that's part of the state we're refactoring away.
    # For now, we rely on the caller to provide the app instance.
    
    print("\nEMERGENCY CLEANUP INITIATED...")
    if app is None:
        print("CRITICAL: App state not available for emergency cleanup. Some resources may not be released.")
        os._exit(1)
        return

    try:
        # Stop all processes first
        stop_all(app)
        
        # Force kill any remaining child processes
        force_kill_child_processes()
        
        # Reset terminal settings
        try:
            restore_canonical_terminal()
        except Exception as e:
            print(f"Error resetting terminal: {e}")
            # Try alternative terminal reset
            try:
                if sys.platform != 'win32':
                    os.system('stty sane; stty echo')
            except:
                pass
        
        print("Emergency cleanup completed.")
    except Exception as e:
        print(f"Error during emergency cleanup: {e}")
    finally:
        # Force exit
        os._exit(1)

# Register the emergency cleanup for various signals
# NOTE: This will be moved into main() after the refactor
# signal.signal(signal.SIGINT, emergency_cleanup)
# signal.signal(signal.SIGTERM, emergency_cleanup)
# if sys.platform != 'win32':
#     signal.signal(signal.SIGHUP, emergency_cleanup)
#     signal.signal(signal.SIGQUIT, emergency_cleanup)

def save_terminal_settings():
    """Save current terminal settings."""
    try:
        if sys.platform != 'win32' and platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            return platform_manager.termios.tcgetattr(fd)
    except:
        return None
    return None

def restore_terminal_settings(old_settings):
    """Restore terminal settings to their original state."""
    try:
        if sys.platform != 'win32' and old_settings is not None and platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSADRAIN, old_settings)
            # Additional terminal reset commands
            try:
                # Reset terminal mode
                os.system('stty sane')
                # Enable echo
                os.system('stty echo')
            except:
                pass
            sys.stdout.write('\n')  # Ensure we're on a new line
            sys.stdout.flush()
    except Exception as e:
        print(f"Warning: Could not restore terminal settings: {e}")
        try:
            # Last resort terminal reset
            if sys.platform != 'win32':
                os.system('stty sane')
                os.system('stty echo')
        except:
            pass

# Add near other global variables
performance_monitor_proc = None
stop_performance_monitor_event = threading.Event()

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

def monitor_system_performance_continuous():
    """Continuously monitor and display CPU and RAM usage."""
    try:
        while not stop_performance_monitor_event.is_set():
            output = get_system_performance()
            print(output, flush=True)
            time.sleep(2)
    except Exception as e:
        print(f"\nError in performance monitor: {e}", end='\r')
    finally:
        print("\nPerformance monitor stopped.", end='\r')

def run_performance_monitor_once(app):
    """Run the performance monitor once."""
    cleanup_process('p', app)  # Clean up any existing process
    proc = multiprocessing.Process(target=monitor_system_performance_once)
    proc.daemon = True
    app.active_processes['p'] = proc
    proc.start()
    proc.join()  # Wait for it to complete
    cleanup_process('p', app)

def toggle_continuous_performance_monitor():
    """Toggle the continuous performance monitor on/off."""
    global performance_monitor_proc, stop_performance_monitor_event
    
    if performance_monitor_proc is None or not performance_monitor_proc.is_alive():
        cleanup_process('P')  # Clean up any existing process
        print("\nStarting continuous performance monitor...", end='\r')
        performance_monitor_proc = multiprocessing.Process(target=monitor_system_performance_continuous)
        performance_monitor_proc.daemon = True
        active_processes['P'] = performance_monitor_proc
        stop_performance_monitor_event.clear()
        performance_monitor_proc.start()
    else:
        print("\nStopping performance monitor...", end='\r')
        stop_performance_monitor_event.set()
        if performance_monitor_proc.is_alive():
            performance_monitor_proc.join(timeout=2)
            if performance_monitor_proc.is_alive():
                performance_monitor_proc.terminate()
        performance_monitor_proc = None
        cleanup_process('P')
        print("Performance monitor stopped", end='\r')

def get_key():
    """Gets a single key press. Handles both Windows and non-Windows platforms."""
    if platform_manager.msvcrt:  # Windows
        if platform_manager.msvcrt.kbhit():
            try:
                return platform_manager.msvcrt.getch().decode('utf-8')
            except UnicodeDecodeError:
                return None # Ignore non-utf-8 keys
    elif platform_manager.termios: # Unix-like
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            return sys.stdin.read(1)
    return None

def set_monitor_channel(app, new_channel_index):
    """Sets the monitor channel and restarts VU meter if active."""
    if new_channel_index < app.sound_in_chs:
        app.monitor_channel = new_channel_index
        logging.info(f"\nNow monitoring channel: {app.monitor_channel + 1} (of {app.sound_in_chs})")

        if app.active_processes.get('i') and app.active_processes['i'].is_alive():
            app.change_ch_event.set()

        vu_process_info = app.active_processes.get('v')
        is_running = vu_process_info and vu_process_info[0].is_alive()
        if is_running:
            logging.info(f"Restarting VU meter for channel: {app.monitor_channel + 1}")
            toggle_vu_meter(app)  # Stop
            time.sleep(0.1)
            toggle_vu_meter(app)  # Start
        
        clear_input_buffer()
        return True
    else:
        logging.warning(f"\nInvalid channel selection: Device has only {app.sound_in_chs} channel(s) (1-{app.sound_in_chs})")
        return False

def change_monitor_channel(app):
    clear_input_buffer()
    
    logging.info(f"\nAvailable channels: 1-{app.sound_in_chs}")
    logging.info("Press channel number (1-9) to monitor, or 0/q to exit:")
    
    while True:
        try:
            key = get_key()
            if key is None:
                time.sleep(0.01)
                continue
                
            if key == '0' or key.lower() == 'q':
                logging.info("\nExiting channel change")
                clear_input_buffer()
                return
                
            if key.isdigit() and int(key) > 0:
                key_int = int(key) - 1
                if set_monitor_channel(app, key_int):
                    return # Exit after successful change
            else:
                if key.isprintable() and key != '0' and key.lower() != 'q':
                    logging.warning(f"\nInvalid input: '{key}'. Use 1-{app.sound_in_chs} for channels or 0/q to exit.")
                    
        except Exception as e:
            logging.error(f"\nError reading input: {e}")
            continue

def keyboard_listener(app):
    """Main keyboard listener loop."""
    
    # Platform-specific terminal setup
    if platform_manager.termios and platform_manager.tty:
        # Unix-like systems (Linux, macOS)
        fd = sys.stdin.fileno()
        old_settings = platform_manager.termios.tcgetattr(fd)
        try:
            platform_manager.tty.setcbreak(sys.stdin.fileno())
            logging.info("\nstarted. Press 'h' for help.")
            
            while app.keyboard_listener_running:
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    key = sys.stdin.read(1)
                    if key is not None:
                        if key == "^":
                            toggle_listening(app)
                        elif app.keyboard_listener_active:
                            if key.isdigit() and int(key) > 0:
                                new_channel_index = int(key) - 1
                                set_monitor_channel(app, new_channel_index)
                            elif key == "a": 
                                check_stream_status(10)
                            elif key == "c":  
                                change_monitor_channel(app)
                            elif key == "d":  
                                show_audio_device_list()
                            elif key == "D":  
                                show_detailed_device_list()
                            elif key == "f":  
                                trigger_fft(app)
                            elif key == "i":  
                                toggle_intercom_m(app)
                            elif key == "m":  
                                show_mic_locations()
                            elif key == "o":  
                                trigger_oscope(app)        
                            elif key == "p":
                                run_performance_monitor_once(app)
                            elif key == "P":
                                toggle_continuous_performance_monitor(app)
                            elif key == "q":  
                                logging.info("\nQuitting...")
                                app.keyboard_listener_running = False
                                stop_all(app)
                            elif key == "s":  
                                trigger_spectrogram(app)
                            elif key == "t":  
                                list_all_threads()        
                            elif key == "v":  
                                toggle_vu_meter(app)      
                            elif key == "h" or key =="?":  
                                show_list_of_commands()
        except Exception as e:
            logging.error("Error in keyboard listener", exc_info=True)
        finally:
            platform_manager.termios.tcsetattr(fd, platform_manager.termios.TCSADRAIN, old_settings)
            print("\n[Terminal restored]", end='\r\n', flush=True)

    elif platform_manager.msvcrt:
        # Windows
        logging.info("\nstarted. Press 'h' for help.")
        while app.keyboard_listener_running:
            if platform_manager.msvcrt.kbhit():
                try:
                    key = platform_manager.msvcrt.getch().decode('utf-8')
                    if key is not None:
                        if key == "^":
                            toggle_listening(app)
                        elif app.keyboard_listener_active:
                            if key.isdigit() and int(key) > 0:
                                new_channel_index = int(key) - 1
                                set_monitor_channel(app, new_channel_index)
                            elif key == "a": 
                                check_stream_status(10)
                            elif key == "c":  
                                change_monitor_channel(app)
                            elif key == "d":  
                                show_audio_device_list()
                            elif key == "D":  
                                show_detailed_device_list()
                            elif key == "f":  
                                trigger_fft(app)
                            elif key == "i":  
                                toggle_intercom_m(app)
                            elif key == "m":  
                                show_mic_locations()
                            elif key == "o":  
                                trigger_oscope(app)        
                            elif key == "p":
                                run_performance_monitor_once(app)
                            elif key == "P":
                                toggle_continuous_performance_monitor(app)
                            elif key == "q":  
                                logging.info("\nQuitting...")
                                app.keyboard_listener_running = False
                                stop_all(app)
                            elif key == "s":  
                                trigger_spectrogram(app)
                            elif key == "t":  
                                list_all_threads()        
                            elif key == "v":  
                                toggle_vu_meter(app)      
                            elif key == "h" or key =="?":  
                                show_list_of_commands()
                except Exception as e:
                    logging.error("Error in keyboard listener", exc_info=True)
            time.sleep(0.01)
    else:
        logging.warning("No keyboard input method available for this OS. The application will be unresponsive.")
        while app.keyboard_listener_running:
            time.sleep(1)


if __name__ == "__main__":
    main()

