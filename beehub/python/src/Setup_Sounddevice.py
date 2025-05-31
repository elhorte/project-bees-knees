#!/usr/bin/env python3


"""
Windows Audio Port Configuration Script
Sets sample rate and bit depth for different Windows audio APIs (WASAPI, DirectSound, MME)
Requires: pip install sounddevice numpy

Here's a Python script that sets audio input port configurations for different Windows audio APIs 
using the `sounddevice` library:I've created a comprehensive Python script for configuring Windows 
audio input ports with support for WASAPI, DirectSound, and MME APIs. Here are the key features:

## Main Components:

1. **AudioPortManager Class**: Handles device discovery and configuration
2. **Device Listing**: Shows all available input devices with their API types
3. **Configuration Testing**: Attempts to set specific sample rates and bit depths
4. **Interactive Mode**: Allows manual device configuration

## Key Features:

- **API-Specific Examples**: Separate configuration examples for WASAPI, DirectSound, and MME
- **Multiple Configurations**: Tests various sample rate/bit depth combinations
- **Error Handling**: Graceful handling of unsupported configurations  
- **Device Discovery**: Automatically finds devices for each API type

## Installation Requirements:

```bash
pip install sounddevice numpy
```

## Usage Examples:

The script provides automated examples for each API:
- **WASAPI**: High-quality configurations (48kHz/16-bit, 44.1kHz/24-bit, 96kHz/32-bit)
- **DirectSound**: Standard configurations (44.1kHz/16-bit, 48kHz/16-bit)
- **MME**: Basic configurations (44.1kHz/16-bit, 22kHz/16-bit)

## Important Notes:

1. **WASAPI** generally offers the best performance and highest quality options
2. **DirectSound** provides good compatibility with moderate quality
3. **MME** is the most basic but widely supported API
4. Some configurations may not be supported by all hardware
5. The script tests configurations by opening audio streams temporarily

The script includes an interactive mode where you can manually specify device indices and configurations, 
making it easy to test specific setups for your audio hardware.
"""

import sounddevice as sd
import numpy as np
import sys
from typing import List, Dict, Optional

class AudioPortManager:
    def __init__(self):
        """Initialize the Audio Port Manager"""
        self.supported_apis = ['WASAPI', 'DirectSound', 'MME']
        
    def list_audio_devices(self, api: Optional[str] = None) -> List[Dict]:
        """
        List all available audio devices, optionally filtered by API
        
        Args:
            api: Audio API to filter by ('WASAPI', 'DirectSound', 'MME')
        
        Returns:
            List of device dictionaries
        """
        devices = sd.query_devices()
        
        if api:
            # Filter devices by API
            filtered_devices = []
            for i, device in enumerate(devices):
                try:
                    device_info = sd.query_devices(i)
                    if api.upper() in str(device_info.get('hostapi', '')).upper():
                        filtered_devices.append({
                            'index': i,
                            'name': device['name'],
                            'channels': device['max_input_channels'],
                            'sample_rate': device['default_samplerate'],
                            'api': api
                        })
                except:
                    continue
            return filtered_devices
        
        # Return all devices with their API info
        all_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:  # Only input devices
                try:
                    hostapi_info = sd.query_hostapis(device['hostapi'])
                    all_devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'sample_rate': device['default_samplerate'],
                        'api': hostapi_info['name']
                    })
                except:
                    continue
        
        return all_devices
    
    def set_audio_port_config(self, device_index: int, sample_rate: int, 
                            bit_depth: int = 16, channels: int = 2) -> bool:
        """
        Set audio port configuration for a specific device
        
        Args:
            device_index: Device index from list_audio_devices()
            sample_rate: Target sample rate (e.g., 44100, 48000)
            bit_depth: Bit depth (16, 24, 32)
            channels: Number of channels (1 for mono, 2 for stereo)
        
        Returns:
            True if configuration was successful, False otherwise
        """
        try:
            # Map bit depth to numpy dtype
            dtype_map = {
                16: np.int16,
                24: np.int32,  # 24-bit is typically handled as 32-bit
                32: np.int32
            }
            
            if bit_depth not in dtype_map:
                print(f"Unsupported bit depth: {bit_depth}")
                return False
            
            dtype = dtype_map[bit_depth]
            
            # Test the configuration by attempting to open a stream
            print(f"Testing configuration: {sample_rate}Hz, {bit_depth}-bit, {channels} channels")
            
            with sd.InputStream(
                device=device_index,
                channels=channels,
                samplerate=sample_rate,
                dtype=dtype,
                blocksize=1024
            ) as stream:
                print(f"✓ Successfully configured device {device_index}")
                print(f"  Sample Rate: {stream.samplerate}Hz")
                print(f"  Channels: {stream.channels}")
                print(f"  Data Type: {stream.dtype}")
                return True
                
        except Exception as e:
            print(f"✗ Failed to configure device {device_index}: {str(e)}")
            return False
    
    def find_devices_by_api(self, api: str) -> List[Dict]:
        """Find all input devices for a specific API"""
        devices = self.list_audio_devices()
        return [d for d in devices if api.upper() in d['api'].upper()]

def main():
    """Main function with examples for WASAPI, DirectSound, and MME"""
    
    manager = AudioPortManager()
    
    print("Windows Audio Port Configuration Script")
    print("=" * 50)
    
    # List all available audio devices
    print("\nAvailable Audio Input Devices:")
    all_devices = manager.list_audio_devices()
    
    for device in all_devices:
        print(f"[{device['index']}] {device['name']}")
        print(f"    API: {device['api']}")
        print(f"    Channels: {device['channels']}")
        print(f"    Default Sample Rate: {device['sample_rate']}Hz")
        print()
    
    # Examples for each API type
    
    # WASAPI Example
    print("\n" + "="*50)
    print("WASAPI CONFIGURATION EXAMPLE")
    print("="*50)
    
    wasapi_devices = manager.find_devices_by_api('WASAPI')
    if wasapi_devices:
        device = wasapi_devices[0]  # Use first WASAPI device
        print(f"Configuring WASAPI device: {device['name']}")
        
        # Try different configurations
        configs = [
            (48000, 16),  # 48kHz, 16-bit
            (44100, 24),  # 44.1kHz, 24-bit
            (96000, 32),  # 96kHz, 32-bit
        ]
        
        for sample_rate, bit_depth in configs:
            print(f"\nTrying {sample_rate}Hz, {bit_depth}-bit:")
            success = manager.set_audio_port_config(
                device['index'], sample_rate, bit_depth, 2
            )
            if success:
                print("Configuration applied successfully!")
            else:
                print("Configuration failed or not supported.")
    else:
        print("No WASAPI devices found.")
    
    # DirectSound Example
    print("\n" + "="*50)
    print("DIRECTSOUND CONFIGURATION EXAMPLE")
    print("="*50)
    
    ds_devices = manager.find_devices_by_api('DirectSound')
    if ds_devices:
        device = ds_devices[0]  # Use first DirectSound device
        print(f"Configuring DirectSound device: {device['name']}")
        
        # DirectSound typically supports fewer configurations
        configs = [
            (44100, 16),  # 44.1kHz, 16-bit
            (48000, 16),  # 48kHz, 16-bit
        ]
        
        for sample_rate, bit_depth in configs:
            print(f"\nTrying {sample_rate}Hz, {bit_depth}-bit:")
            success = manager.set_audio_port_config(
                device['index'], sample_rate, bit_depth, 2
            )
            if success:
                print("Configuration applied successfully!")
            else:
                print("Configuration failed or not supported.")
    else:
        print("No DirectSound devices found.")
    
    # MME Example
    print("\n" + "="*50)
    print("MME CONFIGURATION EXAMPLE")
    print("="*50)
    
    mme_devices = manager.find_devices_by_api('MME')
    if mme_devices:
        device = mme_devices[0]  # Use first MME device
        print(f"Configuring MME device: {device['name']}")
        
        # MME has the most limited support
        configs = [
            (44100, 16),  # 44.1kHz, 16-bit
            (22050, 16),  # 22.05kHz, 16-bit
        ]
        
        for sample_rate, bit_depth in configs:
            print(f"\nTrying {sample_rate}Hz, {bit_depth}-bit:")
            success = manager.set_audio_port_config(
                device['index'], sample_rate, bit_depth, 2
            )
            if success:
                print("Configuration applied successfully!")
            else:
                print("Configuration failed or not supported.")
    else:
        print("No MME devices found.")
    
    # Interactive mode
    print("\n" + "="*50)
    print("INTERACTIVE MODE")
    print("="*50)
    
    print("Enter device index and configuration (or 'quit' to exit):")
    
    while True:
        try:
            user_input = input("\nDevice index (or 'quit'): ").strip()
            
            if user_input.lower() == 'quit':
                break
            
            device_index = int(user_input)
            sample_rate = int(input("Sample rate (Hz): "))
            bit_depth = int(input("Bit depth (16/24/32): "))
            channels = int(input("Channels (1 for mono, 2 for stereo): "))
            
            success = manager.set_audio_port_config(
                device_index, sample_rate, bit_depth, channels
            )
            
            if success:
                print("✓ Configuration successful!")
            else:
                print("✗ Configuration failed!")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except ValueError:
            print("Invalid input. Please enter numeric values.")
        except Exception as e:
            print(f"Error: {str(e)}")

# Additional utility functions for specific API configurations

def configure_wasapi_exclusive_mode(device_index: int, sample_rate: int, bit_depth: int):
    """
    Example function for WASAPI exclusive mode configuration
    Note: Requires additional Windows-specific libraries like pycaw
    """
    print(f"WASAPI Exclusive Mode configuration would require additional libraries")
    print(f"Consider using pycaw or Windows Core Audio APIs directly")
    print(f"This would allow lower latency and direct hardware control")

def configure_asio_alternative():
    """
    Information about ASIO as an alternative to Windows APIs
    """
    print("For professional audio applications, consider ASIO drivers:")
    print("- Lower latency than WASAPI/DirectSound/MME")
    print("- Direct hardware access")
    print("- Requires ASIO4ALL or manufacturer-specific ASIO drivers")
    print("- Use python-rtaudio or similar libraries for ASIO support")

if __name__ == "__main__":
    main()
    