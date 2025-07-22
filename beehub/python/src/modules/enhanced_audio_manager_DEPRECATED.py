"""
Pure PyAudio Audio Manager for BMAR
Provides comprehensive audio management using AudioPortManager exclusively.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple, Union
from .class_PyAudio import AudioPortManager

class PureAudioManager:
    """
    Pure PyAudio audio manager - no sounddevice dependencies.
    
    Provides:
    - Device discovery using AudioPortManager
    - Hierarchical API fallback (WASAPI → DirectSound → MME)
    - Stream management and testing
    - Configuration validation
    """
    
    def __init__(self, target_sample_rate: int = 44100, target_bit_depth: int = 16):
        self.target_sample_rate = target_sample_rate
        self.target_bit_depth = target_bit_depth
        
        # Initialize PyAudio manager
        try:
            self.audio_manager = AudioPortManager(target_sample_rate, target_bit_depth)
            self._audio_available = True
            logging.info("PyAudio audio manager initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize PyAudio manager: {e}")
            self.audio_manager = None
            self._audio_available = False

    def is_available(self) -> bool:
        """Check if audio system is available"""
        return self._audio_available and self.audio_manager is not None

    def list_input_devices(self) -> List[Dict]:
        """List all available input devices"""
        if not self.is_available():
            return []
        
        try:
            devices = self.audio_manager.list_audio_devices()
            return [d for d in devices if d['is_input']]
        except Exception as e:
            logging.error(f"Error listing input devices: {e}")
            return []

    def configure_best_device(self, preferred_channels: int = 2) -> Optional[Dict]:
        """Configure the best available device using hierarchical strategy"""
        if not self.is_available():
            return None
        
        try:
            success, device, sample_rate, bit_depth = self.audio_manager.configure_audio_input(
                channels=preferred_channels
            )
            
            if success:
                return {
                    'device': device,
                    'sample_rate': sample_rate,
                    'bit_depth': bit_depth,
                    'channels': device['input_channels']
                }
            else:
                logging.error("Could not configure any audio device")
                return None
        except Exception as e:
            logging.error(f"Error configuring audio device: {e}")
            return None

    def test_device_configuration(self, device_index: int, sample_rate: int, 
                                bit_depth: int, channels: int) -> bool:
        """Test if a specific device configuration works"""
        if not self.is_available():
            return False
        
        return self.audio_manager.test_device_configuration(
            device_index, sample_rate, bit_depth, channels
        )

    def create_input_stream(self, device_index: int, sample_rate: int, 
                          channels: int, callback, blocksize: int = 1024):
        """Create an input stream using PyAudio"""
        if not self.is_available():
            raise RuntimeError("Audio system not available")
        
        return self.audio_manager.create_input_stream(
            device_index=device_index,
            sample_rate=sample_rate,
            channels=channels,
            callback=callback,
            frames_per_buffer=blocksize
        )

    def create_output_stream(self, device_index: int, sample_rate: int, 
                           channels: int, blocksize: int = 1024):
        """Create an output stream using PyAudio"""
        if not self.is_available():
            raise RuntimeError("Audio system not available")
        
        return self.audio_manager.create_output_stream(
            device_index=device_index,
            sample_rate=sample_rate,
            channels=channels,
            frames_per_buffer=blocksize
        )

    def create_duplex_stream(self, input_device: int, output_device: int, 
                           sample_rate: int, channels: int, callback, 
                           blocksize: int = 1024):
        """Create a duplex stream using PyAudio"""
        if not self.is_available():
            raise RuntimeError("Audio system not available")
        
        return self.audio_manager.create_duplex_stream(
            input_device=input_device,
            output_device=output_device,
            sample_rate=sample_rate,
            channels=channels,
            callback=callback,
            frames_per_buffer=blocksize
        )

    def get_device_capabilities(self, device_index: int) -> Dict:
        """Get detailed device capabilities"""
        if not self.is_available():
            return {}
        
        try:
            return self.audio_manager.get_device_capabilities(device_index)
        except Exception as e:
            logging.error(f"Error getting device capabilities: {e}")
            return {}

    def print_device_list(self):
        """Print a formatted list of all devices"""
        if not self.is_available():
            print("Audio system not available")
            return
        
        try:
            self.audio_manager.print_device_list()
        except Exception as e:
            logging.error(f"Error printing device list: {e}")
            print("Error displaying device list")

    def cleanup(self):
        """Clean up audio resources"""
        if self.audio_manager:
            try:
                # AudioPortManager cleanup is handled in its __del__ method
                self.audio_manager = None
                self._audio_available = False
                logging.info("Audio manager cleaned up")
            except Exception as e:
                logging.error(f"Error during audio cleanup: {e}")
