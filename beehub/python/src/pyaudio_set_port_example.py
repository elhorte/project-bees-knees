import pyaudio
import platform

def set_sound_in_port():
    global sound_in_id, sound_in_chs, sound_in_samplerate, sound_in_bitdepth, sound_in_format, stream, p
    # Common parameters
    sample_rate = sound_in_samplerate       
    channels = sound_in_chs    

    pa_format = None
    if sound_in_bitdepth == 16:
        pa_format = pyaudio.paInt16
    elif sound_in_bitdepth == 24:
        pa_format = pyaudio.paInt24
    elif sound_in_bitdepth == 32:
        pa_format = pyaudio.paInt32
        
    # Create PyAudio instance
    p = pyaudio.PyAudio()

    stream = p.open(
        format=pa_format,         
        channels=channels,
        rate=sample_rate,
        input=True,
        input_device_index=None,        # Default device
        frames_per_buffer=1024,
        start=False                     # Don't start immediately
    )

    # When ready to start recording
    stream.start_stream()

def stop_stream():
    global stream, p
    # When done
    if stream:
        stream.stop_stream()
        stream.close()
    if p:
        p.terminate()
