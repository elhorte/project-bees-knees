#!/usr/bin/env python3
"""
Test script for current audio devices function
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_current_devices():
    """Test the current audio devices function."""
    
    print("Testing current audio devices function...")
    
    try:
        # Create a minimal app instance
        from modules.bmar_app import BmarApp
        
        app = BmarApp()
        app.initialize()
        
        # Test the current devices function
        from modules.audio_devices import show_current_audio_devices
        
        print("\nTesting show_current_audio_devices:")
        show_current_audio_devices(app)
        
        print("\nCurrent audio devices test completed successfully!")
        
    except Exception as e:
        print(f"Error in current audio devices test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_current_devices()
