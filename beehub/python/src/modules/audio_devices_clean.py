"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management using PyAudio.
"""

import logging
import sys
from typing import List, Dict, Optional, Tuple

# Use PyAudio exclusively
from .class_PyAudio import AudioPortManager

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
        
        # Search for matching device
        matching_devices = []
        for device in devices:
            if not device['is_input']:
                continue
                
            name_match = target_device_name.lower() in device['name'].lower()
            api_match = target_api is None or target_api in device['api']
            
            if name_match and api_match:
                matching_devices.append(device)
        
        if not matching_devices:
            print(f"Device '{target_device_name}' not found")
            return False
        
        # Use the first matching device
        device = matching_devices[0]
        print(f"Found device: {device['name']} (API: {device['api']})")
        
        # Configure the application with this device
        bmar_app.device_index = device['index']
        bmar_app.samplerate = int(device['default_sample_rate'])
        bmar_app.channels = min(2, device['input_channels'])
        bmar_app.sound_in_id = device['index']
        bmar_app.sound_in_chs = bmar_app.channels
        bmar_app.PRIMARY_IN_SAMPLERATE = bmar_app.samplerate
        
        # Test the configuration
        if not manager.test_device_configuration(
            bmar_app.device_index, bmar_app.samplerate, 16, bmar_app.channels
        ):
            print(f"Warning: Device configuration test failed")
            return False
        
        print(f"Device configured successfully: {device['name']} at {bmar_app.samplerate}Hz ({bmar_app.channels} ch)")
        return True
        
    except Exception as e:
        logging.error(f"Error in find_device_by_config: {e}")
        print(f"Error finding device by config: {e}")
        return False

def get_audio_device_config() -> Optional[Dict]:
    """Get audio device configuration with fallback to first available input device."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        # Find first working input device
        for device in devices:
            if device['is_input'] and device['input_channels'] > 0:
                # Test if device works with basic configuration
                if manager.test_device_configuration(
                    device['index'], int(device['default_sample_rate']), 16, 
                    min(2, device['input_channels'])
                ):
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
            bmar_app.samplerate = int(device['default_sample_rate'])
            bmar_app.channels = min(2, device['input_channels'])
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
