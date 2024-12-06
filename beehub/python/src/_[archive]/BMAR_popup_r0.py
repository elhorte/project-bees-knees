#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Code definition: 

# uses pop up menu windows for control in place of cli commands
# only value is pop up menu code, all other functions behind current rev

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

##os.environ['NUMBA_NUM_THREADS'] = '1'
import keyboard
import atexit
import msvcrt
import signal
import sys
import os
import io
import warnings
import queue
import librosa
import librosa.display
import resampy
##import TestPyQT5

import BMAR_config as config

lock = threading.Lock()

# Ignore this specific warning
warnings.filterwarnings("ignore", category=UserWarning)

def signal_handler(sig, frame):
    print('Stopping all threads...')
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
buffer_size = 0
buffer = None
buffer_index = 0
file_offset = 0

# #############################################################
# #### Control Panel ##########################################
# #############################################################

# audio parameters:
PRIMARY_SAMPLERATE = 192000                     # Audio sample rate
PRIMARY_BITDEPTH = 16                           # Audio bit depth
PRIMARY_FILE_FORMAT = "FLAC"                    # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

AUDIO_MONITOR_SAMPLERATE = 44100                # For continuous audio
AUDIO_MONITOR_BITDEPTH = 16                     # Audio bit depthv
AUDIO_MONITOR_CHANNELS = 2                      # Number of channels
AUDIO_MONITOR_QUALITY = 0                       # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
AUDIO_MONITOR_FORMAT = "MP3"                    # accepts mp3, flac, or wav

MONITOR_CH = 0                                  # channel to monitor for event (if > number of chs, all channels are monitored)
TRACE_DURATION = 10                             # seconds of audio to show on oscope
OSCOPE_GAIN_DB = 12                             # Gain in dB of audio level for oscope 

# instrumentation parms
FFT_BINS = 900                                  # number of bins for fft
FFT_BW = 1000                                   # bandwidth of each bucket in hertz
FFT_DURATION = 5                                # seconds of audio to show on fft
FFT_GAIN = 20                                   # gain in dB for fft
FFT_INTERVAL = 30                               # minutes between ffts

OSCOPE_DURATION = 10                            # seconds of audio to show on oscope
OSCOPE_GAIN_DB = 12                             # gain in dB for oscope

FULL_SCALE = 2 ** 16                            # just for cli vu meter level reference
BUFFER_SECONDS = 1000                           # time length of circular buffer 

# translate human to machine
if PRIMARY_BITDEPTH == 16:
    _dtype = 'int16'
    _subtype = 'PCM_16'
elif PRIMARY_BITDEPTH == 24:
    _dtype = 'int24'
    _subtype = 'PCM_24'
elif PRIMARY_BITDEPTH == 32:
    _dtype = 'int32' 
    _subtype = 'PCM_32'
else:
    print("The bit depth is not supported: ", PRIMARY_BITDEPTH)
    quit(-1)

# Date and time stuff for file naming
current_date = datetime.datetime.now()
current_year = current_date.strftime('%Y')
current_month = current_date.strftime('%m')
current_day = current_date.strftime('%d')

# to be discovered from sounddevice.query_devices()
sound_in_id = None                          # id of input device
sound_in_chs = config.SOUND_IN_CHS          # number of input channels
sound_in_samplerate = None                  # sample rate of input device

sound_out_id = config.SOUND_OUT_ID_DEFAULT
sound_out_chs = config.SOUND_OUT_CHS_DEFAULT                        
sound_out_samplerate = config.SOUND_OUT_SR_DEFAULT    

PRIMARY_DIRECTORY = f"{config.data_drive}/{config.data_directory}/{config.LOCATION_ID}/{config.HIVE_ID}/recordings/{current_year}{current_month}_primary/"
MONITOR_DIRECTORY = f"{config.data_drive}/{config.data_directory}/{config.LOCATION_ID}/recordings/{current_year}{current_month}_monitor/"
PLOT_DIRECTORY = f"{config.data_drive}/{config.data_directory}/{config.LOCATION_ID}/plots/{current_year}{current_month}/"

testmode = False                            # True to run in test mode with lower than neeeded sample rate
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

    # Purpose is to find connected audio device and set the sound_in_id
    # to the device that matches the MODEL_NAME and HOSTAPI_NAME
    # If no device is found, then it is set to any device that uses WASAPI (in Windows) 
    # and sets the sound_in_samplerate to the default sample rate of the device.
    # If the default device cannot manage 192k, then the system operated in the testmode.
    # The device_id is used to set the input device for the sounddevice module
    # and to set the input device for the pyaudio module.
    # Output device is unimportant and uses the default device.

    # Redirect stdout to a string buffer
    original_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    # Call the function that prints to stdout
    print(sd.query_devices())
    # Reset stdout to its original value
    sys.stdout = original_stdout
    # Get the string value from the buffer and split by lines to get the array
    devices_str = buffer.getvalue().splitlines()

    # loop through known MODEL_NAME
    for i in range(len(devices_str)):
        if (str(sound_in_chs)+" in" in devices_str[i] and api_name in devices_str[i]):
            print("Looking at device: ", devices_str[i])
            device = sd.query_devices(i)
            sound_in_id = i
            ##sound_in_chs = device['max_input_channels']
            sound_in_samplerate = int(device['default_samplerate'])
            try:    # found an input device and of type WASAPI, do we know about it?
                for j in range(len(model_name)):
                    if (model_name[j] in devices_str[i]):
                        print("Found device: ", devices_str[i])
                        time.sleep(3)      # in case a human is looking at the screen
                        return
            except:
                # if input device model not found, use default device
                if sound_in_samplerate < 192000:
                    print("Default device not fast enought to do the job.", sd.query_devices(i))
                    print("Caution: running in testmode with lower than needed sample rate")
                    testmode = True
                print(f"Known devices not found, using default {i}\n", sd.query_devices(i))
                
    # wlh - force sound in device parms
    ##sound_in_id = 16
    ##sound_in_chs = 4
    ##sound_in_samplerate = 192000



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
    while msvcrt.kbhit():
        msvcrt.getch()


def show_audio_device_info_for_SOUND_IN_OUT():
    device_info = sd.query_devices(sound_in_id)  
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Input Channels: {}'.format(device_info['max_input_channels']))
    device_info = sd.query_devices(sound_out_id)  
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Output Channels: {}'.format(device_info['max_output_channels']))
    print()


def show_audio_device_info_for_defaults():
    print("\nsounddevices default device info:")
    default_input_info = sd.query_devices(kind='input')
    default_output_info = sd.query_devices(kind='output')
    print(f"\nDefault Input Device: {default_input_info}")
    print(f"Default Output Device: {default_output_info}\n")


def show_audio_device_list():
    print(sd.query_devices())
    show_audio_device_info_for_defaults()
    print(f"\nCurrent device in: {sound_in_id}, device out: {SOUND_OUT_ID_DEFAULT}\n")
    show_audio_device_info_for_SOUND_IN_OUT()


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
def find_file_of_type_with_offset_1(directory=PRIMARY_DIRECTORY, file_type=PRIMARY_FILE_FORMAT, offset=0):
    matching_files = [os.path.join(directory, f) for f in os.listdir(directory) \
                      if os.path.isfile(os.path.join(directory, f)) and f.endswith(f".{file_type.lower()}")]
    if offset < len(matching_files):
        return matching_files[offset]
    # else:
    return None

# return the most recent audio file in the directory minus offset (next most recent, etc.)
def find_file_of_type_with_offset(offset, directory=PRIMARY_DIRECTORY, file_type=PRIMARY_FILE_FORMAT):
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

    int_array = np_array.astype(np.int16)
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=AUDIO_MONITOR_SAMPLERATE,
        channels=AUDIO_MONITOR_CHANNELS
    )
    if AUDIO_MONITOR_QUALITY >= 64 and AUDIO_MONITOR_QUALITY <= 320:    # use constant bitrate, 64k would be the min, 320k the best
        cbr = str(AUDIO_MONITOR_QUALITY) + "k"
        audio_segment.export(full_path, format="mp3", bitrate=cbr)
    elif AUDIO_MONITOR_QUALITY < 10:                      # use variable bitrate, 0 to 9, 0 is highest quality
        audio_segment.export(full_path, format="mp3", parameters=["-q:a", "0"])
    else:
        print("Don't know of a mp3 mode with parameter:", AUDIO_MONITOR_QUALITY)
        quit(-1)

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


def trigger_oscope():
    clear_input_buffer()
    oscope_proc = multiprocessing.Process(target=plot_oscope, args=(sound_in_samplerate, sound_in_id, sound_in_chs))
    oscope_proc.start()
    clear_input_buffer()  
    oscope_proc.join()
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
    global file_offset, monitor_channel, time_diff

    diff = time_diff()       # time since last file was read
    if diff < (config.PERIOD_RECORD + config.PERIOD_INTERVAL):
        file_offset +=1
    else:
        file_offset = 1 
    one_shot_spectrogram_proc = multiprocessing.Process(target=plot_spectrogram, args=(monitor_channel, 'lin', file_offset-1))
    one_shot_spectrogram_proc.start()
    print("Plotting spectrogram...")
    clear_input_buffer()
    one_shot_spectrogram_proc.join()
    print("exit spectrogram")
    
# called from a thread
# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
def vu_meter(sound_in_id, sound_in_samplerate, sound_in_chs, channel, stop_vu_queue, asterisks):

    buffer = np.zeros((sound_in_samplerate,))

    def callback_input(indata, frames, time, status):
        # Only process audio from the designated channel
        channel_data = indata[:, channel]
        buffer[:frames] = channel_data

        audio_level = np.max(np.abs(channel_data))
        normalized_value = int((audio_level / 1.0) * 50)  

        asterisks.value = '*' * normalized_value
        ##print(f"Audio level: {audio_level}, Normalized value: {normalized_value}")
        print(asterisks.value.ljust(50, ' '), end='\r')

    with sd.InputStream(callback=callback_input, device=sound_in_id, channels=sound_in_chs, samplerate=sound_in_samplerate):
        while not stop_vu_queue.get():
            sd.sleep(0.1)
            ##pass
        print("Stopping vu...")


def toggle_vu_meter():
    global vu_proc, monitor_channel, asterisks, stop_vu_queue

    if vu_proc is None:
        print("\nVU meter monitoring channel:", monitor_channel+1)
        vu_manager = multiprocessing.Manager()
        stop_vu_queue = multiprocessing.Queue()
        asterisks = vu_manager.Value(str, '*' * 50)
        print("fullscale:",asterisks.value.ljust(50, ' '))
        if config.MODE_EVENT:
            normalized_value = int(config.EVENT_THRESHOLD / 1000)
            asterisks.value = '*' * normalized_value
            print("threshold:",asterisks.value.ljust(50, ' '))
        vu_proc = multiprocessing.Process(target=vu_meter, args=(sound_in_id, sound_in_samplerate, sound_in_chs, monitor_channel, stop_vu_queue, asterisks))
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
    print(f"\nChannel {monitor_channel+1} is active, {sound_in_chs} are available: select a channel:") #, end='\r')

    while True:
        while msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8')
            if key.isdigit():
                key_int = int(key)
                if key_int >= 1 and key_int <= sound_in_chs:
                    monitor_channel = key_int - 1
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

                    return        
                else:
                    print(f"Sound device has only {sound_in_chs} channels")

            if key == '\x1b':       # escape
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

def setup_audio_circular_buffer():
    global buffer_size, buffer, buffer_index, buffer_wrap, buffer_wrap_event, blocksize

    # Create a buffer to hold the audio data
    buffer_size = int(BUFFER_SECONDS * sound_in_samplerate)
    buffer = np.zeros((buffer_size, sound_in_chs), dtype=_dtype)
    buffer_index = 0
    buffer_wrap = False
    blocksize = 8196
    buffer_wrap_event = threading.Event()

# 
# ### WORKER THREAD ########################################################
#

def recording_worker_thread(record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod):
    #
    # recording_period is the length of time to record in seconds
    # interval is the time between recordings in seconds if > 0
    # thread_id is a string to label the thread
    # file_format is the format in which to save the audio file
    # target_sample_rate is the sample rate in which to save the audio file
    # start_tod is the time of day to start recording, if 'None', record continuously
    # end_tod is the time of day to stop recording, if start_tod == None, ignore & record continuously
    #
    global buffer, buffer_size, buffer_index, stop_recording_event

    if start_tod is None:
        print(f"{thread_id} is recording continuously")

    samplerate = sound_in_samplerate

    while not stop_recording_event.is_set():

        current_time = datetime.datetime.now().time()

        if start_tod is None or (start_tod <= current_time <= end_tod):        
            print(f"{thread_id} recording started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec")

            period_start_index = buffer_index 
            # wait PERIOD seconds to accumulate audio
            interruptable_sleep(record_period, stop_recording_event)

            period_end_index = buffer_index 
            ##print(f"Recording length in worker thread: {period_end_index - period_start_index}, after {record_period} seconds")
            save_start_index = period_start_index % buffer_size
            save_end_index = period_end_index % buffer_size

            # saving from a circular buffer so segments aren't necessarily contiguous
            if save_end_index > save_start_index:   # indexing is contiguous
                audio_data = buffer[save_start_index:save_end_index]
            else:                                   # ain't contiguous so concatenate to make it contiguous
                audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

            if target_sample_rate < sound_in_samplerate:
                # resample to lower sample rate
                audio_data = downsample_audio(audio_data, sound_in_samplerate, target_sample_rate)

            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            output_filename = f"{timestamp}_{thread_id}_{record_period}_{interval}_{config.LOCATION_ID}_{config.HIVE_ID}.{file_format.lower()}"


            if file_format.upper() == 'MP3':
                if target_sample_rate == 44100 or target_sample_rate == 48000:
                    full_path_name = os.path.join(MONITOR_DIRECTORY, output_filename)
                    pcm_to_mp3_write(audio_data, full_path_name)
                else:
                    print("mp3 only supports 44.1k and 48k sample rates")
                    quit(-1)
            else:
                full_path_name = os.path.join(PRIMARY_DIRECTORY, output_filename)
                sf.write(full_path_name, audio_data, target_sample_rate, format=file_format.upper())

            if not stop_recording_event.is_set():
                print(f"Saved {thread_id} audio to {full_path_name}, period: {record_period}, interval {interval} seconds")
            # wait "interval" seconds before starting recording again
            interruptable_sleep(interval, stop_recording_event)


def callback(indata, frames, time, status):
    global buffer, buffer_index
    ##print("callback", indata.shape, frames, time, status)
    if status:
        print("Callback status:", status)
        if status.input_overflow:
            print("Sounddevice input overflow at:", datetime.datetime.now())

    data_len = len(indata)

    # managing the circular buffer
    print(f"buffer_index={buffer_index}, data_len={data_len}, buffer_size={buffer_size}\n")
    if buffer_index + data_len <= buffer_size:
        buffer[buffer_index:buffer_index + data_len] = indata
        buffer_wrap_event.clear()
    else:
        overflow = (buffer_index + data_len) - buffer_size
        buffer[buffer_index:] = indata[:-overflow]
        buffer[:overflow] = indata[-overflow:]
        buffer_wrap_event.set()

    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream(blocksize):
    global stop_program, sound_in_id, sound_in_chs, sound_in_samplerate, _dtype, testmode

    print("Start audio_stream...")
    stream = sd.InputStream(device=sound_in_id, channels=sound_in_chs, samplerate=sound_in_samplerate, dtype=_dtype, blocksize=blocksize, callback=callback)

    with stream:
        # start the recording worker threads
        # NOTE: these threads will run until the program is stopped, it will not stop when the stream is stopped
        # NOTE: replace <name>_START with None to disable time of day recording
        if config.MODE_AUDIO_MONITOR:
            print("starting recording_worker_thread for down sampling audio to 48k and saving mp3...")
            threading.Thread(target=recording_worker_thread, args=(config.AUDIO_MONITOR_RECORD, config.AUDIO_MONITOR_INTERVAL, "Audio_monitor", AUDIO_MONITOR_FORMAT, AUDIO_MONITOR_SAMPLERATE, config.AUDIO_MONITOR_START, config.AUDIO_MONITOR_END)).start()

        if config.MODE_PERIOD and not testmode:
            print("starting recording_worker_thread for saving period audio at primary sample rate and all channels...")
            threading.Thread(target=recording_worker_thread, args=(config.PERIOD_RECORD, config.PERIOD_INTERVAL, "Period_recording", PRIMARY_FILE_FORMAT, sound_in_samplerate, config.PERIOD_START, config.PERIOD_END)).start()

        if config.MODE_EVENT and not testmode:  # *** UNDER CONSTRUCTION, NOT READY FOR PRIME TIME ***
            print("starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
            threading.Thread(target=recording_worker_thread, args=(config.SAVE_BEFORE_EVENT, config.SAVE_AFTER_EVENT, "Event_recording", PRIMARY_FILE_FORMAT, sound_in_samplerate, config.EVENT_START, config.EVENT_END)).start()

        while stream.active and not stop_program[0]:
            time.sleep(1)
        
        stream.stop()

        print("Stopped audio_stream...")


def kill_worker_threads():
    for t in threading.enumerate():
        print("thread name:", t)

        if "recording_worker_thread" in t.name:
            if t.is_alive():
                stop_recording_event.set()
                t.join
                print("recording_worker_thread stopped ***")  


def stop_all():
    global stop_program, stop_recording_event, stop_fft_periodic_plot_event, fft_periodic_plot_proc

    if KB_or_CP == 'KB':
        # Unhook all hooks
        keyboard.unhook_all()
        print("Unhooked all keyboard hooks")

    stop_program[0] = True
    stop_recording_event.set()

    stop_fft_periodic_plot_event.set()
    if fft_periodic_plot_proc is not None:
        fft_periodic_plot_proc.join()
        print("fft_periodic_plot_proc stopped ***")

    stop_vu()
    stop_intercom_m()
    keyboard.write('\b') 
    clear_input_buffer()
    list_all_threads()

    print("\nHopefully we have turned off all the lights...")


###########################
########## MAIN ###########
###########################

from tkinter import *
import atexit

def cleanup():
    print("Cleaning up...")
    if fft_periodic_plot_proc.is_alive():
        fft_periodic_plot_proc.terminate()
    keyboard.unhook_all()

atexit.register(cleanup) 

def main():
    global fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel, sound_in_id, sound_in_chs

    blocksize = 8196

    print("Beehive Multichannel Acoustic-Signal Recorder\n")
    print(f"Saving data to: {PRIMARY_DIRECTORY}\n")

    set_input_device(config.MODEL_NAME, config.API_NAME)
    setup_audio_circular_buffer()

    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/1000000:.2f} megabytes")
    print(f"Sample Rate: {sound_in_samplerate}; File Format: {PRIMARY_FILE_FORMAT}; Channels: {sound_in_chs}")

    # Create the output directory if it doesn't exist
    try:
        os.makedirs(PRIMARY_DIRECTORY, exist_ok=True)
        os.makedirs(MONITOR_DIRECTORY, exist_ok=True)
        os.makedirs(PLOT_DIRECTORY, exist_ok=True)
    except Exception as e:
        print(f"An error occurred while trying to make or find output directory: {e}")
        quit(-1)

    # Create and start the process, note: using mp because matplotlib wants in be in the mainprocess threqad
    if config.MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft, args=(sound_in_samplerate, monitor_channel,)) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")
        
    try:
        if KB_or_CP == 'KB':
            # Function to create and show the popup menu
            def show_popup_menu(event=None):
                def execute_command(command):
                    if command == 'c':
                        check_stream_status(10)
                    elif command == 'd':
                        show_audio_device_list()
                    elif command == 'f':
                        trigger_fft()
                    elif command == 'i':
                        toggle_intercom_m()
                    elif command == 'm':
                        change_monitor_channel()
                    elif command == 'o':
                        trigger_oscope()
                    elif command == 'q':
                        stop_all()
                    elif command == 's':
                        trigger_spectrogram()
                    elif command == 't':
                        list_all_threads()
                    elif command == 'v':
                        toggle_vu_meter()
                    #popup.destroy()  # Close the popup after executing command

                popup = Tk()  
                popup.title("Beehive Commands")

                Button(popup, text="Check Stream Status (c)", command=lambda: execute_command('c')).pack(pady=5)
                Button(popup, text="Show Audio Device List (d)", command=lambda: execute_command('d')).pack(pady=5)
                Button(popup, text="Trigger FFT (f)", command=lambda: execute_command('f')).pack(pady=5)
                Button(popup, text="Toggle Intercom (i)", command=lambda: execute_command('i')).pack(pady=5)
                Button(popup, text="Change Monitor Channel (m)", command=lambda: execute_command('m')).pack(pady=5)
                Button(popup, text="Trigger Oscilloscope (o)", command=lambda: execute_command('o')).pack(pady=5)
                Button(popup, text="Stop All (q)", command=lambda: execute_command('q')).pack(pady=5)
                Button(popup, text="Trigger Spectrogram (s)", command=lambda: execute_command('s')).pack(pady=5)
                Button(popup, text="List All Threads (t)", command=lambda: execute_command('t')).pack(pady=5)
                Button(popup, text="Toggle VU Meter (v)", command=lambda: execute_command('v')).pack(pady=5)

                # Bind Enter key to close the popup
                popup.bind('<Return>', lambda event: execute_command(''))
                popup.mainloop()
           
            root = Tk()
            root.title("Beehive Main Window")                

            # Watch for the "ESC ESC" hotkey
            root.bind('0', show_popup_menu)

            # Start the audio stream in a separate thread
            #import threading
            #audio_thread = threading.Thread(target=audio_stream)
            #audio_thread.daemon = True  # Allow main thread to exit even if audio_thread is running
            #audio_thread.start()
            audio_process = multiprocessing.Process(target=audio_stream, args=(blocksize,))
            audio_process.daemon = True
            audio_process.start()

            root.mainloop()

    except KeyboardInterrupt:  # ctrl-c in windows
        print('\nCtrl-C: Recording process stopped by user.')
        cleanup()  # Call cleanup in case of KeyboardInterrupt

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1) 

if __name__ == "__main__":
    main()