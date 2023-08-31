#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#import youtube_dl              # older version of youtube_dl
import yt_dlp as youtube_dl
import subprocess
import threading
import time
import datetime
import keyboard
import os
import json

exit_signal = False
audio_samplerate = None
SOURCE_ID = "KLEO_YouTube"
AUDIO_DIRECTORY= "."
duration = 0
start_time = 0
duration = 0


def time_it(func):
    """
    A decorator function to measure the execution time of audio capture.
    """
    def wrapper(*args, **kwargs):
        global duration

        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        return result

    return wrapper


def get_hls_url(video_url):
    global audio_samplerate

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        # let's get the audio sample rate from the HLS stream if possible
        if 'asr' in info_dict:
            audio_samplerate = info_dict['asr']
            print("Found in info_dict['asr'], audio sample rate:", audio_samplerate)
        else:
            # This will be a fallback, in case 'asr' isn't directly provided
            for format in info_dict.get('formats', []):
                if format.get('vcodec') == 'none' and 'asr' in format:
                    audio_samplerate = format['asr']
                    print("Found in format['asr'], audio sample rate:", audio_samplerate)

        return info_dict['url']

def extract_audio(hls_url, output_option,file_name):
    global exit_signal, start_time, end_time, duration

    start_time = time.time()

    if output_option == "alsa":
        command = [
            'ffmpeg',
            '-i', hls_url,
            '-f', 'alsa',
            'default'
        ]
    else:
        command = [
            'ffmpeg',
            '-i', hls_url,
            '-acodec', 'pcm_s16le',
            '-ar', str(audio_samplerate),
            '-live_start_index', '0',
            '-y', file_name
        ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    while True:
        # If exit_signal becomes True, we kill the process
        if exit_signal:
            process.terminate()
            end_time = time.time()
            duration = end_time - start_time
            print("Audio capture duration:", duration)
            break
        time.sleep(1)

def listen_for_exit_key():
    global exit_signal

    while True:
        key = input("Press 's' to stop: ")
        if key in ['s']:
            exit_signal = True
            time.sleep(1)           # reduce load on CPU
            break

def stop_all():
    global exit_signal
    exit_signal = True

if __name__ == "__main__":

    # usage: press q to stop all processes
    keyboard.on_press_key("q", lambda _: stop_all(), suppress=True)

    video_url = input("Enter the YouTube video URL: ")
    hls_url = get_hls_url(video_url)

    print("Choose an output option:")
    print("1: Output to ALSA")
    print("2: Save as WAV file")
    choice = input("Enter your choice (1/2): ")

    if choice == "1":
        output_option = "alsa"
    elif choice == "2":
        output_option = "wav"
    else:
        print("Invalid choice.")
        exit()

    print("press 'Q' to stop all processes")

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    # Save plot to disk with a unique filename based on current time
    output_filename = f"{timestamp}_{duration}_{audio_samplerate}_Athena_{SOURCE_ID}.wav"
    full_path_name = os.path.join(AUDIO_DIRECTORY, output_filename)

    # Start the audio extraction in a separate thread
    audio_thread = threading.Thread(target=extract_audio, args=(hls_url, output_option, full_path_name))
    audio_thread.start()

    # Start listening for the exit key in the main thread
    #listen_for_exit_key()

    while audio_thread is not None and not exit_signal:
        time.sleep(1)

    # Wait for the audio_thread to finish
    audio_thread.join()

    if output_option == "wav":
        print(f"Audio saved to {full_path_name}")


# YouTube-dl: https://youtube.com/live/wfuQLdrlrqg

# Use youtube-dl to get the audio sample rate from the HLS stream

def get_audio_sample_rate_from_hls(video_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        
        if 'asr' in info_dict:
            return info_dict['asr']
        else:
            # This will be a fallback, in case 'asr' isn't directly provided
            for format in info_dict.get('formats', []):
                if format.get('vcodec') == 'none' and 'asr' in format:
                    return format['asr']

    return None

# Use ffprobe to get the audio sample rate from the HLS stream

def get_audio_sample_rate_from_ffmpeg(hls_url):
    # Use ffprobe to get stream details in JSON format
    command = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        hls_url
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    output = result.stdout

    # Parse the JSON output
    stream_data = json.loads(output)
    
    # Iterate through the streams to find the audio stream and extract sample rate
    for stream in stream_data['streams']:
        if stream['codec_type'] == 'audio':
            return int(stream['sample_rate'])
    
    return None




