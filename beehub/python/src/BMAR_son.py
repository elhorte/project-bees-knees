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

import BMAR_config as config
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
            print(f"\nDetected operating system: {self.get_os_info()}\r")
            
            if sys.platform == 'win32' and not self.is_wsl():
                import msvcrt
                self._msvcrt = msvcrt
                print("Using Windows keyboard handling (msvcrt)")
                self._keyboard_info = "Windows"
            elif self.is_macos() or (sys.platform != 'win32' and not self.is_wsl()):
                try:
                    import termios
                    import tty
                    import fcntl
                    self._termios = termios
                    self._tty = tty
                    self._fcntl = fcntl
                    print("Using Unix keyboard handling (termios)")
                    self._keyboard_info = "Unix"
                except ImportError:
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
    import sys
    import select
    import time
    
    # Print the prompt
    print(prompt, end='', flush=True)
    
    # Check if stdin is available (not redirected/piped)
    if not sys.stdin.isatty():
        print(f"[Headless mode] Using default: '{default}'")
        return default
    
    start_time = time.time()
    
    # Platform-specific input handling
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        # Windows implementation using msvcrt
        user_input = ""
        while (time.time() - start_time) < timeout:
            if platform_manager.msvcrt and platform_manager.msvcrt.kbhit():
                char = platform_manager.msvcrt.getch().decode('utf-8', errors='ignore')
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
            time.sleep(0.01)  # Small delay to prevent high CPU usage
    else:
        # Unix/Linux/macOS implementation using select
        while (time.time() - start_time) < timeout:
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if ready:
                try:
                    user_input = sys.stdin.readline().strip()
                    return user_input.lower() if user_input else default
                except:
                    break
    
    # Timeout occurred
    print(f"\n[Timeout after {timeout}s] Using default: '{default}'")
    return default



def set_input_device(model_name_arg, api_name_preference):
    global sound_in_id, sound_in_chs, testmode, device_id, make_name, model_name, device_name, api_name, hostapi_name, hostapi_index

    print("\nScanning for audio input devices...")
    sys.stdout.flush()

    print_all_input_devices()

    try:
        # Get all devices
        devices = sd.query_devices()
        
        # First try the specified device_id if it exists
        if device_id is not None and device_id >= 0:
            try:
                device = sd.query_devices(device_id)
                if device['max_input_channels'] > 0:
                    print(f"\nTrying specified device [{device_id}]: {device['name']}")
                    print(f"  API: {sd.query_hostapis(index=device['hostapi'])['name']}")
                    print(f"  Max Channels: {device['max_input_channels']}")
                    print(f"  Default Sample Rate: {device['default_samplerate']} Hz")
                    
                    # Check channel compatibility and ask user permission if needed
                    original_channels = sound_in_chs
                    user_approved = True
                    
                    if sound_in_chs > device['max_input_channels']:
                        print(f"\nChannel mismatch detected:")
                        print(f"  Configuration requires: {original_channels} channels")
                        print(f"  Device supports: {device['max_input_channels']} channels")
                        response = timed_input(f"\nWould you like to proceed with {device['max_input_channels']} channel(s) instead? (y/N): ", timeout=3, default='n')

                        if response.lower() != 'y':
                            print("User declined to use fewer channels.")
                            print("Falling back to device search...")
                            user_approved = False
                        else:
                            sound_in_chs = device['max_input_channels']
                            print(f"Adjusting channel count from {original_channels} to {sound_in_chs}")
                    
                    if user_approved:
                        try:
                            # Try to set the sample rate using PyAudio first
                            if not platform_manager.is_wsl():
                                try:
                                    import pyaudio
                                    p = pyaudio.PyAudio()
                                    device_info = p.get_device_info_by_index(device_id)
                                    print(f"\nCurrent Windows sample rate: {device_info['defaultSampleRate']} Hz")
                                    
                                    # Try to open a stream with our desired sample rate
                                    stream = p.open(format=pyaudio.paInt16,
                                                  channels=sound_in_chs,
                                                  rate=config.PRIMARY_IN_SAMPLERATE,
                                                  input=True,
                                                  input_device_index=device_id,
                                                  frames_per_buffer=1024)
                                    
                                    # Verify the actual sample rate
                                    actual_rate = stream._get_stream_info()['sample_rate']
                                    print(f"PyAudio stream sample rate: {actual_rate} Hz")
                                    
                                    stream.close()
                                    p.terminate()
                                    
                                    if actual_rate != config.PRIMARY_IN_SAMPLERATE:
                                        print(f"\nWARNING: PyAudio could not set sample rate to {config.PRIMARY_IN_SAMPLERATE} Hz")
                                        print(f"Device is using {actual_rate} Hz instead")
                                        print("This may affect recording quality.")
                                except Exception as e:
                                    print(f"Warning: Could not set sample rate using PyAudio: {e}")
                            
                            # Now try with sounddevice
                            print("\nAttempting to configure device with sounddevice...")
                            sd.default.samplerate = config.PRIMARY_IN_SAMPLERATE
                            
                            with sd.InputStream(device=device_id, 
                                              channels=sound_in_chs,
                                              samplerate=config.PRIMARY_IN_SAMPLERATE,
                                              dtype=_dtype,
                                              blocksize=1024) as stream:
                                # Verify the actual sample rate being used
                                actual_rate = stream.samplerate
                                if actual_rate != config.PRIMARY_IN_SAMPLERATE:
                                    print(f"\nWARNING: Requested sample rate {config.PRIMARY_IN_SAMPLERATE} Hz, but device is using {actual_rate} Hz")
                                    print("This may affect recording quality.")
                                
                                # If we get here, the device works with our settings
                                sound_in_id = device_id
                                print(f"\nSuccessfully configured specified device [{device_id}]")
                                print(f"Device Configuration:")
                                print(f"  Sample Rate: {actual_rate} Hz")
                                print(f"  Bit Depth: {config.PRIMARY_BITDEPTH} bits")
                                print(f"  Channels: {sound_in_chs}")
                                if original_channels != sound_in_chs:
                                    print(f"  Note: Channel count was adjusted from {original_channels} to {sound_in_chs}")
                                testmode = False
                                return True
                        except Exception as e:
                            print(f"\nERROR: Could not use specified device ID {device_id}")
                            print(f"Reason: {str(e)}")
                            response = timed_input("\nThe specified device could not be used. Would you like to proceed with an alternative device? (y/n): ", timeout=3, default='n')
                            if response.lower() != 'y':
                                print("Exiting as requested.")
                                sys.exit(1)
                            print("Falling back to device search...")
                else:
                    print(f"\nERROR: Specified device ID {device_id} is not an input device")
                    response = timed_input("\nThe specified device is not an input device. Would you like to proceed with an alternative device? (y/n): ", timeout=3, default='n')
                    if response.lower() != 'y':
                        print("Exiting as requested.")
                        sys.exit(1)
                    print("Falling back to device search...")
            except Exception as e:
                print(f"\nERROR: Could not access specified device ID {device_id}")
                print(f"Reason: {str(e)}")
                response = timed_input("\nThe specified device could not be accessed. Would you like to proceed with an alternative device? (y/n): ", timeout=3, default='n')
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
        if make_name and make_name.strip():
            print(f"\nLooking for devices matching make name: {make_name}")
            matching_devices = [(i, device) for i, device in input_devices 
                              if make_name.lower() in device['name'].lower()]
            
            if matching_devices:
                print(f"Found {len(matching_devices)} devices matching make name")
                # Try matching devices first
                for dev_id, device in matching_devices:
                    print(f"\nTrying device [{dev_id}]: {device['name']}")
                    print(f"  API: {sd.query_hostapis(index=device['hostapi'])['name']}")
                    print(f"  Max Channels: {device['max_input_channels']}")
                    print(f"  Default Sample Rate: {device['default_samplerate']} Hz")
                    
                    # Auto-adjust channel count to match device capabilities
                    original_channels = sound_in_chs
                    actual_channels = min(sound_in_chs, device['max_input_channels'])
                    if actual_channels != sound_in_chs:
                        print(f"\nChannel mismatch detected:")
                        print(f"  Configuration requires: {sound_in_chs} channels")
                        print(f"  Device supports: {actual_channels} channels")
                        response = timed_input(f"\nWould you like to proceed with {actual_channels} channel(s) instead? (y/N): ", timeout=3, default='n')
                        if response.lower() != 'y':
                            print("Skipping this device...")
                            continue
                        sound_in_chs = actual_channels
                        print(f"Adjusting channel count from {original_channels} to {sound_in_chs}")
                    
                    try:
                        # Try to open a stream with our desired settings
                        with sd.InputStream(device=dev_id, 
                                          channels=sound_in_chs,  # Use adjusted channel count
                                          samplerate=config.PRIMARY_IN_SAMPLERATE,
                                          dtype=_dtype,
                                          blocksize=1024) as stream:
                            # If we get here, the device works with our settings
                            sound_in_id = dev_id
                            print(f"\nSuccessfully configured device [{dev_id}]")
                            print(f"Device Configuration:")
                            print(f"  Sample Rate: {config.PRIMARY_IN_SAMPLERATE} Hz")
                            print(f"  Bit Depth: {config.PRIMARY_BITDEPTH} bits")
                            print(f"  Channels: {sound_in_chs}")
                            if original_channels != sound_in_chs:
                                print(f"  Note: Channel count was auto-adjusted from {original_channels} to {sound_in_chs}")
                            testmode = False
                            return True
                            
                    except Exception as e:
                        print(f"\nERROR: Could not configure device [{dev_id}]")
                        print(f"  Failed to configure device: {str(e)}")
                        continue
            else:
                print(f"No devices found matching make name: {make_name}")
                print("Falling back to trying all devices...")
        
        # Try all devices if no matching devices were found or if make_name was empty
        for dev_id, device in input_devices:
            print(f"\nTrying device [{dev_id}]: {device['name']}")
            print(f"  API: {sd.query_hostapis(index=device['hostapi'])['name']}")
            print(f"  Max Channels: {device['max_input_channels']}")
            print(f"  Default Sample Rate: {device['default_samplerate']} Hz")
            
            # Auto-adjust channel count to match device capabilities
            original_channels = sound_in_chs
            actual_channels = min(sound_in_chs, device['max_input_channels'])
            if actual_channels != sound_in_chs:
                print(f"\nChannel mismatch detected:")
                print(f"  Configuration requires: {sound_in_chs} channels")
                print(f"  Device supports: {actual_channels} channels")
                response = timed_input(f"\nWould you like to proceed with {actual_channels} channel(s) instead? (y/N): ", timeout=3, default='n')
                if response.lower() != 'y':
                    print("Skipping this device...")
                    continue
                sound_in_chs = actual_channels
                print(f"Adjusting channel count from {original_channels} to {sound_in_chs}")
            
            try:
                # Try to open a stream with our desired settings
                with sd.InputStream(device=dev_id, 
                                  channels=sound_in_chs,  # Use adjusted channel count
                                  samplerate=config.PRIMARY_IN_SAMPLERATE,
                                  dtype=_dtype,
                                  blocksize=1024) as stream:
                    # If we get here, the device works with our settings
                    sound_in_id = dev_id
                    print(f"\nSuccessfully configured device [{dev_id}]")
                    print(f"Device Configuration:")
                    print(f"  Sample Rate: {config.PRIMARY_IN_SAMPLERATE} Hz")
                    print(f"  Bit Depth: {config.PRIMARY_BITDEPTH} bits")
                    print(f"  Channels: {sound_in_chs}")
                    if original_channels != sound_in_chs:
                        print(f"  Note: Channel count was auto-adjusted from {original_channels} to {sound_in_chs}")
                    testmode = False
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

def trigger_fft():
    """Trigger FFT plot generation with proper cleanup."""
    try:
        # Clean up any existing FFT process
        cleanup_process('f')
        
        # Create a queue for communication
        stop_queue = multiprocessing.Queue()
        
        # Create new process
        fft_process = multiprocessing.Process(
            target=plot_fft,
            args=(sound_in_id, sound_in_chs, monitor_channel, stop_queue)
        )
        
        # Store process reference
        active_processes['f'] = fft_process
        
        # Start process
        fft_process.start()
        
        # Wait for completion with timeout
        timeout = config.FFT_DURATION + 30  # Recording duration plus extra time for processing
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
    finally:
        # Always clean up
        try:
            cleanup_process('f')
        except Exception as e:
            print(f"Warning during cleanup: {e}")
        clear_input_buffer()
        print("FFT process completed")

def trigger_spectrogram():
    """Trigger spectrogram generation."""
    try:
        # Clean up any existing spectrogram process
        cleanup_process('s')
        
        # Clear input buffer before starting
        clear_input_buffer()
        
        # Get file offset and time difference
        global file_offset, monitor_channel, time_diff
        time_since_last = time_diff()  # Store the time difference
        
        # Only increment offset if we're within the recording period
        if time_since_last < (config.PERIOD_RECORD + config.PERIOD_INTERVAL):
            file_offset = min(file_offset + 1, 0)  # Cap at 0 to prevent going negative
        else:
            file_offset = 0  # Reset to first file
            
        print(f"Time since last file: {time_since_last:.1f}s, using file offset: {file_offset}")
            
        # Create and start the spectrogram process
        active_processes['s'] = multiprocessing.Process(
            target=plot_spectrogram, 
            args=(monitor_channel, 'lin', file_offset, spectrogram_period)
        )
        active_processes['s'].daemon = True  # Make it a daemon process
        active_processes['s'].start()
        
        # Brief delay to allow the spectrogram process to initialize properly
        # and prevent interference with subsequent audio operations
        import time
        time.sleep(0.2)
        
        print("Plotting spectrogram...")
        clear_input_buffer()
        
        # Wait for completion with timeout
        active_processes['s'].join(timeout=240)  # Increased timeout for spectrogram generation
        
        # Cleanup if process is still running
        if active_processes['s'].is_alive():
            print("Spectrogram process taking too long, terminating...")
            try:
                active_processes['s'].terminate()
                active_processes['s'].join(timeout=1)
                if active_processes['s'].is_alive():
                    # Force kill if still running
                    active_processes['s'].kill()
                    active_processes['s'].join(timeout=1)
            except Exception as e:
                print(f"Warning during process termination: {e}")
        
    except Exception as e:
        print(f"Error in trigger_spectrogram: {e}")
    finally:
        # Always clean up
        try:
            cleanup_process('s')
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

def vu_meter(sound_in_id, sound_in_chs, channel, stop_vu_queue, asterisks):
    # Debug: Print incoming parameter types
    if config.DEBUG_VERBOSE:
        print(f"\n[VU Debug] Parameter types:")
        print(f"  sound_in_id: {sound_in_id} (type: {type(sound_in_id)})")
        print(f"  config.PRIMARY_IN_SAMPLERATE: {config.PRIMARY_IN_SAMPLERATE} (type: {type(config.PRIMARY_IN_SAMPLERATE)})")
        print(f"  sound_in_chs: {sound_in_chs} (type: {type(sound_in_chs)})")
        print(f"  channel: {channel} (type: {type(channel)})")
    
    # Ensure sample rate is an integer for buffer size calculation
    buffer_size = int(config.PRIMARY_IN_SAMPLERATE)
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
            if config.DEBUG_VERBOSE and last_print == "":
                print(f"\n[VU Debug] First callback: frames={frames}, indata.shape={indata.shape}")
            
            # Always validate channel before accessing the data
            selected_channel = int(min(channel, indata.shape[1] - 1))
            
            channel_data = indata[:, selected_channel]
            # Ensure frames is an integer for array slicing
            frames_int = int(frames)
            buffer[:frames_int] = channel_data
            audio_level = np.max(np.abs(channel_data))
            normalized_value = int((audio_level / 1.0) * 50)
            
            asterisks.value = '*' * normalized_value
            current_print = ' ' * 11 + asterisks.value.ljust(50, ' ')
            
            # Only print if the value has changed
            if current_print != last_print:
                print(current_print, end='\r')
                last_print = current_print
                sys.stdout.flush()  # Ensure output is displayed immediately
        except Exception as e:
            # Log the error but don't crash
            print(f"\rVU meter callback error: {e}", end='\r\n')
            if config.DEBUG_VERBOSE:
                print(f"Error details: channel={channel}, frames={frames}, indata.shape={indata.shape}", end='\r\n')
                import traceback
                traceback.print_exc()
            time.sleep(0.1)  # Prevent too many messages

    try:
        # Debug platform detection
        if config.DEBUG_VERBOSE:
            print(f"\n[VU Debug] Platform detection:")
            print(f"  sys.platform: {sys.platform}")
            print(f"  platform_manager.is_wsl(): {platform_manager.is_wsl()}")
            print(f"  Platform OS info: {platform_manager.get_os_info()}")
        
        # In WSL, we need to use different stream parameters
        if platform_manager.is_wsl():
            if config.DEBUG_VERBOSE:
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
                    while not stop_vu_queue.get():
                        sd.sleep(100)  # Changed from 0.1 to 100 milliseconds
            except Exception as e:
                print(f"\nError with default configuration: {e}")
                print("\nPlease ensure your WSL audio is properly configured.")
                raise
        else:
            if config.DEBUG_VERBOSE:
                print("[VU Debug] Using standard audio configuration (non-WSL)")
            # Make sure we request at least as many channels as our selected channel
            # Ensure all parameters are integers for compatibility
            try:
                # Simple approach - just ensure the critical parameters are integers
                with sd.InputStream(callback=callback_input,
                                  device=int(sound_in_id) if sound_in_id is not None else None,
                                  channels=int(sound_in_chs),
                                  samplerate=int(config.PRIMARY_IN_SAMPLERATE),
                                  blocksize=1024,
                                  latency='low'):
                    while not stop_vu_queue.get():
                        sd.sleep(100)  # Changed from 0.1 to 100 milliseconds
            except Exception as e:
                print(f"\nError in VU meter InputStream: {e}")
                print(f"Debug info:")
                print(f"  sound_in_id={sound_in_id} (type: {type(sound_in_id)})")
                print(f"  sound_in_chs={sound_in_chs} (type: {type(sound_in_chs)})")
                print(f"  config.PRIMARY_IN_SAMPLERATE={config.PRIMARY_IN_SAMPLERATE} (type: {type(config.PRIMARY_IN_SAMPLERATE)})")
                import traceback
                traceback.print_exc()
                raise
    except Exception as e:
        print(f"\nError in VU meter: {e}")
    finally:
        print("\nStopping VU meter...")

def toggle_vu_meter():
    global vu_proc, monitor_channel, asterisks, stop_vu_queue, sound_in_chs

    # Clear any buffered input before toggling
    clear_input_buffer()

    if vu_proc is None:
        cleanup_process('v')  # Clean up any existing process
        
        # Validate channel before starting process
        if monitor_channel >= sound_in_chs:
            print(f"\nError: Selected channel {monitor_channel+1} exceeds available channels ({sound_in_chs})")
            print(f"Defaulting to channel 1")
            monitor_channel = 0  # Default to first channel
            
        print("\nVU meter monitoring channel:", monitor_channel+1)
        vu_manager = multiprocessing.Manager()
        stop_vu_queue = multiprocessing.Queue()
        stop_vu_queue.put(False)  # Initialize with False to keep running
        asterisks = vu_manager.Value(str, '*' * 50)

        # Print initial state once
        print("fullscale:", asterisks.value.ljust(50, ' '))

        if config.MODE_EVENT:
            normalized_value = int(config.EVENT_THRESHOLD / 1000)
            asterisks.value = '*' * normalized_value
            print("threshold:", asterisks.value.ljust(50, ' '))
            
        # Debug and validate parameters before creating process
        if config.DEBUG_VERBOSE:
            print(f"\n[Toggle VU Debug] Parameter validation:")
            print(f"  sound_in_id: {sound_in_id} (type: {type(sound_in_id)})")
            print(f"  config.PRIMARY_IN_SAMPLERATE: {config.PRIMARY_IN_SAMPLERATE} (type: {type(config.PRIMARY_IN_SAMPLERATE)})")
            print(f"  sound_in_chs: {sound_in_chs} (type: {type(sound_in_chs)})")
            print(f"  monitor_channel: {monitor_channel} (type: {type(monitor_channel)})")
        
        # Ensure all parameters are the correct type
        try:
            proc_sound_in_id = int(sound_in_id) if sound_in_id is not None else None
            proc_sound_in_chs = int(sound_in_chs)
            proc_monitor_channel = int(monitor_channel)
        except (ValueError, TypeError) as e:
            print(f"Error converting parameters to integers: {e}")
            return
            
        # Create the VU meter process
        vu_proc = multiprocessing.Process(
            target=vu_meter, 
            args=(proc_sound_in_id, proc_sound_in_chs, proc_monitor_channel, stop_vu_queue, asterisks)
        )
        
        # Set the process to start in a clean environment
        vu_proc.daemon = True
            
        active_processes['v'] = vu_proc
        vu_proc.start()
    else:
        stop_vu()
    
    # Clear input buffer after toggling
    clear_input_buffer()

def stop_vu():
    global vu_proc, stop_vu_event, stop_vu_queue

    if vu_proc is not None:
        try:
            stop_vu_event.set()
            stop_vu_queue.put(True)  # Signal the process to stop
            
            # Give the process a short time to stop gracefully
            vu_proc.join(timeout=1)
            
            if vu_proc.is_alive():
                # If still running after timeout, terminate
                vu_proc.terminate()
                vu_proc.join(timeout=1)
                if vu_proc.is_alive():
                    vu_proc.kill()  # Force kill if still alive
            
            print("\nvu stopped")
        except Exception as e:
            print(f"\nError stopping VU meter: {e}")
        finally:
            vu_proc = None
            cleanup_process('v')
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

def stop_intercom_m():
    global intercom_proc, stop_intercom_event
    
    if intercom_proc is not None:
        print("\nStopping intercom...")
        stop_intercom_event.set()
        if intercom_proc.is_alive():
            intercom_proc.join(timeout=2)  # Wait up to 2 seconds for clean shutdown
            if intercom_proc.is_alive():
                intercom_proc.terminate()  # Force terminate if still running
                intercom_proc.join(timeout=1)
        intercom_proc = None
        stop_intercom_event.clear()  # Reset the event for next use
        print("Intercom stopped")

def toggle_intercom_m():
    global intercom_proc, sound_in_id, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel, change_ch_event

    if intercom_proc is None:
        # Validate channel before starting
        if monitor_channel >= sound_in_chs:
            print(f"\nError: Selected channel {monitor_channel+1} exceeds available channels ({sound_in_chs})")
            print(f"Defaulting to channel 1")
            monitor_channel = 0  # Default to first channel
            
        print("Starting intercom on channel:", monitor_channel + 1)
        try:
            # Initialize the change channel event if it doesn't exist
            if not hasattr(change_ch_event, 'set'):
                change_ch_event = multiprocessing.Event()
            
            # Verify device configuration before starting
            input_device = sd.query_devices(sound_in_id)
            output_device = sd.query_devices(sound_out_id)
            
            # Only show device configuration in the main process
            if is_main_process():
                print("\nDevice configuration:")
                print(f"Input device: [{sound_in_id}] {input_device['name']}")
                print(f"Input channels: {input_device['max_input_channels']}")
                print(f"Input sample rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz")
                print(f"Output device: [{sound_out_id}] {output_device['name']}")
                print(f"Output channels: {output_device['max_output_channels']}")
                print(f"Output sample rate: {int(sound_out_samplerate)} Hz")
            
            # Create the process with daemon setting to ensure proper cleanup
            intercom_proc = multiprocessing.Process(
                target=intercom_m, 
                args=(sound_in_id, sound_in_chs, 
                     sound_out_id, sound_out_samplerate, sound_out_chs, 
                     monitor_channel)
            )
            intercom_proc.daemon = True  # Make the process a daemon so it exits when the main program exits
            intercom_proc.start()
            print("Intercom process started successfully")
        except Exception as e:
            print(f"Error starting intercom process: {e}")
            intercom_proc = None
    else:
        stop_intercom_m()
        print("\nIntercom stopped")
        intercom_proc = None

#
# Function to switch the channel being monitored
#

def change_monitor_channel():
    global monitor_channel, change_ch_event, vu_proc, intercom_proc, sound_in_chs

    # Clear input buffer before starting to ensure no leftover keystrokes
    clear_input_buffer()
    
    # Print available channels
    print(f"\nAvailable channels: 1-{sound_in_chs}")
    print("Press channel number (1-9) to monitor, or 0/q to exit:")
    
    while True:
        try:
            key = get_key()
            if key is None:
                time.sleep(0.01)  # Small delay to prevent high CPU usage
                continue
                
            # First, check for exit conditions and handle them immediately
            if key == '0' or key.lower() == 'q':
                print("\nExiting channel change")
                # Clear the input buffer before returning to prevent stray keystrokes
                clear_input_buffer()
                return
                
            # Handle digit keys for channel selection
            if key.isdigit() and int(key) > 0:
                # Convert the key to 0-indexed channel number
                key_int = int(key) - 1
                
                # Check if the channel is within the valid range (less than sound_in_chs)
                if key_int < sound_in_chs:
                    monitor_channel = key_int
                    print(f"\nNow monitoring channel: {monitor_channel+1} (of {sound_in_chs})")
                    
                    # Handle intercom channel change if active
                    if intercom_proc is not None:
                        change_ch_event.set()
                    
                    # Only restart VU meter if running
                    if vu_proc is not None:
                        print(f"Restarting VU meter on channel: {monitor_channel+1}")
                        toggle_vu_meter()
                        time.sleep(0.1)
                        toggle_vu_meter()
                    
                    # Exit after successful channel change
                    clear_input_buffer()
                    return
                else:
                    print(f"\nInvalid channel selection: Device has only {sound_in_chs} channel(s) (1-{sound_in_chs})")
            else:
                # Handle non-numeric, non-exit keys
                if key.isprintable() and key != '0' and key.lower() != 'q':
                    print(f"\nInvalid input: '{key}'. Use 1-{sound_in_chs} for channels or 0/q to exit.")
                    
        except Exception as e:
            print(f"\nError reading input: {e}")
            continue

#
# continuous fft plot of audio in a separate background process
#

def plot_and_save_fft(channel):
    interval = FFT_INTERVAL * 60    # convert to seconds, time betwwen ffts
    N = int(config.PRIMARY_IN_SAMPLERATE * config.FFT_DURATION)  # Number of samples, ensure it's an integer
    # Convert gain from dB to linear scale
    gain = 10 ** (config.FFT_GAIN / 20)

    while not stop_fft_periodic_plot_event.is_set():
        # Record audio
        print(f"Recording audio for auto fft in {FFT_INTERVAL} minutes...")
        # Wait for the desired time interval before recording and plotting again
        interruptable_sleep(interval, stop_fft_periodic_plot_event)
            
        myrecording = sd.rec(N, samplerate=config.PRIMARY_IN_SAMPLERATE, channels=channel + 1)
        sd.wait()  # Wait until recording is finished
        myrecording *= gain
        print("Recording auto fft finished.")

        # Perform FFT
        yf = rfft(myrecording.flatten())
        xf = rfftfreq(N, 1 / config.PRIMARY_IN_SAMPLERATE)

        # Define bucket width
        bucket_width = FFT_BW  # Hz
        bucket_size = int(bucket_width * N / config.PRIMARY_IN_SAMPLERATE)  # Number of indices per bucket

        # Average buckets
        buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
        bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

        # Plot results
        plt.plot(bucket_freqs, np.abs(buckets))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT Plot monitoring ch: ' + str(channel + 1) + ' of ' + str(sound_in_chs) + ' channels')

        plt.grid(True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Save plot to disk with a unique filename based on current time
        output_filename = f"{timestamp}_fft_{config.PRIMARY_IN_SAMPLERATE/1000:.0F}_{config.PRIMARY_BITDEPTH}_{channel}_{config.LOCATION_ID}_{config.HIVE_ID}.png"
        full_path_name = os.path.join(PLOT_DIRECTORY, output_filename)
        plt.savefig(full_path_name)

    print("Exiting fft periodic")

def reset_terminal_settings():
    """Reset terminal settings to ensure proper output formatting without clearing screen."""
    try:
        # Check if we're on Windows
        if sys.platform == 'win32' and not platform_manager.is_wsl():
            # Windows-specific terminal reset
            # os.system('cls')  # Commented out to preserve terminal history
            sys.stdout.flush()
            print("\n[Terminal formatting reset (Windows)]", end='\r\n', flush=True)
            return
            
        # For Unix-like systems (macOS/Linux) - don't reset to canonical mode during keyboard listening
        try:
            # Flush stdout to ensure all output is displayed
            sys.stdout.flush()
            
            # Force line buffering - but only if supported on this platform/Python version
            try:
                sys.stdout.reconfigure(line_buffering=True)
            except (AttributeError, TypeError):
                # Older Python versions or Windows may not support reconfigure
                pass
                
        except ImportError:
            # Fallback if termios isn't available
            pass
        
        print("\n[Terminal formatting reset]", end='\r\n', flush=True)
        
    except Exception as e:
        print(f"Warning: Could not reset terminal settings: {e}", end='\r\n', flush=True)

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

def recording_worker_thread(record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
    global buffer, buffer_size, buffer_index, stop_recording_event, _subtype

    if start_tod is None:
        print(f"{thread_id} is recording continuously\r")

    samplerate = config.PRIMARY_IN_SAMPLERATE

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
                save_sample_rate = config.PRIMARY_SAVE_SAMPLERATE if config.PRIMARY_SAVE_SAMPLERATE is not None else config.PRIMARY_IN_SAMPLERATE
                
                # Resample if needed
                if save_sample_rate < config.PRIMARY_IN_SAMPLERATE:
                    # resample to lower sample rate
                    audio_data = downsample_audio(audio_data, config.PRIMARY_IN_SAMPLERATE, save_sample_rate)
                    print(f"Resampling from {config.PRIMARY_IN_SAMPLERATE}Hz to {save_sample_rate}Hz for saving")

                # Check if we're shutting down before saving
                if stop_recording_event.is_set():
                    break

                # Check and create new date folders if needed
                check_and_create_date_folders()

                # Get current date for folder name
                current_date = datetime.datetime.now()
                date_folder = current_date.strftime('%y%m%d')  # Format: YYMMDD

                # Handle different file formats
                if file_format.upper() == 'MP3':
                    if target_sample_rate == 44100 or target_sample_rate == 48000:
                        full_path_name = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                                    folders[0], "mp3", date_folder, 
                                                    f"{current_date.strftime('%H%M%S')}_{thread_id}_{record_period}_{interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}")
                        print(f"\nAttempting to save MP3 file: {full_path_name}")
                        try:
                            pcm_to_mp3_write(audio_data, full_path_name)
                            print(f"Successfully saved: {full_path_name}")
                        except Exception as e:
                            print(f"Error saving MP3 file: {e}")
                    else:
                        print("MP3 only supports 44.1k and 48k sample rates")
                        quit(-1)
                elif file_format.upper() in ['FLAC', 'WAV']:
                    full_path_name = os.path.join(data_drive, data_path, config.LOCATION_ID, config.HIVE_ID, 
                                                folders[0], "raw", date_folder, 
                                                f"{current_date.strftime('%H%M%S')}_{thread_id}_{record_period}_{interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}")
                    print(f"\nAttempting to save {file_format.upper()} file: {full_path_name}")
                    # Ensure sample rate is an integer
                    save_sample_rate = int(save_sample_rate)
                    try:
                        sf.write(full_path_name, audio_data, save_sample_rate, 
                                format=file_format.upper(), 
                                subtype=_subtype)
                        print(f"Successfully saved: {full_path_name}")
                    except Exception as e:
                        print(f"Error saving {file_format.upper()} file: {e}")
                else:
                    print(f"Unsupported file format: {file_format}")
                    print("Supported formats are: MP3, FLAC, WAV")
                    quit(-1)
                
                if not stop_recording_event.is_set():
                    print(f"Saved {thread_id} audio to {full_path_name}, period: {record_period}, interval {interval} seconds\r")
                # wait "interval" seconds before starting recording again
                interruptable_sleep(interval, stop_recording_event)
            
        except Exception as e:
            print(f"Error in recording_worker_thread: {e}")
            stop_recording_event.set()

def callback(indata, frames, time, status):
    """Callback function for audio input stream."""
    global buffer, buffer_index
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

def audio_stream():
    global stop_program, sound_in_id, sound_in_chs, _dtype, testmode

    # Reset terminal settings before printing
    reset_terminal_settings()

    # Print initialization info with forced output
    print("Initializing audio stream...", flush=True)
    print(f"Device ID: [{sound_in_id}]", end='\r', flush=True)
    print(f"Channels: {sound_in_chs}", end='\r', flush=True)
    print(f"Sample Rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz", end='\r', flush=True)
    print(f"Bit Depth: {config.PRIMARY_BITDEPTH} bits", end='\r', flush=True)
    print(f"Data Type: {_dtype}", end='\r', flush=True)

    try:
        # First verify the device configuration
        device_info = sd.query_devices(sound_in_id)
        print("\nSelected device info:", flush=True)
        print(f"Name: [{sound_in_id}] {device_info['name']}", end='\r', flush=True)
        print(f"Max Input Channels: {device_info['max_input_channels']}", end='\r', flush=True)
        print(f"Device Sample Rate: {int(device_info['default_samplerate'])} Hz", end='\r', flush=True)

        if device_info['max_input_channels'] < sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {sound_in_chs} channels are required")

        # Set the device's sample rate to match our configuration
        sd.default.samplerate = config.PRIMARY_IN_SAMPLERATE
        
        # Initialize the stream with the configured sample rate and bit depth
        stream = sd.InputStream(
            device=sound_in_id,
            channels=sound_in_chs,
            samplerate=config.PRIMARY_IN_SAMPLERATE,  # Use configured rate
            dtype=_dtype,  # Use configured bit depth
            blocksize=blocksize,
            callback=callback
        )

        print("\nAudio stream initialized successfully\r", flush=True)
        print(f"Stream sample rate: {stream.samplerate} Hz", end='\r', flush=True)
        print(f"Stream bit depth: {config.PRIMARY_BITDEPTH} bits", end='\r', flush=True)

        with stream:
            # start the recording worker threads
            if config.MODE_AUDIO_MONITOR:
                print("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...\r")
                #sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=( config.AUDIO_MONITOR_RECORD, \
                                                                        config.AUDIO_MONITOR_INTERVAL, \
                                                                        "Audio_monitor", \
                                                                        config.AUDIO_MONITOR_FORMAT, \
                                                                        config.AUDIO_MONITOR_SAMPLERATE, \
                                                                        config.AUDIO_MONITOR_START, \
                                                                        config.AUDIO_MONITOR_END)).start()

            if config.MODE_PERIOD and not testmode:
                print("Starting recording_worker_thread for caching period audio at primary sample rate and all channels...\r")
                #sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=( config.PERIOD_RECORD, \
                                                                        config.PERIOD_INTERVAL, \
                                                                        "Period_recording", \
                                                                        config.PRIMARY_FILE_FORMAT, \
                                                                        config.PRIMARY_IN_SAMPLERATE, \
                                                                        config.PERIOD_START, \
                                                                        config.PERIOD_END)).start()

            if config.MODE_EVENT and not testmode:
                print("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...\r")
                #sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=( config.SAVE_BEFORE_EVENT, \
                                                                        config.SAVE_AFTER_EVENT, \
                                                                        "Event_recording", \
                                                                        config.PRIMARY_FILE_FORMAT, \
                                                                        config.PRIMARY_IN_SAMPLERATE, \
                                                                        config.EVENT_START, \
                                                                        config.EVENT_END)).start()

            # Wait for keyboard input to stop
            while not stop_program[0]:
                time.sleep(0.1)

    except Exception as e:
        print(f"\nError initializing audio stream: {str(e)}")
        print("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
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

def toggle_listening():
    global keyboard_listener_active
    keyboard_listener_active = not keyboard_listener_active
    if keyboard_listener_active:
        print("\nKeyboard listener activated. Listening for commands...")
        show_list_of_commands()
    else:
        print("\nKeyboard listener deactivated. Press '^' to reactivate.")
        stop_vu()
        stop_intercom_m()

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

def keyboard_listener():
    """Main keyboard listener loop."""
    global keyboard_listener_running, keyboard_listener_active, monitor_channel, change_ch_event, vu_proc, intercom_proc, sound_in_chs
    
    # Reset terminal settings before starting
    reset_terminal_settings()
    
    print("\nstarted. Press 'h' for help.", end='\n', flush=True)
    
    while keyboard_listener_running:
        try:
            key = get_key()
            if key is not None:
                if key == "^":  # Tilda key
                    toggle_listening()
                elif keyboard_listener_active:
                    if key.isdigit():
                        # Handle direct channel changes when in VU meter or Intercom mode
                        if vu_proc is not None or intercom_proc is not None:
                            key_int = int(key) - 1  # Convert to 0-based index
                            
                            # Validate channel number is within range
                            if key_int < 0 or key_int >= sound_in_chs:
                                print(f"\nInvalid channel selection: Device has only {sound_in_chs} channel(s) (1-{sound_in_chs})", end='\n', flush=True)
                                continue
                                
                            if is_mic_position_in_bounds(MICS_ACTIVE, key_int):
                                monitor_channel = key_int
                                if intercom_proc is not None:
                                    change_ch_event.set()
                                print(f"\nNow monitoring channel: {monitor_channel+1} (of {sound_in_chs})", end='\n', flush=True)
                                # Restart VU meter if running
                                if vu_proc is not None:
                                    print(f"Restarting VU meter on channel: {monitor_channel+1}", end='\n', flush=True)
                                    toggle_vu_meter()
                                    time.sleep(0.1)
                                    toggle_vu_meter()
                            else:
                                print(f"Sound device has only {sound_in_chs} channel(s)", end='\n', flush=True)
                        else:
                            # If not in VU meter or Intercom mode, handle other digit commands
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
                    elif key == "D":  
                        show_detailed_device_list()
                    elif key == "f":  
                        try:
                            trigger_fft()
                        except Exception as e:
                            print(f"Error in FFT trigger: {e}", end='\n', flush=True)
                            # Ensure we clean up any stuck processes
                            cleanup_process('f')
                    elif key == "i":  
                        toggle_intercom_m()
                    elif key == "m":  
                        show_mic_locations()
                    elif key == "o":  
                        trigger_oscope()        
                    elif key == "p":
                        run_performance_monitor_once()
                    elif key == "P":
                        toggle_continuous_performance_monitor()
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
            # Don't exit the keyboard listener on error, just continue
            continue
            
        time.sleep(0.01)  # Small delay to prevent high CPU usage

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

def check_dependencies():
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
        elif platform_manager.is_macos():
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
        if platform_manager.is_wsl():
            print("Run these commands in WSL:")
            print("sudo apt-get update")
            print("sudo apt-get install ffmpeg")
        elif platform_manager.is_macos():
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
    global fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel, sound_in_id, sound_in_chs, MICS_ACTIVE, keyboard_listener_running, make_name, model_name, device_name, api_name, hostapi_name, hostapi_index, device_id, original_terminal_settings

    # --- Setup Logging ---
    log_file_path = os.path.join(data_drive, data_path, 'BMAR.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(processName)s - %(threadName)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("--- Starting Beehive Multichannel Acoustic-Signal Recorder ---")

    # Save original terminal settings at startup
    original_terminal_settings = save_terminal_settings()

    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, emergency_cleanup)   # Ctrl+C
    signal.signal(signal.SIGTERM, emergency_cleanup)  # Termination request
    if sys.platform != 'win32':
        signal.signal(signal.SIGHUP, emergency_cleanup)   # Terminal closed
        signal.signal(signal.SIGQUIT, emergency_cleanup)  # Ctrl+\

    # --- Audio format validation ---
    allowed_primary_formats = ["FLAC", "WAV"]
    allowed_monitor_formats = ["MP3", "FLAC", "WAV"]
    if config.PRIMARY_FILE_FORMAT.upper() not in allowed_primary_formats:
        print(f"WARNING: PRIMARY_FILE_FORMAT '{config.PRIMARY_FILE_FORMAT}' is not allowed. Must be one of: {allowed_primary_formats}")
    if config.AUDIO_MONITOR_FORMAT.upper() not in allowed_monitor_formats:
        print(f"WARNING: AUDIO_MONITOR_FORMAT '{config.AUDIO_MONITOR_FORMAT}' is not allowed. Must be one of: {allowed_monitor_formats}")

    logging.info("Beehive Multichannel Acoustic-Signal Recorder")
   
    # Display platform-specific messages
    if sys.platform == 'win32' and not platform_manager.is_wsl():
        logging.info("Running on Windows - some terminal features will be limited.")
        logging.info("Note: You can safely ignore the 'No module named termios' warning.")
   
    # Check dependencies
    if not check_dependencies():
        logging.warning("Some required packages are missing or outdated.")
        logging.warning("The script may not function correctly.")
        response = timed_input("Do you want to continue anyway? (y/n): ", timeout=3, default='n')
        if response.lower() != 'y':
            sys.exit(1)
    
    logging.info(f"Saving data to: {PRIMARY_DIRECTORY}")

    # Try to set up the input device
    if not set_input_device(model_name, api_name):
        logging.critical("Exiting due to no suitable audio input device found.")
        sys.exit(1)

    # Validate and adjust monitor_channel after device setup
    if monitor_channel >= sound_in_chs:
        logging.warning(f"Monitor channel {monitor_channel+1} exceeds available channels ({sound_in_chs})")
        monitor_channel = 0  # Default to first channel
        logging.info(f"Setting monitor channel to {monitor_channel+1}")

    setup_audio_circular_buffer()

    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/500000:.2f} megabytes")
    print(f"Sample Rate: {int(config.PRIMARY_IN_SAMPLERATE)} Hz; File Format: {config.PRIMARY_FILE_FORMAT}; Channels: {sound_in_chs}")

    # Check and create date-based directories
    if not check_and_create_date_folders():
        logging.critical("Critical directories could not be created. Exiting.")
        sys.exit(1)
    
    # Print directories for verification
    logging.info("Directory setup:")
    logging.info(f"  Primary recordings: {PRIMARY_DIRECTORY}")
    logging.info(f"  Monitor recordings: {MONITOR_DIRECTORY}")
    logging.info(f"  Plot files: {PLOT_DIRECTORY}")
    
    # Ensure all required directories exist
    if not ensure_directories_exist([PRIMARY_DIRECTORY, MONITOR_DIRECTORY, PLOT_DIRECTORY]):
        logging.critical("Critical directories could not be created. Exiting.")
        sys.exit(1)

    # Create and start the process
    if config.MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft, args=(monitor_channel,)) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")

    try:
        if KB_or_CP == 'KB':
            # Give a small delay to ensure prints are visible before starting keyboard listener
            time.sleep(1)
            # Start keyboard listener in a separate thread
            keyboard_thread = threading.Thread(target=keyboard_listener)
            keyboard_thread.daemon = True
            keyboard_thread.start()
            
        # Start the audio stream
        audio_stream()
            
    except KeyboardInterrupt: # ctrl-c in windows
        print('\nCtrl-C: Recording process stopped by user.')
        cleanup()

    except Exception as e:
        logging.critical("An error occurred while attempting to execute this script", exc_info=True)
        cleanup()
    finally:
        # Ensure terminal is reset even if an error occurs
        restore_terminal_settings(original_terminal_settings)

def stop_all():
    """Stop all processes and threads."""
    global stop_program, stop_recording_event, stop_fft_periodic_plot_event, fft_periodic_plot_proc, keyboard_listener_running
    print("Stopping all processes...\r")
    
    try:
        # Set all stop events
        stop_program[0] = True
        stop_recording_event.set()
        stop_fft_periodic_plot_event.set()
        stop_vu_event.set()
        stop_intercom_event.set()
        stop_tod_event.set()
        stop_performance_monitor_event.set()  # Add this line
        keyboard_listener_running = False

        # Clean up all active processes
        for command in active_processes:
            cleanup_process(command)

        # Stop the FFT periodic plot process
        if fft_periodic_plot_proc is not None:
            print("Stopping FFT periodic plot process...\r")
            try:
                # Check if it's still alive without raising an exception
                if hasattr(fft_periodic_plot_proc, 'is_alive') and fft_periodic_plot_proc.is_alive():
                    fft_periodic_plot_proc.terminate()
                    fft_periodic_plot_proc.join(timeout=2)
                    if fft_periodic_plot_proc.is_alive():
                        fft_periodic_plot_proc.kill()
            except Exception as e:
                print(f"Error stopping FFT process: {e}")

        # Stop VU meter
        stop_vu()

        # Stop intercom
        stop_intercom_m()

        # List and stop all worker threads
        print("Stopping worker threads...\r")
        current_thread = threading.current_thread()
        for thread in threading.enumerate():
            if thread != threading.main_thread() and thread != current_thread:
                print(f"Stopping thread: {thread.name}\r")
                if thread.is_alive():
                    try:
                        thread.join(timeout=1)
                    except RuntimeError:
                        pass
    except Exception as e:
        print(f"Error in stop_all: {e}")
        # Don't call emergency_cleanup here as it creates recursion

    print("\nAll processes and threads stopped\r")

def cleanup():
    """Clean up and exit."""
    print("Cleaning up...\r")
    
    try:
        # Set stop flags to prevent any new recordings
        stop_program[0] = True
        stop_recording_event.set()
        
        # Stop all processes and threads
        stop_all()
        
        # Platform-specific terminal cleanup
        try:
            restore_canonical_terminal()
        except Exception as e:
            print(f"Error resetting terminal: {e}", end='\r\n', flush=True)
            # Try alternative terminal reset
            try:
                if sys.platform != 'win32':
                    os.system('stty sane')
                    os.system('stty echo')
            except:
                pass
    except Exception as e:
        print(f"Error during cleanup: {e}", end='\r\n', flush=True)
        # Don't call emergency_cleanup here as it may cause recursion
    
    # Give threads a moment to clean up
    time.sleep(0.5)
    
    # Force kill any remaining processes
    force_kill_child_processes()
    
    # Final terminal reset attempt
    try:
        if sys.platform != 'win32':
            os.system('stty sane')
            os.system('stty echo')
            sys.stdout.write('\n')
            sys.stdout.flush()
    except:
        pass
    
    # Force exit after cleanup
    print("Exiting...", end='\r\n', flush=True)
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

def emergency_cleanup(signum=None, frame=None):
    """Emergency cleanup function for handling signals and abnormal termination."""
    global emergency_cleanup_in_progress
    
    # Prevent recursive calls
    if emergency_cleanup_in_progress:
        return
        
    emergency_cleanup_in_progress = True
    print("\nEmergency cleanup initiated...")
    try:
        # Stop all processes first
        stop_all()
        
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
                    os.system('stty sane')
                    os.system('stty echo')
            except:
                pass
        
        print("Emergency cleanup completed")
    except Exception as e:
        print(f"Error during emergency cleanup: {e}")
    finally:
        # Force exit
        os._exit(1)

# Register the emergency cleanup for various signals
signal.signal(signal.SIGINT, emergency_cleanup)   # Ctrl+C
signal.signal(signal.SIGTERM, emergency_cleanup)  # Termination request
if sys.platform != 'win32':
    signal.signal(signal.SIGHUP, emergency_cleanup)   # Terminal closed
    signal.signal(signal.SIGQUIT, emergency_cleanup)  # Ctrl+\

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

def run_performance_monitor_once():
    """Run the performance monitor once."""
    cleanup_process('p')  # Clean up any existing process
    proc = multiprocessing.Process(target=monitor_system_performance_once)
    proc.daemon = True
    active_processes['p'] = proc
    proc.start()
    proc.join()  # Wait for it to complete
    cleanup_process('p')

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

if __name__ == "__main__":
    main()

