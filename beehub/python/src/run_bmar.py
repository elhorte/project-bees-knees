#!/usr/bin/env python3
"""
BMAR Quick Launcher
Simple script to run BMAR with minimal setup.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        print("BMAR - Bioacoustic Monitoring and Recording")
        print("=" * 45)
        
        # Import and run the application
        from modules.bmar_app import BmarApp
        
        print("Starting BMAR application...")
        
        # Create and run the application
        app = BmarApp()
        app.run()
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("\nMake sure all required packages are installed:")
        print("pip install numpy scipy matplotlib sounddevice librosa pydub")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
