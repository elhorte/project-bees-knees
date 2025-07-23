#!/usr/bin/env python3
"""
Test script to demonstrate keyboard toggle functionality.
This simulates the keyboard listener behavior with terminal control.
"""

import time
import threading
from modules.user_interface import keyboard_listener_enabled, background_keyboard_monitor
from modules.system_utils import get_key, setup_terminal_for_input, restore_terminal_settings

class MockApp:
    """Mock app class for testing."""
    def __init__(self):
        self.keyboard_listener_running = True
        self.original_terminal_settings = None

def test_keyboard_toggle():
    """Test the keyboard toggle functionality."""
    
    app = MockApp()
    
    print("=== Keyboard Toggle Test ===")
    print("This test demonstrates terminal control switching.")
    print("1. Initially, BMAR has terminal control")
    print("2. Press '^' to release terminal control")
    print("3. Try typing commands in the terminal")
    print("4. Press '^' again to return control to BMAR")
    print("5. Press 'q' to quit this test")
    print("\nStarting test in 3 seconds...")
    
    time.sleep(3)
    
    # Start background keyboard monitor
    if hasattr(threading, 'Thread'):
        monitor_thread = threading.Thread(
            target=background_keyboard_monitor,
            args=(app,),
            daemon=True
        )
        monitor_thread.start()
        print("Background keyboard monitor started.")
    
    print("\nBMAR Test Mode - Press '^' to toggle, 'q' to quit")
    
    # Track terminal mode
    terminal_in_raw_mode = False
    
    try:
        while app.keyboard_listener_running:
            # Check if keyboard listener is enabled
            if not keyboard_listener_enabled:
                # Restore terminal to normal mode when disabled
                if terminal_in_raw_mode:
                    if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
                        restore_terminal_settings(app, app.original_terminal_settings)
                    terminal_in_raw_mode = False
                    print("Terminal restored to normal mode - you can type commands now")
                
                time.sleep(0.1)
                continue
            else:
                # Set up raw mode when enabled
                if not terminal_in_raw_mode:
                    setup_terminal_for_input(app)
                    terminal_in_raw_mode = True
                    print("Terminal in BMAR control mode - single key commands")
                
                # Get key input
                key = get_key()
                if key:
                    if key.lower() == 'q':
                        print("\nQuitting test...")
                        break
                    elif key == 'h':
                        print("\nTest Commands:")
                        print("  '^' - Toggle keyboard listener")
                        print("  'h' - This help")
                        print("  'q' - Quit test")
                    else:
                        print(f"\nKey pressed: '{key}' (use 'h' for help)")
                
                time.sleep(0.05)  # Small delay to prevent high CPU usage
                
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        # Always restore terminal
        if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
            restore_terminal_settings(app, app.original_terminal_settings)
        app.keyboard_listener_running = False
        print("Terminal restored to normal mode")
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    test_keyboard_toggle()
