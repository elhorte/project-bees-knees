#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#import youtube_dl              # older version of youtube_dl
import yt_dlp as youtube_dl     # newer version of youtube_dl 
import subprocess
import threading
import os
import time
import datetime

exit_signal = False

def get_hls_url(video_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        return info_dict['url']

def extract_audio_to_pcm(hls_url, output_filename):
    global exit_signal
    
    # Set up the command, but this time we use the subprocess.PIPE to monitor output.
    command = [
        'ffmpeg',
        '-i', hls_url,
        '-acodec', 'pcm_s16le',
        '-ar', '48000',
        '-y', output_filename
    ]
    
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    while True:
        # If exit_signal becomes True, we kill the process
        if exit_signal:
            process.terminate()
            break

def listen_for_exit_key():
    global exit_signal

    while True:
        key = input("Press 's' or 'esc' to stop recording: ")
        if key in ['s', 'esc']:
            exit_signal = True
            time.sleep(1)
            break

if __name__ == "__main__":
    video_url = input("Enter the YouTube video URL: ")
    hls_url = get_hls_url(video_url)
    output_filename = "output_audio.wav"
    
    # Start the audio extraction in a separate thread
    audio_thread = threading.Thread(target=extract_audio_to_pcm, args=(hls_url, output_filename))
    audio_thread.start()

    # Start listening for the exit key in the main thread
    listen_for_exit_key()

    # Wait for the audio_thread to finish
    audio_thread.join()

    print(f"Audio extracted to {output_filename}")


# YouTube-dl: https://youtube.com/live/wfuQLdrlrqg