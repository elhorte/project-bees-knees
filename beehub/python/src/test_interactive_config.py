#!/usr/bin/env python3
"""
Test script to verify interactive configuration prompts
"""

import sys
import os
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_interactive_config():
    """Test interactive configuration functionality."""
    
    print("Testing interactive configuration...")
    
    try:
        # Test timed_input function
        from modules.user_interface import timed_input
        from modules.bmar_app import BmarApp
        
        app = BmarApp()
        app.headless = False  # Ensure interactive mode
        
        print("\n" + "="*60)
        print("Testing timed_input function:")
        print("="*60)
        
        print("Test 1: Normal prompt (you have 5 seconds to respond)")
        response = timed_input(app, "Enter 'y' to continue (y/N): ", timeout=5, default='n')
        print(f"You responded: '{response}'")
        
        print("\nTest 2: Headless mode test")
        app.headless = True
        response = timed_input(app, "This should use default immediately: ", timeout=3, default='auto')
        print(f"Headless response: '{response}'")
        
        # Test audio device configuration
        app.headless = False  # Back to interactive
        app.channels = 2  # Set to 2 to test channel adjustment prompts
        app.samplerate = 44100
        
        print("\n" + "="*60)
        print("Testing interactive audio device configuration:")
        print("="*60)
        
        from modules.audio_devices import configure_audio_device_interactive
        
        success = configure_audio_device_interactive(app)
        
        if success:
            print("Audio configuration completed successfully!")
            print(f"  Device: {app.device_index}")
            print(f"  Channels: {app.channels}")
            print(f"  Sample rate: {app.samplerate}")
        else:
            print("Audio configuration failed or was cancelled")
        
        print("\nInteractive configuration test completed!")
        
    except Exception as e:
        print(f"Error in interactive configuration test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_interactive_config()
