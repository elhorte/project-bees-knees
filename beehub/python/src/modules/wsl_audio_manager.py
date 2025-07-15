"""
WSL Audio Device Manager
Handles audio device detection and configuration in WSL environment.
"""

import logging
import subprocess
import os
import re
from typing import List, Dict, Optional

class WSLAudioManager:
    """Manages audio devices in WSL environment."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pulseaudio_available = self._check_pulseaudio()
        self.pipewire_available = self._check_pipewire()
        
    def _check_pulseaudio(self) -> bool:
        """Check if PulseAudio is available."""
        try:
            result = subprocess.run(['pulseaudio', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _check_pipewire(self) -> bool:
        """Check if PipeWire is available."""
        try:
            result = subprocess.run(['pipewire', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def setup_wsl_audio(self) -> bool:
        """Set up WSL audio environment."""
        try:
            self.logger.info("Setting up WSL audio environment...")
            
            # Check if PulseAudio server is running
            if self.pulseaudio_available:
                return self._setup_pulseaudio()
            elif self.pipewire_available:
                return self._setup_pipewire()
            else:
                self.logger.warning("Neither PulseAudio nor PipeWire found")
                return self._setup_minimal_audio()
        
        except Exception as e:
            self.logger.error(f"Error setting up WSL audio: {e}")
            return False
    
    def _setup_pulseaudio(self) -> bool:
        """Set up PulseAudio for WSL."""
        try:
            # Set PULSE_RUNTIME_PATH for WSL
            pulse_runtime = "/mnt/wslg/runtime-dir/pulse"
            if os.path.exists(pulse_runtime):
                os.environ['PULSE_RUNTIME_PATH'] = pulse_runtime
                self.logger.info(f"Set PULSE_RUNTIME_PATH to {pulse_runtime}")
            
            # Try to start PulseAudio if not running
            try:
                subprocess.run(['pulseaudio', '--check'], check=True, 
                             capture_output=True, timeout=5)
                self.logger.info("PulseAudio is already running")
            except subprocess.CalledProcessError:
                self.logger.info("Starting PulseAudio...")
                subprocess.run(['pulseaudio', '--start'], check=True, 
                             capture_output=True, timeout=10)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up PulseAudio: {e}")
            return False
    
    def _setup_pipewire(self) -> bool:
        """Set up PipeWire for WSL."""
        try:
            self.logger.info("Attempting to use PipeWire...")
            # PipeWire setup would go here
            return True
        except Exception as e:
            self.logger.error(f"Error setting up PipeWire: {e}")
            return False
    
    def _setup_minimal_audio(self) -> bool:
        """Set up minimal audio environment."""
        try:
            self.logger.info("Setting up minimal audio environment for WSL")
            
            # Try to use ALSA directly
            os.environ['ALSA_CARD'] = '0'  # Use default card
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up minimal audio: {e}")
            return False
    
    def get_wsl_audio_devices(self) -> List[Dict]:
        """Get available audio devices in WSL."""
        devices = []
        
        try:
            # Try multiple methods to detect audio devices
            devices.extend(self._get_alsa_devices())
            devices.extend(self._get_pulse_devices())
            
            # If no devices found, create a default virtual device
            if not devices:
                devices.append(self._create_default_device())
            
        except Exception as e:
            self.logger.error(f"Error getting WSL audio devices: {e}")
            devices.append(self._create_default_device())
        
        return devices
    
    def _get_alsa_devices(self) -> List[Dict]:
        """Get ALSA audio devices."""
        devices = []
        
        try:
            # Try to list ALSA devices
            result = subprocess.run(['arecord', '-l'], capture_output=True, 
                                  text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                card_num = 0
                
                for line in lines:
                    if 'card' in line.lower() and 'device' in line.lower():
                        # Parse ALSA device line
                        match = re.search(r'card (\d+).*device (\d+)', line)
                        if match:
                            card = match.group(1)
                            device = match.group(2)
                            
                            devices.append({
                                'index': card_num,
                                'name': f"ALSA Card {card} Device {device}",
                                'api': 'ALSA',
                                'is_input': True,
                                'is_output': False,
                                'input_channels': 2,
                                'output_channels': 0,
                                'default_sample_rate': 44100,
                                'alsa_card': card,
                                'alsa_device': device
                            })
                            card_num += 1
            
        except Exception as e:
            self.logger.debug(f"Could not get ALSA devices: {e}")
        
        return devices
    
    def _get_pulse_devices(self) -> List[Dict]:
        """Get PulseAudio devices."""
        devices = []
        
        if not self.pulseaudio_available:
            return devices
        
        try:
            # List PulseAudio sources (input devices)
            result = subprocess.run(['pactl', 'list', 'short', 'sources'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for i, line in enumerate(lines):
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            source_name = parts[1]
                            
                            devices.append({
                                'index': i,
                                'name': f"PulseAudio: {source_name}",
                                'api': 'PulseAudio',
                                'is_input': True,
                                'is_output': False,
                                'input_channels': 2,
                                'output_channels': 0,
                                'default_sample_rate': 44100,
                                'pulse_source': source_name
                            })
            
        except Exception as e:
            self.logger.debug(f"Could not get PulseAudio devices: {e}")
        
        return devices
    
    def _create_default_device(self) -> Dict:
        """Create a default virtual audio device for WSL."""
        return {
            'index': 0,
            'name': 'WSL Default Audio Device',
            'api': 'Virtual',
            'is_input': True,
            'is_output': False,
            'input_channels': 2,
            'output_channels': 0,
            'default_sample_rate': 44100,
            'virtual': True
        }
    
    def test_wsl_audio_device(self, device_info: Dict) -> bool:
        """Test if a WSL audio device works."""
        try:
            if device_info.get('virtual'):
                # Virtual device always "works" but won't actually record
                self.logger.warning("Using virtual audio device - no actual audio will be recorded")
                return True
            
            # Try to test actual device
            if 'alsa_card' in device_info:
                return self._test_alsa_device(device_info)
            elif 'pulse_source' in device_info:
                return self._test_pulse_device(device_info)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing WSL audio device: {e}")
            return False
    
    def _test_alsa_device(self, device_info: Dict) -> bool:
        """Test ALSA device."""
        try:
            card = device_info['alsa_card']
            device = device_info['alsa_device']
            
            # Try a very short recording test
            cmd = [
                'arecord', 
                '-D', f"hw:{card},{device}",
                '-d', '0.1',  # 0.1 second test
                '-f', 'S16_LE',
                '-r', '44100',
                '/dev/null'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=2)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"ALSA device test failed: {e}")
            return False
    
    def _test_pulse_device(self, device_info: Dict) -> bool:
        """Test PulseAudio device."""
        try:
            source = device_info['pulse_source']
            
            # Try a very short recording test
            cmd = [
                'parecord',
                '--device', source,
                '--duration', '0.1',
                '--format', 's16le',
                '--rate', '44100',
                '/dev/null'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=2)
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"PulseAudio device test failed: {e}")
            return False

def setup_wsl_environment():
    """Set up WSL environment for audio recording."""
    try:
        manager = WSLAudioManager()
        
        # Set up audio environment
        audio_setup = manager.setup_wsl_audio()
        if not audio_setup:
            logging.warning("WSL audio setup had issues, but continuing...")
        
        # Get available devices
        devices = manager.get_wsl_audio_devices()
        
        logging.info(f"Found {len(devices)} audio devices in WSL")
        for device in devices:
            logging.info(f"  Device {device['index']}: {device['name']} ({device['api']})")
        
        return devices
        
    except Exception as e:
        logging.error(f"Error setting up WSL environment: {e}")
        # Return a default device so the app can continue
        return [{
            'index': 0,
            'name': 'WSL Fallback Device',
            'api': 'Virtual',
            'is_input': True,
            'is_output': False,
            'input_channels': 1,
            'output_channels': 0,
            'default_sample_rate': 44100,
            'virtual': True
        }]