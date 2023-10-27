import sounddevice as sd

def print_sound_devices():
    """Print a list of audio devices with their IDs."""
    print(sd.query_devices())

def device_capabilities(device_id):
    """Check the capabilities of a specific device."""
    try:
        # Get device info
        device_info = sd.query_devices(device_id)
        
        # The device's default sample rate
        print(f"Default Sample Rate: {device_info['default_samplerate']}")

        # Check supported sample rates
        for rate in [32000, 44100, 48000, 96000]:  # common sample rates
            if sd.check_samplerate(device_id, rate):
                print(f"{rate} Hz supported")
            else:
                print(f"{rate} Hz not supported")

    except ValueError as e:
        print(f"Error: {e}")

# First, print out all the connected audio devices
print_sound_devices()

# Based on the list of devices, choose the device ID you want to check.
# For example, if your device ID is 1, you would call device_capabilities(1).
device_id = 9  # please replace this with your actual device ID
device_capabilities(device_id)
