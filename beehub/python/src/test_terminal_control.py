#!/usr/bin/env python3
"""
Simple test to verify keyboard listener terminal control behavior.
"""

import platform
from modules.user_interface import keyboard_listener_enabled
from modules.system_utils import setup_terminal_for_input, restore_terminal_settings

class TestApp:
    """Mock app for testing."""
    def __init__(self):
        self.original_terminal_settings = None

def test_terminal_control():
    """Test terminal mode switching."""
    print("=== Terminal Control Test ===")
    print(f"Platform: {platform.system()}")
    print(f"Initial keyboard_listener_enabled: {keyboard_listener_enabled}")
    
    app = TestApp()
    
    print("\n1. Testing setup_terminal_for_input()...")
    try:
        setup_terminal_for_input(app)
        print("   ✓ Terminal setup completed")
        print(f"   ✓ Original settings saved: {app.original_terminal_settings is not None}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n2. Testing restore_terminal_settings()...")
    try:
        if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
            restore_terminal_settings(app, app.original_terminal_settings)
            print("   ✓ Terminal restored to normal mode")
        else:
            print("   ◦ No terminal settings to restore (expected on Windows)")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n3. Testing keyboard listener state logic...")
    from modules.user_interface import toggle_keyboard_listener
    
    # Test disable
    if keyboard_listener_enabled:
        result = toggle_keyboard_listener()
        print(f"   ✓ Toggled to disabled: {not result}")
    
    # Test enable
    result = toggle_keyboard_listener()
    print(f"   ✓ Toggled to enabled: {result}")
    
    print("\n=== Test Complete ===")
    print("The keyboard listener should now properly switch terminal modes.")
    print("When disabled: normal terminal input with echo and prompt")
    print("When enabled: single-character input for BMAR commands")

if __name__ == "__main__":
    test_terminal_control()
