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
import os
##os.environ['NUMBA_NUM_THREADS'] = '1'
import keyboard
import atexit
import msvcrt
import signal
import sys
import warnings
import queue
import librosa
import librosa.display
##import TestPyQT5

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

# procs
vu_proc = None
stop_vu_queue = None
oscope_proc = None
intercom_proc = None
fft_periodic_plot_proc = None
one_shot_fft_proc = None  

# event flags

stop_recording_event = threading.Event()
stop_tod_event = threading.Event()
stop_vu_event = threading.Event()
stop_intercom_event = threading.Event()
stop_fft_periodic_plot_event = threading.Event()

trigger_oscope_event = threading.Event()
trigger_fft_event = threading.Event()
stop_worker_event = threading.Event()

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


# #############################################################
# #### Control Panel ##########################################
# #############################################################

# mode controls
MODE_AUDIO_MONITOR = True           # recording continuously to mp3 files
MODE_PERIOD = True                 # period recording
MODE_EVENT = False                  # event recording
MODE_FFT_PERIODIC_RECORD = True     # record fft periodically

KB_or_CP = 'KB'                    # use keyboard or control panel (PyQT5) to control program

# audio hardware config:
device_id = 0                               

if device_id == 0:                  # windows mme, 2 ch only
    SOUND_IN = 1                           
    SOUND_OUT = 3                          
    SOUND_CHS = 2            
elif device_id == 1:                # WASAPI: Scarlett 2ch
    SOUND_IN = 17                                              
    SOUND_OUT = 14                             
    SOUND_CHS = 2   
elif device_id == 2:                # WASAPI: Behringer 2ch
    SOUND_IN = 16                              
    SOUND_OUT = 14                         
    SOUND_CHS = 2                
elif device_id == 3:                # WASAPI: Behringer 4ch
    SOUND_IN = 16                              
    SOUND_OUT = 14                             
    SOUND_CHS = 4                
else:                               # default
    SOUND_IN = 1                              
    SOUND_OUT = 3                             
    SOUND_CHS = 2 

# audio parameters:
PRIMARY_SAMPLE_RATE = 192000                    # Audio sample rate
PRIMARY_BIT_DEPTH = 16                          # Audio bit depth
PRIMARY_FILE_FORMAT = "FLAC"                    # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

AUDIO_MONITOR_SAMPLE_RATE = 48000               # For continuous audio
AUDIO_MONITOR_BIT_DEPTH = 16                    # Audio bit depthv
AUDIO_MONITOR_CHANNELS = 2                      # Number of channels
AUDIO_MONITOR_QUALITY = 0                       # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
AUDIO_MONITOR_FORMAT = "MP3"                    # accepts mp3, flac, or wav

# recording types controls:
AUDIO_MONITOR_START = datetime.time(4, 0, 0)    # time of day to start recording hr, min, sec
AUDIO_MONITOR_END = datetime.time(23, 0, 0)     # time of day to stop recording hr, min, sec
AUDIO_MONITOR_RECORD = 1800                     # file size in seconds of continuous recording
AUDIO_MONITOR_INTERVAL = 0                      # seconds between recordings

PERIOD_START = datetime.time(4, 0, 0)
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = 300                             # seconds of recording
PERIOD_INTERVAL = 0                             # seconds between start of period, must be > period, of course

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                          # seconds to save before the event
SAVE_AFTER_EVENT = 30                           # seconds to save after the event
EVENT_THRESHOLD = 20000                         # audio level threshold to be considered an event
MONITOR_CH = 0                                  # channel to monitor for event (if > number of chs, all channels are monitored)
TRACE_DURATION = 10                            # seconds of audio to show on oscope
OSCOPE_GAIN_DB = 20                             # Gain in dB of audio level for oscope 

# instrumentation parms
FFT_BINS = 900                                  # number of bins for fft
FFT_BW = 1000                                   # bandwidth of each bucket in hertz
FFT_DURATION = 5                                # seconds of audio to show on fft
FFT_GAIN = 20                                   # gain in dB for fft
FFT_INTERVAL = 30                               # minutes between ffts

OSCOPE_DURATION = 10                            # seconds of audio to show on oscope
OSCOPE_GAIN = 20                                # gain in dB for oscope

FULL_SCALE = 2 ** 16                            # just for cli vu meter level reference
BUFFER_SECONDS = 1000                           # time length of circular buffer 

# translate human to machine
if PRIMARY_BIT_DEPTH == 16:
    _dtype = 'int16'
    _subtype = 'PCM_16'
elif PRIMARY_BIT_DEPTH == 24:
    _dtype = 'int24'
    _subtype = 'PCM_24'
elif PRIMARY_BIT_DEPTH == 32:
    _dtype = 'int32' 
    _subtype = 'PCM_32'
else:
    print("The bit depth is not supported: ", PRIMARY_BIT_DEPTH)
    quit(-1)

##SIGNAL_DIRECTORY = "."                        # for debugging
SIGNAL_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"
PLOT_DIRECTORY = "D:/OneDrive/data/Zeev/plots"

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"

output_image_path = "."
spectrogram_audio_path = os.path.join(SIGNAL_DIRECTORY, "test.flac")

# ==================================================================================================

##########################  
# misc utilities
##########################

# interruptable sleep
def sleep(seconds, stop_sleep_event):
    for i in range(seconds):
        if stop_sleep_event.is_set():
            return
        time.sleep(1)


# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()


def show_audio_device_info_for_SOUND_IN_OUT():
    device_info = sd.query_devices(SOUND_IN)  
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Input Channels: {}'.format(device_info['max_input_channels']))
    device_info = sd.query_devices(SOUND_OUT)  
    print('Default Sample Rate: {}'.format(device_info['default_samplerate']))
    print('Max Output Channels: {}'.format(device_info['max_output_channels']))
    print()
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
    print(f"\nCurrent device in: {SOUND_IN}, device out: {SOUND_OUT}\n")
    show_audio_device_info_for_SOUND_IN_OUT()


def find_file_of_type_with_offset(directory=SIGNAL_DIRECTORY, file_type=PRIMARY_FILE_FORMAT, offset=0):
    print("signal dir:", SIGNAL_DIRECTORY, "file type:", PRIMARY_FILE_FORMAT)
    matching_files = [file for file in os.listdir(directory) if file.endswith(f".{file_type}")]
    
    if offset < len(matching_files):
        print("spectrogram found:", matching_files[offset])
        return matching_files[offset]

    return None

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
        frame_rate=AUDIO_MONITOR_SAMPLE_RATE,
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
def plot_oscope(): 
    global monitor_channel

    # Convert gain from dB to linear scale
    gain = 10 ** (OSCOPE_GAIN_DB / 20)
    # Record audio
    print("Recording audio for oscope traces for ch count:", SOUND_CHS)
    o_recording = sd.rec(int(PRIMARY_SAMPLE_RATE * TRACE_DURATION), samplerate=PRIMARY_SAMPLE_RATE, channels=SOUND_CHS)
    sd.wait()  # Wait until recording is finished
    print("Recording oscope finished.")

    o_recording *= gain

    plt.figure()
    # Plot number of channels
    for i in range(SOUND_CHS):
        plt.subplot(2, 1, i + 1)
        plt.plot(o_recording[:, i])
        plt.title(f"Channel {i + 1}")
        plt.ylim(-0.5, 0.5)

    plt.tight_layout()
    plt.show()


# single-shot fft plot of audio
def plot_fft():
    global monitor_channel

    N = PRIMARY_SAMPLE_RATE * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)
    # Record audio
    print("Recording audio for fft one shot...")
    myrecording = sd.rec(int(N), samplerate=PRIMARY_SAMPLE_RATE, channels=monitor_channel + 1)
    sd.wait()  # Wait until recording is finished
    myrecording *= gain
    print("Recording fft finished.")
    # Perform FFT
    yf = rfft(myrecording.flatten())
    xf = rfftfreq(N, 1 / PRIMARY_SAMPLE_RATE)

    # Define bucket width
    bucket_width = FFT_BW  # Hz
    bucket_size = int(bucket_width * N / PRIMARY_SAMPLE_RATE)  # Number of indices per bucket

    # Average buckets
    buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
    bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

    # Plot results
    plt.plot(bucket_freqs, np.abs(buckets))
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Amplitude')
    plt.title('FFT Plot monitoring ch: ' + str(monitor_channel + 1) + ' of ' + str(SOUND_CHS) + ' channels')
    plt.grid(True)
    plt.show()


# one-shot spectrogram plot of audio in a separate process
def plot_spectrogram(audio_path=spectrogram_audio_path, output_image_path=output_image_path, y_axis_type='log', y_decimal_places=2):
    
    print("find file:",find_file_of_type_with_offset())
    # Load the audio file (only up to 300 seconds or the end of the file, whichever is shorter)
    y, sr = librosa.load(audio_path, sr=None, duration=120)
    
    # Compute the spectrogram
    D = librosa.amplitude_to_db(abs(librosa.stft(y)), ref=np.max)
    
    # Plot the spectrogram
    plt.figure(figsize=(10, 4))
    
    if y_axis_type == 'log':
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
    elif y_axis_type == 'lin':
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='linear')
    else:
        raise ValueError("y_axis_type must be 'log' or 'linear'")
    
    # Adjust y-ticks to be in kilohertz and have the specified number of decimal places
    y_ticks = plt.gca().get_yticks()
    plt.gca().set_yticklabels(['{:.{}f} kHz'.format(tick/1000, y_decimal_places) for tick in y_ticks])
    
    plt.colorbar(format='%+2.0f dB')
    plt.title('Spectrogram')
    plt.tight_layout()
    ##plt.savefig(output_image_path, dpi=300)
    plt.show()


# continuous fft plot of audio in a separate background process
def plot_and_save_fft():
    global monitor_channel, stop_fft_periodic_plot_event, fft_periodic_plot_proc

    interval = FFT_INTERVAL * 60    # convert to seconds, time betwwen ffts
    N = PRIMARY_SAMPLE_RATE * FFT_DURATION  # Number of samples
    # Convert gain from dB to linear scale
    gain = 10 ** (FFT_GAIN / 20)

    while not stop_fft_periodic_plot_event.is_set():
        # Record audio
        print(f"Recording audio for auto fft in {FFT_INTERVAL} minutes...")
        # Wait for the desired time interval before recording and plotting again
        sleep(interval, stop_fft_periodic_plot_event)
            
        myrecording = sd.rec(int(N), samplerate=PRIMARY_SAMPLE_RATE, channels=monitor_channel + 1)
        sd.wait()  # Wait until recording is finished
        myrecording *= gain
        print("Recording auto fft finished.")

        # Perform FFT
        yf = rfft(myrecording.flatten())
        xf = rfftfreq(N, 1 / PRIMARY_SAMPLE_RATE)

        # Define bucket width
        bucket_width = FFT_BW  # Hz
        bucket_size = int(bucket_width * N / PRIMARY_SAMPLE_RATE)  # Number of indices per bucket

        # Average buckets
        buckets = np.array([yf[i:i + bucket_size].mean() for i in range(0, len(yf), bucket_size)])
        bucket_freqs = np.array([xf[i:i + bucket_size].mean() for i in range(0, len(xf), bucket_size)])

        # Plot results
        plt.plot(bucket_freqs, np.abs(buckets))
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Amplitude')
        plt.title('FFT Plot monitoring ch: ' + str(monitor_channel + 1) + ' of ' + str(SOUND_CHS) + ' channels')

        plt.grid(True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Save plot to disk with a unique filename based on current time
        output_filename = f"{timestamp}_fft_{PRIMARY_SAMPLE_RATE/1000:.0F}_{PRIMARY_BIT_DEPTH}_{monitor_channel}_{LOCATION_ID}_{HIVE_ID}.png"
        full_path_name = os.path.join(PLOT_DIRECTORY, output_filename)
        plt.savefig(full_path_name)

    print("Exiting fft periodic")


# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
def vu_meter(stop_vu_queue, asterisks):
    global monitor_channel, device_ch

    buffer = np.zeros((PRIMARY_SAMPLE_RATE,))

    def callback_input(indata, frames, time, status):
        global monitor_channel
        # Only process audio from the designated channel
        channel_data = indata[:, monitor_channel]
        buffer[:frames] = channel_data

        audio_level = np.max(np.abs(channel_data))
        normalized_value = int((audio_level / 1.0) * 50)  

        asterisks.value = '*' * normalized_value
        ##print(f"Audio level: {audio_level}, Normalized value: {normalized_value}")
        print(asterisks.value.ljust(50, ' '), end='\r')

    with sd.InputStream(callback=callback_input, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE):
        while not stop_vu_queue.get():
            sd.sleep(0.1)
            ##pass
        print("Stopping vu...")


def stop_vu():
    global vu_proc, stop_vu_event, stop_vu_queue

    if vu_proc is not None:
        stop_vu_event.set()
        stop_vu_queue.put(True)
        vu_proc.join()            # make sure its stopped, hate zombies
        vu_proc = None
        clear_input_buffer()
        print("\nvu stopped")


def toggle_vu_meter():
    global vu_proc, monitor_channel, asterisks, stop_vu_queue

    if vu_proc is None:
        print("\nVU meter monitoring channel:", monitor_channel)
        vu_manager = multiprocessing.Manager()
        stop_vu_queue = multiprocessing.Queue()
        asterisks = vu_manager.Value(str, '*' * 50)
        print("fullscale:",asterisks.value.ljust(50, ' '))
        if MODE_EVENT:
            normalized_value = int(EVENT_THRESHOLD / 1000)
            asterisks.value = '*' * normalized_value
            print("threshold:",asterisks.value.ljust(50, ' '))

        vu_proc = multiprocessing.Process(target=vu_meter, args=(stop_vu_queue, asterisks))
        vu_proc.start()
    else:
        stop_vu()


def intercom():
    global monitor_channel

    # Create a buffer to hold the audio data
    buffer = np.zeros((PRIMARY_SAMPLE_RATE,))
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
    with sd.InputStream(callback=callback_input, device=SOUND_IN, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE), \
        sd.OutputStream(callback=callback_output, device=3, channels=2, samplerate=44100):  
        # The streams are now open and the callback function will be called every time there is audio input and output
        # In Windows, output is set to the soundmapper output (device=3) which bypasses the ADC/DAC encoder device.
        while not stop_intercom_event.is_set():
            sd.sleep(1)
        print("Stopping intercom...")


def stop_intercom():
    global intercom_proc, stop_intercom_event

    if intercom_proc is not None:
        stop_intercom_event.set()
        intercom_proc.terminate()
        intercom_proc.join()            # make sure its stopped, hate zombies


def toggle_intercom():
    global intercom_proc

    if intercom_proc is None:
        print("Starting intercom...")
        print("listening to channel 0",  end='\r')
        intercom_proc = multiprocessing.Process(target=intercom)
        intercom_proc.start()
    else:
        stop_intercom()
        print("\nIntercom stopped")
        intercom_proc = None

#
# #############################################################
# audio stream & callback functions
# ############################################################
#

# audio buffers and variables
buffer_size = int(BUFFER_SECONDS * PRIMARY_SAMPLE_RATE)
buffer = np.zeros((buffer_size, SOUND_CHS), dtype=_dtype)
buffer_index = 0
buffer_wrap = False
blocksize = 8196
buffer_wrap_event = threading.Event()

recording_start_index = None
thread_id = "Continuous"
period = 300
interval = 0
file_format = "FLAC"
record_start = None

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
        print(f"{thread_id} is reconding continuously")

    samplerate = PRIMARY_SAMPLE_RATE

    while not stop_recording_event.is_set():

        current_time = datetime.datetime.now().time()

        if start_tod is None or (start_tod <= current_time <= end_tod):        
            print(f"{thread_id} recording started at: {datetime.datetime.now()} for {record_period} sec, interval {interval} sec")

            period_start_index = buffer_index 
            # wait PERIOD seconds to accumulate audio
            sleep(record_period, stop_recording_event)

            period_end_index = buffer_index 
            ##print(f"Recording length in worker thread: {period_end_index - period_start_index}, after {record_period} seconds")
            save_start_index = period_start_index % buffer_size
            save_end_index = period_end_index % buffer_size

            # saving from a circular buffer so segments aren't necessarily contiguous
            if save_end_index > save_start_index:   # indexing is contiguous
                audio_data = buffer[save_start_index:save_end_index]
            else:                                   # ain't contiguous so concatenate to make it contiguous
                audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

            if target_sample_rate < PRIMARY_SAMPLE_RATE:
                # resample to lower sample rate
                audio_data = downsample_audio(audio_data, PRIMARY_SAMPLE_RATE, target_sample_rate)

            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            output_filename = f"{timestamp}_{thread_id}_{record_period}_{interval}_{LOCATION_ID}_{HIVE_ID}.{file_format.lower()}"
            full_path_name = os.path.join(SIGNAL_DIRECTORY, output_filename)

            if file_format.upper() == 'MP3':
                if target_sample_rate == 44100 or target_sample_rate == 48000:
                    pcm_to_mp3_write(audio_data, full_path_name)
                else:
                    print("mp3 only supports 44.1k and 48k sample rates")
                    quit(-1)
            else:
                sf.write(full_path_name, audio_data, target_sample_rate, format=file_format.upper())

            if not stop_recording_event.is_set():
                print(f"Saved {thread_id} audio to {full_path_name}, period: {record_period}, interval {interval} seconds")
            # wait "interval" seconds before starting recording again
            sleep(interval, stop_recording_event)


def callback(indata, frames, time, status):
    global buffer, buffer_index
    ##print("callback", indata.shape, frames, time, status)
    if status:
        print("Callback status:", status)

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
    global stop_program

    print("Start audio_stream...")
    stream = sd.InputStream(device=SOUND_IN, channels=SOUND_CHS, samplerate=PRIMARY_SAMPLE_RATE, dtype=_dtype, blocksize=blocksize, callback=callback)

    with stream:
        # start the recording worker threads
        # NOTE: these threads will run until the program is stopped, it will not stop when the stream is stopped
        # NOTE: replace <name>_START with None to disable time of day recording
        if MODE_AUDIO_MONITOR:
            print("starting recording_worker_thread for down sampling audio to 48k and saving mp3...")
            threading.Thread(target=recording_worker_thread, args=(AUDIO_MONITOR_RECORD, AUDIO_MONITOR_INTERVAL, "Audio_monitor", AUDIO_MONITOR_FORMAT, AUDIO_MONITOR_SAMPLE_RATE, AUDIO_MONITOR_START, AUDIO_MONITOR_END)).start()

        if MODE_PERIOD:
            print("starting recording_worker_thread for saving period audio at primary sample rate and all channels...")
            threading.Thread(target=recording_worker_thread, args=(PERIOD_RECORD, PERIOD_INTERVAL, "Period_recording", PRIMARY_FILE_FORMAT, PRIMARY_SAMPLE_RATE, PERIOD_START, PERIOD_END)).start()

        if MODE_EVENT:  # *** UNDER CONSTRUCTION, NOT READY FOR PRIME TIME ***
            print("starting recording_worker_thread for saving event audio at primary sample rate and trigger by event...")
            threading.Thread(target=recording_worker_thread, args=(SAVE_BEFORE_EVENT, SAVE_AFTER_EVENT, "Event_recording", PRIMARY_FILE_FORMAT, PRIMARY_SAMPLE_RATE, EVENT_START, EVENT_END)).start()

        while stream.active and not stop_program[0]:
            time.sleep(1)
        
        stream.stop()

        print("Stopped audio_stream...")


# #############################################################
# shutdown functions
# ############################################################


def list_all_threads():
    for thread in threading.enumerate():
        print(f"Thread name: {thread.name}, Thread ID: {thread.ident}, Alive: {thread.is_alive()}")


def clear_input_buffer():
    while msvcrt.kbhit():
        msvcrt.getch()


def stop_all():
    global stop_program, stop_recording_event, stop_fft_periodic_plot_event, fft_periodic_plot_proc, stop_intercom_event, stop_vu_event

    print("Signalling stop all processes...")
    print("\n\nStopping all threads...\n")

    stop_program[0] = True

    stop_recording_event.set()

    stop_fft_periodic_plot_event.set()
    if fft_periodic_plot_proc is not None:
        fft_periodic_plot_proc.join()

    stop_intercom()
    stop_vu()
    clear_input_buffer()

    for t in threading.enumerate():
        print("thread name:", t)

        if "recording_worker_thread" in t.name:
            if t.is_alive():
                stop_recording_event.set()
                t.join
                print("recording_worker_thread stopped ***")  

    list_all_threads()
    print("\nHopefully we have turned off all the lights...")


###########################
########## MAIN ###########
###########################


def main():
    global time_of_day_thread, fft_periodic_plot_proc, oscope_proc, one_shot_fft_proc, monitor_channel

    print("Acoustic Signal Capture\n")
    print(f"buffer size: {BUFFER_SECONDS} second, {buffer.size/1000000:.2f} megabytes")
    print(f"Sample Rate: {PRIMARY_SAMPLE_RATE}; File Format: {PRIMARY_FILE_FORMAT}; Channels: {SOUND_CHS}")
    
    # Check on input device parms or if input device even exits
    try:
        print("These are the available devices: \n")
        show_audio_device_list()
        device_info = sd.query_devices(SOUND_IN)  
        device_ch = device_info['max_input_channels'] 
        if SOUND_CHS > device_ch:
            print(f"The device only has {device_ch} channel(s) but requires {SOUND_CHS} channels.")
            print("These are the available devices: \n", sd.query_devices())
            quit(-1)

    except Exception as e:
        print(f"An error occurred while attempting to access the input device: {e}")
        quit(-1)

    # Create the output directory if it doesn't exist
    try:
        os.makedirs(SIGNAL_DIRECTORY, exist_ok=True)
        os.makedirs(PLOT_DIRECTORY, exist_ok=True)
    except Exception as e:
        print(f"An error occurred while trying to make or find output directory: {e}")
        quit(-1)

    # Create and start the process, note: using mp because matplotlib wants in be in the mainprocess threqad
    if MODE_FFT_PERIODIC_RECORD:
        fft_periodic_plot_proc = multiprocessing.Process(target=plot_and_save_fft) 
        fft_periodic_plot_proc.daemon = True  
        fft_periodic_plot_proc.start()
        print("started fft_periodic_plot_process")


    def trigger_oscope():
        oscope_proc = multiprocessing.Process(target=plot_oscope)
        oscope_proc.start()
        keyboard.write('\b')
        time.sleep(TRACE_DURATION + 3)
        input("Press any key to continue...")
        # oscope returns here when plot window is closed by user
        print("exit oscope")
        oscope_proc.terminate()
        oscope_proc.join()


    def trigger_fft():
        one_shot_fft_proc = multiprocessing.Process(target=plot_fft)
        one_shot_fft_proc.start()
        keyboard.write('\b')
        time.sleep(FFT_DURATION + 3)
        input("Press any key to continue...")
        # fft one shot returns here when plot window is closed by user
        ##print("one_shot_fft_proc.is_alive():", one_shot_fft_proc.is_alive())
        ##if one_shot_fft_proc.is_alive():
        one_shot_fft_proc.terminate()
        one_shot_fft_proc.join()
        print("exit fft")


    def trigger_spectrogram():
        one_shot_spectrogram_proc = multiprocessing.Process(target=plot_spectrogram)
        one_shot_spectrogram_proc.start()
        keyboard.write('\b')
        print("Plotting spectrogram...")
        time.sleep(30)
        input("Press any key to continue...")
        # spectrogram one shot returns here when plot window is closed by user
        ##print("one_shot_fft_proc.is_alive():", one_shot_fft_proc.is_alive())
        ##if one_shot_fft_proc.is_alive():
        one_shot_spectrogram_proc.terminate()
        one_shot_spectrogram_proc.join()
        print("exit spectrogram")


    # Function to switch the channel being listened to
    def change_monitor_channel():
        global monitor_channel

        ##keyboard.write('\b')  # backspace to erase the current keystroke on the cli
        print("\npress 'esc' to exit monitor channel selection")
        print(f"\nChannel {monitor_channel+1} is active, {SOUND_CHS} are available: select a channel:") #, end='\r')
        keyboard.write('\b')
        while True:
            while msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8')
                if key.isdigit():
                    key_int = int(key)
                    if key_int >= 1 and key_int <= SOUND_CHS:
                        monitor_channel = key_int - 1
                        print(f"Now monitoring: {monitor_channel+1}")
                    else:
                        print(f"Sound device has only {SOUND_CHS} channels")

                if key == '\x1b':       # escape
                    print("exiting monitor channel selection")
                    return
            time.sleep(1)

    try:
        if KB_or_CP == 'KB':

            # beehive keyboard triggered management utilities
            # one shot process to see fft
            keyboard.on_press_key("f", lambda _: trigger_fft(), suppress=True)   
            # one shot process to view oscope
            keyboard.on_press_key("o", lambda _: trigger_oscope(), suppress=True) 
            # usage: press s to plot spectrogram of last recording
            keyboard.on_press_key("s", lambda _: trigger_spectrogram(), suppress=True)            
            # one shot process to see device list
            keyboard.on_press_key("d", lambda _: show_audio_device_list(), suppress=True) 
            # usage: press i then press 0, 1, 2, or 3 to listen to that channel, press 'i' again to stop
            keyboard.on_press_key("i", lambda _: toggle_intercom(), suppress=True)
            # usage: press v to start cli vu meter, press v again to stop
            keyboard.on_press_key("v", lambda _: toggle_vu_meter(), suppress=True)
            # usage: press q to stop all processes
            keyboard.on_press_key("q", lambda _: stop_all(), suppress=True)
            # usage: press t to see all threads
            keyboard.on_press_key("t", lambda _: list_all_threads(), suppress=True)
            # usage: press m to select channel to monitor
            keyboard.on_press_key("m", lambda _: change_monitor_channel(), suppress=True)

        # Start the audio stream
        audio_stream()

        stop_all()

        if KB_or_CP == 'KB':
            # Unhook all hooks
            keyboard.unhook_all()
            clear_input_buffer()

        print("\nHopefully we have turned off all the lights...")
            
    except KeyboardInterrupt: # ctrl-c in windows
        print('\nCtrl-C: Recording process stopped by user.')
        stop_all()

    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1) 


if __name__ == "__main__":
    main()

