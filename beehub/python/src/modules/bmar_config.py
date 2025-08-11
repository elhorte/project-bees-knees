from dataclasses import dataclass, replace
import datetime
import os
import platform
from typing import Optional, List
from pathlib import Path  # FIX: used in type hints and defaults

@dataclass(frozen=True)
class BMARConfig:
    # IDs
    LOCATION_ID: str = "Zeev-Berkeley"
    HIVE_ID: str = "Z1_4mic"
    HIVE_CONFIG: str = "dual-mic, sensor"

    # Modes
    MODE_AUDIO_MONITOR: bool = True
    MODE_PERIOD: bool = True
    MODE_EVENT: bool = False
    MODE_FFT_PERIODIC_RECORD: bool = True

    # Audio/capture basics
    BUFFER_SECONDS: int = 900
    SOUND_IN_CHS: int = 1
    SOUND_OUT_SR_DEFAULT: int = 48000
    SOUND_OUT_ID_DEFAULT: Optional[int] = None

    # Monitor/MP3 settings
    AUDIO_MONITOR_START: Optional[datetime.time] = None
    AUDIO_MONITOR_END: Optional[datetime.time] = datetime.time(23, 0, 0)
    AUDIO_MONITOR_RECORD: int = 900
    AUDIO_MONITOR_INTERVAL: float = 0.1
    AUDIO_MONITOR_QUALITY: int = 128

    # Platform data roots (used by file_utils._platform_base_root)
    win_data_drive: Optional[str] = None     # e.g., "G:"
    win_data_path: Optional[str] = None      # e.g., r"My Drive\eb_beehive_data" (NO leading slash)
    mac_data_root: Optional[str] = None      # e.g., "/Volumes/GoogleDrive/My Drive/eb_beehive_data"
    linux_data_root: Optional[str] = None    # e.g., "/data/eb_beehive_data"

    # Derived/output paths (set at runtime)
    PRIMARY_DIRECTORY: Optional[Path] = None       # audio/raw/YYYY-MM-DD
    MONITOR_DIRECTORY: Optional[Path] = None       # audio/monitor/YYYY-MM-DD
    PLOTS_DIRECTORY: Optional[Path] = None         # audio/plots/YYYY-MM-DD

    # Audio device selection (per-OS). Use empty strings/lists for "not set".
    # Linux
    linux_make_name: str = ""
    linux_model_name: List[str] = None  # tokens to match (substring, case-insensitive)
    linux_device_name: str = ""
    linux_api_name: str = "ALSA"
    linux_hostapi_name: str = "ALSA"
    linux_hostapi_index: Optional[int] = None
    linux_device_id: Optional[int] = None

    # Windows
    windows_make_name: str = "Behringer"
    windows_model_name: str = "UMC204HD"
    windows_device_name: str = "UMC204HD"
    windows_api_name: str = "WASAPI"
    windows_hostapi_name: str = "WASAPI"
    windows_hostapi_index: Optional[int] = None
    windows_device_id: Optional[int] = None

    # macOS (Darwin)
    mac_make_name: str = ""
    mac_model_name: List[str] = None
    mac_device_name: str = "Built-in"
    mac_api_name: str = "Core Audio"
    mac_hostapi_name: str = "Core Audio"
    mac_hostapi_index: Optional[int] = None
    mac_device_id: Optional[int] = None

# Ensure list defaults are lists
def _fix_list_defaults(cfg: BMARConfig) -> BMARConfig:
    return replace(
        cfg,
        linux_model_name=cfg.linux_model_name or [],
        mac_model_name=cfg.mac_model_name or [],
    )

def default_config() -> BMARConfig:
    """OS-sensed defaults with env overrides."""
    cfg = BMARConfig()
    return _fix_list_defaults(cfg)

# Runtime overrides (optional; CLI can set them during this run only)
_runtime = {"Windows": {}, "Darwin": {}, "Linux": {}}

def set_runtime_overrides(device_name: Optional[str] = None,
                          api_name: Optional[str] = None,
                          hostapi_name: Optional[str] = None,
                          hostapi_index: Optional[int] = None):
    sysname = platform.system()
    if device_name not in (None, ""):
        _runtime[sysname]["device_name"] = device_name
    if api_name not in (None, ""):
        _runtime[sysname]["api_name"] = api_name
    if hostapi_name not in (None, ""):
        _runtime[sysname]["hostapi_name"] = hostapi_name
    if hostapi_index is not None:
        _runtime[sysname]["hostapi_index"] = hostapi_index

def _tokens(x) -> List[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x else []
    return [t for t in x if t]

def device_search_criteria(cfg: Optional[BMARConfig] = None) -> dict:
    """
    Returns normalized search spec for current platform:
    {
      'name_tokens': [...],
      'model_tokens': [...],
      'make_tokens': [...],
      'api_name': str|None,
      'hostapi_name': str|None,
      'hostapi_index': int|None,
      'device_id': int|None,
      'strict': bool   # True if any selector provided
    }
    """
    cfg = _fix_list_defaults(cfg or default_config())
    sysname = platform.system()
    if sysname == "Windows":
        name = cfg.windows_device_name
        model = _tokens(cfg.windows_model_name)
        make = _tokens(cfg.windows_make_name)
        api = cfg.windows_api_name
        hostapi = cfg.windows_hostapi_name
        hostapi_idx = cfg.windows_hostapi_index
        dev_id = cfg.windows_device_id
    elif sysname == "Darwin":
        name = cfg.mac_device_name
        model = _tokens(cfg.mac_model_name)
        make = _tokens(cfg.mac_make_name)
        api = cfg.mac_api_name
        hostapi = cfg.mac_hostapi_name
        hostapi_idx = cfg.mac_hostapi_index
        dev_id = cfg.mac_device_id
    else:
        name = cfg.linux_device_name
        model = _tokens(cfg.linux_model_name)
        make = _tokens(cfg.linux_make_name)
        api = cfg.linux_api_name
        hostapi = cfg.linux_hostapi_name
        hostapi_idx = cfg.linux_hostapi_index
        dev_id = cfg.linux_device_id

    # Apply runtime overrides
    ov = _runtime.get(sysname, {})
    name = ov.get("device_name", name)
    api = ov.get("api_name", api)
    hostapi = ov.get("hostapi_name", hostapi)
    hostapi_idx = ov.get("hostapi_index", hostapi_idx)

    strict = any([name, model, make, hostapi, hostapi_idx is not None, dev_id is not None])
    return {
        "name_tokens": _tokens(name),
        "model_tokens": model,
        "make_tokens": make,
        "api_name": api or None,
        "hostapi_name": hostapi or None,
        "hostapi_index": hostapi_idx,
        "device_id": dev_id,
        "strict": strict,
    }

# Back-compat: legacy constants (export derived from dataclass)
def _derive_constants(cfg: Optional[BMARConfig] = None):
    cfg = _fix_list_defaults(cfg or default_config())
    return {
        # Linux
        "LINUX_MAKE_NAME": cfg.linux_make_name,
        "LINUX_MODEL_NAME": cfg.linux_model_name,
        "LINUX_DEVICE_NAME": cfg.linux_device_name,
        "LINUX_API_NAME": cfg.linux_api_name,
        "LINUX_HOSTAPI_NAME": cfg.linux_hostapi_name,
        "LINUX_HOSTAPI_INDEX": cfg.linux_hostapi_index,
        "LINUX_DEVICE_ID": cfg.linux_device_id,
        # Windows
        "WINDOWS_MAKE_NAME": cfg.windows_make_name,
        "WINDOWS_MODEL_NAME": cfg.windows_model_name,
        "WINDOWS_DEVICE_NAME": cfg.windows_device_name,
        "WINDOWS_API_NAME": cfg.windows_api_name,
        "WINDOWS_HOSTAPI_NAME": cfg.windows_hostapi_name,
        "WINDOWS_HOSTAPI_INDEX": cfg.windows_hostapi_index,
        "WINDOWS_DEVICE_ID": cfg.windows_device_id,
        # macOS
        "MACOS_MAKE_NAME": cfg.mac_make_name,
        "MACOS_MODEL_NAME": cfg.mac_model_name,
        "MACOS_DEVICE_NAME": cfg.mac_device_name,
        "MACOS_API_NAME": cfg.mac_api_name,
        "MACOS_HOSTAPI_NAME": cfg.mac_hostapi_name,
        "MACOS_HOSTAPI_INDEX": cfg.mac_hostapi_index,
        "MACOS_DEVICE_ID": cfg.mac_device_id,
    }

_consts = _derive_constants()
globals().update(_consts)

AUDIO_API_PREFERENCE = {
    "Windows": ["WASAPI", "WDM-KS", "MME", "DirectSound", "ASIO"],
    "Darwin":  ["Core Audio"],
    "Linux":   ["ALSA", "JACK", "PulseAudio", "OSS"],
}
def API_PREFERENCE_FOR_PLATFORM():
    return AUDIO_API_PREFERENCE.get(platform.system(), [])

__all__ = [
    "BMARConfig", "default_config", "set_runtime_overrides",
    "device_search_criteria", "AUDIO_API_PREFERENCE", "API_PREFERENCE_FOR_PLATFORM",
    # legacy constant names:
    "LINUX_MAKE_NAME","LINUX_MODEL_NAME","LINUX_DEVICE_NAME","LINUX_API_NAME","LINUX_HOSTAPI_NAME","LINUX_HOSTAPI_INDEX","LINUX_DEVICE_ID",
    "WINDOWS_MAKE_NAME","WINDOWS_MODEL_NAME","WINDOWS_DEVICE_NAME","WINDOWS_API_NAME","WINDOWS_HOSTAPI_NAME","WINDOWS_HOSTAPI_INDEX","WINDOWS_DEVICE_ID",
    "MACOS_MAKE_NAME","MACOS_MODEL_NAME","MACOS_DEVICE_NAME","MACOS_API_NAME","MACOS_HOSTAPI_NAME","MACOS_HOSTAPI_INDEX","MACOS_DEVICE_ID",
]
# --- end back-compat ---
def get_platform_audio_config(platform_manager, _cfg_module=None):
    """
    Back-compat helper used by bmar_app. Uses BMARConfig values only (no env).
    Returns dict with keys: data_drive, data_path, folders.
    """
    cfg = default_config()
    sysname = platform.system()
    if sysname == "Windows":
        drive = (cfg.win_data_drive or "").strip()
        if drive and len(drive) == 1 and drive.isalpha():
            drive = f"{drive.upper()}:"
        elif drive and len(drive) >= 2 and drive[1] != ":" and drive[0].isalpha():
            drive = f"{drive[0].upper()}:"
        data_drive = drive  # e.g., "G:"
        data_path = (cfg.win_data_path or "eb_beehive_data").lstrip("\\/")
    elif sysname == "Darwin":
        data_drive = ""
        data_path = cfg.mac_data_root or os.path.join(os.path.expanduser("~"), "eb_beehive_data")
    else:
        data_drive = ""
        data_path = cfg.linux_data_root or os.path.join(os.path.expanduser("~"), "eb_beehive_data")

    folders = {"primary": "primary", "monitor": "monitor", "plots": "plots"}
    return {"data_drive": data_drive, "data_path": data_path, "folders": folders}
