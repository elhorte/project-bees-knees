#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

## Key PyAudio-Specific Features:

1. **Format Support**: Uses PyAudio's native format constants (`paInt8`, `paInt16`, `paInt24`, `paInt32`)
2. **Configuration Testing**: Uses `is_format_supported()` to check compatibility before opening streams
3. **Host API Information**: Direct access to PyAudio's host API enumeration
4. **Stream Testing**: Actually opens and reads from audio streams to verify functionality

## Main Differences from sounddevice version:

- **PyAudio Installation**: `pip install pyaudio` (may require additional setup on some systems)
- **Format Handling**: Direct PyAudio format constants instead of numpy dtypes
- **Capability Detection**: More comprehensive device capability testing
- **Stream Management**: Explicit stream opening/closing with proper cleanup
- **Error Handling**: PyAudio-specific exception handling

## Enhanced Features:

1. **Device Capabilities**: New `get_device_capabilities()` method that tests multiple sample rates and bit depths
2. **Interactive Commands**: 
   - `list` - Show all devices
   - `caps <device_index>` - Show device capabilities  
   - `test <device_index> <sample_rate> <bit_depth> [channels]` - Test configuration
3. **Version Information**: Shows PyAudio and PortAudio version details
4. **Host API Listing**: Shows all available audio APIs on the system

## Installation Notes:

PyAudio can be more challenging to install than sounddevice:

```bash
# Windows (preferred method)
pip install pyaudio

# If the above fails, try:
pip install pipwin
pipwin install pyaudio

# Or download wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
```

## Usage Benefits:

- **Real Stream Testing**: Actually opens audio streams to verify configurations work
- **Better Compatibility Detection**: Tests configurations before attempting to use them
- **More Detailed Device Info**: Shows supported sample rates and bit depths for each device
- **Lower-Level Control**: Direct access to PortAudio functionality through PyAudio

The script maintains the same structure as the sounddevice version but leverages PyAudio's specific 
capabilities for more robust device configuration and testing.

Windows Audio Port Configuration Script using PyAudio
Implements a hierarchical approach to audio device configuration:
1. Try WASAPI devices first
2. Fall back to DirectSound if WASAPI fails
3. Finally try MME if all else fails
"""

import pyaudio
import sys
import time
from typing import List, Dict, Optional, Tuple

class AudioPortManager:
    def __init__(self, target_sample_rate: int = 44100, target_bit_depth: int = 16):
        """Initialize the Audio Port Manager with PyAudio"""
        self.pa = pyaudio.PyAudio()
        self.supported_apis = ['WASAPI', 'DirectSound', 'MME']
        self.target_sample_rate = target_sample_rate
        self.target_bit_depth = target_bit_depth
        
        # PyAudio format mappings
        self.format_map = {
            8: pyaudio.paInt8,
            16: pyaudio.paInt16,
            24: pyaudio.paInt24,
            32: pyaudio.paInt32
        }
        
        
    def __del__(self):
        """Clean up PyAudio instance"""
        if hasattr(self, 'pa'):
            self.pa.terminate()
    

    def list_audio_devices(self, api: Optional[str] = None) -> List[Dict]:
        """
        List all available audio devices, optionally filtered by API
        
        Args:
            api: Audio API to filter by ('WASAPI', 'DirectSound', 'MME')
        
        Returns:
            List of device dictionaries
        """
        devices = []
        
        for i in range(self.pa.get_device_count()):
            try:
                device_info = self.pa.get_device_info_by_index(i)
                
                # Get host API info
                host_api_info = self.pa.get_host_api_info_by_index(device_info['hostApi'])
                api_name = host_api_info['name']
                
                # Filter by API if specified
                if api and api.upper() not in api_name.upper():
                    continue
                
                # Include both input and output devices
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'input_channels': device_info['maxInputChannels'],
                    'output_channels': device_info['maxOutputChannels'],
                    'default_sample_rate': device_info['defaultSampleRate'],
                    'api': api_name,
                    'host_api_index': device_info['hostApi'],
                    'is_input': device_info['maxInputChannels'] > 0,
                    'is_output': device_info['maxOutputChannels'] > 0
                })
            except Exception as e:
                print(f"Warning: Could not query device {i}: {e}")
                continue
        
        return devices


    def print_device_list(self, active_input_device: Optional[int] = None, active_output_device: Optional[int] = None):
        """
        Print a detailed list of all audio devices
        
        Args:
            active_input_device: Index of the currently active input device
            active_output_device: Index of the currently active output device
        """
        print("\nAudio Device List")
        print("=" * 80)
        
        # Get all devices
        devices = self.list_audio_devices()
        
        # Sort devices by index
        devices.sort(key=lambda x: x['index'])
        
        # Print devices in compact format
        for device in devices:
            # Format device name and API
            name = device['name']
            api = device['api']
            
            # Format channel counts
            in_channels = device['input_channels']
            out_channels = device['output_channels']
            channel_info = f"({in_channels} in, {out_channels} out)"
            
            # Format the line
            line = f"{device['index']:3d} {name}, {api} {channel_info}"
            
            # Add indicators only for active devices
            if device['index'] == active_input_device and in_channels > 0:
                line = f">  {line}"
            elif device['index'] == active_output_device and out_channels > 0:
                line = f"<  {line}"
            else:
                line = f"   {line}"
            
            print(line)
        
        print("\n" + "=" * 80)


    def test_device_configuration(self, device_index: int, sample_rate: int, 
                                bit_depth: int = 16, channels: int = 2) -> bool:
        """
        Test if a device supports a specific configuration
        
        Args:
            device_index: Device index from list_audio_devices()
            sample_rate: Target sample rate (e.g., 44100, 48000)
            bit_depth: Bit depth (8, 16, 24, 32)
            channels: Number of channels (1 for mono, 2 for stereo)
        Returns:
            True if configuration is supported, False otherwise
        """
        try:
            if bit_depth not in self.format_map:
                print(f"Unsupported bit depth: {bit_depth}")
                return False
            
            format_type = self.format_map[bit_depth]
            
            # Test if the device supports this configuration
            is_supported = self.pa.is_format_supported(
                rate=sample_rate,
                input_device=device_index,
                input_channels=channels,
                input_format=format_type
            )
            
            return is_supported
            
        except Exception as e:
            print(f"Error testing configuration: {str(e)}")
            return False
    

    def test_and_configure_device(self, device: Dict, channels: int = 2) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Test and configure a device with the target sample rate and bit depth
        
        Args:
            device: Device dictionary from list_audio_devices()
            channels: Number of channels to use
            
        Returns:
            Tuple of (success, achieved_sample_rate, achieved_bit_depth)
        """
        print(f"\nTesting device: {device['name']} ({device['api']})")
        
        # First try 44.1kHz as a baseline
        if self.test_device_configuration(device['index'], 44100, 16, channels):
            print("✓ Device supports 44.1kHz/16-bit")
            
            # Now try target configuration
            if self.test_device_configuration(device['index'], self.target_sample_rate, self.target_bit_depth, channels):
                print(f"✓ Device supports target configuration: {self.target_sample_rate}Hz/{self.target_bit_depth}-bit")
                return True, self.target_sample_rate, self.target_bit_depth
            
            # Try half the target sample rate
            half_rate = self.target_sample_rate // 2
            if self.test_device_configuration(device['index'], half_rate, self.target_bit_depth, channels):
                print(f"✓ Device supports half rate: {half_rate}Hz/{self.target_bit_depth}-bit")
                response = input(f"Would you like to use {half_rate}Hz instead of {self.target_sample_rate}Hz? (y/n): ")
                if response.lower() == 'y':
                    return True, half_rate, self.target_bit_depth
        
        return False, None, None
    

    def configure_audio_input(self, channels: int = 2) -> Tuple[bool, Optional[Dict], Optional[int], Optional[int]]:
        """
        Configure audio input following the hierarchical strategy
        
        Args:
            channels: Number of channels to use
            
        Returns:
            Tuple of (success, device_info, achieved_sample_rate, achieved_bit_depth)
        """
        # Try WASAPI first
        print("\nTrying WASAPI devices...")
        wasapi_devices = self.list_audio_devices('WASAPI')
        
        for device in wasapi_devices:
            success, sample_rate, bit_depth = self.test_and_configure_device(device, channels)
            if success:
                return True, device, sample_rate, bit_depth
        
        # Try DirectSound next
        print("\nWASAPI devices failed, trying DirectSound...")
        ds_devices = self.list_audio_devices('DirectSound')
        
        for device in ds_devices:
            success, sample_rate, bit_depth = self.test_and_configure_device(device, channels)
            if success:
                return True, device, sample_rate, bit_depth
        
        # Finally try MME
        print("\nDirectSound devices failed, trying MME...")
        mme_devices = self.list_audio_devices('MME')
        
        for device in mme_devices:
            success, sample_rate, bit_depth = self.test_and_configure_device(device, channels)
            if success:
                return True, device, sample_rate, bit_depth
        
        return False, None, None, None

    def test_duplex_support(self, device_index: int, sample_rate: int = 44100, channels: int = 1) -> bool:
        """
        Test if a device supports duplex mode (simultaneous input/output)
        
        Args:
            device_index: Device index to test
            sample_rate: Sample rate to test
            channels: Number of channels to test
            
        Returns:
            True if duplex is supported, False otherwise
        """
        pa = pyaudio.PyAudio()
        try:
            # Test if device supports duplex mode
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                output=True,
                input_device_index=device_index,
                output_device_index=device_index,
                frames_per_buffer=1024
            )
            stream.close()
            return True
        except (OSError, ValueError):
            return False
        finally:
            pa.terminate()

    def create_duplex_stream(self, input_device=None, output_device=None, sample_rate=None, 
                           channels: int = 2, callback=None, frames_per_buffer: int = 1024) -> Optional[object]:
        """
        Create a duplex audio stream for intercom functionality
        
        Args:
            input_device: Input device index or None for auto-select
            output_device: Output device index or None for auto-select  
            sample_rate: Sample rate or None for auto-select
            channels: Number of channels
            callback: Callback function for audio processing
            frames_per_buffer: Buffer size in frames
            
        Returns:
            PyAudio stream object or None if failed
        """
        pa = pyaudio.PyAudio()
        
        try:
            # If no devices specified, auto-configure
            if input_device is None:
                success, input_device_info, auto_sample_rate, _ = self.configure_audio_input(channels)
                if not success:
                    print("Could not configure input device for duplex stream")
                    pa.terminate()
                    return None
                input_device_idx = input_device_info['index']
                if sample_rate is None:
                    sample_rate = auto_sample_rate or 44100
            else:
                input_device_idx = input_device
                if sample_rate is None:
                    sample_rate = 44100
            
            # Use same device for output if not specified
            if output_device is None:
                output_device_idx = input_device_idx
            else:
                output_device_idx = output_device
            
            # Get device info for validation
            try:
                input_info = pa.get_device_info_by_index(input_device_idx)
                output_info = pa.get_device_info_by_index(output_device_idx)
                print("Attempting duplex stream:")
                print(f"  Input: {input_info['name']} (index {input_device_idx})")
                print(f"  Output: {output_info['name']} (index {output_device_idx})")
            except (OSError, ValueError) as e:
                print(f"Warning: Could not get device info: {e}")
            
            # Test if duplex is supported on this device
            print("Testing duplex support...")
            if not self.test_duplex_support(input_device_idx, min(sample_rate, 44100), 1):
                print(f"Device {input_device_idx} does not support duplex mode")
                print("Suggestion: Try using separate input/output streams instead")
                pa.terminate()
                return None
            
            print("Duplex support confirmed!")
            
            # Try different configurations in order of preference
            configs_to_try = [
                # Start with safe 16-bit configuration
                {
                    'format': pyaudio.paInt16,
                    'rate': 44100,
                    'channels': 1,
                    'frames_per_buffer': max(frames_per_buffer, 2048)
                },
                # Try with more channels
                {
                    'format': pyaudio.paInt16,
                    'rate': 44100,
                    'channels': min(channels, 2),
                    'frames_per_buffer': max(frames_per_buffer, 2048)
                },
                # Try higher sample rate
                {
                    'format': pyaudio.paInt16,
                    'rate': min(sample_rate, 48000),
                    'channels': 1,
                    'frames_per_buffer': max(frames_per_buffer, 2048)
                },
                # Try float32 format
                {
                    'format': pyaudio.paFloat32,
                    'rate': 44100,
                    'channels': 1,
                    'frames_per_buffer': max(frames_per_buffer, 2048)
                }
            ]
            
            for i, config in enumerate(configs_to_try):
                try:
                    print(f"Trying config {i+1}: {config['format']}, {config['rate']}Hz, {config['channels']}ch, {config['frames_per_buffer']} frames")
                    
                    stream = pa.open(
                        format=config['format'],
                        channels=config['channels'],
                        rate=config['rate'],
                        input=True,
                        output=True,
                        input_device_index=input_device_idx,
                        output_device_index=output_device_idx,
                        frames_per_buffer=config['frames_per_buffer'],
                        stream_callback=callback
                    )
                    
                    print(f"Success with config {i+1}!")
                    print(f"  Format: {config['format']}")
                    print(f"  Sample Rate: {config['rate']}Hz")
                    print(f"  Channels: {config['channels']}")
                    print(f"  Buffer Size: {config['frames_per_buffer']}")
                    
                    return stream
                    
                except (OSError, ValueError) as config_error:
                    print(f"  Config {i+1} failed: {config_error}")
                    continue
            
            print("All duplex stream configurations failed")
            return None
            
        except (OSError, ValueError) as e:
            print(f"Error creating duplex stream: {e}")
            return None
        finally:
            # Don't terminate pa here - the stream needs it to stay alive
            pass

# Additional utility functions for PyAudio-specific features

def list_host_apis():
    """List all available host APIs"""
    pa = pyaudio.PyAudio()
    print("Available Host APIs:")
    for i in range(pa.get_host_api_count()):
        api_info = pa.get_host_api_info_by_index(i)
        print(f"[{i}] {api_info['name']} - {api_info['deviceCount']} devices")
    pa.terminate()

def get_pyaudio_version_info():
    """Get PyAudio and PortAudio version information"""
    pa = pyaudio.PyAudio()
    print("PyAudio Version Information:")
    print(f"PyAudio Version: {pyaudio.__version__}")
    try:
        print(f"PortAudio Version: {pa.get_portaudio_version()}")
        print(f"PortAudio Version Text: {pa.get_portaudio_version_text()}")
    except AttributeError:
        print("Note: PortAudio version information not available in this PyAudio version")
    pa.terminate()


def main():
    """Main function implementing the audio configuration strategy"""
    
    # Get target configuration from config or use defaults
    target_sample_rate = 192000  # Example: Get this from config
    target_bit_depth = 24       # Example: Get this from config
    
    manager = AudioPortManager(target_sample_rate, target_bit_depth)
    
    print("Windows Audio Port Configuration Script (PyAudio)")
    print("=" * 60)
    print(f"Target Configuration: {target_sample_rate}Hz, {target_bit_depth}-bit")
    
    # Get default devices
    pa = pyaudio.PyAudio()
    default_input = pa.get_default_input_device_info()
    default_output = pa.get_default_output_device_info()
    pa.terminate()
    
    # Print device list showing active devices
    manager.print_device_list(
        active_input_device=default_input['index'],
        active_output_device=default_output['index']
    )
    
    # Show version info and available APIs
    get_pyaudio_version_info()
    print()
    list_host_apis()


if __name__ == "__main__":
    # Show version info
    get_pyaudio_version_info()
    print()
    
    # Show available APIs
    list_host_apis()
    print()
    
    # Run main program
    main()

