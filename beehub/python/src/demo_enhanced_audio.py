#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Audio Configuration Demo for BMAR
Demonstrates the new PyAudio-enhanced audio device testing capabilities.
"""

import sys
import logging
from modules.bmar_config import *
from modules.audio_devices import (
    print_all_input_devices, 
    configure_audio_with_fallback,
    get_enhanced_device_info,
    test_audio_configuration
)
from modules.class_PyAudio import AudioPortManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class MockApp:
    """Mock BMAR app for demonstration purposes."""
    def __init__(self):
        # Set up basic configuration attributes that BMAR expects
        self.PRIMARY_IN_SAMPLERATE = 192000
        self.PRIMARY_BITDEPTH = 16
        self.PRIMARY_SAVE_SAMPLERATE = 192000
        self.sound_in_chs = 2
        self.sound_in_id = None
        self.device_id = None
        self.make_name = "Windows" if sys.platform == 'win32' else ""
        self.testmode = True
        self.debug_print = True
        
        # Set up audio format
        if self.PRIMARY_BITDEPTH == 16:
            self._dtype = 'int16'
        elif self.PRIMARY_BITDEPTH == 24:
            self._dtype = 'int24'
        elif self.PRIMARY_BITDEPTH == 32:
            self._dtype = 'int32'
        else:
            self._dtype = 'int16'  # Default fallback
    
    def print_debug(self, msg, level=1):
        if self.debug_print:
            print(f"INFO: {msg}")

def demo_enhanced_device_listing():
    """Demonstrate enhanced device listing with PyAudio capabilities."""
    print("\n" + "="*80)
    print("ENHANCED AUDIO DEVICE LISTING DEMO")
    print("="*80)
    
    try:
        # Show enhanced device listing
        print_all_input_devices()
        
        # Test specific devices
        manager = AudioPortManager(target_sample_rate=192000, target_bit_depth=24)
        devices = manager.list_audio_devices()
        
        print(f"\nFound {len(devices)} audio devices through PyAudio")
        
        # Show API distribution
        api_count = {}
        for device in devices:
            api = device['api']
            api_count[api] = api_count.get(api, 0) + 1
        
        print("\nAPI Distribution:")
        for api, count in api_count.items():
            print(f"  {api}: {count} devices")
            
    except Exception as e:
        print(f"Error in enhanced device listing: {e}")

def demo_hierarchical_configuration():
    """Demonstrate hierarchical audio configuration (WASAPI -> DirectSound -> MME)."""
    print("\n" + "="*80)
    print("HIERARCHICAL AUDIO CONFIGURATION DEMO")
    print("="*80)
    
    try:
        app = MockApp()
        
        print(f"Target Configuration:")
        print(f"  Sample Rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
        print(f"  Bit Depth: {app.PRIMARY_BITDEPTH} bits")
        print(f"  Channels: {app.sound_in_chs}")
        
        print("\nAttempting enhanced audio configuration...")
        success = configure_audio_with_fallback(app)
        
        if success:
            print("✓ Enhanced audio configuration successful!")
            print(f"  Selected Device: {app.sound_in_id}")
            print(f"  Actual Sample Rate: {app.PRIMARY_IN_SAMPLERATE} Hz")
            print(f"  Actual Bit Depth: {app.PRIMARY_BITDEPTH} bits")
            print(f"  Actual Channels: {app.sound_in_chs}")
        else:
            print("⚠ Enhanced audio configuration failed")
            
    except Exception as e:
        print(f"Error in hierarchical configuration: {e}")

def demo_device_capabilities_testing():
    """Demonstrate detailed device capabilities testing."""
    print("\n" + "="*80)
    print("DEVICE CAPABILITIES TESTING DEMO")
    print("="*80)
    
    try:
        manager = AudioPortManager(target_sample_rate=192000, target_bit_depth=24)
        devices = manager.list_audio_devices()
        
        # Test first few input devices
        input_devices = [d for d in devices if d['is_input']][:3]
        
        for device in input_devices:
            print(f"\nTesting Device [{device['index']}]: {device['name']}")
            print(f"  API: {device['api']}")
            print(f"  Default Sample Rate: {device['default_sample_rate']} Hz")
            print(f"  Max Input Channels: {device['input_channels']}")
            
            # Test various configurations
            test_configs = [
                (44100, 16, 2),
                (48000, 16, 2),
                (96000, 24, 2),
                (192000, 24, 2)
            ]
            
            for sample_rate, bit_depth, channels in test_configs:
                can_use = manager.test_device_configuration(
                    device['index'], sample_rate, bit_depth, channels
                )
                status = "✓" if can_use else "✗"
                print(f"    {status} {sample_rate}Hz/{bit_depth}bit/{channels}ch")
        
    except Exception as e:
        print(f"Error in capabilities testing: {e}")

def demo_enhanced_device_info():
    """Demonstrate enhanced device information retrieval."""
    print("\n" + "="*80)
    print("ENHANCED DEVICE INFORMATION DEMO")
    print("="*80)
    
    try:
        manager = AudioPortManager()
        devices = manager.list_audio_devices()
        
        # Show detailed info for first input device
        input_devices = [d for d in devices if d['is_input']]
        if input_devices:
            device = input_devices[0]
            device_id = device['index']
            
            print(f"Detailed Information for Device [{device_id}]:")
            print(f"  Name: {device['name']}")
            print(f"  API: {device['api']}")
            print(f"  Host API Index: {device['host_api_index']}")
            print(f"  Input Channels: {device['input_channels']}")
            print(f"  Output Channels: {device['output_channels']}")
            print(f"  Default Sample Rate: {device['default_sample_rate']} Hz")
            
            # Get enhanced info
            enhanced_info = get_enhanced_device_info(device_id, 192000, 24)
            if enhanced_info:
                print(f"  Enhanced Capabilities:")
                print(f"    PyAudio Compatible: {enhanced_info.get('pyaudio_compatible', False)}")
                print(f"    Can Use Target Config: {enhanced_info.get('can_use_target_config', False)}")
        
    except Exception as e:
        print(f"Error in enhanced device info: {e}")

def main():
    """Run all demonstration functions."""
    print("BMAR Enhanced Audio Configuration Demo")
    print("=====================================")
    print("This script demonstrates the new PyAudio-enhanced audio capabilities")
    print("integrated into the BMAR system.")
    
    try:
        demo_enhanced_device_listing()
        demo_hierarchical_configuration()
        demo_device_capabilities_testing()
        demo_enhanced_device_info()
        
        print("\n" + "="*80)
        print("DEMO COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nKey Benefits of Enhanced Audio Configuration:")
        print("• Hierarchical API selection (WASAPI → DirectSound → MME)")
        print("• Real device capability testing before configuration")
        print("• Enhanced error handling and fallback mechanisms")
        print("• Detailed device information and compatibility reporting")
        print("• Backward compatibility with existing BMAR audio system")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        logging.exception("Demo error details:")

if __name__ == "__main__":
    main()
