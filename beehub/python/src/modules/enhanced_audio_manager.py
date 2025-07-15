"""
Enhanced Audio Manager for BMAR
Combines the best of sounddevice and AudioPortManager for improved audio reliability.

Integration Points Analysis:
1. Device Discovery & Enumeration
2. Configuration Testing & Validation  
3. Hierarchical API Fallback Strategy
4. Real-time Device Capability Testing
5. Adaptive Configuration Management
"""

import sounddevice as sd
import logging
import sys
import time
from typing import List, Dict, Optional, Tuple, Union
from .class_PyAudio import AudioPortManager

class EnhancedAudioManager:
    """
    Hybrid audio manager that combines sounddevice simplicity with PyAudio robustness.
    
    Key Integration Points:
    - Device discovery: Uses AudioPortManager for comprehensive enumeration
    - Primary audio ops: Uses sounddevice for simplicity and performance
    - Fallback testing: Uses PyAudio for deep compatibility validation
    - API hierarchy: Implements WASAPI → DirectSound → MME strategy
    """
    
    def __init__(self, target_sample_rate: int = 44100, target_bit_depth: int = 16):
        self.target_sample_rate = target_sample_rate
        self.target_bit_depth = target_bit_depth
        
        # Initialize PyAudio manager for advanced device testing
        self.pyaudio_manager = None
        self._pyaudio_available = False
        
        # Try to initialize PyAudio manager
        try:
            self.pyaudio_manager = AudioPortManager(target_sample_rate, target_bit_depth)
            self._pyaudio_available = True
            logging.info("PyAudio AudioPortManager initialized successfully")
        except Exception as e:
            logging.warning(f"PyAudio AudioPortManager not available: {e}")
        
        # API priority order for Windows
        self.api_priority = ['WASAPI', 'DirectSound', 'MME']
        
        # Device cache for performance
        self._device_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = 30  # Cache devices for 30 seconds
    
    def get_enhanced_device_list(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get comprehensive device list using both sounddevice and PyAudio.
        
        Args:
            force_refresh: Force refresh of device cache
            
        Returns:
            List of enhanced device dictionaries with additional metadata
        """
        current_time = time.time()
        
        # Check cache validity
        if not force_refresh and (current_time - self._cache_timestamp) < self._cache_ttl:
            if self._device_cache:
                return self._device_cache['devices']
        
        devices = []
        
        # Get base device list from sounddevice
        try:
            sd_devices = sd.query_devices()
            
            for i, device in enumerate(sd_devices):
                # Get host API info
                try:
                    hostapi_info = sd.query_hostapis(index=device['hostapi'])
                    api_name = hostapi_info['name']
                except:
                    api_name = 'Unknown'
                
                # Create enhanced device dict
                enhanced_device = {
                    'index': i,
                    'name': device['name'],
                    'input_channels': device['max_input_channels'],
                    'output_channels': device['max_output_channels'],
                    'default_sample_rate': device['default_samplerate'],
                    'api': api_name,
                    'hostapi_index': device['hostapi'],
                    'is_input': device['max_input_channels'] > 0,
                    'is_output': device['max_output_channels'] > 0,
                    'source': 'sounddevice',
                    'verified': False,
                    'supported_rates': [],
                    'capabilities_tested': False
                }
                
                devices.append(enhanced_device)
                
        except Exception as e:
            logging.error(f"Error getting sounddevice device list: {e}")
        
        # Enhance with PyAudio data if available
        if self._pyaudio_available and self.pyaudio_manager:
            try:
                pyaudio_devices = self.pyaudio_manager.list_audio_devices()
                
                # Cross-reference and enhance devices
                for device in devices:
                    # Find matching PyAudio device by name
                    matching_pyaudio = None
                    for pa_device in pyaudio_devices:
                        if self._devices_match(device, pa_device):
                            matching_pyaudio = pa_device
                            break
                    
                    if matching_pyaudio:
                        device['pyaudio_index'] = matching_pyaudio['index']
                        device['pyaudio_verified'] = True
                        device['source'] = 'hybrid'
                    
            except Exception as e:
                logging.warning(f"Error enhancing with PyAudio data: {e}")
        
        # Update cache
        self._device_cache = {
            'devices': devices,
            'timestamp': current_time
        }
        self._cache_timestamp = current_time
        
        return devices
    
    def _devices_match(self, sd_device: Dict, pa_device: Dict) -> bool:
        """Check if sounddevice and PyAudio devices represent the same hardware."""
        # Simple name-based matching (could be enhanced with more sophisticated logic)
        sd_name = sd_device['name'].lower().strip()
        pa_name = pa_device['name'].lower().strip()
        
        # Check for exact match
        if sd_name == pa_name:
            return True
        
        # Check if one name contains the other
        if sd_name in pa_name or pa_name in sd_name:
            return True
        
        return False
    
    def test_device_capability(self, device_index: int, sample_rate: int, 
                              channels: int = 2, use_pyaudio: bool = False) -> bool:
        """
        Test if a device supports specific configuration.
        
        Args:
            device_index: Device index to test
            sample_rate: Target sample rate
            channels: Number of channels
            use_pyaudio: Use PyAudio for testing (more reliable but slower)
            
        Returns:
            True if configuration is supported
        """
        # Try PyAudio testing first if available and requested
        if use_pyaudio and self._pyaudio_available and self.pyaudio_manager:
            try:
                return self.pyaudio_manager.test_device_configuration(
                    device_index, sample_rate, self.target_bit_depth, channels
                )
            except Exception as e:
                logging.debug(f"PyAudio test failed for device {device_index}: {e}")
        
        # Fall back to sounddevice testing
        try:
            with sd.InputStream(device=device_index, channels=channels,
                              samplerate=sample_rate, dtype='float32',
                              blocksize=1024) as stream:
                # Just test if we can open the stream
                return True
        except Exception as e:
            logging.debug(f"Sounddevice test failed for device {device_index}: {e}")
            return False
    
    def find_best_device(self, preferred_api: str = None, 
                        channels: int = 2) -> Tuple[bool, Optional[Dict], Optional[int]]:
        """
        Find the best available input device using hierarchical strategy.
        
        Args:
            preferred_api: Preferred audio API (overrides hierarchy)
            channels: Required number of channels
            
        Returns:
            Tuple of (success, device_info, achieved_sample_rate)
        """
        devices = self.get_enhanced_device_list()
        input_devices = [d for d in devices if d['is_input'] and d['input_channels'] >= channels]
        
        if not input_devices:
            logging.error("No suitable input devices found")
            return False, None, None
        
        # If preferred API specified, try those first
        if preferred_api:
            api_devices = [d for d in input_devices if preferred_api.upper() in d['api'].upper()]
            if api_devices:
                for device in api_devices:
                    if self._test_device_thoroughly(device, channels):
                        return True, device, self.target_sample_rate
        
        # Use hierarchical API strategy for Windows
        for api in self.api_priority:
            api_devices = [d for d in input_devices if api.upper() in d['api'].upper()]
            
            if api_devices:
                logging.info(f"Trying {api} devices...")
                
                for device in api_devices:
                    if self._test_device_thoroughly(device, channels):
                        logging.info(f"Successfully configured {api} device: {device['name']}")
                        return True, device, self.target_sample_rate
        
        # If all else fails, try any remaining devices
        logging.warning("Hierarchical strategy failed, trying all remaining devices...")
        for device in input_devices:
            if self._test_device_thoroughly(device, channels):
                logging.info(f"Configured fallback device: {device['name']}")
                return True, device, self.target_sample_rate
        
        return False, None, None
    
    def _test_device_thoroughly(self, device: Dict, channels: int) -> bool:
        """
        Thoroughly test a device with multiple approaches.
        
        Args:
            device: Device dictionary to test
            channels: Number of channels to test
            
        Returns:
            True if device passes all tests
        """
        device_index = device['index']
        
        # Test 1: Try target configuration
        if self.test_device_capability(device_index, self.target_sample_rate, channels):
            logging.debug(f"Device {device_index} supports target config")
            return True
        
        # Test 2: Try with PyAudio if available (more thorough)
        if self._pyaudio_available:
            if self.test_device_capability(device_index, self.target_sample_rate, 
                                         channels, use_pyaudio=True):
                logging.debug(f"Device {device_index} supports target config (PyAudio)")
                return True
        
        # Test 3: Try common fallback rates
        fallback_rates = [44100, 48000, 22050, 16000]
        for rate in fallback_rates:
            if rate != self.target_sample_rate:
                if self.test_device_capability(device_index, rate, channels):
                    logging.info(f"Device {device_index} supports fallback rate {rate}Hz")
                    return True
        
        return False
    
    def get_device_capabilities(self, device_index: int) -> Dict:
        """
        Get comprehensive capabilities for a specific device.
        
        Args:
            device_index: Device index to analyze
            
        Returns:
            Dictionary of device capabilities
        """
        capabilities = {
            'device_index': device_index,
            'supported_rates': [],
            'supported_channels': [],
            'max_tested_channels': 0,
            'api_compatibility': {},
            'latency_info': {}
        }
        
        # Test common sample rates
        test_rates = [8000, 11025, 16000, 22050, 44100, 48000, 88200, 96000, 192000]
        test_channels = [1, 2, 4, 8]
        
        for rate in test_rates:
            for channels in test_channels:
                if self.test_device_capability(device_index, rate, channels):
                    if rate not in capabilities['supported_rates']:
                        capabilities['supported_rates'].append(rate)
                    if channels not in capabilities['supported_channels']:
                        capabilities['supported_channels'].append(channels)
                    if channels > capabilities['max_tested_channels']:
                        capabilities['max_tested_channels'] = channels
        
        # Get device info
        try:
            device = sd.query_devices(device_index)
            capabilities['name'] = device['name']
            capabilities['api'] = sd.query_hostapis(index=device['hostapi'])['name']
            capabilities['default_sample_rate'] = device['default_samplerate']
            capabilities['max_input_channels'] = device['max_input_channels']
        except Exception as e:
            logging.error(f"Error getting device {device_index} info: {e}")
        
        return capabilities
    
    def print_enhanced_device_list(self, show_capabilities: bool = False):
        """
        Print enhanced device list with hierarchical API grouping.
        
        Args:
            show_capabilities: Include detailed capability testing
        """
        devices = self.get_enhanced_device_list()
        input_devices = [d for d in devices if d['is_input']]
        
        print("\nEnhanced Audio Device List (Hierarchical)")
        print("=" * 80)
        
        # Group by API in priority order
        for api in self.api_priority + ['Other']:
            if api == 'Other':
                api_devices = [d for d in input_devices 
                             if d['api'] not in self.api_priority]
            else:
                api_devices = [d for d in input_devices if api in d['api']]
            
            if api_devices:
                print(f"\n{api} Devices:")
                print("-" * 40)
                
                for device in api_devices:
                    status = "✓" if device.get('pyaudio_verified', False) else " "
                    channels = device['input_channels']
                    rate = int(device['default_sample_rate'])
                    
                    print(f"{status} [{device['index']:2d}] {device['name']}")
                    print(f"    Channels: {channels}, Rate: {rate}Hz")
                    
                    if show_capabilities:
                        # Quick capability test
                        basic_test = self.test_device_capability(device['index'], 44100, 2)
                        target_test = self.test_device_capability(
                            device['index'], self.target_sample_rate, 2)
                        
                        print(f"    44.1kHz/Stereo: {'✓' if basic_test else '✗'}")
                        print(f"    Target Config: {'✓' if target_test else '✗'}")
                    
                    print()
        
        print("Legend: ✓ = PyAudio verified")
    
    def configure_for_bmar(self, app) -> bool:
        """
        Configure audio device for BMAR application with enhanced strategy.
        
        Args:
            app: BMAR application object
            
        Returns:
            True if successfully configured
        """
        try:
            # Get required parameters from app
            channels = getattr(app, 'channels', 2)
            preferred_api = getattr(app, 'preferred_api', None)
            
            # Find best device using enhanced strategy
            success, device, sample_rate = self.find_best_device(
                preferred_api=preferred_api, 
                channels=channels
            )
            
            if success and device:
                # Update app configuration
                app.device_index = device['index']
                app.samplerate = sample_rate or self.target_sample_rate
                app.api_name = device['api']
                
                # Test the final configuration
                if self.test_device_capability(app.device_index, app.samplerate, channels):
                    logging.info(f"Successfully configured BMAR audio:")
                    logging.info(f"  Device: [{app.device_index}] {device['name']}")
                    logging.info(f"  API: {device['api']}")
                    logging.info(f"  Sample Rate: {app.samplerate}Hz")
                    logging.info(f"  Channels: {channels}")
                    
                    app.testmode = False
                    return True
                else:
                    logging.error("Final configuration test failed")
                    return False
            else:
                logging.error("No suitable audio device could be configured")
                return False
                
        except Exception as e:
            logging.error(f"Error configuring BMAR audio: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources."""
        if self.pyaudio_manager:
            try:
                del self.pyaudio_manager
            except:
                pass
        self._device_cache.clear()

# Integration helper functions for existing BMAR code

def create_enhanced_audio_manager(app) -> EnhancedAudioManager:
    """Create enhanced audio manager with settings from BMAR app."""
    sample_rate = getattr(app, 'samplerate', 44100)
    bit_depth = getattr(app, 'bit_depth', 16)
    
    return EnhancedAudioManager(sample_rate, bit_depth)

def enhance_existing_device_discovery(app) -> bool:
    """
    Drop-in enhancement for existing BMAR device discovery.
    Can be used to replace or supplement existing set_input_device() calls.
    """
    manager = create_enhanced_audio_manager(app)
    try:
        return manager.configure_for_bmar(app)
    finally:
        manager.cleanup()
