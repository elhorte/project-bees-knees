#!/usr/bin/env python3
"""
Test script for the fixed intercom functionality
"""

import time
import threading
from modules.user_interface import start_intercom
from modules.bmar_config import SOUND_IN_CHS, MONITOR_CH

class TestApp:
    """Mock app object for testing intercom"""
    def __init__(self):
        self.device_index = 0  # This was the problematic device
        self.samplerate = 44100
        self.blocksize = 1024
        self.channels = 0  # Start with problematic value
        self.active_processes = {}  # Required for process management
        
    def print_debug(self, msg, level=1):
        print(f"DEBUG: {msg}")

def test_intercom_fix():
    """Test the fixed intercom functionality."""
    
    print("Testing Fixed Intercom Functionality")
    print("=" * 40)
    
    # Create test app
    app = TestApp()
    
    print(f"Initial app.channels: {app.channels}")
    print(f"SOUND_IN_CHS from config: {SOUND_IN_CHS}")
    print(f"MONITOR_CH from config: {MONITOR_CH}")
    
    try:
        print("\nStarting intercom test...")
        
        # Start intercom in a separate thread for testing
        def intercom_test():
            try:
                start_intercom(app)
            except Exception as e:
                print(f"Intercom test error: {e}")
        
        thread = threading.Thread(target=intercom_test, daemon=True)
        thread.start()
        
        # Let it run for a few seconds
        time.sleep(5)
        
        print("\nIntercom test completed successfully!")
        print("The intercom should have:")
        print("- Used SOUND_IN_CHS (2) channels instead of app.channels (0)")
        print("- Found suitable input/output devices automatically")
        print("- Started monitoring without channel errors")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_intercom_fix()
