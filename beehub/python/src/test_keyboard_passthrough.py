#!/usr/bin/env python3
"""
Test script for keyboard listener passthrough functionality.
This allows testing the keyboard listener in isolation.
"""

import sys
import os
import threading
import time

# Add modules path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

from modules.user_interface import keyboard_listener, keyboard_listener_enabled, toggle_keyboard_listener

class MockApp:
    """Mock app for testing keyboard listener."""
    def __init__(self):
        self.keyboard_listener_running = True
        self.monitor_channel = 0
        self.is_macos = False
        self.os_info = {}
        self.DEBUG_VERBOSE = False

def main():
    print("=== BMAR Keyboard Listener Test ===")
    print("This will test the keyboard listener passthrough functionality.")
    print(f"Current state: keyboard_listener_enabled = {keyboard_listener_enabled}")
    print()
    print("Commands to test:")
    print("- Press '^' to toggle between BMAR command mode and terminal passthrough")
    print("- In BMAR mode: 'h' for help, 'q' to quit")
    print("- In passthrough mode: type normally, press '^' to return to BMAR mode")
    print("- Press Ctrl+C to exit")
    print()
    
    # Create mock app
    app = MockApp()
    
    # Test toggle function first
    print("Testing toggle function:")
    print(f"Initial state: {keyboard_listener_enabled}")
    state1 = toggle_keyboard_listener()
    print(f"After first toggle: {state1}")
    state2 = toggle_keyboard_listener()  
    print(f"After second toggle: {state2}")
    print()
    
    try:
        print("Starting keyboard listener...")
        print("Press Ctrl+C to stop the test.")
        
        # Start keyboard listener in a separate thread
        listener_thread = threading.Thread(target=keyboard_listener, args=(app,), daemon=True)
        listener_thread.start()
        
        # Keep main thread alive
        while listener_thread.is_alive():
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping test...")
        app.keyboard_listener_running = False
    finally:
        print("Test completed.")

if __name__ == "__main__":
    main()
