#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#import youtube_dl
import subprocess
import yt_dlp as youtube_dl


def get_hls_url(video_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [],
        'progress_hooks': [],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        return info_dict['url']

def extract_audio_to_pcm(hls_url, output_filename):
    # Use ffmpeg to extract audio and save it as PCM format with a sample rate of 48000.
    # Note: PCM format in an .wav container
    command = [
        'ffmpeg',
        '-i', hls_url,
        '-acodec', 'pcm_s16le',   # set audio codec to pcm 16 bit little endian
        '-ar', '48000',           # set audio rate to 48K
        '-y',                    # overwrite output file if it exists
        output_filename
    ]

    subprocess.run(command)

if __name__ == "__main__":
    video_url = input("Enter the YouTube video URL: ")
    hls_url = get_hls_url(video_url)
    output_filename = "output_audio.wav"
    
    extract_audio_to_pcm(hls_url, output_filename)
    print(f"Audio extracted to {output_filename}")

# YouTube-dl: https://youtube.com/live/wfuQLdrlrqg