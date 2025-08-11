#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMAR Main Entry Point
Command-line interface for the Biometric Monitoring and Recording system.

Windows usage examples for log file management:

Write logs to a file with rotation: python main.py --verbose --log-file "C:\Temp\bmar\bmar.log"
Quiet console, but keep file logs: python main.py --quiet --log-file "C:\Temp\bmar\bmar.log"
For time-based rotation, swap RotatingFileHandler for TimedRotatingFileHandler(when="midnight", interval=1, backupCount=7).
"""

import sys
import argparse
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler  

# Simplified imports to avoid circular dependencies
import sounddevice as sd
from modules import bmar_config
from modules.file_utils import check_and_create_date_folders

def list_audio_devices():
    """List all available audio devices using sounddevice"""
    try:
        print("Available audio devices:")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"  [{i}] {device['name']} (Input: {device['max_input_channels']} channels)")
            if device['max_output_channels'] > 0:
                print(f"  [{i}] {device['name']} (Output: {device['max_output_channels']} channels)")
        return True

    except Exception as e:
        logging.error(f"Error listing audio devices: {e}")
        return False

def validate_audio_device(device_index: int) -> bool:
    """Validate that the specified audio device exists and is usable"""
    try:
        # Check if device exists using sounddevice
        devices = sd.query_devices()
        
        if device_index >= len(devices):
            logging.error("Audio device %d not found", device_index)
            return False
            
        device = devices[device_index]
        if device['max_input_channels'] == 0:
            logging.error("Audio device %d is not an input device", device_index)
            return False
        
        # Test basic configuration by creating a simple input stream
        try:
            with sd.InputStream(device=device_index, channels=1, samplerate=44100, blocksize=1024):
                logging.info("Audio device %d validated successfully", device_index)
                return True
        except Exception:
            logging.warning("Audio device %d may have limited capabilities", device_index)
            return True  # Still allow usage, but warn
            
    except Exception as e:
        logging.error("Error validating audio device %d: %s", device_index, e)
        return False

def show_configuration():
    """Display current BMAR configuration"""
    try:
        print("Current BMAR Configuration:")
        print("-" * 40)
        
        # Try different ways to access configuration
        config_found = False
        
        # Method 1: Try direct attribute access
        try:
            if hasattr(bmar_config, 'PRIMARY_IN_SAMPLERATE'):
                print(f"Sample Rate: {bmar_config.PRIMARY_IN_SAMPLERATE} Hz")
                config_found = True
            if hasattr(bmar_config, 'BIT_DEPTH'):
                print(f"Bit Depth: {bmar_config.BIT_DEPTH} bits")
            if hasattr(bmar_config, 'CHANNELS'):
                print(f"Channels: {bmar_config.CHANNELS}")
            if hasattr(bmar_config, 'PRIMARY_DIRECTORY'):
                print(f"Recording Directory: {bmar_config.PRIMARY_DIRECTORY}")
        except:
            pass
        
        # Method 2: Try get_config function with different names
        if not config_found:
            for func_name in ['get_config', 'load_config', 'get_configuration', 'config']:
                if hasattr(bmar_config, func_name):
                    try:
                        config = getattr(bmar_config, func_name)()
                        print(f"Sample Rate: {getattr(config, 'PRIMARY_IN_SAMPLERATE', 'Unknown')} Hz")
                        print(f"Bit Depth: {getattr(config, 'BIT_DEPTH', 'Unknown')} bits")
                        print(f"Channels: {getattr(config, 'CHANNELS', 'Unknown')}")
                        print(f"Recording Directory: {getattr(config, 'PRIMARY_DIRECTORY', 'Unknown')}")
                        config_found = True
                        break
                    except:
                        continue
        
        # Method 3: Show available attributes if nothing else works
        if not config_found:
            print("Available configuration attributes:")
            config_attrs = [attr for attr in dir(bmar_config) if not attr.startswith('_')]
            for attr in sorted(config_attrs):
                try:
                    value = getattr(bmar_config, attr)
                    if not callable(value):
                        print(f"  {attr}: {value}")
                except:
                    print(f"  {attr}: <cannot access>")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"Error loading configuration: {e}")
        print("This may indicate the configuration module needs to be updated for PyAudio migration.")

def setup_argument_parser():
    parser = argparse.ArgumentParser(
        description="BMAR - Biometric Monitoring and Recording System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --list-devices           # List available audio devices
  python main.py --test-device 1          # Test audio device 1
  python main.py --config                 # Show current configuration
  python main.py --debug                  # Enable debug logging
  python main.py --verbose                # Show info-level logs
  python main.py --quiet                  # Only show errors
  python main.py --log-level INFO         # Explicitly set log level (overrides --debug/--verbose/--quiet)
        """
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
        "--test-device",
        type=int,
        help="Test specific audio device and exit"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    # New verbosity controls
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable info-level logs"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only errors (suppress info and warnings)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Explicitly set log level (overrides --debug/--verbose/--quiet)"
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Also write logs to this file (rotates at ~10MB, keeps 5 backups)"
    )
    return parser

def main():
    """Main application entry point"""
    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Set up logging (info off by default; enable with --verbose)
    if args.log_level:
        log_level = getattr(logging, args.log_level)
    elif args.debug:
        log_level = logging.DEBUG
    elif args.verbose:
        log_level = logging.INFO
    elif args.quiet:
        log_level = logging.ERROR
    else:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )

    # Optional rotating file output if requested
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            args.log_file,
            maxBytes=10 * 1024 * 1024,  # ~10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info("BMAR application starting with sounddevices support")
    
    # Handle information commands
    if args.list_devices:
        logger.info("Listing available audio devices")
        if list_audio_devices():
            sys.exit(0)
        else:
            sys.exit(1)
    
    if args.test_device is not None:
        logger.info(f"Testing audio device {args.test_device}")
        if validate_audio_device(args.test_device):
            print(f"Device {args.test_device} is working correctly")
            sys.exit(0)
        else:
            print(f"Device {args.test_device} failed validation")
            sys.exit(1)
    
    if args.config:
        logger.info("Showing current configuration")
        show_configuration()
        sys.exit(0)
    
    # If no specific command, try to import and run the main app
    try:
        logger.info("Attempting to load main BMAR application...")
        from modules.bmar_app import create_bmar_app
        
        app = create_bmar_app()
        
        cfg = app.config  # or however your config object is referenced
        dirs = check_and_create_date_folders(cfg)
        logging.info("Recording directory setup (config): %s", dirs["base_dir"])
        logging.info("Today's audio RAW directory (config): %s", dirs["audio_raw_dir"])
        logging.info("Today's audio MONITOR directory (config): %s", dirs["audio_monitor_dir"])
        logging.info("Today's PLOTS directory (config): %s", dirs["plots_dir"])

        # Back-fill config so legacy code uses the correct folders
        cfg.PRIMARY_DIRECTORY = dirs["audio_raw_dir"]       # RAW saves
        cfg.MONITOR_DIRECTORY = dirs["audio_monitor_dir"]   # MONITOR (safety) saves
        cfg.PLOTS_DIRECTORY = dirs["plots_dir"]

        app.run()
        
    except ImportError as e:
        logger.error(f"Could not import BMAR application: {e}")
        logger.info("Try using --list-devices or --test-device commands instead.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
