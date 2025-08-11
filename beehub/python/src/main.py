#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path as _Path

# Ensure src and src/modules are importable for all legacy/new modules
_SRC_DIR = _Path(__file__).resolve().parent
_MOD_DIR = _SRC_DIR / "modules"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_MOD_DIR) not in sys.path:
    sys.path.insert(0, str(_MOD_DIR))

"""
BMAR Main Entry Point
Command-line interface for the Biometric Monitoring and Recording system.

Windows usage examples for log file management:

Write logs to a file with rotation: python main.py --verbose --log-file "C:\Temp\bmar\bmar.log"
Quiet console, but keep file logs: python main.py --quiet --log-file "C:\Temp\bmar\bmar.log"
For time-based rotation, swap RotatingFileHandler for TimedRotatingFileHandler(when="midnight", interval=1, backupCount=7).
"""

import sys, os, argparse, logging, platform
from modules.bmar_config import default_config, set_runtime_overrides
from pathlib import Path
from logging.handlers import RotatingFileHandler
from modules.file_utils import check_and_create_date_folders
from dataclasses import replace, asdict, is_dataclass  # FIX: dataclass utilities

# Simplified imports to avoid circular dependencies
import sounddevice as sd

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

def show_configuration(cfg):
    """Display current BMAR configuration"""
    print("Current BMAR Configuration:")
    print("-" * 40)
    try:
        if is_dataclass(cfg):
            data = asdict(cfg)
            for k in sorted(data.keys()):
                print(f"{k}: {data[k]}")
        else:
            for attr in sorted(a for a in dir(cfg) if not a.startswith("_")):
                try:
                    val = getattr(cfg, attr)
                    if not callable(val):
                        print(f"{attr}: {val}")
                except Exception:
                    print(f"{attr}: <unavailable>")
    except Exception as e:
        print(f"Error displaying configuration: {e}")
    print("-" * 40)

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
        "--show-devices",
        action="store_true",
        help="Alias for --list-devices (show all audio devices and exit)"
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
    parser.add_argument("--data-root", type=Path, help="Override platform data root for this OS")
    parser.add_argument("--win-data-drive", help="Windows data drive, e.g., G:")
    parser.add_argument("--win-data-path", help=r"Windows data path, e.g., 'My Drive\eb_beehive_data'")
    parser.add_argument("--mac-data-root", help="macOS absolute root, e.g., '/Volumes/.../eb_beehive_data'")
    parser.add_argument("--linux-data-root", help="Linux absolute root, e.g., '/data/eb_beehive_data'")
    parser.add_argument(
        "--device-name",
        help="Input audio device name (substring match)."
    )
    parser.add_argument(
        "--api",
        dest="api_name",
        help="Preferred host API name (e.g., WASAPI)."
    )
    parser.add_argument(
        "--hostapi-index",
        type=int,
        help="Preferred host API index."
    )
    return parser

def main():
    """Main application entry point"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    cfg = default_config()

    # Apply runtime-only overrides (no env)
    set_runtime_overrides(
        device_name=args.device_name,
        api_name=args.api_name,
        hostapi_index=args.hostapi_index,
    )

    # Logging setup
    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", force=True)
    logger = logging.getLogger(__name__)

    # If user requested to show devices, do it and exit
    if getattr(args, "list_devices", False) or getattr(args, "show_devices", False):
        try:
            from modules.audio_devices import list_audio_devices_detailed
            list_audio_devices_detailed()
        except Exception as e:
            logger.error("Failed to list audio devices: %s", e, exc_info=True)
            sys.exit(2)
        sys.exit(0)

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

    # cfg already created above

    # Apply CLI overrides (env already applied in default_config)
    sysname = platform.system()
    if sysname == "Windows":
        if args.win_data_drive: cfg = replace(cfg, win_data_drive=args.win_data_drive)
        if args.win_data_path:  cfg = replace(cfg, win_data_path=args.win_data_path.lstrip("\\/"))
        if args.data_root:
            drive, tail = os.path.splitdrive(str(args.data_root))
            tail = tail.lstrip("\\/")
            if drive:
                cfg = replace(cfg, win_data_drive=drive, win_data_path=tail or cfg.win_data_path)
    elif sysname == "Darwin":
        root = args.mac_data_root or (str(args.data_root) if args.data_root else None)
        if root: cfg = replace(cfg, mac_data_root=root)
    else:
        root = args.linux_data_root or (str(args.data_root) if args.data_root else None)
        if root: cfg = replace(cfg, linux_data_root=root)

    dir_info = check_and_create_date_folders(cfg)
    cfg = replace(cfg,
                 PRIMARY_DIRECTORY=Path(dir_info["audio_raw_dir"]),
                 MONITOR_DIRECTORY=Path(dir_info["audio_monitor_dir"]),
                 PLOTS_DIRECTORY=Path(dir_info["plots_dir"]),
    )

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
        show_configuration(cfg)  # FIX: pass the dataclass-based config
        sys.exit(0)
    
    # If no specific command, try to import and run the main app
    try:
        logger.info("Attempting to load main BMAR application...")
        from modules.bmar_app import create_bmar_app
        app = create_bmar_app()
        if app is None:
            logger.error("BMAR application failed to initialize (create_bmar_app returned None). See previous errors.")
            sys.exit(1)

        cfg = app.config  # or however your config object is referenced
        dirs = check_and_create_date_folders(cfg)
        logging.info("Recording directory setup (config): %s", dirs["base_dir"])
        logging.info("Today's audio RAW directory (config): %s", dirs["audio_raw_dir"])
        logging.info("Today's audio MONITOR directory (config): %s", dirs["audio_monitor_dir"])
        logging.info("Today's PLOTS directory (config): %s", dirs["plots_dir"])

        # Back-fill config so legacy code uses the correct folders
        cfg.PRIMARY_DIRECTORY = dirs["audio_raw_dir"]
        cfg.MONITOR_DIRECTORY = dirs["audio_monitor_dir"]
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
