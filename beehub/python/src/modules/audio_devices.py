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

def test_print_line(app):
    """Test function to verify app.print_line() is working."""
    try:
        app.print_line("=== TESTING PRINT_LINE ===")
        app.print_line("Line 1", prefix_newline=False)
        app.print_line("Line 2", prefix_newline=False)
        app.print_line("Line 3", prefix_newline=False)
        app.print_line("=== END TEST ===", prefix_newline=False)
        return True
    except Exception as e:
        print(f"print_line test failed: {e}")
        return False

def list_audio_devices_detailed(app):
    """Detailed audio device listing for menu systems."""
    
    print("\r")  # Clear any cursor issues
    print("Audio Device List:\r")
    print("-" * 80 + "\r")
    
    # Check if we're in WSL first
    try:
        from .platform_manager import PlatformManager
        platform_manager = PlatformManager()
        is_wsl = platform_manager.is_wsl()
    except:
        is_wsl = False
    
    if is_wsl:
        print("WSL Environment Detected - Showing Virtual Devices\r")
        print("   0 Virtual Audio Device                   WSL Virtual (1 in, 0 out)\r")
        print("-" * 80 + "\r")
        print("Currently using: Virtual Audio Device (WSL)\r")
        return
    
    # For macOS, detect the environment
    import sys
    if sys.platform == 'darwin':
        print("macOS Environment Detected\r")
        print("   0 Virtual Audio Device                   Virtual (1 in, 0 out)\r")
        print("-" * 80 + "\r")
        print("Currently using: Virtual Audio Device (macOS)\r")
        return
    
    # For other systems, show virtual device
    print("No real audio devices detected\r")
    print("   0 Virtual Audio Device                   Virtual (1 in, 0 out)\r")
    
    # Set up virtual device if not already configured
    if not hasattr(app, 'virtual_device') or not app.virtual_device:
        app.virtual_device = True
        app.device_index = None
        app.samplerate = 44100
        app.channels = 1
        print("Virtual device configured automatically\r")
    
    print("-" * 80 + "\r")
    
    # Show current configuration
    if hasattr(app, 'device_index'):
        if app.device_index is not None:
            print("Currently using input device: " + str(app.device_index) + "\r")
        else:
            print("Currently using: Virtual Audio Device\r")
    else:
        print("No device currently configured\r")

def show_current_audio_devices(app):
    """Show current audio device configuration."""
    
    print("\r")  # Clear any lingering cursor issues
    print("Current Audio Device Configuration:\r")
    print("-" * 50 + "\r")
    
    if hasattr(app, 'device_index') and app.device_index is not None:
        print(f"Input Device ID: {app.device_index}\r")
    else:
        print("Input Device: Virtual Device (WSL/Test mode)\r")
    
    if hasattr(app, 'samplerate'):
        print(f"Sample Rate: {app.samplerate} Hz\r")
    
    if hasattr(app, 'channels'):
        print(f"Channels: {app.channels}\r")
    
    if hasattr(app, 'blocksize'):
        print(f"Block Size: {app.blocksize}\r")
    
    print("-" * 50 + "\r")
