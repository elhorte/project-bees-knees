#!/usr/bin/env python3
"""
Test script for performance monitoring functions
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_performance_functions():
    """Test the performance monitoring functions."""
    
    print("Testing performance monitoring functions...")
    
    try:
        # Test the system performance function
        from modules.system_utils import get_system_performance, monitor_system_performance_once
        
        print("\n1. Testing get_system_performance():")
        output = get_system_performance()
        print(output)
        
        print("\n2. Testing monitor_system_performance_once():")
        monitor_system_performance_once()
        
        print("\n3. Testing performance monitor from user interface:")
        from modules.bmar_app import BmarApp
        
        # Create a minimal app instance
        app = BmarApp()
        app.initialize()
        
        # Test the performance monitor command handler
        from modules.user_interface import handle_performance_monitor_command
        handle_performance_monitor_command(app)
        
        print("\nAll performance monitoring tests completed successfully!")
        
    except Exception as e:
        print(f"Error in performance test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_performance_functions()
