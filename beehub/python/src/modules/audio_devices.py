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

def get_device_list() -> List[Dict]:
    """Get a list of all audio devices."""
    try:
        manager = AudioPortManager()
        return manager.list_audio_devices()
    except Exception as e:
        logging.error(f"Error getting device list: {e}")
        return []

def get_input_device_list() -> List[Dict]:
    """Get a list of input audio devices only."""
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        return [d for d in devices if d['is_input']]
    except Exception as e:
        logging.error(f"Error getting input device list: {e}")
        return []

def show_current_audio_devices(app=None):
    """Show current audio device configuration and status."""
    try:
        print("\n" + "="*60)
        print("CURRENT AUDIO DEVICE STATUS")
        print("="*60)
        
        manager = AudioPortManager()
        
        # Try to get current configuration from different sources
        current_device_id = None
        current_sample_rate = None
        current_channels = None
        
        # Method 1: Try to get from app parameter (if provided)
        if app is not None:
            try:
                if hasattr(app, 'sound_in_id'):
                    current_device_id = app.sound_in_id
                if hasattr(app, 'PRIMARY_IN_SAMPLERATE'):
                    current_sample_rate = app.PRIMARY_IN_SAMPLERATE
                if hasattr(app, 'sound_in_chs'):
                    current_channels = app.sound_in_chs
            except:
                pass
        
        # Method 2: Try to get from bmar_config (fallback)
        if current_device_id is None:
            try:
                import modules.bmar_config as config
                if hasattr(config, 'sound_in_id'):
                    current_device_id = config.sound_in_id
                if hasattr(config, 'PRIMARY_IN_SAMPLERATE'):
                    current_sample_rate = config.PRIMARY_IN_SAMPLERATE
                if hasattr(config, 'CHANNELS'):
                    current_channels = config.CHANNELS
            except:
                pass
        
        # Method 3: Try to get from app instance (if available globally)
        if current_device_id is None:
            try:
                import modules.bmar_app as app_module
                if hasattr(app_module, 'app_instance') and app_module.app_instance:
                    app_inst = app_module.app_instance
                    if hasattr(app_inst, 'sound_in_id'):
                        current_device_id = app_inst.sound_in_id
                    if hasattr(app_inst, 'PRIMARY_IN_SAMPLERATE'):
                        current_sample_rate = app_inst.PRIMARY_IN_SAMPLERATE
                    if hasattr(app_inst, 'sound_in_chs'):
                        current_channels = app_inst.sound_in_chs
            except:
                pass
        
        # Show current configuration
        if current_device_id is not None:
            print(f"Currently configured device: {current_device_id}")
            
            # Get device details
            devices = manager.list_audio_devices()
            current_device = None
            for device in devices:
                if device['index'] == current_device_id:
                    current_device = device
                    break
            
            if current_device:
                print(f"Device name: {current_device['name']}")
                print(f"API: {current_device['api']}")
                print(f"Max input channels: {current_device['input_channels']}")
                print(f"Default sample rate: {current_device['default_sample_rate']:.0f} Hz")
                
                if current_sample_rate:
                    print(f"Configured sample rate: {current_sample_rate} Hz")
                if current_channels:
                    print(f"Configured channels: {current_channels}")
                
                # Test current configuration
                test_channels = current_channels or min(2, current_device['input_channels'])
                test_sample_rate = current_sample_rate or 44100
                
                is_working = manager.test_device_configuration(
                    current_device_id, test_sample_rate, 16, test_channels
                )
                
                status = "✓ WORKING" if is_working else "⚠ ISSUES DETECTED"
                print(f"Status: {status}")
                
                if not is_working:
                    print("  Note: Current configuration may have problems")
                    print("  Try reconfiguring audio device if experiencing issues")
                
                # Show additional app-specific info if app is provided
                if app is not None:
                    try:
                        testmode = getattr(app, 'testmode', None)
                        if testmode is not None:
                            mode_status = "TEST MODE" if testmode else "NORMAL MODE"
                            print(f"Application mode: {mode_status}")
                    except:
                        pass
                        
            else:
                print(f"⚠ Device {current_device_id} not found in current system")
                print("  Device may have been disconnected or changed")
        else:
            print("No audio device currently configured")
            print("Run audio device configuration to set up audio input")
        
        print()
        
        # Show system defaults for reference
        try:
            default_input = manager.pa.get_default_input_device_info()
            print("System default input device:")
            print(f"  [{default_input['index']}] {default_input['name']}")
            print(f"  API: {default_input.get('hostApi', 'Unknown')}")
        except:
            print("System default input: Not available")
        
        print("="*60)
        
    except Exception as e:
        logging.error(f"Error showing current audio devices: {e}")
        print(f"Error displaying current audio device status: {e}")

def show_audio_device_status(app=None):
    """Alias for show_current_audio_devices (for compatibility)."""
    show_current_audio_devices(app)

def show_detailed_device_list(app=None):
    """Show detailed device list for menu systems (alias for list_audio_devices_detailed)."""
    try:
        # Call the existing detailed listing function
        list_audio_devices_detailed()
        
        # Add some additional context if app is provided
        if app is not None:
            print("\nCURRENT APPLICATION SETTINGS:")
            print("-" * 40)
            try:
                if hasattr(app, 'sound_in_id'):
                    print(f"Selected device ID: {app.sound_in_id}")
                if hasattr(app, 'PRIMARY_IN_SAMPLERATE'):
                    print(f"Sample rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
                if hasattr(app, 'sound_in_chs'):
                    print(f"Channels: {app.sound_in_chs}")
                if hasattr(app, 'testmode'):
                    mode = "TEST MODE" if app.testmode else "NORMAL MODE"
                    print(f"Mode: {mode}")
            except Exception as e:
                print(f"Could not read app settings: {e}")
            print("-" * 40)
        
    except Exception as e:
        logging.error(f"Error in detailed device list: {e}")
        print(f"Error showing detailed device list: {e}")

def show_device_list_detailed(app=None):
    """Alternative alias for show_detailed_device_list (for compatibility)."""
    show_detailed_device_list(app)

def display_detailed_device_info(app=None):
    """Another alias for show_detailed_device_list (for compatibility)."""
    show_detailed_device_list(app)

def ensure_valid_device_for_operation(app=None, operation_name="audio operation"):
    """Ensure we have a valid device before starting an audio operation."""
    try:
        config = get_current_audio_config(app)
        
        if config['device_id'] is None:
            print(f"No audio device configured for {operation_name}")
            print("Attempting to configure a device automatically...")
            
            # Try to auto-configure
            if app is not None:
                success = configure_audio_with_fallback(app)
                if success:
                    config = get_current_audio_config(app)
                    print(f"Auto-configured device {config['device_id']} for {operation_name}")
                    return config
            
            # Manual fallback
            device_id = get_current_audio_device_id(app)
            if device_id is not None:
                config['device_id'] = device_id
                print(f"Using device {device_id} for {operation_name}")
                return config
            
            print(f"Failed to configure audio device for {operation_name}")
            return None
        
        # Validate the existing configuration
        is_valid, message = validate_audio_config_for_recording(app)
        if is_valid:
            return config
        else:
            print(f"Current audio configuration invalid for {operation_name}: {message}")
            return None
            
    except Exception as e:
        logging.error(f"Error ensuring valid device for {operation_name}: {e}")
        print(f"Error configuring audio for {operation_name}: {e}")
        return None

def sync_app_audio_attributes(app):
    """Synchronize audio attributes between different naming conventions in the app."""
    try:
        # Get current audio configuration
        config = get_current_audio_config(app)
        
        if config['device_id'] is not None:
            # Map sound_in_id to device_index for compatibility
            app.device_index = config['device_id']
            app.sound_in_id = config['device_id']
            
            # Map sample rate
            app.samplerate = config['sample_rate']
            app.PRIMARY_IN_SAMPLERATE = config['sample_rate']
            
            # Map channels
            app.channels = config['channels']
            app.sound_in_chs = config['channels']
            
            # Set bit depth
            app._bit_depth = config['bit_depth']
            
            # Ensure other required attributes exist
            if not hasattr(app, 'blocksize'):
                app.blocksize = 1024
                
            if not hasattr(app, 'monitor_channel'):
                app.monitor_channel = 0
                
            if not hasattr(app, 'testmode'):
                app.testmode = False
                
            # Ensure monitor channel is within bounds
            if app.monitor_channel >= app.channels:
                app.monitor_channel = 0
                
            logging.info(f"App audio attributes synchronized: device={app.device_index}, rate={app.samplerate}, channels={app.channels}")
            return True
        else:
            logging.warning("Cannot sync app audio attributes - no valid device configured")
            return False
            
    except Exception as e:
        logging.error(f"Error syncing app audio attributes: {e}")
        return False

def get_current_audio_device_id(app=None):
    """Get the current audio device ID, trying multiple sources."""
    try:
        # Method 1: Try from app parameter
        if app is not None:
            if hasattr(app, 'sound_in_id') and app.sound_in_id is not None:
                return app.sound_in_id
        
        # Method 2: Try from bmar_config
        try:
            import modules.bmar_config as config
            if hasattr(config, 'sound_in_id') and config.sound_in_id is not None:
                return config.sound_in_id
        except:
            pass
        
        # Method 3: Try from global app instance
        try:
            import modules.bmar_app as app_module
            if hasattr(app_module, 'app_instance') and app_module.app_instance:
                app_inst = app_module.app_instance
                if hasattr(app_inst, 'sound_in_id') and app_inst.sound_in_id is not None:
                    return app_inst.sound_in_id
        except:
            pass
        
        # Method 4: Try to get system default and validate it
        try:
            manager = AudioPortManager()
            default_input = manager.pa.get_default_input_device_info()
            device_id = default_input['index']
            
            # Validate the default device works
            if manager.test_device_configuration(device_id, 44100, 16, 2):
                logging.info(f"Using system default device {device_id} for oscilloscope")
                return device_id
        except:
            pass
        
        # Method 5: Find first working input device
        try:
            manager = AudioPortManager()
            devices = manager.list_audio_devices()
            input_devices = [d for d in devices if d['is_input']]
            
            for device in input_devices:
                if manager.test_device_configuration(device['index'], 44100, 16, 2):
                    logging.info(f"Using first available device {device['index']} for oscilloscope")
                    return device['index']
        except:
            pass
        
        logging.error("No suitable audio device found for oscilloscope")
        return None
        
    except Exception as e:
        logging.error(f"Error getting current audio device ID: {e}")
        return None

def get_current_audio_config(app=None):
    """Get current audio configuration for functions that need it."""
    try:
        config = {
            'device_id': None,
            'sample_rate': 44100,
            'channels': 2,
            'bit_depth': 16
        }
        
        # Get device ID
        config['device_id'] = get_current_audio_device_id(app)
        
        # Get other parameters
        if app is not None:
            try:
                if hasattr(app, 'PRIMARY_IN_SAMPLERATE'):
                    config['sample_rate'] = app.PRIMARY_IN_SAMPLERATE
                if hasattr(app, 'sound_in_chs'):
                    config['channels'] = app.sound_in_chs
                if hasattr(app, '_bit_depth'):
                    config['bit_depth'] = app._bit_depth
            except:
                pass
        
        # Fallback to config module
        if config['device_id'] is None or config['sample_rate'] == 44100:
            try:
                import modules.bmar_config as bmar_config
                if hasattr(bmar_config, 'PRIMARY_IN_SAMPLERATE'):
                    config['sample_rate'] = bmar_config.PRIMARY_IN_SAMPLERATE
                if hasattr(bmar_config, 'CHANNELS'):
                    config['channels'] = bmar_config.CHANNELS
                if hasattr(bmar_config, 'BIT_DEPTH'):
                    config['bit_depth'] = bmar_config.BIT_DEPTH
            except:
                pass
        
        return config
        
    except Exception as e:
        logging.error(f"Error getting current audio config: {e}")
        return {
            'device_id': None,
            'sample_rate': 44100,
            'channels': 2,
            'bit_depth': 16
        }

def validate_audio_config_for_recording(app=None):
    """Validate that audio configuration is suitable for recording."""
    try:
        config = get_current_audio_config(app)
        
        if config['device_id'] is None:
            return False, "No audio device configured"
        
        manager = AudioPortManager()
        
        # Test the configuration
        is_working = manager.test_device_configuration(
            config['device_id'], 
            config['sample_rate'], 
            config['bit_depth'], 
            config['channels']
        )
        
        if is_working:
            return True, "Audio configuration is valid"
        else:
            return False, f"Device {config['device_id']} failed configuration test"
            
    except Exception as e:
        return False, f"Error validating audio config: {e}"
