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
import sys
import platform
import select
import os

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
        else:
            self._os_info = f"{platform.system()} {platform.release()}"
        
        return self._os_info
    
    def initialize(self):
        if not self._initialized:
            print(f"\nDetected operating system: {self.get_os_info()}\n")
            
            if sys.platform == 'win32' and not self.is_wsl():
                import msvcrt
                self._msvcrt = msvcrt
                print("Using Windows keyboard handling (msvcrt)")
                self._keyboard_info = "Windows"
            else:
                self._msvcrt = None
                print("Using Linux keyboard handling")
                self._keyboard_info = "Linux"
    
    @property
    def msvcrt(self):
        return self._msvcrt

# Create global platform manager instance
platform_manager = PlatformManager()

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
                import msvcrt
                if msvcrt.kbhit():
                    return msvcrt.getch().decode('utf-8')
                return None
            else:
                # Only try termios on non-Windows platforms
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
        except Exception as e:
            if "termios" in str(e):
                # If termios fails, try alternative method
                try:
                    import msvcrt
                    if msvcrt.kbhit():
                        return msvcrt.getch().decode('utf-8')
                except:
                    pass
            return None

# Initialize platform at startup
platform_manager.initialize()

##os.environ['NUMBA_NUM_THREADS'] = '1'
#import keyboard
from sshkeyboard import listen_keyboard
import curses
import atexit
#import msvcrt
import signal
import sys
import io
import warnings
import queue
import librosa
import librosa.display
import resampy
import atexit

##import TestPyQT5

import BMAR_config as config

lock = threading.Lock()

# Ignore this specific warning
warnings.filterwarnings("ignore", category=UserWarning)

def reset_terminal():
    """Reset terminal settings to default state."""
    try:
        import termios
        import tty
        import sys
        import os
        
        # Reset terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, termios.tcgetattr(sys.stdin))
        
        # Reset terminal modes
        os.system('stty sane')
        
        # Clear screen and reset cursor
        print('\033[2J\033[H', end='')
        
        # Reset keyboard mode
        os.system('stty -raw -echo')
        
        # Flush stdout to ensure all output is displayed
        sys.stdout.flush()
        
    except Exception as e:
        print(f"Warning: Could not reset terminal: {e}")
        # Try alternative reset method
        try:
            os.system('reset')
        except:
            pass

def signal_handler(sig, frame):
    print('\nStopping all threads...')
    reset_terminal()  # Reset terminal before stopping
    stop_all()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

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

# to be discovered from sounddevice.query_devices()
sound_in_id = 1                             # id of input device, set as default in case none is detected
sound_in_chs = config.SOUND_IN_CHS          # number of input channels
sound_in_samplerate = config.PRIMARY_SAMPLERATE    # sample rate of input device

sound_out_id = config.SOUND_OUT_ID_DEFAULT
sound_out_chs = config.SOUND_OUT_CHS_DEFAULT                        
sound_out_samplerate = config.SOUND_OUT_SR_DEFAULT    

PRIMARY_DIRECTORY = f"{config.data_drive}/{config.data_directory}/{config.LOCATION_ID}/{config.HIVE_ID}/recordings/{current_year}{current_month}_primary/"
MONITOR_DIRECTORY = f"{config.data_drive}/{config.data_directory}/{config.LOCATION_ID}/recordings/{current_year}{current_month}_monitor/"
PLOT_DIRECTORY = f"{config.data_drive}/{config.data_directory}/{config.LOCATION_ID}/plots/{current_year}{current_month}/"

testmode = False                            # True = run in test mode with lower than needed sample rate
KB_or_CP = 'KB'                             # use keyboard or control panel (PyQT5) to control program

##########################  
# setup utilities
##########################

def get_api_name_for_device(device_id):
    device = sd.query_devices(device_id)
    hostapi_info = sd.query_hostapis(index=device['hostapi'])
    return hostapi_info['name']

# find the device id that matches the model name and hostapi name
def set_input_device(model_name, api_name):
    global sound_in_id, sound_in_chs, testmode, sound_in_samplerate

    print("\nScanning for audio input devices...")
    sys.stdout.flush()

    try:
        # Get list of all devices
        devices = sd.query_devices()
        input_devices = []
        
        # First, list all available input devices
        print("\nAvailable input devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append((i, device))
                print(f"  {i}: {device['name']} ({device['max_input_channels']} input channels)")
                print(f"     Default Sample Rate: {device['default_samplerate']} Hz")
                # Try to get supported sample rates
                try:
                    device_info = sd.query_devices(i, 'input')
                    if 'default_samplerate' in device_info:
                        print(f"     Supported Sample Rate: {device_info['default_samplerate']} Hz")
                except:
                    pass
        sys.stdout.flush()

        if not input_devices:
            print("\nNo input devices found! Please check your audio device connections.")
            print("Make sure your microphone or audio interface is properly connected and enabled.")
            print("\nTroubleshooting steps:")
            print("1. Check if your microphone is properly connected")
            print("2. Make sure it's enabled in Windows sound settings")
            print("3. Check if it's set as the default input device")
            print("4. Try unplugging and replugging the microphone")
            print("5. Check if the microphone works in other applications (like Windows Voice Recorder)")
            sys.stdout.flush()
            return False

        # Try to find a device that matches our model name
        print(f"\nLooking for preferred device models: {model_name}")
        sys.stdout.flush()
        
        for device_id, device in input_devices:
            for model in model_name:
                if model.lower() in device['name'].lower():
                    if device['max_input_channels'] >= sound_in_chs:
                        sound_in_id = device_id
                        # Force the sample rate to 192000 Hz
                        sound_in_samplerate = 192000
                        print(f"\nFound preferred device: {device['name']}")
                        print(f"Using {sound_in_chs} channel(s) at {sound_in_samplerate} Hz")
                        print(f"Device's default sample rate: {device['default_samplerate']} Hz")
                        print(f"Setting sample rate to: {sound_in_samplerate} Hz")
                        sys.stdout.flush()
                        return True
                    else:
                        print(f"Device {device['name']} doesn't support enough channels (needs {sound_in_chs}, has {device['max_input_channels']})")
                        sys.stdout.flush()

        # If no preferred device found, use the first available input device
        print("\nNo preferred device found, using first available input device")
        sys.stdout.flush()
        
        device_id, device = input_devices[0]
        sound_in_id = device_id
        # Force the sample rate to 192000 Hz
        sound_in_samplerate = 192000
        
        # If the device has fewer channels than requested, adjust our channel count
        if device['max_input_channels'] < sound_in_chs:
            print(f"\nWarning: Device only supports {device['max_input_channels']} channels, adjusting channel count")
            sound_in_chs = device['max_input_channels']
        
        print(f"\nUsing device: {device['name']}")
        print(f"Using {sound_in_chs} channel(s) at {sound_in_samplerate} Hz")
        print(f"Device's default sample rate: {device['default_samplerate']} Hz")
        print(f"Setting sample rate to: {sound_in_samplerate} Hz")
        
        if sound_in_samplerate < 192000:
            print("\nWarning: Device sample rate is lower than required")
            print("Running in test mode with reduced sample rate")
            testmode = True
        
        sys.stdout.flush()
        return True

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
    if sys.platform == 'win32' and not platform_manager.is_wsl() and platform_manager.msvcrt is not None:
        try:
            while platform_manager.msvcrt.kbhit():
                platform_manager.msvcrt.getch()
        except Exception as e:
            print(f"Warning: Could not clear input buffer: {e}")
    else:
        # For Linux/WSL, we could implement alternative methods if needed
        pass


def show_audio_device_info_for_SOUND_IN_OUT():
    """Display detailed information about the selected audio input and output devices."""
    print("\nSelected Audio Device Information:")
    print("-" * 50)
    
    # Get and display input device info
    try:
        input_info = sd.query_devices(sound_in_id)
        print("\nInput Device:")
        print(f"Name: {input_info['name']}")
        print(f"Default Sample Rate: {input_info['default_samplerate']} Hz")
        print(f"Max Input Channels: {input_info['max_input_channels']}")
        print(f"Current Sample Rate: {sound_in_samplerate} Hz")
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
        print(f"Name: {output_info['name']}")
        print(f"Default Sample Rate: {output_info['default_samplerate']} Hz")
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
    print(f"\nDefault Input Device: {default_input_info}")
    print(f"Default Output Device: {default_output_info}\n")


def show_audio_device_list():
    SOUND_OUT_ID_DEFAULT = get_default_output_device()
    print()
    print(sd.query_devices())
    show_audio_device_info_for_defaults()
    print(f"\nCurrent device in: {sound_in_id}, device out: {SOUND_OUT_ID_DEFAULT}\n")
    show_audio_device_info_for_SOUND_IN_OUT()


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
    matching_files = [os.path.join(directory, f) for f in os.listdir(directory) \
                      if os.path.isfile(os.path.join(directory, f)) and f.endswith(f".{file_type.lower()}")]
    if offset < len(matching_files):
        return matching_files[offset]
    # else:
    return None

# return the most recent audio file in the directory minus offset (next most recent, etc.)
def find_file_of_type_with_offset(offset, directory=PRIMARY_DIRECTORY, file_type=config.PRIMARY_FILE_FORMAT):
    # List all files of the specified type in the directory
    files_of_type = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.endswith(f".{file_type.lower()}")]
    # Sort files alphabetically
    files_of_type.sort(reverse=True)
    if files_of_type:
        return files_of_type[offset]
    else:
        return None


def time_between():
    # Using a list to store the last called time because lists are mutable and can be modified inside the nested function.
    # This will act like a "nonlocal" variable.
    last_called = [None]
    
    def helper():
        current_time = time.time()
        
        # If the function has never been called before, set last_called to the current time and return 0.
        if last_called[0] is None:
            last_called[0] = current_time
            return 0
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

# single-shot plot of 'n' seconds of audio of each channels for an oscope view
def plot_oscope(sound_in_samplerate, sound_in_id, sound_in_chs): 
    # Record audio
    print("Recording audio for o-scope traces for channel count of", sound_in_chs)
    o_recording = sd.rec(int(sound_in_samplerate * TRACE_DURATION), samplerate=sound_in_samplerate, channels=sound_in_chs, device=sound_in_id)
    sd.wait()  # Wait until recording is finished
    print("Recording oscope finished.")

    if OSCOPE_GAIN_DB > 0:
        gain = 10 ** (OSCOPE_GAIN_DB / 20)      
        print(f"applying gain of: {gain:.1f}") 
        o_recording *= gain

    plt.figure(figsize=(10, 3 * sound_in_chs))
    # Plot number of channels
    for i in range(sound_in_chs):
        plt.subplot(sound_in_chs, 1, i+1)
        plt.plot(o_recording[:, i])
        plt.title(f"Oscilloscope Traces w/{OSCOPE_GAIN_DB}dB Gain--Ch{i+1}")
        plt.ylim(-1.0, 1.0)
    plt.tight_layout()
    plt.show()


# Add near the top with other global variables
active_processes = {
    'v': None,
    'o': None,
    's': None
}

def cleanup_process(command):
    """Clean up a specific command's process."""
    if active_processes[command] is not None:
        if active_processes[command].is_alive():
            active_processes[command].terminate()
            active_processes[command].join(timeout=1)
            if active_processes[command].is_alive():
                active_processes[command].kill()
        active_processes[command] = None

def trigger_oscope():
    cleanup_process('o')  # Clean up any existing process
    clear_input_buffer()
    active_processes['o'] = multiprocessing.Process(target=plot_oscope, args=(sound_in_samplerate, sound_in_id, sound_in_chs))
    active_processes['o'].start()
    clear_input_buffer()  
    active_processes['o'].join()
    cleanup_process('o')
    print("exit oscope")

# single-shot fft plot of audio
def plot_fft(sound_in_samplerate, sound_in_id, sound_in_chs, channel):

    N = sound_in_samplerate * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)
    # Record audio
    print("Recording audio for fft one shot on channel:", channel+1)
    all_channels_audio = sd.rec(int(N), samplerate=sound_in_samplerate, channels=sound_in_chs, device=sound_in_id)
    sd.wait()  # Wait until recording is finished
    single_channel_audio = all_channels_audio[:, channel]
    single_channel_audio *= gain
    print("Recording fft finished.")

    # Perform FFT
    yf = rfft(single_channel_audio.flatten())
    xf = rfftfreq(N, 1 / sound_in_samplerate)

    # Define bucket width
    bucket_width = FFT_BW  # Hz
    bucket_size = int(bucket_width * N / sound_in_samplerate)  # Number of indices per bucket

    # Average buckets
    buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
    bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

    # Plot results
    plt.plot(bucket_freqs, np.abs(buckets))
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude')
    plt.title('FFT Plot monitoring ch: ' + str(channel + 1) + ' of ' + str(sound_in_chs) + ' channels')
    plt.grid(True)
    plt.show()


def trigger_fft():
    one_shot_fft_proc = multiprocessing.Process(target=plot_fft, args=(sound_in_samplerate, sound_in_id, sound_in_chs, monitor_channel))
    one_shot_fft_proc.start()
    clear_input_buffer()        
    one_shot_fft_proc.join()
    print("exit fft")

# one-shot spectrogram plot of audio in a separate process
def plot_spectrogram(channel, y_axis_type, file_offset):
    """
    Generate a spectrogram from an audio file and display/save it as an image.
    Parameters:
    - audio_path: Path to the audio file (FLAC format).
    - output_image_path: Path to save the spectrogram image.
    - y_axis_type: Type of Y axis for the spectrogram. Can be 'log' or 'linear'.
    - y_decimal_places: Number of decimal places for the Y axis (note: preset in statements below).
    - channel: Channel to use for multi-channel audio files (default is 0 for left channel).

    - in librosa.load() function, sr=None means no resampling, mono=True means all channels are averaged into mono
    """
    next_spectrogram = find_file_of_type_with_offset(file_offset) 
    ##print("preparing spectrogram of:", next_spectrogram)

    if next_spectrogram == None:
        print("No data available to see?")
        return
    else: 
        full_audio_path = PRIMARY_DIRECTORY + next_spectrogram    # quick hack to eval code
        print("Spectrogram source:", full_audio_path)

    # Load the audio file (only up to 300 seconds or the end of the file, whichever is shorter)
    y, sr = librosa.load(full_audio_path, sr=sound_in_samplerate, duration=config.PERIOD_RECORD, mono=False)
    # If multi-channel audio, select the specified channel
    if len(y.shape) > 1: y = y[channel]
    # Compute the spectrogram
    D = librosa.amplitude_to_db(abs(librosa.stft(y)), ref=np.max)
    # Plot the spectrogram
    plt.figure(figsize=(10, 4))

    if y_axis_type == 'log':
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
        y_decimal_places = 3
    elif y_axis_type == 'lin':
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='linear')
        y_decimal_places = 0
    else:
        raise ValueError("y_axis_type must be 'log' or 'linear'")
    
    # Adjust y-ticks to be in kilohertz and have the specified number of decimal places
    y_ticks = plt.gca().get_yticks()
    plt.gca().set_yticklabels(['{:.{}f} kHz'.format(tick/1000, y_decimal_places) for tick in y_ticks])
    
    # Extract filename from the audio path
    filename = os.path.basename(full_audio_path)
    root, _ = os.path.splitext(filename)
    plotname = PLOT_DIRECTORY + root + '_spectrogram' + '.png'

    # Set title to include filename and channel
    plt.title(f'Spectrogram from {config.LOCATION_ID}, hive:{config.HIVE_ID}, Mic Loc:{config.MIC_LOCATION[channel]}\nfile:{filename}, Ch:{channel+1}')
    plt.colorbar(format='%+2.0f dB')
    plt.tight_layout()
    print("\nSaving spectrogram to:", plotname)
    plt.savefig(plotname, dpi=150)
    plt.show()


def trigger_spectrogram():
    cleanup_process('s')  # Clean up any existing process
    global file_offset, monitor_channel, time_diff

    diff = time_diff()       # time since last file was read
    if diff < (config.PERIOD_RECORD + config.PERIOD_INTERVAL):
        file_offset +=1
    else:
        file_offset = 1 
    active_processes['s'] = multiprocessing.Process(target=plot_spectrogram, args=(monitor_channel, 'lin', file_offset-1))
    active_processes['s'].start()
    print("Plotting spectrogram...")
    clear_input_buffer()
    active_processes['s'].join()
    cleanup_process('s')
    print("exit spectrogram")
    
# called from a thread
# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
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

def vu_meter(sound_in_id, sound_in_samplerate, sound_in_chs, channel, stop_vu_queue, asterisks):
    buffer = np.zeros((sound_in_samplerate,))
    last_print = ""

    def callback_input(indata, frames, time, status):
        nonlocal last_print
        # Only process audio from the designated channel
        channel_data = indata[:, channel]
        buffer[:frames] = channel_data

        audio_level = np.max(np.abs(channel_data))
        normalized_value = int((audio_level / 1.0) * 50)  

        asterisks.value = '*' * normalized_value
        current_print = ' ' * 11 + asterisks.value.ljust(50, ' ')
        
        # Only print if the value has changed
        if current_print != last_print:
            print(current_print, end='\r')
            last_print = current_print

    try:
        # In WSL, we need to use different stream parameters
        if platform_manager.is_wsl():
            # Check audio configuration first
            if not check_wsl_audio():
                raise Exception("Audio configuration check failed")
            
            # Try with minimal configuration
            try:
                with sd.InputStream(callback=callback_input,
                                  device=None,  # Use system default
                                  channels=1,   # Use mono
                                  samplerate=44100,  # Use standard rate
                                  blocksize=1024,    # Use smaller block size
                                  latency='low'):    # Use low latency
                    while not stop_vu_queue.get():
                        sd.sleep(0.1)
            except Exception as e:
                print(f"\nError with default configuration: {e}")
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
                raise
        else:
            # Windows behavior remains unchanged
            with sd.InputStream(callback=callback_input,
                              device=sound_in_id,
                              channels=sound_in_chs,
                              samplerate=sound_in_samplerate):
                while not stop_vu_queue.get():
                    sd.sleep(0.1)
    except Exception as e:
        print(f"\nError in VU meter: {e}")
    finally:
        print("\nStopping VU meter...")

def toggle_vu_meter():
    global vu_proc, monitor_channel, asterisks, stop_vu_queue

    if vu_proc is None:
        cleanup_process('v')  # Clean up any existing process
        print("\nVU meter monitoring channel:", monitor_channel+1)
        vu_manager = multiprocessing.Manager()
        stop_vu_queue = multiprocessing.Queue()
        asterisks = vu_manager.Value(str, '*' * 50)

        # Print initial state once
        print("fullscale:", asterisks.value.ljust(50, ' '))

        if config.MODE_EVENT:
            normalized_value = int(config.EVENT_THRESHOLD / 1000)
            asterisks.value = '*' * normalized_value
            print("threshold:", asterisks.value.ljust(50, ' '))
            
        vu_proc = multiprocessing.Process(target=vu_meter, args=(sound_in_id, sound_in_samplerate, sound_in_chs, monitor_channel, stop_vu_queue, asterisks))
        active_processes['v'] = vu_proc
        vu_proc.start()
    else:
        stop_vu()

def stop_vu():
    global vu_proc, stop_vu_event, stop_vu_queue

    if vu_proc is not None:
        stop_vu_event.set()
        stop_vu_queue.put(True)
        if vu_proc.is_alive():
            vu_proc.join()            # make sure its stopped, hate zombies
            print("\nvu stopped")
        vu_proc = None
        cleanup_process('v')
        clear_input_buffer()

#
# ############ intercom using multiprocessing #############
#

def intercom_m_downsampled(sound_in_id, sound_in_samplerate, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel):

    # Create a buffer to hold the audio data
    buffer_size = sound_in_samplerate // 4      # For 48,000 samples per second
    buffer = np.zeros((buffer_size,))
    channel = monitor_channel

    # Callback function to handle audio input
    def callback_input(indata, frames, time, status):
        # Only process audio from the designated channel
        channel_data = indata[:, channel]
        # Downsample the audio using resampy
        downsampled_data = resampy.resample(channel_data, sound_in_samplerate, 44100)
        buffer[:len(downsampled_data)] = downsampled_data

    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        # Play back the audio from the buffer
        outdata[:, 0] = buffer[:frames]         # Play back on the first channel
        ##outdata[:, 1] = buffer[:frames]         # Play back on the second channel

    # Open an input stream and an output stream with the callback function
    with sd.InputStream(callback=callback_input, device=sound_in_id, channels=sound_in_chs, samplerate=sound_in_samplerate), \
        sd.OutputStream(callback=callback_output, device=sound_out_id, channels=sound_out_chs, samplerate=sound_out_samplerate): 
        # The streams are now open and the callback function will be called every time there is audio input and output
        while not stop_intercom_event.is_set():
            sd.sleep(1)
        print("Stopping intercom...")


def intercom_m(sound_in_id, sound_in_samplerate, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel):

    # Create a buffer to hold the audio data
    buffer = np.zeros((sound_in_samplerate,))
    channel = monitor_channel

    # Callback function to handle audio input
    def callback_input(indata, frames, time, status):
        # Only process audio from the designated channel
        channel_data = indata[:, channel]
        buffer[:frames] = channel_data

    # Callback function to handle audio output
    def callback_output(outdata, frames, time, status):
        # Play back the audio from the buffer
        outdata[:, 0] = buffer[:frames]  # Play back on the first channel
        outdata[:, 1] = buffer[:frames]  # Play back on the second channel

    # Open an input stream and an output stream with the callback function
    ##with sd.InputStream(callback=callback_input, device=SOUND_IN, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE), \
    with sd.InputStream(callback=callback_input, device=sound_in_id, channels=sound_in_chs, samplerate=sound_in_samplerate), \
        sd.OutputStream(callback=callback_output, device=sound_out_id, channels=sound_out_chs, samplerate=sound_out_samplerate):  
        # The streams are now open and the callback function will be called every time there is audio input and output
        # In Windows, output is set to the soundmapper output (device=3) which bypasses the ADC/DAC encoder device.
        while not stop_intercom_event.is_set():
            sd.sleep(1)
        print("Stopping intercom...")


# mothballed, hanging around for reference
def stop_intercom_m():
    global intercom_proc, stop_intercom_event

    if intercom_proc is not None:
        stop_intercom_event.set()
        intercom_proc.terminate()
        intercom_proc.join()            # make sure its stopped, hate zombies


def toggle_intercom_m():
    global intercom_proc, sound_in_id, sound_in_samplerate, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel

    if intercom_proc is None:
        print("Starting intercom on channel:", monitor_channel + 1)
        ##intercom_proc = multiprocessing.Process(target=intercom_m_downsampled, args=(sound_in_id, sound_in_samplerate, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel))
        intercom_proc = multiprocessing.Process(target=intercom_m, args=(sound_in_id, sound_in_samplerate, sound_in_chs, sound_out_id, sound_out_samplerate, sound_out_chs, monitor_channel))
        intercom_proc.start()
    else:
        stop_intercom_m()
        print("\nIntercom stopped")
        intercom_proc = None

#
# Function to switch the channel being monitored
#

def change_monitor_channel():
    global monitor_channel, change_ch_event
    # usage: press m then press 1, 2, 3, 4
    print(f"\nChannel {monitor_channel+1} is active, {sound_in_chs} are available: select a channel (0 to quit): ") #, end='\r')
    while True:
        while platform_manager.msvcrt.kbhit():
            key = platform_manager.msvcrt.getch().decode('utf-8')
            # Clear the input buffer:
            while platform_manager.msvcrt.kbhit(): 
                platform_manager.msvcrt.getch() 
            if key.isdigit():
                if int(key) == 0:
                    print("exiting channel change\n")
                    return
                else:
                    key_int = int(key) - 1
                if (is_mic_position_in_bounds(MICS_ACTIVE, key_int)):
                    monitor_channel = key_int
                    change_ch_event.set()                         
                    print(f"Now monitoring: {monitor_channel+1}")
                    if intercom_proc is not None:
                        toggle_intercom_m()
                        time.sleep(0.1)
                        toggle_intercom_m()
                    if vu_proc is not None:
                        toggle_vu_meter()
                        time.sleep(0.1)
                        toggle_vu_meter()
                else:
                    print(f"Sound device has only {sound_in_chs} channel(s)")
 
            if key == chr(27):       # escape
                print("exiting monitor channel selection")
                return

        time.sleep(1)

#
# continuous fft plot of audio in a separate background process
#

def plot_and_save_fft(sound_in_samplerate, channel):

    interval = FFT_INTERVAL * 60    # convert to seconds, time betwwen ffts
    N = sound_in_samplerate * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)

    while not stop_fft_periodic_plot_event.is_set():
        # Record audio
        print(f"Recording audio for auto fft in {FFT_INTERVAL} minutes...")
        # Wait for the desired time interval before recording and plotting again
        interruptable_sleep(interval, stop_fft_periodic_plot_event)
            
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
        plt.plot(bucket_freqs, np.abs(buckets))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT Plot monitoring ch: ' + str(channel + 1) + ' of ' + str(sound_in_chs) + ' channels')

        plt.grid(True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Save plot to disk with a unique filename based on current time
        output_filename = f"{timestamp}_fft_{sound_in_samplerate/1000:.0F}_{PRIMARY_BITDEPTH}_{channel}_{config.LOCATION_ID}_{config.HIVE_ID}.png"
        full_path_name = os.path.join(PLOT_DIRECTORY, output_filename)
        plt.savefig(full_path_name)

    print("Exiting fft periodic")

#
# #############################################################
# audio stream & callback functions
# ############################################################
#

def reset_terminal_settings():
    """Reset terminal settings to ensure proper output formatting."""
    if not platform_manager.is_wsl():
        return
        
    try:
        import termios
        import tty
        import sys
        
        # Get current terminal settings
        old_settings = termios.tcgetattr(sys.stdin)
        
        # Set terminal to raw mode temporarily
        tty.setraw(sys.stdin.fileno())
        
        # Reset terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        
        # Reset terminal modes
        os.system('stty sane')
        
        # Clear screen and reset cursor
        print('\033[2J\033[H', end='')
        
        # Reset keyboard mode
        os.system('stty -raw -echo')
        
        # Flush stdout
        sys.stdout.flush()
        
    except Exception as e:
        print(f"Warning: Could not reset terminal settings: {e}")

def setup_audio_circular_buffer():
    """Set up the circular buffer for audio recording."""
    global buffer_size, buffer, buffer_index, buffer_wrap, blocksize, buffer_wrap_event

    # Create a buffer to hold the audio data
    buffer_size = int(BUFFER_SECONDS * sound_in_samplerate)
    buffer = np.zeros((buffer_size, sound_in_chs), dtype=_dtype)
    buffer_index = 0
    buffer_wrap = False
    blocksize = 8196
    buffer_wrap_event = threading.Event()
    print(f"\naudio buffer size: {sys.getsizeof(buffer)}\n")
    sys.stdout.flush()

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
    global stop_program, sound_in_id, sound_in_chs, sound_in_samplerate, _dtype, testmode

    # Reset terminal settings before printing
    reset_terminal_settings()

    # Print initialization info
    print("\nInitializing audio stream...")
    print(f"Device ID: {sound_in_id}")
    print(f"Channels: {sound_in_chs}")
    print(f"Sample Rate: {sound_in_samplerate}")
    print(f"Data Type: {_dtype}")
    sys.stdout.flush()

    try:
        # First verify the device configuration
        device_info = sd.query_devices(sound_in_id)
        print("\nSelected device info:")
        print(f"Name: {device_info['name']}")
        print(f"Max Input Channels: {device_info['max_input_channels']}")
        print(f"Default Sample Rate: {device_info['default_samplerate']} Hz")
        print(f"Target Sample Rate: {sound_in_samplerate} Hz")
        sys.stdout.flush()

        if device_info['max_input_channels'] < sound_in_chs:
            raise RuntimeError(f"Device only supports {device_info['max_input_channels']} channels, but {sound_in_chs} channels are required")

        # Initialize the stream with explicit channel count and sample rate
        stream = sd.InputStream(
            device=sound_in_id,
            channels=sound_in_chs,
            samplerate=sound_in_samplerate,  # Force 192000 Hz
            dtype=_dtype,
            blocksize=blocksize,
            callback=callback
        )

        print("\nAudio stream initialized successfully")
        print(f"Actual stream sample rate: {stream.samplerate} Hz")
        sys.stdout.flush()

        with stream:
            # start the recording worker threads
            if config.MODE_AUDIO_MONITOR:
                print("Starting recording_worker_thread for down sampling audio to 48k and saving mp3...")
                sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=(config.AUDIO_MONITOR_RECORD, config.AUDIO_MONITOR_INTERVAL, "Audio_monitor", config.AUDIO_MONITOR_FORMAT, config.AUDIO_MONITOR_SAMPLERATE, config.AUDIO_MONITOR_START, config.AUDIO_MONITOR_END)).start()

            if config.MODE_PERIOD and not testmode:
                print("Starting recording_worker_thread for saving period audio at primary sample rate and all channels...")
                sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=(config.PERIOD_RECORD, config.PERIOD_INTERVAL, "Period_recording", config.PRIMARY_FILE_FORMAT, sound_in_samplerate, config.PERIOD_START, config.PERIOD_END)).start()

            if config.MODE_EVENT and not testmode:
                print("Starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
                sys.stdout.flush()
                threading.Thread(target=recording_worker_thread, args=(config.SAVE_BEFORE_EVENT, config.SAVE_AFTER_EVENT, "Event_recording", config.PRIMARY_FILE_FORMAT, sound_in_samplerate, config.EVENT_START, config.EVENT_END)).start()

            while stream.active and not stop_program[0]:
                time.sleep(1)
            
            stream.stop()
            print("Audio stream stopped")
            sys.stdout.flush()

    except Exception as e:
        print(f"\nError initializing audio stream: {str(e)}")
        print("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        raise


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
    """Stop the keyboard listener and restore terminal settings."""
    global keyboard_listener_running
    keyboard_listener_running = False
    
    # Force terminal reset
    os.system('stty sane')
    os.system('stty -raw -echo')
    
    # Clear any pending input
    import termios
    import tty
    import sys
    try:
        # Get current terminal settings
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
    
    # Final terminal reset
    os.system('reset')

def keyboard_listener():
    """Main keyboard listener loop."""
    global keyboard_listener_running, keyboard_listener_active
    
    print("\nKeyboard listener started. Press 'h' for help.")
    
    while keyboard_listener_running:
        try:
            key = get_key()
            if key is not None:
                if key == "^":  # Tilda key
                    toggle_listening()
                elif keyboard_listener_active:
                    if key == "a": 
                        check_stream_status(10)
                    elif key == "c":  
                        change_monitor_channel()
                    elif key == "d":  
                        show_audio_device_list()
                    elif key == "f":  
                        trigger_fft()
                    elif key == "i":  
                        toggle_intercom_m()
                    elif key == "m":  
                        show_mic_locations()
                    elif key == "o":  
                        trigger_oscope()        
                    elif key == "q":  
                        print("\nQuitting...")
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
            print(f"Error in keyboard listener: {e}")
            keyboard_listener_running = False
            break
            
        time.sleep(0.01)  # Small delay to prevent high CPU usage

def show_list_of_commands():
    print("\na  audio pathway--check for over/underflows")
    print("c  channel--select channel to monitor, either before or during use of vu or intercom, '0' to exit")
    print("d  device list--show list of devices")
    print("f  fft--show plot")
    print("i  intercom: press i then press 1, 2, 3, ... to listen to that channel")
    print("m  mic--show active positions")
    print("o  oscilloscope--show trace of each active channel")
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
        'resampy': '0.4.2'
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
        else:
            print("For Windows:")
            print("1. Download ffmpeg from https://www.gyan.dev/ffmpeg/builds/")
            print("2. Extract the zip file")
            print("3. Add the bin folder to your system PATH")
            print("   (e.g., add 'C:\\ffmpeg\\bin' to your PATH environment variable)")
    
    if not missing_packages and not outdated_packages and not missing_system_deps:
        print("\nAll required packages and dependencies are installed and up to date!\n")
    
    return len(missing_packages) == 0 and len(outdated_packages) == 0 and len(missing_system_deps) == 0

def main():
    global fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel, sound_in_id, sound_in_chs, MICS_ACTIVE, keyboard_listener_running

    print("\n\nBeehive Multichannel Acoustic-Signal Recorder\n")
    sys.stdout.flush()
    
    # Check dependencies
    if not check_dependencies():
        print("\nWarning: Some required packages are missing or outdated.")
        print("The script may not function correctly.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    print(f"Saving data to: {PRIMARY_DIRECTORY}\n")
    sys.stdout.flush()

    # Try to set up the input device
    if not set_input_device(config.MODEL_NAME, config.API_NAME):
        print("\nExiting due to no suitable audio input device found.")
        sys.exit(1)

    setup_audio_circular_buffer()

    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/500000:.2f} megabytes")
    sys.stdout.flush()
    print(f"Sample Rate: {sound_in_samplerate}; File Format: { config.PRIMARY_FILE_FORMAT}; Channels: {sound_in_chs}")
    sys.stdout.flush()

    # Create the output directory if it doesn't exist
    try:
        os.makedirs(PRIMARY_DIRECTORY, exist_ok=True)
        os.makedirs(MONITOR_DIRECTORY, exist_ok=True)
        os.makedirs(PLOT_DIRECTORY, exist_ok=True)
    except Exception as e:
        print(f"An error occurred while trying to make or find output directory: {e}")
        sys.stdout.flush()
        sys.exit(1)

    # Create and start the process
    if config.MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft, args=(sound_in_samplerate, monitor_channel,)) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")
        sys.stdout.flush()

    # Register cleanup handler before starting any threads
    atexit.register(cleanup)

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
        sys.stdout.flush()
        cleanup()

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        sys.stdout.flush()
        cleanup()

def stop_all():
    """Stop all processes and threads."""
    global stop_program, stop_recording_event, stop_fft_periodic_plot_event, fft_periodic_plot_proc, keyboard_listener_running
    print("\nStopping all processes...")
    sys.stdout.flush()
    
    # Set all stop events
    stop_program[0] = True
    stop_recording_event.set()
    stop_fft_periodic_plot_event.set()
    stop_vu_event.set()
    stop_intercom_event.set()
    stop_tod_event.set()
    keyboard_listener_running = False

    # Clean up all active processes
    for command in active_processes:
        cleanup_process(command)

    # Stop the FFT periodic plot process
    if fft_periodic_plot_proc is not None and fft_periodic_plot_proc.is_alive():
        print("Stopping FFT periodic plot process...")
        fft_periodic_plot_proc.terminate()
        fft_periodic_plot_proc.join(timeout=2)
        if fft_periodic_plot_proc.is_alive():
            fft_periodic_plot_proc.kill()
        print("FFT periodic plot process stopped")

    # Stop VU meter
    stop_vu()

    # Stop intercom
    stop_intercom_m()

    # List and stop all worker threads
    print("\nStopping worker threads...")
    current_thread = threading.current_thread()
    for thread in threading.enumerate():
        if thread != threading.main_thread() and thread != current_thread:
            print(f"Stopping thread: {thread.name}")
            if thread.is_alive():
                try:
                    thread.join(timeout=1)
                except RuntimeError:
                    pass

    print("\nAll processes and threads stopped")
    sys.stdout.flush()

def cleanup():
    """Clean up and exit."""
    print("\nCleaning up...")
    sys.stdout.flush()
    
    try:
        stop_all()
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    # Give threads a moment to clean up
    time.sleep(0.5)
    
    # Force exit after cleanup
    print("Exiting...")
    sys.stdout.flush()
    os._exit(0)

if __name__ == "__main__":
    main()
