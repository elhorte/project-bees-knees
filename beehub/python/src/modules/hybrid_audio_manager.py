"""
Hybrid Audio Manager for BMAR
Demonstration of integration between existing audio_devices.py and class_PyAudio.py

This module shows how to progressively enhance the existing BMAR audio system
without breaking existing functionality.
"""

import logging
from typing import Dict, List, Optional, Tuple
from .enhanced_audio_manager import EnhancedAudioManager
from . import audio_devices as existing_audio


class HybridAudioManager:
    """
    Hybrid manager that gradually integrates AudioPortManager capabilities
    into the existing BMAR audio system.
    
    Strategy:
    1. Keep existing sounddevice-based functions working
    2. Add enhanced discovery and testing on top
    3. Provide fallback mechanisms
    4. Allow progressive adoption
    """
    
    def __init__(self, app):
        self.app = app
        self.enhanced_manager = None
        self.use_enhanced = True
        
        # Try to initialize enhanced manager
        try:
            self.enhanced_manager = EnhancedAudioManager(
                target_sample_rate=getattr(app, 'samplerate', 44100),
                target_bit_depth=getattr(app, 'bit_depth', 16)
            )
            logging.info("Hybrid audio manager initialized with enhanced capabilities")
        except Exception as e:
            logging.warning(f"Enhanced manager not available, using basic mode: {e}")
            self.use_enhanced = False
    
    def set_input_device_enhanced(self) -> bool:
        """
        Enhanced version of set_input_device that combines old and new approaches.
        
        Falls back to original implementation if enhanced fails.
        """
        # Try enhanced approach first
        if self.use_enhanced and self.enhanced_manager:
            try:
                logging.info("Attempting enhanced device configuration...")
                
                # Use enhanced hierarchical strategy
                success = self.enhanced_manager.configure_for_bmar(self.app)
                
                if success:
                    logging.info("Enhanced device configuration successful")
                    return True
                else:
                    logging.warning("Enhanced configuration failed, falling back to original")
            
            except Exception as e:
                logging.error(f"Enhanced configuration error: {e}")
                logging.info("Falling back to original device configuration")
        
        # Fall back to original implementation
        logging.info("Using original device configuration method")
        return existing_audio.set_input_device(self.app)
    
    def get_device_list_enhanced(self, show_enhanced_info: bool = True) -> List[Dict]:
        """
        Get device list with optional enhanced information.
        
        Args:
            show_enhanced_info: Include PyAudio verification and capabilities
            
        Returns:
            List of device dictionaries
        """
        if self.use_enhanced and self.enhanced_manager and show_enhanced_info:
            try:
                return self.enhanced_manager.get_enhanced_device_list()
            except Exception as e:
                logging.warning(f"Enhanced device list failed: {e}")
        
        # Fall back to basic sounddevice listing
        import sounddevice as sd
        devices = []
        
        try:
            sd_devices = sd.query_devices()
            for i, device in enumerate(sd_devices):
                if device['max_input_channels'] > 0:
                    try:
                        hostapi_info = sd.query_hostapis(index=device['hostapi'])
                        devices.append({
                            'index': i,
                            'name': device['name'],
                            'input_channels': device['max_input_channels'],
                            'output_channels': device['max_output_channels'],
                            'default_sample_rate': device['default_samplerate'],
                            'api': hostapi_info['name'],
                            'is_input': True,
                            'source': 'sounddevice_fallback'
                        })
                    except Exception as e:
                        logging.debug(f"Error processing device {i}: {e}")
        
        except Exception as e:
            logging.error(f"Error getting device list: {e}")
        
        return devices
    
    def show_device_list_enhanced(self, detailed: bool = False):
        """
        Show enhanced device list with better formatting and additional info.
        
        Args:
            detailed: Show detailed capability information
        """
        if self.use_enhanced and self.enhanced_manager:
            try:
                self.enhanced_manager.print_enhanced_device_list(show_capabilities=detailed)
                return
            except Exception as e:
                logging.warning(f"Enhanced device list display failed: {e}")
        
        # Fall back to existing display
        print("\nAudio Device List (Basic Mode):")
        print("=" * 50)
        existing_audio.print_all_input_devices()
    
    def test_device_configuration_enhanced(self, device_index: int, 
                                         sample_rate: int, channels: int = 2) -> bool:
        """
        Test device configuration with enhanced validation.
        
        Args:
            device_index: Device to test
            sample_rate: Target sample rate
            channels: Number of channels
            
        Returns:
            True if configuration is supported
        """
        if self.use_enhanced and self.enhanced_manager:
            try:
                # Try enhanced testing first (PyAudio + sounddevice)
                result = self.enhanced_manager.test_device_capability(
                    device_index, sample_rate, channels, use_pyaudio=True
                )
                
                if result:
                    logging.debug(f"Enhanced test passed for device {device_index}")
                    return True
                else:
                    logging.debug(f"Enhanced test failed for device {device_index}")
            
            except Exception as e:
                logging.debug(f"Enhanced test error for device {device_index}: {e}")
        
        # Fall back to basic sounddevice test
        try:
            import sounddevice as sd
            with sd.InputStream(device=device_index, channels=channels,
                              samplerate=sample_rate, dtype='float32',
                              blocksize=1024) as stream:
                return True
        except Exception as e:
            logging.debug(f"Basic test failed for device {device_index}: {e}")
            return False
    
    def get_api_priority_list(self) -> List[str]:
        """Get the API priority list for device selection."""
        if self.use_enhanced and self.enhanced_manager:
            return self.enhanced_manager.api_priority
        else:
            return ['WASAPI', 'DirectSound', 'MME']  # Default Windows priority
    
    def configure_with_api_fallback(self, preferred_apis: List[str] = None) -> bool:
        """
        Configure device using API fallback strategy.
        
        Args:
            preferred_apis: List of APIs to try in order
            
        Returns:
            True if successfully configured
        """
        if preferred_apis is None:
            preferred_apis = self.get_api_priority_list()
        
        devices = self.get_device_list_enhanced()
        channels = getattr(self.app, 'channels', 2)
        target_rate = getattr(self.app, 'samplerate', 44100)
        
        for api in preferred_apis:
            logging.info(f"Trying {api} devices...")
            
            # Filter devices by API
            api_devices = [d for d in devices if api.upper() in d['api'].upper()]
            
            for device in api_devices:
                device_index = device['index']
                
                logging.info(f"Testing device [{device_index}]: {device['name']}")
                
                # Test the device
                if self.test_device_configuration_enhanced(device_index, target_rate, channels):
                    # Configure the app
                    self.app.device_index = device_index
                    self.app.samplerate = target_rate
                    self.app.api_name = device['api']
                    
                    logging.info(f"Successfully configured {api} device:")
                    logging.info(f"  [{device_index}] {device['name']}")
                    logging.info(f"  Sample Rate: {target_rate}Hz")
                    logging.info(f"  Channels: {channels}")
                    
                    return True
                else:
                    logging.debug(f"Device {device_index} failed configuration test")
        
        logging.error("No devices could be configured with API fallback strategy")
        return False
    
    def get_device_capabilities_report(self, device_index: int) -> Dict:
        """
        Get comprehensive device capabilities report.
        
        Args:
            device_index: Device to analyze
            
        Returns:
            Capabilities dictionary
        """
        if self.use_enhanced and self.enhanced_manager:
            try:
                return self.enhanced_manager.get_device_capabilities(device_index)
            except Exception as e:
                logging.error(f"Enhanced capabilities test failed: {e}")
        
        # Basic capabilities test
        import sounddevice as sd
        
        capabilities = {
            'device_index': device_index,
            'supported_rates': [],
            'basic_test_only': True
        }
        
        try:
            device = sd.query_devices(device_index)
            capabilities['name'] = device['name']
            capabilities['default_sample_rate'] = device['default_samplerate']
            capabilities['max_input_channels'] = device['max_input_channels']
            
            # Test a few common rates
            test_rates = [44100, 48000, 96000]
            for rate in test_rates:
                try:
                    with sd.InputStream(device=device_index, channels=2,
                                      samplerate=rate, dtype='float32',
                                      blocksize=1024) as stream:
                        capabilities['supported_rates'].append(rate)
                except:
                    pass
        
        except Exception as e:
            logging.error(f"Basic capabilities test failed: {e}")
        
        return capabilities
    
    def cleanup(self):
        """Clean up resources."""
        if self.enhanced_manager:
            self.enhanced_manager.cleanup()


# Wrapper functions to gradually replace existing audio_devices.py functions

def set_input_device_hybrid(app) -> bool:
    """
    Drop-in replacement for audio_devices.set_input_device() with enhanced capabilities.
    
    Args:
        app: BMAR application object
        
    Returns:
        True if device configured successfully
    """
    manager = HybridAudioManager(app)
    try:
        return manager.set_input_device_enhanced()
    finally:
        manager.cleanup()

def show_detailed_device_list_hybrid(app, show_capabilities: bool = False):
    """
    Enhanced version of show_detailed_device_list with better information.
    
    Args:
        app: BMAR application object
        show_capabilities: Include capability testing
    """
    manager = HybridAudioManager(app)
    try:
        manager.show_device_list_enhanced(detailed=show_capabilities)
    finally:
        manager.cleanup()

def test_device_configuration_hybrid(app, device_index: int, 
                                   sample_rate: int, channels: int = 2) -> bool:
    """
    Enhanced device configuration testing.
    
    Args:
        app: BMAR application object
        device_index: Device to test
        sample_rate: Target sample rate
        channels: Number of channels
        
    Returns:
        True if configuration is supported
    """
    manager = HybridAudioManager(app)
    try:
        return manager.test_device_configuration_enhanced(device_index, sample_rate, channels)
    finally:
        manager.cleanup()

def configure_with_api_hierarchy(app, preferred_apis: List[str] = None) -> bool:
    """
    Configure audio device using hierarchical API strategy.
    
    Args:
        app: BMAR application object
        preferred_apis: List of APIs to try in order
        
    Returns:
        True if successfully configured
    """
    manager = HybridAudioManager(app)
    try:
        return manager.configure_with_api_fallback(preferred_apis)
    finally:
        manager.cleanup()

# Migration helpers for existing code

def migrate_to_hybrid_gradually():
    """
    Guide for gradually migrating existing BMAR audio code to hybrid approach.
    
    Migration steps:
    1. Replace set_input_device() calls with set_input_device_hybrid()
    2. Use show_detailed_device_list_hybrid() for better device display
    3. Add test_device_configuration_hybrid() for validation
    4. Eventually use configure_with_api_hierarchy() for full enhancement
    """
    migration_guide = """
    Gradual Migration Guide:
    
    Step 1 - Drop-in replacement:
    OLD: from .audio_devices import set_input_device
         success = set_input_device(app)
    
    NEW: from .hybrid_audio_manager import set_input_device_hybrid
         success = set_input_device_hybrid(app)
    
    Step 2 - Enhanced device listing:
    OLD: from .audio_devices import show_detailed_device_list
         show_detailed_device_list(app)
    
    NEW: from .hybrid_audio_manager import show_detailed_device_list_hybrid
         show_detailed_device_list_hybrid(app, show_capabilities=True)
    
    Step 3 - API hierarchy configuration:
    NEW: from .hybrid_audio_manager import configure_with_api_hierarchy
         success = configure_with_api_hierarchy(app, ['WASAPI', 'DirectSound'])
    
    Benefits at each step:
    - Step 1: Better error handling and fallback
    - Step 2: More informative device information
    - Step 3: Intelligent API selection and testing
    """
    
    print(migration_guide)
    return migration_guide
