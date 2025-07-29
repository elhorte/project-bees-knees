"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management using sounddevice.
"""

import logging
from typing import Dict, Optional
import sounddevice as sd

# Use sounddevice for audio device management
from . import bmar_config as config

# Removed unused function print_all_input_devices() - not used in codebase

def test_device_configuration_sounddevice(device_index: int, samplerate: int, channels: int) -> bool:
    """Test if a device can handle the specified configuration using sounddevice."""
    try:
        with sd.InputStream(device=device_index, channels=channels, samplerate=samplerate, blocksize=1024):
            return True
    except (sd.PortAudioError, ValueError, OSError):
        return False

# Removed unused function get_enhanced_device_info() - not used in codebase

def find_device_by_config(bmar_app) -> bool:
    """Find and configure audio device based on platform-specific configuration."""
    try:
        from .platform_manager import PlatformManager
        from .bmar_config import WINDOWS_DEVICE_NAME, MACOS_DEVICE_NAME, LINUX_DEVICE_NAME
        
        pm = PlatformManager()
        devices = sd.query_devices()
        
        # Get platform-specific device configuration
        if pm.is_windows():
            target_device_name = WINDOWS_DEVICE_NAME
            target_api = "Windows WASAPI"
        elif pm.is_macos():
            target_device_name = MACOS_DEVICE_NAME
            target_api = "Core Audio"
        elif pm.is_linux():
            target_device_name = LINUX_DEVICE_NAME
            target_api = None  # Linux can use various APIs
        else:
            print("Unknown platform detected")
            return False
        
        # Determine platform name for logging
        if pm.is_windows():
            platform_name = "Windows"
        elif pm.is_macos():
            platform_name = "macOS" 
        elif pm.is_linux():
            platform_name = "Linux"
        else:
            platform_name = "Unknown"
            
        print(f"Looking for device: '{target_device_name}' on {platform_name}")
        
        # Search for matching device with API priority
        matching_devices = []
        
        # First priority: Exact device name + API match
        for i, device in enumerate(devices):
            if device['max_input_channels'] == 0:
                continue
                
            hostapi_info = sd.query_hostapis(index=device['hostapi'])
            api_name = hostapi_info['name']
            
            name_match = target_device_name.lower() in device['name'].lower()
            api_match = target_api in api_name if target_api else True
            
            device_info = {
                'index': i,
                'name': device['name'],
                'api': api_name,
                'max_channels': device['max_input_channels']
            }
            
            if name_match and api_match:
                matching_devices.insert(0, device_info)  # Priority device goes first
            elif name_match:
                matching_devices.append(device_info)  # Name match goes second
        
        # If no name matches, try API matches
        if not matching_devices and target_api:
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    hostapi_info = sd.query_hostapis(index=device['hostapi'])
                    api_name = hostapi_info['name']
                    if target_api in api_name:
                        device_info = {
                            'index': i,
                            'name': device['name'],
                            'api': api_name,
                            'max_channels': device['max_input_channels']
                        }
                        matching_devices.append(device_info)
        
        if not matching_devices:
            print(f"Device '{target_device_name}' with API '{target_api}' not found")
            return False
        
        # Test devices in priority order
        for device_info in matching_devices:
            print(f"Testing device: {device_info['name']} (API: {device_info['api']})")
            
            # Test with configured parameters
            channels = min(config.SOUND_IN_CHS, device_info['max_channels'])
            if test_device_configuration_sounddevice(
                device_info['index'], config.PRIMARY_IN_SAMPLERATE, channels
            ):
                print(f"Device configured successfully: {device_info['name']} at {config.PRIMARY_IN_SAMPLERATE}Hz ({channels} ch)")
                
                # Configure the application with this device
                bmar_app.device_index = device_info['index']
                bmar_app.samplerate = config.PRIMARY_IN_SAMPLERATE
                bmar_app.channels = channels
                bmar_app.sound_in_id = device_info['index']
                bmar_app.sound_in_chs = channels
                bmar_app.PRIMARY_IN_SAMPLERATE = config.PRIMARY_IN_SAMPLERATE
                
                return True
            else:
                print(f"Device test failed for: {device_info['name']}")
        
        print("No compatible devices found with required configuration")
        return False
        
    except (sd.PortAudioError, ImportError, AttributeError) as e:
        logging.error("Error in find_device_by_config: %s", e)
        print(f"Error finding device by config: {e}")
        return False

def get_audio_device_config() -> Optional[Dict]:
    """Get audio device configuration prioritizing configured device and API."""
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        
        from .platform_manager import PlatformManager
        pm = PlatformManager()
        
        # Get platform-specific configuration
        if pm.is_windows():
            target_device_name = config.WINDOWS_DEVICE_NAME
            target_api = config.WINDOWS_API_NAME
            preferred_apis = config.AUDIO_API_PREFERENCE
        elif pm.is_macos():
            target_device_name = config.MACOS_DEVICE_NAME
            target_api = config.MACOS_API_NAME
            preferred_apis = ["Core Audio"]
        else:  # Linux
            target_device_name = config.LINUX_DEVICE_NAME
            target_api = config.LINUX_API_NAME
            preferred_apis = ["ALSA"]
        
        # Convert devices to our expected format and filter for input devices
        device_list = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                hostapi = hostapis[device['hostapi']]
                device_list.append({
                    'index': i,
                    'name': device['name'],
                    'api': hostapi['name'],
                    'is_input': True,
                    'input_channels': device['max_input_channels'],
                    'default_sample_rate': device['default_samplerate']
                })
        
        # First priority: Find exact device name + API match
        for device in device_list:
            name_match = target_device_name and target_device_name.lower() in device['name'].lower()
            api_match = target_api and target_api.lower() in device['api'].lower()
            
            if name_match and api_match:
                # Test with configured parameters
                if test_device_configuration_sounddevice(
                    device_index=device['index'],
                    samplerate=config.PRIMARY_IN_SAMPLERATE,
                    channels=config.SOUND_IN_CHS
                ):
                    print(f"Found exact match: {device['name']} ({device['api']})")
                    return {
                        'default_device': device,
                        'all_devices': device_list
                    }
        
        # Second priority: Find device name match with preferred API
        if target_device_name:
            for api_name in preferred_apis:
                for device in device_list:
                    name_match = target_device_name.lower() in device['name'].lower()
                    api_match = api_name.lower() in device['api'].lower()
                    
                    if name_match and api_match:
                        # Test with configured parameters
                        if test_device_configuration_sounddevice(
                            device_index=device['index'],
                            samplerate=config.PRIMARY_IN_SAMPLERATE,
                            channels=config.SOUND_IN_CHS
                        ):
                            print(f"Found device with preferred API: {device['name']} ({device['api']})")
                            return {
                                'default_device': device,
                                'all_devices': device_list
                            }
        
        # Third priority: Any device with preferred API
        for api_name in preferred_apis:
            for device in device_list:
                if api_name.lower() in device['api'].lower():
                    # Test with configured parameters
                    if test_device_configuration_sounddevice(
                        device_index=device['index'],
                        samplerate=config.PRIMARY_IN_SAMPLERATE,
                        channels=config.SOUND_IN_CHS
                    ):
                        print(f"Found device with preferred API: {device['name']} ({device['api']})")
                        return {
                            'default_device': device,
                            'all_devices': device_list
                        }
        
        # Last resort: Find any working input device with configured parameters
        for device in device_list:
            # Test with configured parameters, adjusting channels if needed
            test_channels = min(config.SOUND_IN_CHS, device['input_channels'])
            if test_device_configuration_sounddevice(
                device_index=device['index'],
                samplerate=config.PRIMARY_IN_SAMPLERATE,
                channels=test_channels
            ):
                print(f"Fallback device: {device['name']} ({device['api']})")
                return {
                    'default_device': device,
                    'all_devices': device_list
                }
        
        print("No working input devices found")
        return None
        
    except (sd.PortAudioError, ImportError, AttributeError) as e:
        logging.error("Error getting audio device config: %s", e)
        return None

# Removed unused function configure_audio_device_interactive() - not used in codebase
# Removed unused function list_audio_devices() - not used in codebase
# Removed unused function test_device_configuration() - not used in codebase

def list_audio_devices_detailed(app=None):
    """List all audio devices in compact single-line format matching original BMAR style."""
    print("\nAudio Device List:")
    print("-" * 80)
    
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        
        # Get current device index if available
        current_input_device = None
        current_output_device = None
        if app and hasattr(app, 'device_index'):
            current_input_device = app.device_index
        if app and hasattr(app, 'sound_out_id'):
            current_output_device = app.sound_out_id
        
        # Sort devices by index for consistent display
        sorted_devices = list(enumerate(devices))
        
        for i, device in sorted_devices:
            index = i
            name = device['name']
            hostapi = hostapis[device['hostapi']]['name']
            input_channels = device['max_input_channels']
            output_channels = device['max_output_channels']
            
            # Truncate long device names to fit in line
            if len(name) > 40:
                name = name[:37] + "..."
            
            # Create prefix indicator for selected devices
            prefix = "   "  # Default: 3 spaces
            if index == current_input_device:
                prefix = "> "  # Input device indicator
            elif index == current_output_device:
                prefix = "< "  # Output device indicator
            
            # Format the line with consistent spacing
            # Format: "  INDEX NAME                               API (X in, Y out)"
            line = f"{prefix}{index:2d} {name:<40} {hostapi} ({input_channels} in, {output_channels} out)"
            print(line)
        
        print("-" * 80)
        
    except (sd.PortAudioError, ValueError) as e:
        logging.error("Error listing detailed audio devices: %s", e)
        print("Error: Could not enumerate audio devices")
        print(f"Error: Could not get detailed device information - {e}")

def show_current_audio_devices(app):
    """Show currently configured audio device information."""
    print("\n" + "="*60)
    print("CURRENT AUDIO DEVICE CONFIGURATION")
    print("="*60)
    
    try:
        if hasattr(app, 'device_index') and app.device_index is not None:
            print(f"Device Index: {app.device_index}")
            print(f"Sample Rate: {getattr(app, 'samplerate', 'Not set')} Hz")
            print(f"Channels: {getattr(app, 'channels', 'Not set')}")
            print(f"Sound Input ID: {getattr(app, 'sound_in_id', 'Not set')}")
            print(f"Sound Input Channels: {getattr(app, 'sound_in_chs', 'Not set')}")
            
            # Try to get device name
            try:
                devices = sd.query_devices()
                hostapis = sd.query_hostapis()
                device_name = "Unknown"
                api_name = "Unknown"
                if app.device_index < len(devices):
                    device = devices[app.device_index]
                    device_name = device['name']
                    hostapi = hostapis[device['hostapi']]
                    api_name = hostapi['name']
                print(f"Device Name: {device_name}")
                print(f"API: {api_name}")
            except (sd.PortAudioError, ValueError, IndexError):
                print("Device Name: Could not retrieve")
                
        else:
            print("No audio device currently configured")
            
    except (AttributeError, KeyError) as e:
        print(f"Error getting current device info: {e}")
        logging.error("Error in show_current_audio_devices: %s", e)
    
    print("="*60)

def show_detailed_device_list(app=None):
    """Show detailed device list for menu systems (alias for list_audio_devices_detailed)."""
    list_audio_devices_detailed(app)
