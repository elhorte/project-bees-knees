"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management.
"""

import sounddevice as sd
import logging
import sys
import subprocess
import datetime
import time

def print_all_input_devices():
    """Print a list of all available input devices."""
    print("\nFull input device list (from sounddevice):\r")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            hostapi_info = sd.query_hostapis(index=device['hostapi'])
            print(f"  [{i}] {device['name']} - {hostapi_info['name']} "
                  f"({device['max_input_channels']} ch, {int(device['default_samplerate'])} Hz)")
    print()
    sys.stdout.flush()

def get_api_name_for_device(device_id):
    """Get the API name for a specific device ID."""
    device = sd.query_devices(device_id)
    hostapi_info = sd.query_hostapis(index=device['hostapi'])
    return hostapi_info['name']

def get_windows_sample_rate(device_name):
    """Get the actual sample rate from Windows using PyAudio."""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        
        # Find device by name
        device_id = None
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if device_name.lower() in info['name'].lower():
                device_id = i
                break
        
        if device_id is not None:
            device_info = p.get_device_info_by_index(device_id)
            sample_rate = int(device_info['defaultSampleRate'])
            p.terminate()
            return sample_rate
        else:
            p.terminate()
            return None
    except Exception as e:
        logging.error(f"Error getting Windows sample rate: {e}")
        return None

def get_current_device_sample_rate(app, device_id):
    """Query the current sample rate of the device from the operating system."""
    try:
        device_info = sd.query_devices(device_id)
        sample_rate = int(device_info['default_samplerate'])
        
        # For Windows, try to get more accurate rate
        if app.platform_manager.is_windows():
            windows_rate = get_windows_sample_rate(device_info['name'])
            if windows_rate:
                sample_rate = windows_rate
        
        return sample_rate
    except Exception as e:
        logging.error(f"Error getting device sample rate: {e}")
        return None

def show_audio_device_info_for_SOUND_IN_OUT(app):
    """Display detailed information about the selected audio input and output devices."""
    print("\nSelected Audio Device Information:")
    print("-" * 50)
    
    # Get and display input device info
    try:
        input_info = sd.query_devices(app.sound_in_id)
        print("\nInput Device:")
        print(f"Name: [{app.sound_in_id}] {input_info['name']}")
        print(f"Default Sample Rate: {int(input_info['default_samplerate'])} Hz")
        print(f"Bit Depth: {app.config.PRIMARY_BITDEPTH} bits")
        print(f"Max Input Channels: {input_info['max_input_channels']}")
        print(f"Current Sample Rate: {int(app.config.PRIMARY_IN_SAMPLERATE)} Hz")
        print(f"Current Channels: {app.sound_in_chs}")
        if 'hostapi' in input_info:
            hostapi_info = sd.query_hostapis(index=input_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting input device info: {e}")
    
    # Get and display output device info
    try:
        output_info = sd.query_devices(app.sound_out_id)
        print("\nOutput Device:")
        print(f"Name: [{app.sound_out_id}] {output_info['name']}")
        print(f"Default Sample Rate: {int(output_info['default_samplerate'])} Hz")
        print(f"Max Output Channels: {output_info['max_output_channels']}")
        if 'hostapi' in output_info:
            hostapi_info = sd.query_hostapis(index=output_info['hostapi'])
            print(f"Audio API: {hostapi_info['name']}")
    except Exception as e:
        print(f"Error getting output device info: {e}")
    
    print("-" * 50)
    sys.stdout.flush()

def show_audio_device_info_for_defaults():
    """Show information about the default audio devices."""
    print("\nsounddevices default device info:")
    default_input_info = sd.query_devices(kind='input')
    default_output_info = sd.query_devices(kind='output')
    print(f"\nDefault Input Device: [{default_input_info['index']}] {default_input_info['name']}")
    print(f"Default Output Device: [{default_output_info['index']}] {default_output_info['name']}\n")

def show_detailed_device_list(app):
    """Display a detailed list of all audio devices with input/output indicators."""
    print("\nAudio Device List:")
    print("-" * 80)
    
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        # Get API name
        hostapi_info = sd.query_hostapis(index=device['hostapi'])
        api_name = hostapi_info['name']

        # Determine if device is input, output, or both
        in_channels = device['max_input_channels']
        out_channels = device['max_output_channels']
        
        # Create prefix based on device type and whether it's the active device
        if i == app.device_index:
            prefix = "*"  # Active device (used by BMAR)
        else:
            prefix = " "
            
        # Format the device name to fit in 40 characters
        device_name = device['name']
        if len(device_name) > 40:
            device_name = device_name[:37] + "..."

        # Print the device information
        print(f"{prefix} {i:2d} {device_name:<40} {api_name} ({in_channels} in, {out_channels} out)")

    print("-" * 80)
    print(f"* = Currently selected device (Index: {app.device_index})")
    print(f"Sample Rate: {app.samplerate} Hz")
    print(f"Block Size: {app.blocksize}")
    sys.stdout.flush()

def set_input_device(app):
    """Find and configure a suitable audio input device based on settings in the app object."""
    logging.info("Scanning for audio input devices...")
    sys.stdout.flush()

    # Initialize testmode to True. It will be set to False upon success.
    app.testmode = True

    print_all_input_devices()

    try:
        # Get all devices
        devices = sd.query_devices()
        
        # First try the specified device_id if it exists
        if app.device_id is not None and app.device_id >= 0:
            try:
                device = devices[app.device_id]
                if device['max_input_channels'] >= app.sound_in_chs:
                    app.sound_in_id = app.device_id
                    logging.info(f"Using specified device ID {app.device_id}: {device['name']}")
                    app.testmode = False
                    return True
            except IndexError:
                logging.warning(f"Specified device ID {app.device_id} not found")
        else:
            logging.info("No specific device ID provided, scanning for suitable devices")
        
        # Create a list of input devices with their IDs
        input_devices = [(i, device) for i, device in enumerate(devices) 
                        if device['max_input_channels'] > 0]
        
        # Sort by device ID in descending order
        input_devices.sort(reverse=True, key=lambda x: x[0])
        
        # If make_name is specified, try those devices first
        if app.make_name and app.make_name.strip():
            logging.info(f"Looking for devices matching make name: '{app.make_name}'")
            matching_devices = [(dev_id, device) for dev_id, device in input_devices
                              if app.make_name.lower() in device['name'].lower()]
            if matching_devices:
                input_devices = matching_devices + [(dev_id, device) for dev_id, device in input_devices 
                                                  if (dev_id, device) not in matching_devices]
        
        # Try all devices if no matching devices were found or if make_name was empty
        for dev_id, device in input_devices:
            try:
                # Check if device supports required channels
                actual_channels = min(device['max_input_channels'], app.sound_in_chs)
                if actual_channels != app.sound_in_chs:
                    logging.warning(f"Device {dev_id} only supports {actual_channels} channels, "
                                  f"requested {app.sound_in_chs}")
                
                # Try to test the device
                try:
                    with sd.InputStream(device=dev_id, channels=actual_channels, 
                                      samplerate=app.config.PRIMARY_IN_SAMPLERATE,
                                      dtype=app._dtype, blocksize=1024):
                        pass  # Just test if we can open the stream
                    
                    # If we get here, the device works
                    app.sound_in_id = dev_id
                    app.sound_in_chs = actual_channels
                    logging.info(f"Successfully configured device {dev_id}: {device['name']}")
                    logging.info(f"Using {actual_channels} channel(s) at {app.config.PRIMARY_IN_SAMPLERATE} Hz")
                    app.testmode = False
                    return True
                    
                except Exception as e:
                    logging.debug(f"Device {dev_id} failed test: {e}")
                    continue
                    
            except Exception as e:
                logging.debug(f"Error testing device {dev_id}: {e}")
                continue
        
        print("\nNo devices could be configured with acceptable settings.")
        return False

    except Exception as e:
        print(f"\nError during device selection: {str(e)}")
        print("Please check your audio device configuration and ensure it supports the required settings")
        sys.stdout.flush()
        return False

def check_stream_status(app, stream_duration):
    """
    Check the status of a sounddevice input stream for overflows and underflows.
    
    Parameters:
    - app: BmarApp instance containing audio device configuration
    - stream_duration: Duration for which the stream should be open and checked (in seconds).
    """
    print(f"Checking input stream for overflow. Watching for {stream_duration} seconds")

    # Define a callback function to process the audio stream
    def callback(indata, frames, time, status):
        if status and status.input_overflow:
            print("Input overflow detected at:", datetime.datetime.now())

    # Open an input stream
    with sd.InputStream(callback=callback, device=app.sound_in_id) as stream:
        # Run the stream for the specified duration
        timeout = time.time() + stream_duration
        while time.time() < timeout:
            time.sleep(0.1)  # Sleep for a short duration before checking again

    print("Stream checking finished at", datetime.datetime.now())
    show_audio_device_info_for_SOUND_IN_OUT(app)

def get_default_output_device():
    """Get the name of the default output device."""
    devices = sd.query_devices()
    for device in devices:
        if device['max_output_channels'] > 0:
            return device['name']
    return None

def get_enabled_mic_locations(app):
    """
    Reads microphone enable states (MIC_1 to MIC_4) and maps to their corresponding locations.
    """
    # Define microphone states and corresponding locations
    mic_location_names = [app.config.MIC_LOCATION[i] for i, enabled in enumerate(app.MICS_ACTIVE) if enabled]
    return mic_location_names

def show_mic_locations(app):
    """Display enabled microphone locations."""
    print("Enabled microphone locations:", get_enabled_mic_locations(app))

def is_mic_position_in_bounds(mic_list, position):
    """
    Checks if the mic is present in the hive and powered on.
    
    Args:
        mic_list: A list of boolean values (True/False) or integers (1/0).
        position: The index of the element to check.
        
    Returns:
        bool: Status of mic at position
    """
    try:
        return bool(mic_list[position])
    except IndexError:
        print(f"Error: mic {position} is out of bounds.")
        return False

def get_audio_device_config():
    """
    Get a suitable audio device configuration.
    
    Returns:
        dict: Audio device configuration with device_index and samplerate
        None: If no suitable device found
    """
    try:
        devices = sd.query_devices()
        
        # Look for a good input device
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                samplerate = int(device['default_samplerate'])
                
                # Prefer standard sample rates
                if samplerate in [44100, 48000]:
                    return {
                        'device_index': i,
                        'samplerate': samplerate,
                        'channels': 1,
                        'device_name': device['name']
                    }
        
        # If no preferred device found, use default input
        default_device = sd.default.device[0]  # Input device
        if default_device is not None:
            device = sd.query_devices(default_device)
            return {
                'device_index': default_device,
                'samplerate': int(device['default_samplerate']),
                'channels': 1,
                'device_name': device['name']
            }
        
        return None
        
    except Exception as e:
        logging.error(f"Error getting audio device config: {e}")
        return None

def list_audio_devices_detailed():
    """List all available audio devices with detailed information."""
    try:
        print("\nAvailable Audio Devices:")
        print("=" * 50)
        
        devices = sd.query_devices()
        
        print("Input Devices:")
        print("-" * 20)
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                hostapi_info = sd.query_hostapis(index=device['hostapi'])
                print(f"  [{i:2d}] {device['name']}")
                print(f"       API: {hostapi_info['name']}")
                print(f"       Channels: {device['max_input_channels']} in")
                print(f"       Sample Rate: {int(device['default_samplerate'])} Hz")
                print()
        
        print("Output Devices:")
        print("-" * 20)
        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                hostapi_info = sd.query_hostapis(index=device['hostapi'])
                print(f"  [{i:2d}] {device['name']}")
                print(f"       API: {hostapi_info['name']}")
                print(f"       Channels: {device['max_output_channels']} out")
                print(f"       Sample Rate: {int(device['default_samplerate'])} Hz")
                print()
        
        # Show default devices
        try:
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]
            print(f"Default input device: {default_input}")
            print(f"Default output device: {default_output}")
        except:
            pass
            
    except Exception as e:
        print(f"Error listing audio devices: {e}")
        logging.error(f"Error listing audio devices: {e}")

def show_current_audio_devices(app):
    """Display information about the currently selected audio devices."""
    try:
        print("\nCurrently Selected Audio Devices:")
        print("=" * 45)
        
        # Get current input device information
        if app.device_index is not None:
            try:
                device_info = sd.query_devices(app.device_index)
                hostapi_info = sd.query_hostapis(index=device_info['hostapi'])
                
                print(f"Input Device:")
                print(f"  Index: {app.device_index}")
                print(f"  Name: {device_info['name']}")
                print(f"  API: {hostapi_info['name']}")
                print(f"  Channels: {device_info['max_input_channels']} in, {device_info['max_output_channels']} out")
                print(f"  Sample Rate: {app.samplerate} Hz")
                print(f"  Block Size: {app.blocksize}")
                
                # Show if device supports both input and output
                if device_info['max_input_channels'] > 0 and device_info['max_output_channels'] > 0:
                    print(f"  Note: This device supports both input and output")
                elif device_info['max_input_channels'] > 0:
                    print(f"  Note: Input-only device")
                elif device_info['max_output_channels'] > 0:
                    print(f"  Note: Output-only device")
                    
            except Exception as e:
                print(f"Error getting current device info: {e}")
        else:
            print("No audio device currently selected")
        
        print("=" * 45)
        
    except Exception as e:
        print(f"Error displaying current audio devices: {e}")
        logging.error(f"Error displaying current audio devices: {e}")
