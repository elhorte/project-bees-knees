#!/usr/bin/env python3
"""
Test script to verify both d and D commands work correctly
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_both_device_commands():
    """Test both lowercase and uppercase device commands."""
    
    print("Testing both device commands...")
    
    try:
        # Create a minimal app instance
        from modules.bmar_app import BmarApp
        
        app = BmarApp()
        app.initialize()
        
        # Test lowercase 'd' command (current device)
        print("\n" + "="*60)
        print("Testing lowercase 'd' command (current device):")
        print("="*60)
        from modules.audio_devices import show_current_audio_devices
        show_current_audio_devices(app)
        
        # Test uppercase 'D' command (all devices)
        print("\n" + "="*60)
        print("Testing uppercase 'D' command (all devices):")
        print("="*60)
        from modules.audio_devices import show_detailed_device_list
        show_detailed_device_list(app)
        
        print("\n" + "="*60)
        print("Both device commands test completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"Error in device commands test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_both_device_commands()
