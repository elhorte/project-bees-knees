import pyaudio

def get_device_info():
    p = pyaudio.PyAudio()
    device_info = {}

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:  # Filtering input devices
            device_info[info["name"]] = {
                "sample_rate": info["defaultSampleRate"],
                "word_size": p.get_sample_size(pyaudio.paInt16) * 8  # Assumes 16-bit audio
            }

    p.terminate()
    return device_info

if __name__ == "__main__":
    devices = get_device_info()
    for name, specs in devices.items():
        print(f"Device: {name}")
        print(f"  Sample Rate: {specs['sample_rate']} Hz")
        print(f"  Word Size: {specs['word_size']} bits")
