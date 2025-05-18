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
import subprocess  # Add this import
#import curses
#import io
#import queue
import queue

# Try to import pynput for direct keyboard handling
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("pynput not available - keyboard input may not work optimally")
    print("To install pynput: pip install pynput")

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
            elif self.is_macos():
                self._msvcrt = None
                print("Using macOS keyboard handling")
                self._keyboard_info = "macOS"
            else:
                self._msvcrt = None
                print("Using Linux keyboard handling")
                self._keyboard_info = "Linux"
    
    @property
    def msvcrt(self):
        return self._msvcrt

# Create global platform manager instance
platform_manager = PlatformManager()
# Initialize platform at startup
platform_manager.initialize()

# Now that we've properly detected the platform, import platform-specific modules
if platform_manager.is_macos() or (sys.platform != 'win32' and not platform_manager.is_wsl()):
    # For macOS and Linux systems
    import termios
    import tty
elif sys.platform == 'win32' and not platform_manager.is_wsl():
    # Windows-specific imports (if any needed in the future)
    pass

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
keyboard_listener_active = True  # Add this line - default state is active

# #############################################################
# #### Control Panel ##########################################
# #############################################################

MONITOR_CH = 0                                  # channel to monitor for event (if > number of chs, all channels are monitored)
TRACE_DURATION = 10                             # seconds of audio to show on oscope
OSCOPE_GAIN_DB = 12                             # Gain in dB of audio level for oscope 

# instrumentation parms
FFT_BINS = 800                                  # number of bins for fft
FFT_BW = 1000                                   # bandwidth of each bucket in hertz
FFT_DURATION = 5                                # seconds of audio to show on fft
FFT_GAIN = 20                                   # gain in dB for fft
FFT_INTERVAL = 30                               # minutes between ffts

OSCOPE_DURATION = 10                            # seconds of audio to show on oscope
OSCOPE_GAIN_DB = 12                             # gain in dB for oscope

FULL_SCALE = 2 ** 16                            # just for cli vu meter level reference
BUFFER_SECONDS = 1000                           # time length of circular buffer 

# global: list of mics present in system
MICS_ACTIVE = [config.MIC_1, config.MIC_2, config.MIC_3, config.MIC_4]

# translate human to machine
if  config.PRIMARY_BITDEPTH == 16:
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

# Select the appropriate data drive and path based on OS
if platform_manager.is_macos():
    data_drive = os.path.expanduser(config.mac_data_drive)  # Expand ~ if present
    data_path = config.mac_data_path
    folders = config.mac_data_folders
elif sys.platform == 'win32':
    data_drive = config.win_data_drive
    data_path = config.win_data_path
    folders = config.win_data_folders
else:  # Linux or other Unix-like
    data_drive = os.path.expanduser(config.linux_data_drive)  # Expand ~ if present
    data_path = config.linux_data_path
    folders = config.linux_data_folders

# to be discovered from sounddevice.query_devices()
sound_in_id = 1                             # id of input device, set as default in case none is detected
sound_in_chs = config.SOUND_IN_CHS          # number of input channels
sound_in_samplerate = None                   # will be set to actual device rate in set_input_device

sound_out_id = config.SOUND_OUT_ID_DEFAULT
sound_out_chs = config.SOUND_OUT_CHS_DEFAULT                        
sound_out_samplerate = config.SOUND_OUT_SR_DEFAULT    

# Create date components in the correct format
# For folder structure we need YY (2-digit year), MM, DD format
yy = current_date.strftime('%y')  # 2-digit year (e.g., '23' for 2023)
mm = current_date.strftime('%m')  # Month (01-12)
dd = current_date.strftime('%d')  # Day (01-31)
date_folder = f"{yy}{mm}{dd}"     # Format YYMMDD (e.g., '230516')

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
    Check if directories exist and create them if necessary with user permission.
    
    Args:
        directories: List of directory paths to check and potentially create
        
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
    
    print("\nThe following directories do not exist:")
    for d in missing_dirs:
        print(f"  - {d}")
    
    response = input("\nDo you want to create these directories? (y/n): ")
    if response.lower() != 'y':
        print("Directory creation aborted. The program may not function correctly.")
        return False
    
    success = True
    for d in missing_dirs:
        try:
            print(f"Attempting to create directory: {d}")
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


def signal_handler(sig, frame):
    print('\nStopping all threads...\r')
    
    # Reset terminal before stopping
    reset_terminal()
    _better_clear_input_buffer()
    
    # Then call stop_all
    stop_all()
    
    # Final cleanup
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def reset_terminal():
    """Reset terminal settings to default state without clearing the screen."""
    try:
        # Flush any pending input first
        clear_input_buffer()
        
        # For macOS/Linux systems
        if platform_manager.is_macos() or not platform_manager.msvcrt:
            try:
                # Reset terminal settings
                import termios
                fd = sys.stdin.fileno()
                try:
                    old_settings = termios.tcgetattr(fd)
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except:
                    pass
                
                # Direct terminal reset commands
                os.system('stty sane')  # Basic sanity
                os.system('stty echo')  # Turn echo back on
                os.system('stty icanon')  # Line buffering mode
            except Exception as e:
                print(f"\nWarning during terminal reset: {e}")
        
        # For Windows systems
        elif platform_manager.msvcrt is not None:
            # Windows handles this differently, no special action needed
            pass
        
        # Flush stdout to ensure all output is displayed
        sys.stdout.flush()
        
        print("\n[Terminal mode reset]")
        
    except Exception as e:
        print(f"\nWarning: Could not reset terminal: {e}")
        try:
            # Last resort
            os.system('stty sane')
        except:
            pass

def cleanup():
    """Clean up and exit."""
    print("\nCleaning up resources...")
    
    try:
        # First stop the keyboard thread and other inputs
        if 'keyboard_thread_active' in globals():
            global keyboard_thread_active
            keyboard_thread_active = False
        
        # Stop all other processes and threads
        stop_all()
        
        # Clean up the input buffer
        clear_input_buffer()
        
        # Reset terminal settings
        reset_terminal()
        
        # Additional terminal reset as backup
        if platform_manager.is_macos() or not platform_manager.msvcrt:
            try:
                os.system('stty sane')
                os.system('stty echo')
                os.system('stty icanon')
            except Exception as e:
                print(f"\nAdditional reset failed: {e}")
        
        # Give threads a moment to clean up
        time.sleep(0.1)
        
    except Exception as e:
        print(f"\nError during cleanup: {e}")
    
    # Final flush
    sys.stdout.flush()
    
    # Force exit after cleanup to avoid any lingering processes
    print("\nExiting program. Thank you for using the Beehive Audio Recorder.")
    os._exit(0)

def clear_input_buffer():
    """Clear the keyboard input buffer. Enhanced version for better cleanup."""
    
    # Windows implementation
    if sys.platform == 'win32' and not platform_manager.is_wsl() and platform_manager.msvcrt is not None:
        try:
            # For Windows, keep reading keys until the buffer is empty
            while platform_manager.msvcrt.kbhit():
                platform_manager.msvcrt.getch()
        except:
            pass  # Silent fail
    
    # macOS/Linux implementation
    else:
        try:
            # For Unix-like systems, try to read everything available
            import termios, tty, select
            
            # Set a short timeout
            timeout = 0.1
            
            # Get file descriptor for stdin
            fd = sys.stdin.fileno()
            
            # Save original settings
            try:
                old_settings = termios.tcgetattr(fd)
                
                # Try raw mode with very brief timeout
                try:
                    # Set non-blocking mode
                    tty.setraw(fd, termios.TCSANOW)
                    
                    # Read all pending input
                    while select.select([sys.stdin], [], [], 0)[0]:
                        sys.stdin.read(1)
                        
                    # One more time with a short timeout
                    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
                    if rlist:
                        sys.stdin.read(len(rlist))
                finally:
                    # Restore settings
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except:
                # Last resort
                try:
                    os.system('stty -raw echo')
                except:
                    pass
        except:
            pass  # Silent fail

def keyboard_listener():
    """Main keyboard listener function"""
    global keyboard_listener_running, keyboard_listener_active, monitor_channel, change_ch_event, vu_proc, intercom_proc, pynput_listener
    
    print("\nKeyboard listener active. Press 'h' for help (no Enter needed).", end='\r\n', flush=True)
    
    # Initialize keyboard input (either through pynput or traditional thread)
    keyboard_thread = start_keyboard_thread()
    
    if PYNPUT_AVAILABLE and pynput_listener:
        print("Using pynput for keyboard input - direct key capture active", end='\r\n', flush=True)
    elif keyboard_thread:
        print(f"Using traditional keyboard thread: {keyboard_thread.name}", end='\r\n', flush=True)
    else:
        print("WARNING: No keyboard input method active!", end='\r\n', flush=True)
    
    # Initialize last command time for debouncing
    last_command_time = 0
    min_command_interval = 0.1  # Minimum seconds between commands
    
    # Counter to occasionally check thread status
    status_counter = 0
    
    try:
        while keyboard_listener_running:
            # Check status occasionally
            status_counter += 1
            if status_counter >= 1000:
                status_counter = 0
                # Check thread status if using traditional method
                if keyboard_thread and not keyboard_thread.is_alive():
                    print("WARNING: Keyboard thread died! Restarting...", end='\r\n', flush=True)
                    keyboard_thread = start_keyboard_thread()
                # Check pynput status if using that method
                elif PYNPUT_AVAILABLE and pynput_listener and not pynput_listener.is_alive():
                    print("WARNING: pynput listener died! Restarting...", end='\r\n', flush=True)
                    start_pynput_listener()
            
            # Get key from the queue
            key = get_key()
            
            # Process detected key if any and if active
            if key:
                # Skip newline characters entirely
                if key == '\n' or key == '\r':
                    continue
                
                # Don't echo the key itself to terminal
                
                current_time = time.time()
                
                # Skip processing if too soon after the last command
                if current_time - last_command_time < min_command_interval:
                    continue
                    
                # Update last command time
                last_command_time = current_time
                
                # Process the key
                if key == "^":  # Tilda key for toggling listener
                    toggle_listening()
                elif keyboard_listener_active:
                    # Handle digit keys for channel selection
                    if key.isdigit():
                        # Process digit keys...
                        process_digit_key(key)
                    # Process single-letter commands
                    elif key == "a": 
                        print("\nAudio status check starting...", end='\r\n', flush=True)
                        check_stream_status(10)
                    elif key == "c":  
                        print("\nChanging channel...", end='\r\n', flush=True)
                        change_monitor_channel()
                    elif key == "d":  
                        print("\nShowing device list...", end='\r\n', flush=True)
                        show_audio_device_list()
                    elif key == "f":  
                        print("\nGenerating FFT plot...", end='\r\n', flush=True)
                        try:
                            trigger_fft()
                        except Exception as e:
                            print(f"Error in FFT: {e}", end='\r\n', flush=True)
                            cleanup_process('f')
                    elif key == "i":  
                        print("\nToggling intercom...", end='\r\n', flush=True)
                        toggle_intercom_m()
                    elif key == "m":  
                        print("\nShowing mic locations...", end='\r\n', flush=True)
                        show_mic_locations()
                    elif key == "o":  
                        print("\nGenerating oscilloscope...", end='\r\n', flush=True)
                        trigger_oscope()        
                    elif key == "q":  
                        print("\nQuitting program...", end='\r\n', flush=True)
                        keyboard_listener_running = False
                        # Force a terminal reset before stopping
                        reset_terminal()
                        # Then stop all and clean up
                        stop_all()
                        break  # Exit the loop immediately
                    elif key == "s":  
                        print("\nGenerating spectrogram...", end='\r\n', flush=True)
                        trigger_spectrogram()
                    elif key == "t":  
                        print("\nListing threads...", end='\r\n', flush=True)
                        list_all_threads()        
                    elif key == "v":  
                        print("\nToggling VU meter...", end='\r\n', flush=True)
                        toggle_vu_meter()      
                    elif key == "h" or key =="?":  
                        print("\nShowing help...", end='\r\n', flush=True)  
                        show_list_of_commands()
                    else:
                        # Only show for printable characters
                        if key.isprintable():
                            print(f"\nUnknown command: '{key}' - Press 'h' for help", end='\r\n', flush=True)
            
            # Sleep to reduce CPU usage - shorter value for faster response
            time.sleep(0.005)
    
    except Exception as e:
        print(f"Error in keyboard listener: {e}", end='\r\n', flush=True)
    
    finally:
        # Make sure to stop the keyboard thread when we're done
        print("Stopping keyboard thread...", end='\r\n', flush=True)
        stop_keyboard_thread()
        
        # Final terminal reset
        reset_terminal()
        
        if keyboard_thread:
            try:
                keyboard_thread.join(timeout=1)
                print("Keyboard thread stopped", end='\r\n', flush=True)
            except Exception as e:
                print(f"Error stopping keyboard thread: {e}", end='\r\n', flush=True)

# Create a _better_clear_input_buffer function to help with keyboard cleanup
def _better_clear_input_buffer():
    """Enhanced version of clear_input_buffer for better cleanup."""
    # First call the original implementation
    clear_input_buffer()
    
    # Then do additional clearing for macOS/Linux
    if platform_manager.is_macos() or (sys.platform != 'win32' and not platform_manager.is_wsl()):
        try:
            # Try an additional reset approach with timeout
            import termios, tty, select
            
            fd = sys.stdin.fileno()
            try:
                old_settings = termios.tcgetattr(fd)
                
                # Set non-blocking mode temporarily
                tty.setraw(fd, termios.TCSANOW)
                
                # Read any pending input with a short timeout
                timeout = 0.1
                rlist, _, _ = select.select([sys.stdin], [], [], timeout)
                if rlist:
                    # Read and discard all pending input
                    sys.stdin.read(len(rlist))
                    
                # Reset terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except:
                # Last resort
                try:
                    os.system('stty -raw echo')
                except:
                    pass
        except:
            pass

# Update the toggle_listening function to create the variable if needed
def toggle_listening():
    global keyboard_listener_active
    
    # Make sure the variable exists
    if 'keyboard_listener_active' not in globals():
        globals()['keyboard_listener_active'] = True
    
    # Toggle the state
    keyboard_listener_active = not keyboard_listener_active
    
    # Clear the screen line
    print("\r" + " " * 80, end="\r", flush=True)
    
    if keyboard_listener_active:
        print("\nKeyboard listener activated. Listening for commands...", end='\r', flush=True)
        show_list_of_commands()
    else:
        print("\nKeyboard listener deactivated. Press '^' to reactivate.", end='\r', flush=True)
        # Only try to stop processes if they exist
        if 'stop_vu' in globals():
            try:
                stop_vu()
            except:
                pass
        if 'stop_intercom_m' in globals():
            try:
                stop_intercom_m()
            except:
                pass

# Add a minimal show_list_of_commands function if it doesn't exist
def show_list_of_commands():
    """Show a list of available keyboard commands."""
    print("\nAvailable commands:")
    print("  q  Quit program")
    print("  ^  Toggle keyboard listener on/off")
    print("  c  Change channel")
    print("  h  Show this help message")

# Enhance the original stop_all function
def _enhance_stop_all():
    """Helper to enhance the original stop_all function."""
    # Call the original stop_all function
    stop_all()
    
    # Add additional terminal cleanup
    _better_clear_input_buffer()
    reset_terminal()
    
    # Make sure we flush stdout
    sys.stdout.flush()

# Function to get keyboard input without requiring Enter
def get_key():
    """Get a single keypress from the user."""
    if platform_manager.msvcrt is not None:
        try:
            # Windows implementation
            return platform_manager.msvcrt.getch().decode('utf-8')
        except Exception as e:
            print(f"Error reading key in Windows: {e}")
            return None
    else:
        try:
            if sys.platform == 'win32':
                # Alternative Windows method
                import msvcrt
                if msvcrt.kbhit():
                    return msvcrt.getch().decode('utf-8')
                return None
            elif platform_manager.is_macos() or sys.platform.startswith('linux'):
                # Unix-like systems implementation
                import termios, tty, select
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setraw(sys.stdin.fileno())
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        key = sys.stdin.read(1)
                        return key
                    return None
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            else:
                # Fallback for other platforms
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    return sys.stdin.read(1)
                return None
        except Exception as e:
            if "termios" in str(e):
                # Try alternative method if termios fails
                try:
                    import msvcrt
                    if msvcrt.kbhit():
                        return msvcrt.getch().decode('utf-8')
                except:
                    pass
            print(f"Error reading key: {e}")
            return None

# Function to check if a mic position is valid
def is_mic_position_in_bounds(mic_list, position):
    """Check if the given mic position is within bounds."""
    if not mic_list:
        return position < sound_in_chs
    else:
        return position < len(mic_list) and position < sound_in_chs

# Function to process digit key input for various commands
def process_digit_key(key):
    """Process digit key input."""
    # This function can be expanded for digit key commands
    # Currently, it doesn't need to do anything as change_monitor_channel handles its own input
    pass

# Function to switch the channel being monitored
def change_monitor_channel():
    """Change the channel to monitor."""
    global monitor_channel, change_ch_event, vu_proc, intercom_proc

    print("\nPress channel number (1-9) to monitor, or 0/q to exit:")
    while True:
        try:
            key = get_key()
            if key is None:
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                continue
                
            if key.isdigit():
                if int(key) == 0:
                    print("\nExiting channel change")
                    return
                else:
                    key_int = int(key) - 1
                if (is_mic_position_in_bounds(MICS_ACTIVE, key_int)):
                    monitor_channel = key_int
                    if intercom_proc is not None:
                        change_ch_event.set()
                        print(f"\nNow monitoring channel: {monitor_channel+1} (of {sound_in_chs})")
                    # Only restart VU meter if running
                    if vu_proc is not None:
                        print(f"\nRestarting VU meter on channel: {monitor_channel+1}")
                        toggle_vu_meter()
                        time.sleep(0.1)
                        toggle_vu_meter()
                    else:
                        print(f"\nChanged to channel: {monitor_channel+1} (of {sound_in_chs})")
                else:
                    print(f"\nSound device has only {sound_in_chs} channel(s)")
            elif key.lower() == 'q':
                print("\nExiting channel change")
                return
        except Exception as e:
            print(f"\nError reading input: {e}")
            continue

# Add a proper check_dependencies function
def check_dependencies():
    """Check for required Python libraries and their versions."""
    print("Checking for required dependencies...")
    
    # Just verify the critical libraries are available
    required = ['sounddevice', 'soundfile', 'numpy', 'matplotlib']
    missing = []
    
    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)
    
    if missing:
        print("Missing required libraries:")
        for lib in missing:
            print(f"  - {lib}")
        print("\nPlease install these packages with:")
        print(f"pip install {' '.join(missing)}")
        return False
        
    return True  # All dependencies found

# Add a proper set_input_device function
def set_input_device(model_name, api_name_preference):
    """Set up the audio input device."""
    global sound_in_id, sound_in_chs, sound_in_samplerate, testmode
    
    print("\nScanning for audio input devices...")
    
    try:
        # Print all available input devices
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"  {i}: {device['name']} | Ch: {device['max_input_channels']} | SR: {device['default_samplerate']} Hz")
        
        # Find a suitable device (using first available input device for simplicity)
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                sound_in_id = i
                sound_in_samplerate = int(device['default_samplerate'])
                
                # Make sure we have a valid channel count
                if device['max_input_channels'] < sound_in_chs:
                    print(f"Warning: Device only supports {device['max_input_channels']} channels, adjusting from {sound_in_chs}")
                    sound_in_chs = device['max_input_channels']
                
                print(f"\nSelected device: {device['name']}")
                print(f"  Device ID: {sound_in_id}")
                print(f"  Sample Rate: {sound_in_samplerate} Hz")
                print(f"  Channels: {sound_in_chs}")
                
                if sound_in_samplerate < 192000:
                    if sound_in_samplerate < 48000:
                        print("Running in test mode with reduced sample rate.")
                        testmode = True
                    else:
                        testmode = False
                else:
                    testmode = False
                
                return True
        
        print("No suitable input device found.")
        return False
        
    except Exception as e:
        print(f"Error during device selection: {e}")
        return False

# Add setup_audio_circular_buffer function
def setup_audio_circular_buffer():
    """Set up the circular buffer for audio recording."""
    global buffer_size, buffer, buffer_index, buffer_wrap, blocksize, buffer_wrap_event
    
    print("\nInitializing audio buffer...")
    
    # Create a buffer to hold the audio data
    buffer_size = int(BUFFER_SECONDS * sound_in_samplerate)
    buffer = np.zeros((buffer_size, sound_in_chs), dtype=_dtype)
    buffer_index = 0
    buffer_wrap = False
    blocksize = 8196  # Standard block size for audio processing
    buffer_wrap_event = threading.Event()
    
    print(f"Buffer created: {BUFFER_SECONDS} seconds, {buffer.size/1000000:.2f} MB")
    
    # Additional buffer settings could be added here
    return True

def plot_and_save_fft(sound_in_samplerate, channel):
    """Periodically record audio, analyze it with FFT, and save the plots."""
    global stop_fft_periodic_plot_event

    interval = FFT_INTERVAL * 60    # convert to seconds, time between ffts
    N = sound_in_samplerate * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)

    stop_fft_periodic_plot_event = threading.Event()

    while not stop_fft_periodic_plot_event.is_set():
        # Record audio
        print(f"Recording audio for auto fft in {FFT_INTERVAL} minutes...")
        # Wait for the desired time interval before recording and plotting again
        time.sleep(interval)
        if stop_fft_periodic_plot_event.is_set():
            break
            
        myrecording = sd.rec(int(N), samplerate=sound_in_samplerate, channels=channel + 1)
        sd.wait()  # Wait until recording is finished
        myrecording *= gain
        print("Recording auto fft finished.")

        # Perform FFT
        yf = rfft(myrecording.flatten())
        xf = rfftfreq(N, 1 / sound_in_samplerate)

        # Define bucket width
        bucket_width = FFT_BW  # Hz
        bucket_size = int(bucket_width * N / sound_in_samplerate)  # Number of indices per bucket

        # Average buckets
        buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
        bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

        # Plot results
        plt.figure()
        plt.plot(bucket_freqs, np.abs(buckets))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT Plot monitoring ch: ' + str(channel + 1) + ' of ' + str(sound_in_chs) + ' channels')
        plt.grid(True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Save plot to disk with a unique filename based on current time
        output_filename = f"{timestamp}_fft_{sound_in_samplerate/1000:.0F}_{config.PRIMARY_BITDEPTH}_{channel}_{config.LOCATION_ID}_{config.HIVE_ID}.png"
        full_path_name = os.path.join(PLOT_DIRECTORY, output_filename)
        plt.savefig(full_path_name)
        plt.close()

    print("Exiting fft periodic plotting")

def callback(indata, frames, time, status):
    """Callback function for the audio stream to handle incoming audio data."""
    global buffer, buffer_index, buffer_wrap_event
    
    if status:
        print("Callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    data_len = len(indata)

    # Managing the circular buffer
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
    """Set up and start the audio input stream and recording threads."""
    global stop_program, sound_in_id, sound_in_chs, sound_in_samplerate, _dtype, testmode, blocksize

    print("Starting audio stream...")
    stream = sd.InputStream(
        device=sound_in_id, 
        channels=sound_in_chs, 
        samplerate=sound_in_samplerate, 
        dtype=_dtype, 
        blocksize=blocksize, 
        callback=callback
    )

    with stream:
        # Start the recording worker threads
        # NOTE: these threads will run until the program is stopped
        if config.MODE_AUDIO_MONITOR:
            print("Starting recording worker thread for downsampling audio to 48k and saving mp3...")
            threading.Thread(
                target=recording_worker_thread, 
                args=(
                    config.AUDIO_MONITOR_RECORD, 
                    config.AUDIO_MONITOR_INTERVAL, 
                    "Audio_monitor", 
                    config.AUDIO_MONITOR_FORMAT, 
                    config.AUDIO_MONITOR_SAMPLERATE, 
                    config.AUDIO_MONITOR_START, 
                    config.AUDIO_MONITOR_END
                )
            ).start()

        if config.MODE_PERIOD and not testmode:
            print("Starting recording worker thread for saving period audio at primary sample rate...")
            threading.Thread(
                target=recording_worker_thread, 
                args=(
                    config.PERIOD_RECORD, 
                    config.PERIOD_INTERVAL, 
                    "Period_recording", 
                    config.PRIMARY_FILE_FORMAT, 
                    sound_in_samplerate, 
                    config.PERIOD_START, 
                    config.PERIOD_END
                )
            ).start()

        # Main loop to keep the stream active
        while stream.active and not stop_program[0]:
            time.sleep(1)
        
        stream.stop()
        print("Stopped audio stream")

# Simplify the main function to focus on testing toggle_listening
def main():
    global fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel, sound_in_id, sound_in_chs, MICS_ACTIVE, keyboard_listener_running
    global PYNPUT_AVAILABLE, keyboard  # Added global declaration at beginning of function

    print("\n\nBeehive Multichannel Acoustic-Signal Recorder\n")
   
    # Check dependencies
    if not check_dependencies():
        print("\nWarning: Some required packages are missing or outdated.")
        print("The script may not function correctly.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Check for pynput and offer to install if needed
    if not PYNPUT_AVAILABLE:
        print("\nThe pynput package is recommended for better keyboard handling.")
        response = input("Would you like to install pynput now? (y/n): ")
        if response.lower() == 'y':
            try:
                print("Installing pynput...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pynput"])
                print("pynput installed successfully! Restarting the program is recommended.")
                # Try to reload the module
                try:
                    # global declaration moved to top of function
                    from pynput import keyboard
                    PYNPUT_AVAILABLE = True
                    print("pynput loaded successfully!")
                except ImportError:
                    print("pynput installed but not loaded. Please restart the program.")
            except Exception as e:
                print(f"Failed to install pynput: {e}")
    
    print(f"Saving data to: {PRIMARY_DIRECTORY}\n")

    # Try to set up the input device
    if not set_input_device(config.MODEL_NAME, config.API_NAME):
        print("\nExiting due to no suitable audio input device found.")
        sys.exit(1)

    setup_audio_circular_buffer()

    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/500000:.2f} megabytes")
    print(f"Sample Rate: {sound_in_samplerate}; File Format: {config.PRIMARY_FILE_FORMAT}; Channels: {sound_in_chs}")

    # Check and create required directories
    required_directories = [PRIMARY_DIRECTORY, MONITOR_DIRECTORY, PLOT_DIRECTORY]
    
    # Print directories for verification
    print("\nDirectory setup:")
    print(f"  Primary recordings: {PRIMARY_DIRECTORY}")
    print(f"  Monitor recordings: {MONITOR_DIRECTORY}")
    print(f"  Plot files: {PLOT_DIRECTORY}")
    
    # Ensure all required directories exist
    if not ensure_directories_exist(required_directories):
        print("\nCritical directories could not be created. Exiting.")
        sys.exit(1)

    # Create and start the process
    if config.MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft, args=(sound_in_samplerate, monitor_channel,)) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")

    # Register cleanup handler before starting any threads
    atexit.register(cleanup)
    
    # Setup terminal for keyboard input
    print("\nPreparing keyboard input system...", flush=True)
    
    if PYNPUT_AVAILABLE:
        print("Using pynput for direct keyboard input (no terminal configuration needed)", flush=True)
    else:
        # Only need to set up terminal if not using pynput
        try:
            # Reset terminal to known good state, then set to raw mode
            if platform_manager.is_macos():
                # First reset to normal mode
                os.system('stty sane')
                # Then disable echo and switch to raw mode directly
                os.system('stty -echo raw -isig -icanon')
                print("Terminal set to raw mode")
        except Exception as e:
            print(f"Error setting terminal mode: {e}")
    
    print("Keyboard setup complete. Press 'h' for help (no need to press Enter).", flush=True)
    
    try:
        if KB_or_CP == 'KB':
            # Start keyboard listener thread
            print("Starting keyboard listener...", flush=True)
            keyboard_thread = threading.Thread(target=keyboard_listener, name="KeyboardListenerThread")
            keyboard_thread.daemon = True
            keyboard_thread.start()
            print("Keyboard listener started")
            
        # Start the audio stream
        audio_stream()
            
    except KeyboardInterrupt:
        print('\nCtrl-C: Recording process stopped by user.')
        cleanup()

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        cleanup()

if __name__ == "__main__":
    main()
