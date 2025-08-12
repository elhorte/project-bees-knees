import os
import platform
import logging
from pathlib import Path
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

def check_and_create_date_folders(config=None):
    """
    Create today's raw/monitor/plots folders under configured audio root and
    wire them onto bmar_config so other modules (plotting, UI) use the same paths.
    """
    try:
        from .bmar_config import get_platform_audio_config, default_config
        import modules.bmar_config as _cfgmod  # module to attach runtime dirs
    except Exception as e:
        logging.error("bmar_config import error: %s", e)
        return None

    cfg = config if config is not None else default_config()
    plat = get_platform_audio_config(None, cfg)

    # Build audio root: <drive>/<path>/<LOCATION>/<HIVE>/audio
    audio_root = Path(plat["data_drive"]) / plat["data_path"] / cfg.LOCATION_ID / cfg.HIVE_ID / "audio"
    today = datetime.date.today().strftime("%Y-%m-%d")

    raw_dir = audio_root / "raw" / today
    monitor_dir = audio_root / "monitor" / today
    plots_dir = audio_root / "plots" / today

    # Ensure folders exist
    for p in (raw_dir, monitor_dir, plots_dir):
        p.mkdir(parents=True, exist_ok=True)

    logging.info(f"Audio raw dir (config): {raw_dir}")
    logging.info(f"Audio monitor dir (config): {monitor_dir}")
    logging.info(f"Plots dir (config): {plots_dir}")

    # Wire onto config module for use by plotting/UI/etc.
    try:
        _cfgmod.PRIMARY_DIRECTORY = raw_dir
        _cfgmod.MONITOR_DIRECTORY = monitor_dir
        _cfgmod.PLOTS_DIRECTORY = plots_dir
    except Exception as e:
        logging.warning("Could not wire runtime directories onto bmar_config: %s", e)

    # Export for consumers that avoid importing bmar_config at runtime
    os.environ["BMAR_AUDIO_RAW_DIR"] = str(raw_dir)
    os.environ["BMAR_AUDIO_MONITOR_DIR"] = str(monitor_dir)
    os.environ["BMAR_PLOTS_DIR"] = str(plots_dir)
    return {
        "raw": str(raw_dir),
        "monitor": str(monitor_dir),
        "plots": str(plots_dir),
    }

def log_saved_file(path: str, prefix: str = "") -> None:
    try:
        logging.info("%sSaved: %s", f"{prefix}: " if prefix else "", os.path.normpath(path))
    except Exception:
        pass

# If setup_directories/get_today_dir exist, keep behavior but ensure we wire runtime paths too
def setup_directories(config=None):
    d = check_and_create_date_folders(config)
    return Path(d["raw"]).parent if d else Path.home() / "BMAR_Recordings"

def get_today_dir(recording_dir):
    # Expect recording_dir like .../audio/raw/<date>
    rd = Path(recording_dir)
    return rd if rd.name.count("-") == 2 else rd / datetime.date.today().strftime("%Y-%m-%d")
