#!/usr/bin/env python3
"""
BMAR Main Entry Point
Command-line interface for the Bioacoustic Monitoring and Recording system.
"""

import sys
import os
import argparse
import logging

# Add the modules directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def setup_argument_parser():
    """Setup command line argument parser."""
    
    parser = argparse.ArgumentParser(
        description="BMAR - Bioacoustic Monitoring and Recording System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Run with default settings
  python main.py --device 1              # Use audio device 1
  python main.py --samplerate 48000       # Use 48kHz sample rate
  python main.py --list-devices           # List available audio devices
  python main.py --config                 # Show current configuration
  python main.py --debug                  # Enable debug logging
        """
    )
    
    # Audio configuration
    parser.add_argument(
        "--device", "-d",
        type=int,
        help="Audio device index to use (use --list-devices to see options)"
    )
    
    parser.add_argument(
        "--samplerate", "-r",
        type=int,
        choices=[8000, 16000, 22050, 44100, 48000, 96000, 192000],
        help="Audio sample rate in Hz"
    )
    
    parser.add_argument(
        "--blocksize", "-b",
        type=int,
        help="Audio block size (buffer size)"
    )
    
    parser.add_argument(
        "--max-file-size", "-m",
        type=int,
        help="Maximum file size in MB before creating new file"
    )
    
    # Directory configuration
    parser.add_argument(
        "--recording-dir", "-o",
        type=str,
        help="Output directory for recordings"
    )
    
    # Information commands
    parser.add_argument(
        "--list-devices", "-l",
        action="store_true",
        help="List available audio devices and exit"
    )
    
    parser.add_argument(
        "--config", "-c",
        action="store_true",
        help="Show current configuration and exit"
    )
    
    parser.add_argument(
        "--test-audio", "-t",
        action="store_true",
        help="Test audio device functionality and exit"
    )
    
    # Debugging and logging
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no interactive prompts, use defaults)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path (default: logs to console)"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="BMAR 1.0.0"
    )
    
    return parser

def configure_logging(debug=False, log_file=None):
    """Configure logging based on command line options."""
    
    level = logging.DEBUG if debug else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    if log_file:
        logging.basicConfig(
            level=level,
            format=format_str,
            filename=log_file,
            filemode='a'
        )
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(level)
        formatter = logging.Formatter(format_str)
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    else:
        logging.basicConfig(level=level, format=format_str)

def list_audio_devices():
    """List available audio devices."""
    
    try:
        from modules.audio_devices import list_audio_devices_detailed
        print("Available Audio Devices:")
        print("=" * 50)
        list_audio_devices_detailed()
        return 0
    except Exception as e:
        print(f"Error listing audio devices: {e}")
        return 1

def show_configuration():
    """Show current configuration."""
    
    try:
        from modules.bmar_config import get_platform_config
        from modules.file_utils import setup_directories
        
        print("BMAR Configuration:")
        print("=" * 40)
        
        # Platform info
        platform_config = get_platform_config()
        print(f"Platform: {platform_config['name']}")
        if platform_config['is_wsl']:
            print("WSL detected - audio routing may require configuration")
        
        # Default directories
        recording_dir = setup_directories()
        print(f"Default recording directory: {recording_dir}")
        
        # Audio defaults
        print(f"Default sample rate: 44100 Hz")
        print(f"Default block size: 1024 samples")
        print(f"Default max file size: 100 MB")
        
        return 0
    except Exception as e:
        print(f"Error showing configuration: {e}")
        return 1

def test_audio_device(device_index=None):
    """Test audio device functionality."""
    
    try:
        from modules.audio_devices import get_audio_device_config
        from modules.audio_tools import audio_device_test
        
        print("Testing Audio Device...")
        print("-" * 30)
        
        if device_index is None:
            device_config = get_audio_device_config()
            if not device_config:
                print("No suitable audio device found")
                return 1
            device_index = device_config['device_index']
        
        print(f"Testing device {device_index}...")
        success = audio_device_test(device_index)
        
        if success:
            print("Audio device test PASSED")
            return 0
        else:
            print("Audio device test FAILED")
            return 1
            
    except Exception as e:
        print(f"Error testing audio device: {e}")
        return 1

def main():
    """Main entry point."""
    
    try:
        # Parse command line arguments
        parser = setup_argument_parser()
        args = parser.parse_args()
        
        # Configure logging
        configure_logging(args.debug, args.log_file)
        
        # Handle information commands that don't require the full app
        if args.list_devices:
            return list_audio_devices()
        
        if args.config:
            return show_configuration()
        
        if args.test_audio:
            return test_audio_device(args.device)
        
        # Import and create the main application
        from modules import create_bmar_app
        
        print("Creating BMAR application...")
        app = create_bmar_app()
        
        if app is None:
            print("Failed to create BMAR application")
            return 1
        
        # Set headless mode if specified
        if args.headless:
            app.headless = True
            print("Running in headless mode (no interactive prompts)")
        
        # Apply command line overrides
        if args.device is not None:
            app.device_index = args.device
            print(f"Using audio device: {args.device}")
        
        if args.samplerate is not None:
            app.samplerate = args.samplerate
            print(f"Using sample rate: {args.samplerate}Hz")
        
        if args.blocksize is not None:
            app.blocksize = args.blocksize
            print(f"Using block size: {args.blocksize}")
        
        if args.max_file_size is not None:
            app.max_file_size_mb = args.max_file_size
            print(f"Using max file size: {args.max_file_size}MB")
        
        if args.recording_dir is not None:
            app.recording_dir = args.recording_dir
            print(f"Using recording directory: {args.recording_dir}")
        
        # Run the application
        print("\nStarting BMAR application...")
        print("Press 'h' for help once the application starts")
        print("Press 'q' to quit")
        print("-" * 50)
        
        return app.run()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Application error: {e}")
        if args.debug if 'args' in locals() else False:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
