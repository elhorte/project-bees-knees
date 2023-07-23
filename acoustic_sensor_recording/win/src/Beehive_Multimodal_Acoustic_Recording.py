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
from datetime import datetime
import time
import threading
import numpy as np
#from scipy.io import wavfile
#from scipy.io.wavfile import read as wavread
#import resampy
from scipy.signal import resample_poly
#from scipy import signal
from pydub import AudioSegment
import os
os.environ['NUMBA_NUM_THREADS'] = '1'
import librosa

FULL_SCALE = 2 ** 16            # just for cli vu meter level reference
THRESHOLD = 24000               # audio level threshold to be considered an event
BUFFER_SECONDS = 660            # seconds of a circular buffer
SAMPLE_RATE = 192000            # Audio sample rate
BIT_DEPTH = 16                  # Audio bit depth
CHANNELS = 2                    # Number of channels
FORMAT = 'FLAC'                 # 'WAV' or 'FLAC'INTERVAL = 0 # seconds between recordings

CONTINUOUS_SAMPLE_RATE = 48000  # For continuous audio
CONTINUOUS_BIT_DEPTH = 16       # Audio bit depth
CONTINUOUS_CHANNELS = 2         # Number of channels
CONTINUOUS_FORMAT = 'MP3'      # accepts mp3, flac, or wav
CONTINUOUS_QUALITY = 0          # for mp3 only: 0-9 sets vbr (0=best); 64-320 sets cbr in kbps
DEVICE_IN = 1                   # Device ID of input device
DEVICE_OUT = 3                  # Device ID of output device

OUTPUT_DIRECTORY = "."        # for debugging
##OUTPUT_DIRECTORY = "D:/OneDrive/data/Zeev/recordings"


#periodic & continuous recording timing
PERIOD = 300                    # seconds of recording
INTERVAL = 1800                 # seconds between start of period, must be > period, of course
CONTINUOUS = 10                # file size in seconds of continuous recording

# init continuous recording varibles
continuous_start_index = None
continuous_save_thread = None
continuous_end_index = 0        # so the next start = this end

# init period recording varibles
period_start_index = None
period_save_thread = None

# event capture recording
SAVE_BEFORE_EVENT = 30          # seconds to save before the event
SAVE_AFTER_EVENT = 30           # seconds to save after the event
MONITOR_CH = 0                  # channel to monitor for event (0 = left, 1 = right, else both)

# init event variables
event_start_index = None
event_save_thread = None
detected_level = None

_dtype = None                   # parms sd lib cares about
_subtype = None

# Op Mode & ID =====================================================================================
MODE_CONTINUOUS = True          # recording continuously to mp3 files
MODE_PERIOD = True              # period only
MODE_EVENT = False              # event only

LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1"
# ==================================================================================================

### startup housekeeping ###
def initialization():
    global buffer, buffer_index, _dtype, buffer_size, _subtype

    # Check on parms
    if (SAVE_BEFORE_EVENT + SAVE_AFTER_EVENT) * 1.2 > BUFFER_SECONDS:
        print("The buffer is not large enough to hold the maximum amount of audio that can be saved.")
        print("Reduce SAVE_DURATION_BEFORE and/or SAVE_DURATION_AFTER or increase the size of the circular buffer 'BUFFER_SECONDS'")
        quit(-1)

    if (PERIOD) * 1.1 > BUFFER_SECONDS:
        print("The buffer is not large enough to hold the maximum amount of audio that can be saved.")
        print("Reduce PERIOD or increase the size of the circular buffer 'BUFFER_SECONDS'")
        quit(-1)

    # Check on input device parms or if input device even exits
    try:
        device_info = sd.query_devices(DEVICE_IN)  
        device_CH = device_info['max_input_channels'] 
        if device_CH < CHANNELS:
            print(f"The device only has {device_CH} channel(s) but require {CHANNELS} channels.")
            quit(-1)
        ##device_SR = device_info['default_samplerate'] 
        ##if device_SR != SAMPLE_RATE:
        ##    print(f"The device sample rate {device_SR} is not equal to the required 'SAMPLE_RATE' of {SAMPLE_RATE}")
        ##    quit(-1)
    except Exception as e:
        print(f"An error occurred while attempting to access the input device: {e}")
        print("These are the available devices: \n", sd.query_devices())
        quit(-1)

    # Create the output directory if it doesn't exist
    try:
        os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    except Exception as e:
        print(f"An error occurred while trying to make or find output directory: {e}")
        quit(-1)

    # translate human to machine
    if BIT_DEPTH == 16:
        _dtype = 'int16'
        _subtype = 'PCM_16'
    elif BIT_DEPTH == 24:
        _dtype = 'int24'
        _subtype = 'PCM_24'
    elif BIT_DEPTH == 32:
        _dtype = 'int32' 
        _subtype = 'PCM_32'
    else:
        print("The bit depth is not supported: ", BIT_DEPTH)
        quit(-1)

    # audio buffers and variables
    buffer_size = int(BUFFER_SECONDS * SAMPLE_RATE)
    buffer = np.zeros((buffer_size, CHANNELS), dtype=_dtype)
    buffer_index = 0


# Print a string of asterisks, ending with only a carriage return to overwrite the line
# value (/1000) is the number of asterisks to print, end = '\r' or '\n' to overwrite or not
def fake_vu_meter(value, end):
    normalized_value = int(value / 1000)
    asterisks = '*' * normalized_value
    print(asterisks.ljust(50, ' '), end=end)


def get_level(audio_data, channel_select):
    if channel_select == 0 or channel_select == 1:
        audio_level = np.max(np.abs(audio_data[:,channel_select]))
    else: # both channels
        audio_level = np.max(np.abs(audio_data))

    return audio_level

#
# convert audio to mp3 and save to file
#
'''
def numpy_to_mp3(np_array, orig_sample_rate=192000, target_sample_rate=48000):

    int_array = np_array.astype(np.int16)
    int_array = int_array.T
    # Resample each channel
    resampled_array = np.array([
        resample_poly(ch, target_sample_rate, orig_sample_rate)
        for ch in int_array
    ])
    # Transpose the array back to the original shape and convert to bytes
    byte_array = resampled_array.T.astype(np.int16).tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=target_sample_rate,
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file with VBR
    audio_segment.export("output.mp3", format="mp3", parameters=["-q:a", "0"])
'''

import numpy as np
from scipy.signal import resample_poly
from pydub import AudioSegment

def numpy_to_mp3(np_array, orig_sample_rate=192000, target_sample_rate=48000):
    #np_array = np_array.T

    # Ensure the array is formatted as float64
    float_array = np_array.astype(np.float64)

    # Transpose the array to have channels as the first dimension
    float_array = float_array.T

    # Resample each channel
    resampled_array = np.array([
        resample_poly(ch, target_sample_rate, orig_sample_rate)
        for ch in float_array
    ])

    # Transpose the array back to the original shape and convert to int16
    int_array = resampled_array.T.astype(np.int16)

    # Convert the array to bytes
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=target_sample_rate,
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file with VBR
    audio_segment.export("output.mp3", format="mp3", parameters=["-q:a", "0"])



'''
def numpy_to_mp3(np_array, sample_rate, full_path, qty=CONTINUOUS_QUALITY):
    # Ensure the array is formatted as int16
    int_array = np_array.astype(np.int16)

    # Convert the array to bytes
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        data=byte_array,
        sample_width=2,
        frame_rate=sample_rate,
        channels=2
    )
    if qty >= 64 and qty <= 320:    # use constant bitrate, 64k would be the min, 320k the best
        cbr = str(qty) + "k"
        audio_segment.export(full_path, format="mp3", bitrate=cbr)
    elif qty < 10:                      # use variable bitrate, 0 to 9, 0 is highest quality
        audio_segment.export(full_path, format="mp3", parameters=["-q:a", str(qty)])
    else:
        print("Don't know of a mp3 mode with parameter:", qty)
        quit(-1)
'''
#
# continuous recording functions at low sample rate
#

def save_audio_for_continuous():
    time.sleep(CONTINUOUS)
    save_continuous_audio()


def save_continuous_audio():
    global buffer, continuous_start_index, continuous_save_thread, continuous_end_index

    if continuous_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = continuous_start_index % buffer_size
    save_end_index = (continuous_start_index + (CONTINUOUS * SAMPLE_RATE)) % buffer_size
    continuous_end_index = save_end_index

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    # assuming audio_data is stereo 16-bit PCM in a numpy array
    audio_data = audio_data.astype(np.float32)
    # transposing the audio_data
    audio_data = audio_data.T
    downsampled_data = np.zeros((audio_data.shape[0], int(audio_data.shape[1] * CONTINUOUS_SAMPLE_RATE / SAMPLE_RATE)))

    # apply resampling to each channel
    for ch in range(audio_data.shape[0]):
        downsampled_data[ch] = librosa.resample(audio_data[ch], orig_sr=SAMPLE_RATE, target_sr=CONTINUOUS_SAMPLE_RATE, res_type='kaiser_fast')

    # transposing the downsampled_data back
    downsampled_data = downsampled_data.T

    audio_data = downsampled_data.astype(np.int16)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}_continuous_{CONTINUOUS}_{LOCATION_ID}_{HIVE_ID}.{CONTINUOUS_FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)

    if CONTINUOUS_FORMAT == 'MP3':
        numpy_to_mp3(audio_data) 
    elif CONTINUOUS_FORMAT == 'FLAC' or CONTINUOUS_FORMAT == 'WAV': 
        sf.write(full_path_name, audio_data, CONTINUOUS_SAMPLE_RATE, format=CONTINUOUS_FORMAT, subtype=_subtype)
    else:
        print("don't know about file format:", CONTINUOUS_FORMAT)
        quit(-1)

    print(f"Saved continuous audio to {full_path_name}, block size: {CONTINUOUS} seconds")

    continuous_save_thread = None
    continuous_start_index = None


def check_continuous(audio_data, index):
    global continuous_start_index, continuous_save_thread, continuous_end_index

    audio_level = get_level(audio_data, MONITOR_CH)
    # just keep doing it, no testing
    if continuous_start_index is None: 
        print("continuous block started at:", datetime.now())
        continuous_start_index = continuous_end_index 
        continuous_save_thread = threading.Thread(target=save_audio_for_continuous)
        continuous_save_thread.start()

    if MODE_CONTINUOUS and not MODE_EVENT:
        fake_vu_meter(audio_level,'\r')

#
# period recording functions
#

def save_audio_for_period():
    time.sleep(PERIOD)
    save_period_audio()


def save_period_audio():
    global buffer, period_start_index, period_save_thread

    if period_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = period_start_index % buffer_size
    save_end_index = (period_start_index + (PERIOD * SAMPLE_RATE)) % buffer_size

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"{timestamp}_period_{PERIOD}_{INTERVAL}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved period audio to {full_path_name}, period: {PERIOD}, interval {INTERVAL} seconds")

    period_save_thread = None
    period_start_index = None


def check_period(audio_data, index):
    global period_start_index, period_save_thread, detected_level

    audio_level = get_level(audio_data, MONITOR_CH)

    ##print("Time:", int(time.time()),"INTERVAL:", INTERVAL, "modulo:", int(time.time()) % INTERVAL)
    # if modulo INTERVAL == zero then start of period
    if not int(time.time()) % INTERVAL and period_start_index is None: 
        print("period started at:", datetime.now(), "audio level:", audio_level)
        period_start_index = index 
        period_save_thread = threading.Thread(target=save_audio_for_period)
        period_save_thread.start()

    if not MODE_CONTINUOUS and not MODE_EVENT:
        fake_vu_meter(audio_level,'\r')

#
# event recording functions
#

def save_audio_around_event():
    time.sleep(SAVE_AFTER_EVENT)
    save_event_audio()


def save_event_audio():
    global buffer, event_start_index, event_save_thread, detected_level

    if event_start_index is None:  # if this has been reset already, don't try to save
        return

    save_start_index = (event_start_index - SAVE_BEFORE_EVENT * SAMPLE_RATE) % buffer_size
    save_end_index = (event_start_index + SAVE_AFTER_EVENT * SAMPLE_RATE) % buffer_size

    # saving from a circular buffer so segments aren't necessarily contiguous
    if save_end_index > save_start_index:   # is contiguous
        audio_data = buffer[save_start_index:save_end_index]
    else:                                   # ain't contiguous
        audio_data = np.concatenate((buffer[save_start_index:], buffer[:save_end_index]))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    threshold_tag = int(THRESHOLD/1000)
    output_filename = f"{timestamp}_event_{detected_level}_{SAVE_BEFORE_EVENT}_{SAVE_AFTER_EVENT}_{LOCATION_ID}_{HIVE_ID}.{FORMAT.lower()}"
    full_path_name = os.path.join(OUTPUT_DIRECTORY, output_filename)
    sf.write(full_path_name, audio_data, SAMPLE_RATE, format=FORMAT, subtype=_subtype)

    print(f"Saved evemt audio to {full_path_name}, audio threshold level: {detected_level}, duration: {audio_data.shape[0] / SAMPLE_RATE} seconds")

    event_save_thread = None
    event_start_index = None


def check_level(audio_data, index):
    global event_start_index, event_save_thread, detected_level

    audio_level = get_level(audio_data, MONITOR_CH)

    if (audio_level > THRESHOLD) and event_start_index is None:
        print("event detected at:", datetime.now(), "audio level:", audio_level)
        detected_level = audio_level
        event_start_index = index
        event_save_thread = threading.Thread(target=save_audio_around_event)
        event_save_thread.start()

    fake_vu_meter(audio_level,'\r') # no line feed

#
# audio stream and callback functions
#

def callback(indata, frames, time, status):
    global buffer, buffer_index

    if status:
        print("Callback status:", status)

    data_len = len(indata)
    # managing a circular buffer
    if buffer_index + data_len <= buffer_size:
        buffer[buffer_index:buffer_index + data_len] = indata
    else:
        overflow = (buffer_index + data_len) - buffer_size
        buffer[buffer_index:] = indata[:-overflow]
        buffer[:overflow] = indata[-overflow:]

    if MODE_EVENT:
        check_level(indata, buffer_index)   # trigger saving audio if above threshold, 
    if MODE_PERIOD:
        check_period(indata, buffer_index)  # start saving audio if save period expired
    if MODE_CONTINUOUS:
        check_continuous(indata, buffer_index)  # start saving audio if save period expired

    buffer_index = (buffer_index + data_len) % buffer_size


def audio_stream():
    global buffer, buffer_index, _dtype

    stream = sd.InputStream(device=DEVICE_IN, channels=CHANNELS, samplerate=SAMPLE_RATE, dtype=_dtype, callback=callback)
    with stream:
        print("Start recording...")
        print("Monitoring audio level on channel:", MONITOR_CH)
        fake_vu_meter(FULL_SCALE, '\n')  # mark max audio level on the CLI
        if MODE_EVENT:
            fake_vu_meter(THRESHOLD, '\n')  # mark audio event threshold on the CLI for ref

        while stream.active:
            pass


###########################
########## MAIN ###########
###########################

if __name__ == "__main__":

    initialization()

    print("Acoustic Signal Capture")
    print(f"Sample Rate: {SAMPLE_RATE}; File Format: {FORMAT}; Channels: {CHANNELS}")
    try:
        if MODE_CONTINUOUS:
            print("Starting continuous, low-sample-rate recording mode, duration per file:", CONTINUOUS)
        if MODE_PERIOD:
            print("Starting periodic recording mode, PERIOD every INTERVAL:", PERIOD, INTERVAL)
        if MODE_EVENT:
            print("Starting event detect mode, threshold trigger:", THRESHOLD)

        audio_stream()

    except KeyboardInterrupt:
        print('\nRecording process stopped by user.')
    except Exception as e:
        print(f"An error occurred while attempting to execute this script: {e}")
        quit(-1)         # quit with error


##########################  
# utilities
##########################

# for debugging
def play_audio(filename, device):
    print("* Playing back")
    data, fs = sf.read(filename)
    sd.play(data, fs, device)
    sd.wait()

'''
def numpy_to_mp3(np_array, sample_rate):
    # Ensure the array is formatted as int16
    int_array = np_array.astype(np.int16)

    # Convert the array to bytes
    byte_array = int_array.tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        # raw audio data (bytes)
        data=byte_array,
        # 2 byte (16 bit) samples
        sample_width=2,
        # 48000 frame rate
        frame_rate=sample_rate,
        # stereo audio
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file
    audio_segment.export("output.mp3", format="mp3")

'''
'''
import numpy as np
from scipy.signal import resample_poly
from pydub import AudioSegment

def numpy_to_mp3(np_array, orig_sample_rate, target_sample_rate, vbr_quality="2"):
    int_array = np_array.astype(np.int16)
    int_array = int_array.T
    # Resample each channel
    resampled_array = np.array([
        resample_poly(ch, target_sample_rate, orig_sample_rate)
        for ch in int_array
    ])
    # Transpose the array back to the original shape and convert to bytes
    byte_array = resampled_array.T.astype(np.int16).tobytes()

    # Create an AudioSegment instance from the byte array
    audio_segment = AudioSegment(
        # raw audio data (bytes)
        data=byte_array,

        # 2 byte (16 bit) samples
        sample_width=2,

        # target frame rate
        frame_rate=target_sample_rate,

        # stereo audio
        channels=2
    )

    # Export the AudioSegment instance as an MP3 file with VBR
    audio_segment.export("output.mp3", format="mp3", parameters=["-q:a", vbr_quality])
'''
# Usage example:
# Assume 'audio_data' is your original data
# audio_data = ...

##numpy_to_mp3(audio_data, orig_sample_rate=48000, target_sample_rate=44100, vbr_quality="2")

'''The actual MP3 conversion is performed by the LAME encoder. PyDub, the Python library you're using, provides a convenient and Pythonic interface to this process, but the heavy lifting is done by LAME itself.

Here's a brief explanation of the process:

1. PyDub takes the audio data and formats it into a form that can be understood by the LAME encoder. This includes converting the data into bytes and setting the appropriate sample width, frame rate, and number of channels.

2. PyDub calls the LAME encoder with the appropriate parameters, including the quality setting for Variable Bitrate (VBR) encoding.

3. LAME encodes the audio data into the MP3 format. This involves several steps, including quantization, Huffman coding, and adding MP3 headers and metadata.

4. The encoded MP3 data is then written to a file, which is what the `AudioSegment.export` function does in your Python script.

So, while your Python script is managing the process, the actual conversion from raw audio data to the MP3 format is done by LAME. This is why you need to have the LAME encoder installed on your system to be able to export MP3 files with PyDub.'''

'''First, make sure your np_array is a 2D array where each row is a channel of audio and each column is a sample. In stereo audio, there should be two rows. If your audio is mono but in a 2D array, make sure it has two identical rows. If your np_array is a 1D array, you need to convert it to the correct 2D format before resampling.

Next, the length of the output can be influenced by how the resampling is done. Both the resample function from scipy.signal and the resample function from librosa change the number of samples in the signal, which directly impacts the duration of the output. The ratio between the original and target sample rates determines the new number of samples.

Lastly, let's consider the export parameters used for MP3 encoding. VBR (Variable Bit Rate) encoding allows the bit rate to vary depending on the complexity of the audio, but the duration should not be affected.'''

''' print("Array Type: ", type(audio_data))
    print("Data Type: ", audio_data.dtype)
    print("Array Shape: ", audio_data.shape)
    print("Number of dimensions: ", audio_data.ndim)
    print("Total Number of elements: ", audio_data.size)
    print("First few elements: ", audio_data[:10])
    print(".....transposing array......")
    audio_data = np_array.T
    print("Array Type: ", type(audio_data))
    print("Data Type: ", audio_data.dtype)
    print("Array Shape: ", audio_data.shape)
    print("Number of dimensions: ", audio_data.ndim)
    print("Total Number of elements: ", audio_data.size)
    print("First few elements: ", audio_data[:10])
    print(".....transposing array......")'''