#!/usr/bin/env python3
"""
Test character passthrough functionality for keyboard listener.
"""

import sys
import time
from modules.user_interface import keyboard_listener_enabled, toggle_keyboard_listener
from modules.system_utils import get_key, setup_terminal_for_input, restore_terminal_settings

class MockApp:
    """Mock app for testing."""
    def __init__(self):
        self.keyboard_listener_running = True
        self.original_terminal_settings = None

def test_character_passthrough():
    """Test the character passthrough functionality."""
    print("=== Character Passthrough Test ===")
    print("This test simulates the new keyboard listener behavior.")
    print("When disabled, characters should be passed through to terminal.")
    print("Press '^' to toggle, 'q' to quit test.")
    
    app = MockApp()
    setup_terminal_for_input(app)
    
    # Disable keyboard listener for testing passthrough
    if keyboard_listener_enabled:
        toggle_keyboard_listener()
    
    print("\nTest mode: Characters will be echoed, press '^' to toggle, 'q' to quit")
    
    try:
        while app.keyboard_listener_running:
            key = get_key()
            
            if key:
                if not keyboard_listener_enabled:
                    # Simulate passthrough behavior
                    if key == '^':
                        toggle_keyboard_listener()
                    elif key.lower() == 'q':
                        print("\nQuitting test...")
                        break
                    else:
                        # Echo the character to show passthrough
                        sys.stdout.write(key)
                        sys.stdout.flush()
                        
                        if key == '\r' or key == '\n':
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                else:
                    # In enabled mode, just handle basic commands
                    if key == '^':
                        toggle_keyboard_listener()
                    elif key.lower() == 'q':
                        print("\nQuitting test...")
                        break
                    elif key.lower() == 'h':
                        print("\nTest commands: '^' = toggle, 'q' = quit")
                    else:
                        print(f"\n[BMAR mode] Key pressed: '{key}'")
            else:
                time.sleep(0.01)
                
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
            restore_terminal_settings(app, app.original_terminal_settings)
        print("\nTest completed - terminal restored.")

if __name__ == "__main__":
    test_character_passthrough()
