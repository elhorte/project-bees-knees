#!/usr/bin/env python3
"""
BMAR Toggle Helper Script
Provides easy command-line control of BMAR keyboard listener mode.
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# Add modules path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

# Path for the toggle state file
TOGGLE_STATE_FILE = Path(tempfile.gettempdir()) / "bmar_keyboard_state.json"

def read_toggle_state():
    """Read the current toggle state from file."""
    try:
        if TOGGLE_STATE_FILE.exists():
            with open(TOGGLE_STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('enabled', True)
        else:
            # Default to enabled if file doesn't exist
            return True
    except (IOError, json.JSONDecodeError):
        return True

def write_toggle_state(enabled):
    """Write the toggle state to file."""
    try:
        with open(TOGGLE_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'enabled': enabled}, f)
        return True
    except IOError as e:
        print(f"Error writing toggle state: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        current_state = read_toggle_state()
        print("BMAR Toggle Helper")
        print("Usage:")
        print("  python bmar_toggle.py on     - Enable BMAR command mode")
        print("  python bmar_toggle.py off    - Disable BMAR command mode")
        print("  python bmar_toggle.py status - Show current status")
        print()
        print(f"Current status: {'ENABLED' if current_state else 'DISABLED'}")
        return
    
    command = sys.argv[1].lower()
    
    if command in ['on', 'enable', 'start']:
        if write_toggle_state(True):
            print("BMAR command mode enabled.")
            print("The running BMAR application will detect this change.")
        else:
            print("Failed to enable BMAR command mode.")
    elif command in ['off', 'disable', 'stop']:
        if write_toggle_state(False):
            print("BMAR command mode disabled.")
            print("The running BMAR application will detect this change.")
        else:
            print("Failed to disable BMAR command mode.")
    elif command in ['status', 'state']:
        current_state = read_toggle_state()
        status = "ENABLED" if current_state else "DISABLED"
        print(f"BMAR keyboard listener status: {status}")
    else:
        print(f"Unknown command: {command}")
        print("Use 'on', 'off', or 'status'")

if __name__ == "__main__":
    main()
