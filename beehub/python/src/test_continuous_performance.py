#!/usr/bin/env python3
"""
Test script for continuous performance monitoring
"""

import sys
import os
import multiprocessing
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_continuous_performance():
    """Test the continuous performance monitoring function."""
    
    print("Testing continuous performance monitoring...")
    
    try:
        # Test the standalone function
        from modules.system_utils import monitor_system_performance_continuous_standalone
        
        print("\nTesting standalone continuous performance monitor...")
        
        # Create a shared dictionary to control the stop signal
        manager = multiprocessing.Manager()
        stop_event_dict = manager.dict()
        stop_event_dict['stop'] = False
        
        # Start the process
        process = multiprocessing.Process(
            target=monitor_system_performance_continuous_standalone,
            args=(stop_event_dict,),
            daemon=True
        )
        
        process.start()
        print(f"Performance monitor started with PID: {process.pid}")
        
        # Let it run for a few seconds
        print("Letting it run for 5 seconds...")
        time.sleep(5)
        
        # Stop it
        print("Stopping performance monitor...")
        stop_event_dict['stop'] = True
        
        # Wait for it to finish
        process.join(timeout=3)
        
        if process.is_alive():
            print("Force terminating process...")
            process.terminate()
            process.join()
        
        print("Continuous performance monitor test completed!")
        
    except Exception as e:
        print(f"Error in continuous performance test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_continuous_performance()
