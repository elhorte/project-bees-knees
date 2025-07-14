#!/usr/bin/env python3
"""
Test script for detailed device list function
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_detailed_device_list():
    """Test the detailed device list function."""
    
    print("Testing detailed device list function...")
    
    try:
        # Create a minimal app instance
        from modules.bmar_app import BmarApp
        
        app = BmarApp()
        app.initialize()
        
        # Test the detailed device list function
        from modules.audio_devices import show_detailed_device_list
        
        print("\nTesting show_detailed_device_list:")
        show_detailed_device_list(app)
        
        print("\nDetailed device list test completed successfully!")
        
    except Exception as e:
        print(f"Error in detailed device list test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_detailed_device_list()
