import sounddevice as sd

def get_active_usb_audio_device_name():
    """
    Queries Windows 11 to find the name of the currently active audio device
    connected to the computer's USB port.

    Returns:
        str: The name of the active USB audio device, or None if not found.
    """
    try:
        # Get the default input device info
        default_input_device_info = sd.query_devices(kind='input')

        # Check if the device name contains "USB"
        if "USB" in default_input_device_info['name']:
            return default_input_device_info['name']
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Call the function and print the result
active_usb_device_name = get_active_usb_audio_device_name()
if active_usb_device_name is not None:
    print("Active USB audio device:", active_usb_device_name)
else:
    print("No active USB audio device found.")
