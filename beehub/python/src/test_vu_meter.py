#!/usr/bin/env python3
"""
Test VU meter functionality
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_vu_meter():
    """Test VU meter functionality."""
    
    print("Testing VU meter...")
    
    try:
        # Create a minimal app instance
        from modules.bmar_app import BmarApp
        
        app = BmarApp()
        if not app.initialize():
            print("Failed to initialize app")
            return
        
        print("\n" + "="*60)
        print("Testing VU meter ('v' command):")
        print("="*60)
        print("Note: This will start VU meter - press Ctrl+C to stop")
        
        # Test VU meter
        from modules.user_interface import handle_vu_meter_command
        handle_vu_meter_command(app)
        
        print("\nVU meter test completed!")
        
    except KeyboardInterrupt:
        print("\nVU meter stopped by user")
    except Exception as e:
        print(f"Error in VU meter test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vu_meter()
