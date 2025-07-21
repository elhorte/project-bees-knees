"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management using PyAudio.
"""

import logging
from typing import List, Dict, Optional, Tuple

# Use PyAudio exclusively
from .class_PyAudio import AudioPortManager
from . import bmar_config as config

def print_all_input_devices():
    """Print a list of all available input devices using PyAudio."""
    print("\nFull input device list (PyAudio):")
    
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        for device in devices:
            if device['is_input']:
                # Enhanced device info with PyAudio testing
                base_info = f"  [{device['index']}] {device['name']} - {device['api']} " \
                           f"({device['input_channels']} ch, {int(device['default_sample_rate'])} Hz)"
                
                # Test basic configuration
                can_use_basic = manager.test_device_configuration(
                    device['index'], 44100, 16, min(2, device['input_channels'])
                )
                
                config_test = "✓" if can_use_basic else "⚠"
                print(f"{base_info} {config_test}")
        
    except Exception as e:
        logging.error(f"Error listing audio devices: {e}")
        print("Error: Could not enumerate audio devices")

def get_enhanced_device_info(device_index: int) -> Dict:
    """Get enhanced device information using PyAudio testing."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        # Find the device
        device_info = None
        for device in devices:
            if device['index'] == device_index:
                device_info = device
                break
        
        if not device_info:
            return {}
        
        # Test various configurations
        test_configs = [
            (44100, 16, 1),
            (44100, 16, 2),
            (48000, 16, 1),
            (48000, 16, 2),
            (96000, 16, 1),
            (96000, 16, 2)
        ]
        
        supported_configs = []
        for sample_rate, bit_depth, channels in test_configs:
            if channels <= device_info['input_channels']:
                if manager.test_device_configuration(device_index, sample_rate, bit_depth, channels):
                    supported_configs.append({
                        'sample_rate': sample_rate,
                        'bit_depth': bit_depth,
                        'channels': channels
                    })
        
        return {
            'device_info': device_info,
            'supported_configs': supported_configs
        }
        
    except Exception as e:
        logging.error(f"Error getting enhanced device info: {e}")
        return {}

def find_device_by_config(bmar_app) -> bool:
    """Find and configure audio device based on platform-specific configuration."""
    try:
        from .platform_manager import PlatformManager
        from .bmar_config import WINDOWS_DEVICE_NAME, MACOS_DEVICE_NAME, LINUX_DEVICE_NAME
        
        pm = PlatformManager()
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
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
        for device in devices:
            if not device['is_input']:
                continue
                
            name_match = target_device_name.lower() in device['name'].lower()
            api_match = target_api in device['api']
            
            if name_match and api_match:
                matching_devices.insert(0, device)  # Priority device goes first
            elif name_match:
                matching_devices.append(device)  # Name match goes second
        
        # If no name matches, try API matches
        if not matching_devices:
            for device in devices:
                if device['is_input'] and target_api in device['api']:
                    matching_devices.append(device)
        
        if not matching_devices:
            print(f"Device '{target_device_name}' with API '{target_api}' not found")
            return False
        
        # Test devices in priority order
        for device in matching_devices:
            print(f"Testing device: {device['name']} (API: {device['api']})")
            
            # Test with configured parameters
            if manager.test_device_configuration(
                device['index'], config.PRIMARY_IN_SAMPLERATE, config.PRIMARY_BITDEPTH, config.SOUND_IN_CHS
            ):
                print(f"Device configured successfully: {device['name']} at {config.PRIMARY_IN_SAMPLERATE}Hz ({config.SOUND_IN_CHS} ch)")
                
                # Configure the application with this device
                bmar_app.device_index = device['index']
                bmar_app.samplerate = config.PRIMARY_IN_SAMPLERATE
                bmar_app.channels = config.SOUND_IN_CHS
                bmar_app.sound_in_id = device['index']
                bmar_app.sound_in_chs = bmar_app.channels
                bmar_app.PRIMARY_IN_SAMPLERATE = bmar_app.samplerate
                
                return True
            else:
                print(f"Device test failed for: {device['name']}")
        
        print("No compatible devices found with required configuration")
        return False
        
    except Exception as e:
        logging.error(f"Error in find_device_by_config: {e}")
        print(f"Error finding device by config: {e}")
        return False

def get_audio_device_config() -> Optional[Dict]:
    """Get audio device configuration prioritizing configured device and API."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
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
        
        # First priority: Find exact device name + API match
        for device in devices:
            if not device['is_input'] or device['input_channels'] == 0:
                continue
                
            name_match = target_device_name.lower() in device['name'].lower()
            api_match = target_api in device['api']
            
            if name_match and api_match:
                # Test with configured parameters, not device defaults
                if manager.test_device_configuration(
                    device['index'], config.PRIMARY_IN_SAMPLERATE, config.PRIMARY_BITDEPTH, 
                    config.SOUND_IN_CHS
                ):
                    print(f"Found exact match: {device['name']} ({device['api']})")
                    return {
                        'default_device': {
                            'index': device['index'],
                            'name': device['name'],
                            'api': device['api'],
                            'input_channels': device['input_channels'],
                            'default_sample_rate': device['default_sample_rate']
                        },
                        'all_devices': devices
                    }
        
        # Second priority: Find device name match with preferred API
        for api_name in preferred_apis:
            for device in devices:
                if not device['is_input'] or device['input_channels'] == 0:
                    continue
                    
                name_match = target_device_name.lower() in device['name'].lower()
                api_match = api_name in device['api']
                
                if name_match and api_match:
                    # Test with configured parameters
                    if manager.test_device_configuration(
                        device['index'], config.PRIMARY_IN_SAMPLERATE, config.PRIMARY_BITDEPTH, 
                        config.SOUND_IN_CHS
                    ):
                        print(f"Found device with preferred API: {device['name']} ({device['api']})")
                        return {
                            'default_device': {
                                'index': device['index'],
                                'name': device['name'],
                                'api': device['api'],
                                'input_channels': device['input_channels'],
                                'default_sample_rate': device['default_sample_rate']
                            },
                            'all_devices': devices
                        }
        
        # Third priority: Any device with preferred API
        for api_name in preferred_apis:
            for device in devices:
                if not device['is_input'] or device['input_channels'] == 0:
                    continue
                    
                if api_name in device['api']:
                    # Test with configured parameters
                    if manager.test_device_configuration(
                        device['index'], config.PRIMARY_IN_SAMPLERATE, config.PRIMARY_BITDEPTH, 
                        config.SOUND_IN_CHS
                    ):
                        print(f"Found device with preferred API: {device['name']} ({device['api']})")
                        return {
                            'default_device': {
                                'index': device['index'],
                                'name': device['name'],
                                'api': device['api'],
                                'input_channels': device['input_channels'],
                                'default_sample_rate': device['default_sample_rate']
                            },
                            'all_devices': devices
                        }
        
        # Last resort: Find any working input device with configured parameters
        for device in devices:
            if device['is_input'] and device['input_channels'] > 0:
                # Test with configured parameters, not device defaults
                if manager.test_device_configuration(
                    device['index'], config.PRIMARY_IN_SAMPLERATE, config.PRIMARY_BITDEPTH, 
                    min(config.SOUND_IN_CHS, device['input_channels'])
                ):
                    print(f"Fallback device: {device['name']} ({device['api']})")
                    return {
                        'default_device': {
                            'index': device['index'],
                            'name': device['name'],
                            'api': device['api'],
                            'input_channels': device['input_channels'],
                            'default_sample_rate': device['default_sample_rate']
                        },
                        'all_devices': devices
                    }
        
        print("No working input devices found")
        return None
        
    except Exception as e:
        logging.error(f"Error getting audio device config: {e}")
        return None

def configure_audio_device_interactive(bmar_app) -> bool:
    """Configure audio device interactively by trying config-based detection first."""
    try:
        # Try config-based detection first
        if find_device_by_config(bmar_app):
            return True
        
        # Fallback to first available device
        print("Config-based detection failed, trying fallback...")
        device_config = get_audio_device_config()
        if device_config and device_config.get('default_device'):
            device = device_config['default_device']
            bmar_app.device_index = device['index']
            bmar_app.samplerate = config.PRIMARY_IN_SAMPLERATE  # Use configured sample rate, not device default
            bmar_app.channels = config.SOUND_IN_CHS  # Use configured channels from config
            bmar_app.sound_in_id = device['index']
            bmar_app.sound_in_chs = bmar_app.channels
            bmar_app.PRIMARY_IN_SAMPLERATE = bmar_app.samplerate
            print(f"Fallback device configured: {device['name']}")
            return True
        
        return False
        
    except Exception as e:
        logging.error(f"Error in configure_audio_device_interactive: {e}")
        return False

def list_audio_devices() -> List[Dict]:
    """List all available audio devices."""
    try:
        manager = AudioPortManager()
        return manager.list_audio_devices()
    except Exception as e:
        logging.error(f"Error listing audio devices: {e}")
        return []

def test_device_configuration(device_index: int, sample_rate: int, bit_depth: int, channels: int) -> bool:
    """Test if a device configuration is supported."""
    try:
        manager = AudioPortManager()
        return manager.test_device_configuration(device_index, sample_rate, bit_depth, channels)
    except Exception as e:
        logging.error(f"Error testing device configuration: {e}")
        return False

def list_audio_devices_detailed(app=None):
    """List all audio devices in compact single-line format matching original BMAR style."""
    print("\nAudio Device List:")
    print("-" * 80)
    
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        # Get current device index if available
        current_input_device = None
        current_output_device = None
        if app and hasattr(app, 'device_index'):
            current_input_device = app.device_index
        if app and hasattr(app, 'sound_out_id'):
            current_output_device = app.sound_out_id
        
        # Sort devices by index for consistent display
        sorted_devices = sorted(devices, key=lambda d: d['index'])
        
        for device in sorted_devices:
            index = device['index']
            name = device['name']
            api = device['api']
            input_channels = device['input_channels']
            output_channels = device['output_channels']
            
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
            line = f"{prefix}{index:2d} {name:<40} {api} ({input_channels} in, {output_channels} out)"
            print(line)
        
        print("-" * 80)
        
    except Exception as e:
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
                manager = AudioPortManager()
                devices = manager.list_audio_devices()
                device_name = "Unknown"
                for device in devices:
                    if device['index'] == app.device_index:
                        device_name = device['name']
                        api_name = device['api']
                        break
                print(f"Device Name: {device_name}")
                print(f"API: {api_name}")
            except:
                print("Device Name: Could not retrieve")
                
        else:
            print("No audio device currently configured")
            
    except Exception as e:
        print(f"Error getting current device info: {e}")
        logging.error(f"Error in show_current_audio_devices: {e}")
    
    print("="*60)

def show_detailed_device_list(app=None):
    """Show detailed device list for menu systems (alias for list_audio_devices_detailed)."""
    try:
        list_audio_devices_detailed(app)
    except Exception as e:
        print(f"Error showing detailed device list: {e}")
        logging.error("Error in show_detailed_device_list: %s", e)
