import os
import platform
import logging
import datetime

"""
BMAR File Management Module
Handles file operations, directory management, and file discovery.
"""

def _platform_base_root(cfg) -> str:
    """Resolve the platform-specific data root from config with safe fallbacks."""
    sysname = platform.system()
    if sysname == "Windows":
        drive = getattr(cfg, "win_data_drive", None)
        path = getattr(cfg, "win_data_path", None)
        if drive and path:
            drv = str(drive).strip()
            # Normalize to "X:"
            if len(drv) == 1 and drv.isalpha():
                drv = f"{drv.upper()}:"
            elif len(drv) >= 2 and drv[1] != ":" and drv[0].isalpha():
                drv = f"{drv[0].upper()}:"
            path_str = str(path).lstrip("\\/")
            base = os.path.join(drv + os.sep, path_str)
        else:
            base = os.path.join(os.path.expanduser("~"), "eb_beehive_data")
    elif sysname == "Darwin":
        root = getattr(cfg, "mac_data_root", None)
        base = str(root) if root else os.path.join(os.path.expanduser("~"), "eb_beehive_data")
    else:
        root = getattr(cfg, "linux_data_root", None)
        base = str(root) if root else os.path.join(os.path.expanduser("~"), "eb_beehive_data")
    return os.path.normpath(base)

def ensure_directories_exist(directories):
    """
    Check if directories exist and create them if necessary.
    """
    expanded_dirs = [os.path.expanduser(d) for d in directories]
    missing_dirs = [d for d in expanded_dirs if not os.path.exists(d)]
    if not missing_dirs:
        return True

    print("\nCreating the following directories:")
    for d in missing_dirs:
        print(f"  - {d}")

    success = True
    for d in missing_dirs:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            success = False
            logging.error("Failed to create directory '%s': %s", d, e)
    return success

def check_and_create_date_folders(cfg):
    """
    <platform-root>/<LOCATION_ID>/<HIVE_ID>/audio/{monitor,raw,plots}/YYYY-MM-DD
    """
    root = _platform_base_root(cfg)
    location = str(getattr(cfg, "LOCATION_ID", "UNKNOWN"))
    hive = str(getattr(cfg, "HIVE_ID", "UNKNOWN"))

    base_dir = os.path.join(root, location, hive)
    audio_base = os.path.join(base_dir, "audio")
    monitor_base = os.path.join(audio_base, "monitor")
    raw_base = os.path.join(audio_base, "raw")
    plots_base = os.path.join(audio_base, "plots")

    ensure_directories_exist((base_dir, audio_base, monitor_base, raw_base, plots_base))

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    monitor_dir = os.path.join(monitor_base, today)
    raw_dir = os.path.join(raw_base, today)
    plots_dir = os.path.join(plots_base, today)
    ensure_directories_exist((monitor_dir, raw_dir, plots_dir))

    info = {
        "base_dir": os.path.normpath(base_dir),
        "audio_base": os.path.normpath(audio_base),
        "plots_base": os.path.normpath(plots_base),
        "today": today,
        "audio_monitor_dir": os.path.normpath(monitor_dir),
        "audio_raw_dir": os.path.normpath(raw_dir),
        "plots_dir": os.path.normpath(plots_dir),
        "audio_dir": os.path.normpath(raw_dir),  # back-compat alias
    }
    logging.info("Audio raw dir (config): %s", info["audio_raw_dir"])
    logging.info("Audio monitor dir (config): %s", info["audio_monitor_dir"])
    logging.info("Plots dir (config): %s", info["plots_dir"])
    return info

def log_saved_file(path: str, prefix: str = "") -> None:
    try:
        logging.info("%sSaved: %s", f"{prefix}: " if prefix else "", os.path.normpath(path))
    except Exception:
        pass

# --- Back-compat functions expected by BMAR_app ---
def setup_directories(cfg):
    """Legacy: create directories and return a dict of paths."""
    return check_and_create_date_folders(cfg)

def get_today_dir(cfg):
    """Legacy: return today's primary (raw) directory path."""
    info = check_and_create_date_folders(cfg)
    return info["audio_raw_dir"]
# --- end back-compat ---
