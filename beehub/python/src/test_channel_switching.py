#!/usr/bin/env python3
"""
Test script to verify channel switching functionality
"""

import sys
import os
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_channel_switching():
    """Test channel switching functionality."""
    
    print("Testing channel switching...")
    
    try:
        # Create a minimal app instance
        from modules.bmar_app import BmarApp
        
        app = BmarApp()
        if not app.initialize():
            print("Failed to initialize app")
            return
        
        print(f"App initialized successfully:")
        print(f"  Device: {app.device_index}")
        print(f"  Sample rate: {app.samplerate}Hz")
        print(f"  Channels: {app.channels}")
        print(f"  Monitor channel: {app.monitor_channel}")
        
        # Test channel switching command
        from modules.user_interface import handle_channel_switch_command
        
        print("\n" + "="*60)
        print("Testing channel switching:")
        print("="*60)
        
        print(f"Current monitor channel: {app.monitor_channel + 1}")
        
        # Test switching to channel 1 (which should be channel 0 internally)
        print("Testing switch to channel 1...")
        handle_channel_switch_command(app, "1")
        
        # Test invalid channel
        print("Testing switch to invalid channel 5...")
        handle_channel_switch_command(app, "5")
        
        print("\nChannel switching test completed!")
        
    except Exception as e:
        print(f"Error in channel switching test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_channel_switching()
