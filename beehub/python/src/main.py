#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path as _Path

# Ensure src and src/modules are importable
_SRC_DIR = _Path(__file__).resolve().parent
_MOD_DIR = _SRC_DIR / "modules"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_MOD_DIR) not in sys.path:
    sys.path.insert(0, str(_MOD_DIR))

import argparse
import datetime
import logging
import platform
import traceback
from dataclasses import replace
from pathlib import Path
from logging.handlers import RotatingFileHandler
import sounddevice as sd

from modules.bmar_config import default_config, wire_today_dirs


def validate_audio_device(device_index: int) -> bool:
    """Validate that the specified audio device exists and is usable."""
    try:
        devices = sd.query_devices()
        if device_index < 0 or device_index >= len(devices):
            logging.error("Audio device %d not found", device_index)
            return False
        dev = devices[device_index]
        if int(dev.get('max_input_channels', 0)) == 0:
            logging.error("Audio device %d is not an input device", device_index)
            return False
        try:
            # Validate with PCM16 to match primary capture path
            with sd.InputStream(device=device_index, channels=1, samplerate=44100, blocksize=1024, dtype='int16'):
                logging.info("Audio device %d validated successfully", device_index)
                return True
        except Exception:
            logging.warning("Audio device %d may have limited capabilities", device_index)
            return True
    except Exception as e:
        logging.error("Error validating audio device %d: %s", device_index, e)
        return False


def setup_argument_parser():
    p = argparse.ArgumentParser(description="BMAR - Biometric Monitoring and Recording System")
    p.add_argument("--list-devices", "-l", action="store_true")
    p.add_argument("--show-devices", action="store_true")
    p.add_argument("--config", "-c", action="store_true")
    p.add_argument("--test-device", type=int)

    p.add_argument("--debug", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--quiet", "-q", action="store_true")
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    p.add_argument("--log-file", type=Path)

    p.add_argument("--device-name")
    p.add_argument("--api", dest="api_name")
    p.add_argument("--hostapi-index", type=int)

    p.add_argument("--data-root", type=Path)
    p.add_argument("--win-data-drive")
    p.add_argument("--win-data-path")
    p.add_argument("--mac-data-root")
    p.add_argument("--linux-data-root")
    return p


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


def _extract_dir_paths(d: dict) -> tuple[str, str, str]:
    """
    Normalize return keys from check_and_create_date_folders.
    Accepts variants: raw/monitor/plots or audio_raw_dir/audio_monitor_dir/plots_dir.
    """
    raw = d.get("raw") or d.get("audio_raw_dir")
    mon = d.get("monitor") or d.get("audio_monitor_dir")
    plt = d.get("plots") or d.get("plots_dir")
    return str(raw) if raw else "", str(mon) if mon else "", str(plt) if plt else ""


def main():
    parser = setup_argument_parser()
    args = parser.parse_args()

    cfg = default_config()
    try:
        cfg, wired = wire_today_dirs(cfg)
        logging.info("Audio raw dir (config): %s", wired["raw"])
        logging.info("Audio monitor dir (config): %s", wired["monitor"])
        logging.info("Plots dir (config): %s", wired["plots"])
    except Exception as e:
        logging.warning("Failed to wire directories: %s", e)

    # Create the app and pass cfg (ensures BmarApp sees the dataclass-based config)
    from modules.bmar_app import create_bmar_app
    app = create_bmar_app()
    try:
        app.config = cfg
    except Exception:
        pass

    if app is None:
        logging.error("BMAR application failed to initialize")
        sys.exit(1)

    # Ensure app uses cfg
    try:
        app.config = cfg
    except Exception:
        pass

    app.run()

if __name__ == "__main__":
    main()
