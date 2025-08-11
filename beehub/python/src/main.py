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
"""

import os, argparse, logging, platform
from modules.bmar_config import default_config, set_runtime_overrides
from pathlib import Path
from logging.handlers import RotatingFileHandler
from modules.file_utils import check_and_create_date_folders
from dataclasses import replace, asdict, is_dataclass
import sounddevice as sd
import traceback

def validate_audio_device(device_index: int) -> bool:
    """Validate that the specified audio device exists and is usable"""
    try:
        devices = sd.query_devices()
        if device_index >= len(devices):
            logging.error("Audio device %d not found", device_index)
            return False
        device = devices[device_index]
        if device['max_input_channels'] == 0:
            logging.error("Audio device %d is not an input device", device_index)
            return False
        try:
            with sd.InputStream(device=device_index, channels=1, samplerate=44100, blocksize=1024):
                logging.info("Audio device %d validated successfully", device_index)
                return True
        except Exception:
            logging.warning("Audio device %d may have limited capabilities", device_index)
            return True
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
  python main.py --log-level INFO         # Explicitly set log level
        """
    )
    # Information commands
    parser.add_argument("--list-devices", "-l", action="store_true", help="List available audio devices and exit")
    parser.add_argument("--show-devices", action="store_true", help="Alias for --list-devices (show and exit)")
    parser.add_argument("--config", "-c", action="store_true", help="Show current configuration and exit")
    parser.add_argument("--test-device", type=int, help="Test specific audio device and exit")

    # Logging / verbosity
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable info-level logs")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only errors (suppress info and warnings)")
    parser.add_argument("--log-level", choices=["DEBUG","INFO","WARNING","ERROR","CRITICAL"], help="Explicit log level")
    parser.add_argument("--log-file", type=Path, help="Also write logs to this file (rotates at ~10MB, keeps 5 backups)")

    # Data roots
    parser.add_argument("--data-root", type=Path, help="Override platform data root for this OS")
    parser.add_argument("--win-data-drive", help="Windows data drive, e.g., G:")
    parser.add_argument("--win-data-path", help=r"Windows data path, e.g., 'My Drive\eb_beehive_data'")
    parser.add_argument("--mac-data-root", help="macOS absolute root, e.g., '/Volumes/.../eb_beehive_data'")
    parser.add_argument("--linux-data-root", help="Linux absolute root, e.g., '/data/eb_beehive_data'")

    # Audio selection
    parser.add_argument("--device-name", help="Input audio device name (substring match).")
    parser.add_argument("--api", dest="api_name", help="Preferred host API name (e.g., WASAPI).")
    parser.add_argument("--hostapi-index", type=int, help="Preferred host API index.")
    return parser

def _compute_log_level(args) -> int:
    if args.log_level:
        return getattr(logging, args.log_level.upper(), logging.INFO)
    if args.debug:
        return logging.DEBUG
    if args.quiet:
        return logging.ERROR
    if args.verbose:
        return logging.INFO
    return logging.WARNING

def main():
    """Main application entry point"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    cfg = default_config()

    # Runtime overrides (no env)
    set_runtime_overrides(
        device_name=args.device_name,
        api_name=args.api_name,
        hostapi_index=args.hostapi_index,
    )

    # Logging setup
    log_level = _compute_log_level(args)
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", force=True)
    logger = logging.getLogger(__name__)

    # Optional rotating file output if requested
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(args.log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)

    # Show devices and exit
    if args.list_devices or args.show_devices:
        try:
            from modules.audio_devices import list_audio_devices_detailed
            list_audio_devices_detailed()
        except Exception as e:
            logger.error("Failed to list audio devices: %s", e, exc_info=True)
            sys.exit(2)
        sys.exit(0)

    # Apply CLI data-root overrides
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

    # Ensure directories exist and wire into cfg
    dir_info = check_and_create_date_folders(cfg)
    cfg = replace(
        cfg,
        PRIMARY_DIRECTORY=Path(dir_info["audio_raw_dir"]),
        MONITOR_DIRECTORY=Path(dir_info["audio_monitor_dir"]),
        PLOTS_DIRECTORY=Path(dir_info["plots_dir"]),
    )

    # --test-device
    if args.test_device is not None:
        logger.info("Testing audio device %d", args.test_device)
        ok = validate_audio_device(args.test_device)
        print(f"Device {args.test_device} {'is working correctly' if ok else 'failed validation'}")
        sys.exit(0 if ok else 1)

    # --config
    if args.config:
        logger.info("Showing current configuration")
        show_configuration(cfg)
        sys.exit(0)

    # Run main application
    try:
        logger.info("Attempting to load main BMAR application...")
        from modules.bmar_app import create_bmar_app
        app = create_bmar_app()
        if app is None:
            logger.error("BMAR application failed to initialize (create_bmar_app returned None). See previous errors.")
            sys.exit(1)

        cfg = app.config
        dirs = check_and_create_date_folders(cfg)
        logging.info("Recording directory setup (config): %s", dirs["base_dir"])
        logging.info("Today's audio RAW directory (config): %s", dirs["audio_raw_dir"])
        logging.info("Today's audio MONITOR directory (config): %s", dirs["audio_monitor_dir"])
        logging.info("Today's PLOTS directory (config): %s", dirs["plots_dir"])

        # If cfg is a dataclass and frozen, prefer replace() instead of attribute assignment
        try:
            cfg.PRIMARY_DIRECTORY = dirs["audio_raw_dir"]
            cfg.MONITOR_DIRECTORY = dirs["audio_monitor_dir"]
            cfg.PLOTS_DIRECTORY = dirs["plots_dir"]
        except Exception:
            cfg = replace(
                cfg,
                PRIMARY_DIRECTORY=Path(dirs["audio_raw_dir"]),
                MONITOR_DIRECTORY=Path(dirs["audio_monitor_dir"]),
                PLOTS_DIRECTORY=Path(dirs["plots_dir"]),
            )

        app.run()
    except ImportError as e:
        logger.error("Could not import BMAR application: %s", e)
        logger.info("Try using --list-devices or --test-device commands instead.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        print(f"Application error: {e}")
        traceback.print_exc()
        logging.exception("Application run error")
        sys.exit(1)

if __name__ == "__main__":
    main()
