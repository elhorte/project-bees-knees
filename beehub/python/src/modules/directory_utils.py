import os
import re
import logging
from datetime import datetime
from typing import Optional

"""
Directory Utilities Module
Handles creation and management of recording directories.
"""

def _is_date_dir(path: str) -> bool:
    """Return True if the last component looks like YYYY-MM-DD."""
    try:
        base = os.path.basename(os.path.normpath(path or ""))
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", base))
    except Exception:
        return False

def setup_directories():
    """Legacy helper – prefer file_utils.check_and_create_date_folders(cfg)."""
    try:
        home_dir = os.path.expanduser("~")
        recording_dir = os.path.join(home_dir, "BMAR_Recordings")
        os.makedirs(recording_dir, exist_ok=True)
        logging.info(f"Recording directory setup: {recording_dir}")
        return recording_dir
    except Exception as e:
        logging.error(f"Error setting up recording directory: {e}")
        return os.getcwd()

def get_today_dir(recording_dir: str):
    """Return a dated subfolder under recording_dir.
       If recording_dir itself is already a date folder (YYYY-MM-DD), return it unchanged.
    """
    try:
        if not recording_dir:
            return recording_dir
        if _is_date_dir(recording_dir):
            os.makedirs(recording_dir, exist_ok=True)
            logging.debug(f"Today's directory already set: {recording_dir}")
            return recording_dir
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = os.path.join(recording_dir, today)
        os.makedirs(today_dir, exist_ok=True)
        logging.info(f"Today's directory: {today_dir}")
        return today_dir
    except Exception as e:
        logging.error(f"Error setting up today's directory: {e}")
        return recording_dir

def ensure_directory_exists(directory_path: Optional[str]):
    """Ensure a directory exists, creating it if necessary."""
    try:
        if directory_path:
            os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Error creating directory {directory_path}: {e}")
        return False

# Explicit helpers – use these so RAW and MONITOR never get mixed up
def get_today_raw_dir_from_cfg(cfg) -> str:
    """Return today's RAW directory from cfg.PRIMARY_DIRECTORY (already dated)."""
    base = getattr(cfg, "PRIMARY_DIRECTORY", None)
    if not base:
        raise ValueError("cfg.PRIMARY_DIRECTORY is not set")
    return get_today_dir(str(base))

def get_today_monitor_dir_from_cfg(cfg) -> str:
    """Return today's MONITOR directory from cfg.MONITOR_DIRECTORY (already dated)."""
    base = getattr(cfg, "MONITOR_DIRECTORY", None)
    if not base:
        raise ValueError("cfg.MONITOR_DIRECTORY is not set")
    return get_today_dir(str(base))

def get_today_plots_dir_from_cfg(cfg) -> str:
    """Return today's PLOTS directory from cfg.PLOTS_DIRECTORY (already dated)."""
    base = getattr(cfg, "PLOTS_DIRECTORY", None)
    if not base:
        raise ValueError("cfg.PLOTS_DIRECTORY is not set")
    return get_today_dir(str(base))

def build_raw_output_path(cfg, filename: str) -> str:
    base = get_today_raw_dir_from_cfg(cfg)
    return os.path.join(base, filename)

def build_monitor_output_path(cfg, filename: str) -> str:
    base = get_today_monitor_dir_from_cfg(cfg)
    return os.path.join(base, filename)

def build_plots_output_path(cfg, filename: str) -> str:
    base = get_today_plots_dir_from_cfg(cfg)
    return os.path.join(base, filename)