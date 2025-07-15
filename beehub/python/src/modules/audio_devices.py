"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management using PyAudio.
"""

import logging
import sys
import subprocess
import datetime
import time
from typing import List, Dict, Optional, Tuple, Union

# Use PyAudio exclusively
from .class_PyAudio import AudioPortManager

def print_all_input_devices():
    """Print a list of all available input devices using PyAudio."""
    print("\nFull input device list (PyAudio):\r")
    
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
            return {'pyaudio_compatible': False, 'error': 'Device not found'}
        
        # Test basic configuration
        can_use_target = manager.test_device_configuration(
            device_index, manager.target_sample_rate, manager.target_bit_depth, 
            min(2, device_info['input_channels'])
        )
        
        return {
            'pyaudio_compatible': True,
            'can_use_target_config': can_use_target,
            'api': device_info['api'],
            'max_channels': device_info['input_channels'],
            'default_sample_rate': device_info['default_sample_rate']
        }
        
    except Exception as e:
        return {'pyaudio_compatible': False, 'error': str(e)}

def configure_audio_with_fallback(app):
    """Configure audio using PyAudio with hierarchical fallback strategy."""
    try:
        manager = AudioPortManager(
            target_sample_rate=app.config.PRIMARY_IN_SAMPLERATE,
            target_bit_depth=app.config.BIT_DEPTH
        )
        
        # Use the hierarchical configuration
        success, device, sample_rate, bit_depth = manager.configure_audio_input(
            channels=app.config.CHANNELS
        )
        
        if success:
            # Update app configuration with working settings
            app.sound_in_id = device['index']
            app.sound_in_chs = device['input_channels']
            app.PRIMARY_IN_SAMPLERATE = sample_rate
            app._bit_depth = bit_depth
            app.testmode = False
            
            logging.info(f"Audio configured successfully:")
            logging.info(f"  Device: {device['name']} ({device['api']})")
            logging.info(f"  Sample Rate: {sample_rate} Hz")
            logging.info(f"  Bit Depth: {bit_depth} bits")
            logging.info(f"  Channels: {device['input_channels']}")
            
            return True
        else:
            logging.error("Could not configure any audio device")
            return False
            
    except Exception as e:
        logging.error(f"Error configuring audio: {e}")
        return False

def set_input_device(app):
    """Find and configure a suitable audio input device using PyAudio."""
    logging.info("Scanning for audio input devices...")
    sys.stdout.flush()

    # Initialize testmode to True. It will be set to False upon success.
    app.testmode = True

    try:
        print_all_input_devices()
    except Exception as e:
        logging.error(f"Could not list audio devices: {e}")
        return False

    # Try to configure with fallback strategy
    if configure_audio_with_fallback(app):
        logging.info(f"Audio device configured successfully: Device {app.sound_in_id}")
        return True
    
    # If automatic configuration failed, manual selection
    logging.warning("Automatic audio configuration failed. Manual selection required.")
    
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        input_devices = [d for d in devices if d['is_input']]
        
        if not input_devices:
            logging.critical("No input devices found.")
            return False
        
        print("\nAvailable input devices:")
        for device in input_devices:
            print(f"  [{device['index']}] {device['name']} - {device['api']}")
        
        # Try the first available input device
        test_device = input_devices[0]
        
        if manager.test_device_configuration(
            test_device['index'], 44100, 16, min(2, test_device['input_channels'])
        ):
            app.sound_in_id = test_device['index']
            app.sound_in_chs = test_device['input_channels']
            app.PRIMARY_IN_SAMPLERATE = 44100
            app._bit_depth = 16
            app.testmode = False
            
            logging.info(f"Using fallback device: {test_device['name']}")
            return True
    
    except Exception as e:
        logging.error(f"Error in manual device selection: {e}")
    
    logging.critical("No suitable audio input device could be configured.")
    return False

def test_device_stream(device_index: int, sample_rate: int, channels: int) -> bool:
    """Test if a device can stream audio with the given parameters."""
    try:
        manager = AudioPortManager()
        return manager.test_device_configuration(device_index, sample_rate, 16, channels)
    except Exception as e:
        logging.error(f"Error testing device stream: {e}")
        return False

# Add the missing functions that bmar_app.py expects:

def get_audio_device_config():
    """Get audio device configuration with WSL awareness."""
    try:
        from .platform_manager import PlatformManager
        platform_manager = PlatformManager()
        
        # Check if we're in WSL
        if platform_manager.is_wsl():
            return get_wsl_audio_config()
        
        # Try standard PyAudio device detection
        try:
            manager = AudioPortManager()
            devices = manager.list_audio_devices()
            input_devices = [d for d in devices if d['is_input']]
            
            if input_devices:
                # Use first working device
                for device in input_devices:
                    if manager.test_device_configuration(device['index'], 44100, 16, 1):
                        return {
                            'device_id': device['index'],  # ✅ Use consistent key
                            'sample_rate': 44100,
                            'channels': min(2, device['input_channels']),
                            'bit_depth': 16
                        }
        except Exception as e:
            logging.debug(f"PyAudio device detection failed: {e}")
        
        # No devices found - return virtual device config
        logging.info("No real audio devices found, using virtual device")
        return {
            'device_id': None,  # Virtual device
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }
        
    except Exception as e:
        logging.error(f"Error getting audio device config: {e}")
        return {
            'device_id': None,
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }

def get_wsl_audio_config():
    """Get WSL-specific audio configuration."""
    try:
        # Try to import WSL audio manager
        try:
            from .wsl_audio_manager import setup_wsl_environment
            
            wsl_devices = setup_wsl_environment()
            if wsl_devices:
                device = wsl_devices[0]
                return {
                    'device_id': device['index'],  # ✅ Use consistent key
                    'sample_rate': device['default_sample_rate'],
                    'channels': device['input_channels'],
                    'bit_depth': 16,
                    'wsl_device': device
                }
        except ImportError:
            logging.info("WSL audio manager not available, using virtual device")
        
        # Return virtual device config
        return {
            'device_id': None,  # Virtual device
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }
        
    except Exception as e:
        logging.error(f"Error getting WSL audio config: {e}")
        return {
            'device_id': None,
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }

def configure_audio_device_interactive(app):
    """Configure audio device interactively with WSL awareness."""
    try:
        from .platform_manager import PlatformManager
        platform_manager = PlatformManager()
        
        # In WSL, skip interactive configuration and use fallback
        if platform_manager.is_wsl():
            logging.info("WSL detected - skipping interactive audio configuration")
            return False  # This will trigger fallback logic
        
        # Regular interactive configuration for non-WSL systems
        try:
            manager = AudioPortManager()
            devices = manager.list_audio_devices()
            input_devices = [d for d in devices if d['is_input']]
            
            if not input_devices:
                logging.error("No input devices found for interactive configuration")
                return False
            
            # Auto-select first working device for now
            for device in input_devices:
                if manager.test_device_configuration(device['index'], 44100, 16, 1):
                    app.device_index = device['index']
                    app.samplerate = 44100
                    app.channels = min(2, device['input_channels'])
                    app.sound_in_chs = app.channels
                    app.PRIMARY_IN_SAMPLERATE = app.samplerate
                    app._bit_depth = 16
                    app.blocksize = 1024
                    app.monitor_channel = 0
                    
                    logging.info(f"Auto-configured device {device['index']}: {device['name']}")
                    return True
            
            logging.error("No working input devices found")
            return False
            
        except Exception as e:
            logging.error(f"Interactive audio configuration failed: {e}")
            return False
            
    except Exception as e:
        logging.error(f"Error in configure_audio_device_interactive: {e}")
        return False

def setup_wsl_audio_fallback(app):
    """Set up WSL audio as a fallback when no PyAudio devices are found."""
    try:
        logging.info("Setting up WSL audio environment...")
        
        # Try to import WSL audio manager
        try:
            from .wsl_audio_manager import setup_wsl_environment
            wsl_devices = setup_wsl_environment()
        except ImportError:
            logging.warning("WSL audio manager not available, creating virtual device")
            wsl_devices = []
        
        if wsl_devices:
            # Use the first available WSL device
            device = wsl_devices[0]
            
            # Configure the app with WSL device
            app.device_index = device['index']
            app.sound_in_id = device['index']
            app.sound_in_chs = device['input_channels']
            app.samplerate = device['default_sample_rate']
            app.PRIMARY_IN_SAMPLERATE = device['default_sample_rate']
            app.channels = device['input_channels']
            app._bit_depth = 16
            app.blocksize = 1024
            app.monitor_channel = 0
            app.wsl_audio_device = device  # Store WSL device info
            
            print(f"Configured WSL audio device: {device['name']}")
            print("Note: WSL audio support is experimental")
            
            if device.get('virtual'):
                print("Warning: Using virtual audio device - no actual audio will be recorded")
            
            return True
        else:
            # Create virtual device
            print("Creating virtual audio device for WSL...")
            app.device_index = 0
            app.sound_in_id = 0
            app.sound_in_chs = 1
            app.samplerate = 44100
            app.PRIMARY_IN_SAMPLERATE = 44100
            app.channels = 1
            app._bit_depth = 16
            app.blocksize = 1024
            app.monitor_channel = 0
            app.virtual_device = True
            
            print("Virtual WSL audio device created")
            print("Warning: No actual audio will be recorded")
            return True
            
    except Exception as e:
        logging.error(f"Error setting up WSL audio fallback: {e}")
        print(f"WSL audio setup failed: {e}")
        return False

def get_audio_device_config() -> Dict:
    """Get current audio device configuration."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        input_devices = [d for d in devices if d['is_input']]
        
        if not input_devices:
            return {'available_devices': [], 'default_device': None}
        
        # Try to find a good default device
        default_device = None
        for device in input_devices:
            if manager.test_device_configuration(device['index'], 44100, 16, 2):
                default_device = device
                break
        
        return {
            'available_devices': input_devices,
            'default_device': default_device
        }
    except Exception as e:
        logging.error(f"Error getting audio device config: {e}")
        return {'available_devices': [], 'default_device': None}

def configure_audio_device_interactive(app=None) -> Optional[Dict]:
    """Interactive audio device configuration.
    
    Args:
        app: Optional app instance for configuration storage
        
    Returns:
        Dict with device configuration or None if failed
    """
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        input_devices = [d for d in devices if d['is_input']]
        
        if not input_devices:
            print("No input devices found.")
            logging.error("No input devices found for interactive configuration")
            return None
        
        print("\nAvailable audio input devices:")
        for i, device in enumerate(input_devices):
            # Test device compatibility
            is_compatible = manager.test_device_configuration(
                device['index'], 44100, 16, min(2, device['input_channels'])
            )
            status = "✓" if is_compatible else "⚠"
            print(f"  {i}: [{device['index']}] {device['name']} - {device['api']} {status}")
        
        # Auto-select the first working device
        selected_device = None
        for device in input_devices:
            if manager.test_device_configuration(device['index'], 44100, 16, 2):
                selected_device = device
                break
        
        if selected_device:
            device_config = {
                'device_index': selected_device['index'],
                'device_name': selected_device['name'],
                'sample_rate': 44100,
                'channels': min(2, selected_device['input_channels']),
                'bit_depth': 16,
                'api': selected_device['api']
            }
            
            print(f"Auto-selected: {selected_device['name']} ({selected_device['api']})")
            logging.info(f"Interactive config selected device: {selected_device['name']}")
            
            # If app instance is provided, configure it
            if app is not None:
                try:
                    app.sound_in_id = device_config['device_index']
                    app.sound_in_chs = device_config['channels']
                    app.PRIMARY_IN_SAMPLERATE = device_config['sample_rate']
                    app._bit_depth = device_config['bit_depth']
                    app.testmode = False
                    logging.info(f"App configured with device {app.sound_in_id}")
                except Exception as e:
                    logging.error(f"Error configuring app with selected device: {e}")
            
            return device_config
        else:
            logging.error("No compatible devices found for interactive configuration")
            return None
        
    except Exception as e:
        logging.error(f"Error in interactive device configuration: {e}")
        return None

def get_device_info(device_index: int) -> Optional[Dict]:
    """Get information about a specific device."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        for device in devices:
            if device['index'] == device_index:
                return device
        
        return None
    except Exception as e:
        logging.error(f"Error getting device info: {e}")
        return None

def validate_device_configuration(device_index: int, sample_rate: int, 
                                channels: int, bit_depth: int = 16) -> bool:
    """Validate a specific device configuration."""
    try:
        manager = AudioPortManager()
        return manager.test_device_configuration(device_index, sample_rate, bit_depth, channels)
    except Exception as e:
        logging.error(f"Error validating device configuration: {e}")
        return False

# Additional helper functions that might be expected

def validate_audio_device(device_index: int) -> bool:
    """Validate that an audio device exists and works."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        # Check if device exists
        device_found = False
        for device in devices:
            if device['index'] == device_index and device['is_input']:
                device_found = True
                break
        
        if not device_found:
            logging.error(f"Audio device {device_index} not found or not an input device")
            return False
        
        # Test basic configuration
        if manager.test_device_configuration(device_index, 44100, 16, 2):
            logging.info(f"Audio device {device_index} validated successfully")
            return True
        else:
            logging.warning(f"Audio device {device_index} has limited capabilities")
            return True  # Still allow usage but warn
            
    except Exception as e:
        logging.error(f"Error validating audio device {device_index}: {e}")
        return False

# Additional functions that may be expected by other modules

def list_audio_devices():
    """Simple device listing function (alias for print_all_input_devices)."""
    print_all_input_devices()

def list_audio_devices_detailed():
    """Detailed audio device listing for menu systems using PyAudio."""
    try:
        print("\n" + "="*80)
        print("DETAILED AUDIO DEVICE INFORMATION (PyAudio)")
        print("="*80)
        
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        input_devices = [d for d in devices if d['is_input']]
        output_devices = [d for d in devices if d['is_output']]
        
        print(f"\nFound {len(input_devices)} input devices and {len(output_devices)} output devices")
        
        # Show input devices
        if input_devices:
            print("\nINPUT DEVICES:")
            print("-" * 60)
            for device in input_devices:
                print(f"[{device['index']}] {device['name']}")
                print(f"    API: {device['api']}")
                print(f"    Channels: {device['input_channels']}")
                print(f"    Default Sample Rate: {device['default_sample_rate']:.0f} Hz")
                
                # Test different configurations
                test_configs = [
                    (44100, 16, 1),
                    (44100, 16, 2),
                    (48000, 16, 2),
                    (96000, 24, 2)
                ]
                
                working_configs = []
                for sample_rate, bit_depth, channels in test_configs:
                    max_channels = min(channels, device['input_channels'])
                    if manager.test_device_configuration(device['index'], sample_rate, bit_depth, max_channels):
                        working_configs.append(f"{sample_rate}Hz/{bit_depth}bit/{max_channels}ch")
                
                if working_configs:
                    print(f"    Working configs: {', '.join(working_configs)}")
                else:
                    print("    ⚠ No standard configurations work")
                
                # Check if this device is currently configured
                try:
                    import modules.bmar_config as config
                    if hasattr(config, 'sound_in_id') and config.sound_in_id == device['index']:
                        print("    ★ CURRENTLY SELECTED")
                except:
                    pass
                
                print()
        
        # Show output devices (for reference)
        if output_devices:
            print("OUTPUT DEVICES:")
            print("-" * 60)
            for device in output_devices:
                print(f"[{device['index']}] {device['name']}")
                print(f"    API: {device['api']}")
                print(f"    Channels: {device['output_channels']}")
                print(f"    Default Sample Rate: {device['default_sample_rate']:.0f} Hz")
                print()
        
        # Show default devices
        try:
            default_input = manager.pa.get_default_input_device_info()
            default_output = manager.pa.get_default_output_device_info()
            print("SYSTEM DEFAULTS:")
            print("-" * 60)
            print(f"Default Input: [{default_input['index']}] {default_input['name']}")
            print(f"Default Output: [{default_output['index']}] {default_output['name']}")
        except:
            print("System default devices: Not available")
        
        print("\n" + "="*80)
        
    except Exception as e:
        logging.error(f"Error in detailed device listing: {e}")
        print(f"Error listing audio devices: {e}")

def sync_app_audio_attributes(app):
    """Sync app audio attributes from current configuration."""
    try:
        # Get current audio configuration
        config = get_current_audio_config(app)
        
        if config['device_id'] is not None:
            # Update app attributes with current config
            app.device_index = config['device_id']
            app.sound_in_id = config['device_id']
            app.samplerate = config['sample_rate']
            app.PRIMARY_IN_SAMPLERATE = config['sample_rate']
            app.channels = config['channels']
            app.sound_in_chs = config['channels']
            app._bit_depth = config['bit_depth']
            
            logging.info(f"App audio attributes synced: device={config['device_id']}, rate={config['sample_rate']}, channels={config['channels']}")
            return True
        else:
            logging.warning("No valid audio device available for sync")
            return False
            
    except Exception as e:
        logging.error(f"Error syncing app audio attributes: {e}")
        return False

def get_current_audio_config(app):
    """Get current audio configuration from app or detect best available."""
    try:
        # Check if app already has valid audio configuration
        if (hasattr(app, 'device_index') and app.device_index is not None and
            hasattr(app, 'samplerate') and hasattr(app, 'channels')):
            
            return {
                'device_id': app.device_index,  # ✅ This key exists
                'sample_rate': app.samplerate,
                'channels': app.channels,
                'bit_depth': getattr(app, '_bit_depth', 16)
            }
        
        # Try to detect a working audio device using the corrected function
        device_config = get_audio_device_config()
        
        # Fix the return from get_audio_device_config - it returns different structure
        if device_config and 'default_device' in device_config and device_config['default_device']:
            device = device_config['default_device']
            return {
                'device_id': device['index'],  # ✅ Use correct key mapping
                'sample_rate': int(device['default_sample_rate']),
                'channels': min(2, device['input_channels']),
                'bit_depth': 16
            }
        
        # Check if we're in a virtual/test environment
        if (hasattr(app, 'virtual_device') and app.virtual_device) or (hasattr(app, 'testmode') and app.testmode):
            logging.info("Using virtual device configuration")
            return {
                'device_id': None,  # Virtual device
                'sample_rate': getattr(app, 'samplerate', 44100),
                'channels': getattr(app, 'channels', 1),
                'bit_depth': getattr(app, '_bit_depth', 16),
                'virtual': True
            }
        
        # Fallback configuration for virtual devices
        logging.warning("Using fallback virtual audio configuration")
        return {
            'device_id': None,  # Virtual device
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }
        
    except Exception as e:
        logging.error(f"Error getting current audio config: {e}")
        # Emergency fallback
        return {
            'device_id': None,
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }

def ensure_valid_device_for_operation(app, operation_name="operation"):
    """Ensure we have a valid audio device for the requested operation."""
    try:
        # Check if we already have a configured device
        if hasattr(app, 'device_index') and app.device_index is not None:
            # Validate the existing device is still available
            try:
                device_info = get_audio_device_info(app.device_index)
                if device_info is not None:
                    return {
                        'device_id': app.device_index,
                        'sample_rate': getattr(app, 'samplerate', 44100),
                        'channels': getattr(app, 'channels', 1),
                        'bit_depth': getattr(app, '_bit_depth', 16)
                    }
            except Exception as e:
                logging.warning(f"Previously configured device {app.device_index} no longer available: {e}")
        
        # Try to find a working input device
        device_config = get_audio_device_config()
        
        # Fix: Check the correct structure that get_audio_device_config() returns
        if (device_config and 
            'default_device' in device_config and 
            device_config['default_device'] is not None):
            
            device = device_config['default_device']
            logging.info(f"Found working audio device {device['index']} for {operation_name}")
            return {
                'device_id': device['index'],
                'sample_rate': int(device['default_sample_rate']),
                'channels': min(2, device['input_channels']),
                'bit_depth': 16
            }
        
        # Check if we're in a virtual/test environment
        if (hasattr(app, 'virtual_device') and app.virtual_device) or (hasattr(app, 'testmode') and app.testmode):
            logging.info(f"Using virtual device configuration for {operation_name}")
            return {
                'device_id': None,  # Virtual device
                'sample_rate': getattr(app, 'samplerate', 44100),
                'channels': getattr(app, 'channels', 1),
                'bit_depth': getattr(app, '_bit_depth', 16),
                'virtual': True
            }
        
        # Fallback - create virtual device configuration
        logging.info(f"No real devices found, using virtual device for {operation_name}")
        return {
            'device_id': None,  # Virtual device
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }
        
    except Exception as e:
        logging.error(f"Error ensuring valid device for {operation_name}: {e}")
        # Return virtual device as emergency fallback
        return {
            'device_id': None,
            'sample_rate': 44100,
            'channels': 1,
            'bit_depth': 16,
            'virtual': True
        }

def get_audio_device_info(device_index):
    """Get information about a specific audio device."""
    try:
        import pyaudio
        
        pa = pyaudio.PyAudio()
        try:
            device_info = pa.get_device_info_by_index(device_index)
            return device_info
        finally:
            pa.terminate()
            
    except Exception as e:
        logging.debug(f"Error getting device info for index {device_index}: {e}")
        return None

def show_current_audio_devices(app):
    """Show current audio device configuration."""
    try:
        print("\nCurrent Audio Device Configuration:")
        print("-" * 40)
        
        if hasattr(app, 'device_index') and app.device_index is not None:
            # Show real device info
            device_info = get_audio_device_info(app.device_index)
            if device_info:
                print(f"Device ID: {app.device_index}")
                print(f"Device Name: {device_info.get('name', 'Unknown')}")
                print(f"Max Input Channels: {device_info.get('maxInputChannels', 0)}")
                print(f"Default Sample Rate: {device_info.get('defaultSampleRate', 'Unknown')} Hz")
            else:
                print(f"Device ID: {app.device_index} (device info not available)")
        else:
            print("Device: Virtual Device (No hardware)")
        
        print(f"Configured Sample Rate: {getattr(app, 'samplerate', 'Unknown')} Hz")
        print(f"Configured Channels: {getattr(app, 'channels', 'Unknown')}")
        print(f"Monitor Channel: {getattr(app, 'monitor_channel', 0) + 1}")
        print(f"Block Size: {getattr(app, 'blocksize', 'Unknown')}")
        
        if hasattr(app, 'virtual_device') and app.virtual_device:
            print("\nNote: Running with virtual audio device")
            print("This is normal in WSL or systems without audio hardware")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"Error showing current audio devices: {e}")

def show_detailed_device_list(app):
    """Show detailed list of all available audio devices."""
    try:
        import pyaudio
        
        print("Scanning for audio devices...")
        
        pa = pyaudio.PyAudio()
        try:
            device_count = pa.get_device_count()
            
            if device_count == 0:
                print("No audio devices found")
                return
            
            print(f"Found {device_count} audio device(s):")
            print()
            
            for i in range(device_count):
                try:
                    device_info = pa.get_device_info_by_index(i)
                    
                    print(f"Device {i}:")
                    print(f"  Name: {device_info.get('name', 'Unknown')}")
                    print(f"  Max Input Channels: {device_info.get('maxInputChannels', 0)}")
                    print(f"  Max Output Channels: {device_info.get('maxOutputChannels', 0)}")
                    print(f"  Default Sample Rate: {device_info.get('defaultSampleRate', 0):.0f} Hz")
                    
                    # Test if device can be used for input
                    if device_info.get('maxInputChannels', 0) > 0:
                        try:
                            # Quick test to see if device is accessible
                            test_stream = pa.open(
                                format=pyaudio.paInt16,
                                channels=1,
                                rate=int(device_info.get('defaultSampleRate', 44100)),
                                input=True,
                                input_device_index=i,
                                frames_per_buffer=1024
                            )
                            test_stream.close()
                            print(f"  Status: ✓ Available for input")
                        except Exception as e:
                            print(f"  Status: ✗ Not available ({str(e)[:50]}...)")
                    else:
                        print(f"  Status: Output only")
                    
                    print()
                    
                except Exception as e:
                    print(f"Device {i}: Error getting info - {e}")
                    print()
        
        finally:
            pa.terminate()
            
    except Exception as e:
        print(f"Error listing audio devices: {e}")
        print("\nNote: This may be normal in WSL or headless environments")
        
        # Show virtual device info as fallback
        if hasattr(app, 'virtual_device') and app.virtual_device:
            print("\nVirtual Device Configuration:")
            print("  Name: Virtual Audio Device")
            print("  Channels: 1 (synthetic)")
            print("  Sample Rate: 44100 Hz")
            print("  Status: ✓ Available (virtual)")
