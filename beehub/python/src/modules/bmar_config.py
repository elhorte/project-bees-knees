from __future__ import annotations
"""
BMAR Configuration Module
Humans edit the section labeled "USER CONFIGURATION" below to configure the program.
The rest of this file adapts those values for runtime.
"""

import os
import platform
import datetime
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# --------------------------------------------------------------------------------------
# USER CONFIGURATION (edit these values)
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BMARConfig:

    # Canonical subfolder names under the audio root
    RAW_FOLDER_NAME: str = "raw"                # data folder for primary audio recordings
    MONITOR_FOLDER_NAME: str = "monitor"        # mp3/continuous recordings
    PLOTS_FOLDER_NAME: str = "plots"            # data folder for audio plots

    # Runtime-wired directories (set by wire_today_dirs)
    PRIMARY_DIRECTORY: Optional[Path] = None
    MONITOR_DIRECTORY: Optional[Path] = None
    PLOTS_DIRECTORY: Optional[Path] = None

    # Identity
    LOCATION_ID: str = "Zeev-Berkeley"
    HIVE_ID: str = "Z1_4mic"
    HIVE_CONFIG: str = "dual-mic, sensor"
    
    # Modes and timing
    MODE_AUDIO_MONITOR: bool = True                         # enable audio monitoring
    MODE_PERIOD: bool = True                                # enable periodic recording
    MODE_EVENT: bool = False                                # enable event recording
    MODE_FFT_PERIODIC_RECORD: bool = True                   # enable FFT periodic recording

    BUFFER_SECONDS: int = 900                               # default buffer size for audio recording (15 minutes)

    AUDIO_MONITOR_START: Optional[datetime.time] = None     # start time for audio monitoring
    AUDIO_MONITOR_END: Optional[datetime.time] = None       # end time for audio monitoring
    AUDIO_MONITOR_RECORD: int = BUFFER_SECONDS              # duration of audio monitoring recording
    AUDIO_MONITOR_INTERVAL: float = 0.0                     # interval between audio monitoring recordings

    PERIOD_START: Optional[datetime.time] = None            # start time for periodic recording
    PERIOD_END: Optional[datetime.time] = None              # end time for periodic recording
    PERIOD_RECORD: int = BUFFER_SECONDS                     # duration of periodic recording
    PERIOD_SPECTROGRAM: int = 120                           # duration of spectrogram analysis
    PERIOD_INTERVAL: float = 0.1                            # interval between periodic recordings

    EVENT_START: datetime.time = 0                          # start time for event recording
    EVENT_END: datetime.time = 0                            # end time for event recording
    SAVE_BEFORE_EVENT: int = 30                             # seconds to save before event
    SAVE_AFTER_EVENT: int = 30                              # seconds to save after event
    EVENT_THRESHOLD: int = 20000                            # threshold for event triggering
    MONITOR_CH: int = 0                                     # channel for audio monitoring (0 = none)

    # Audio input and instrumentation
    MIC_1: bool = True
    MIC_2: bool = True
    MIC_3: bool = False
    MIC_4: bool = False
    # provides count of active microphone channels
    SOUND_IN_CHS = int(MIC_1) + int(MIC_2) + int(MIC_3) + int(MIC_4) 

    FFT_INTERVAL: int = 30                                  # interval in minutes between FFT analyses
    LOG_AUDIO_CALLBACK: bool = False                        # enable logging of audio callbacks
    DEBUG_VERBOSE: bool = False                             # enable verbose debugging output

    ENABLE_ENHANCED_AUDIO: bool = True                      # enable enhanced audio processing
    AUDIO_API_PREFERENCE: List[str] = ("WASAPI", "DirectSound", "MME")
    AUDIO_FALLBACK_ENABLED: bool = False                    # enable audio fallback

    # Per-OS device prefs
    LINUX_MAKE_NAME: str = ""                               # Leave empty for linux default
    LINUX_MODEL_NAME: List[str] = ("pipewire")              # Use pipewire as the audio system
    LINUX_DEVICE_NAME: str = "pipewire"                     # Use pipewire as the audio device
    LINUX_API_NAME: str = "ALSA"                            # Use ALSA as the audio API
    LINUX_HOSTAPI_NAME: str = "ALSA"                        # Use ALSA as the audio host API
    LINUX_HOSTAPI_INDEX: int = 0                            # Default ALSA host API index
    LINUX_DEVICE_ID: Optional[int] = None                   # Use pipewire device ID

    WINDOWS_MAKE_NAME: str = "Behringer"                    # Use Behringer as the audio device manufacturer
    WINDOWS_MODEL_NAME: str = "UMC204HD"                    # Use UMC204HD as the audio device model
    WINDOWS_DEVICE_NAME: str = "UMC204HD"                   # Use UMC204HD as the audio device name
    WINDOWS_API_NAME: str = "WASAPI"                        # Use WASAPI as the audio API
    WINDOWS_HOSTAPI_NAME: str = "WASAPI"                    # Use WASAPI as the audio host API
    WINDOWS_HOSTAPI_INDEX: int = 15                         # Default WASAPI host API index
    WINDOWS_DEVICE_ID: Optional[int] = None                 # Device ID for UMC204HD

    MACOS_MAKE_NAME: str = "Behringer"                      # Leave empty for macOS default
    MACOS_MODEL_NAME: str = "UMC204HD"                      # Use Built-in as the audio device model
    MACOS_DEVICE_NAME: str = "UMC204HD"                     # Use Built-in as the audio device name
    MACOS_API_NAME: str = "CoreAudio"                       # Use CoreAudio as the audio API
    MACOS_HOSTAPI_NAME: str = "CoreAudio"                   # Use CoreAudio as the audio host API
    MACOS_HOSTAPI_INDEX: int = 0                            # Default CoreAudio host API index
    MACOS_DEVICE_ID: int = 0                                # Use Built-in device ID

    # Audio parameters
    PRIMARY_IN_SAMPLERATE: int = 192000                     # Use 192000 Hz as the primary input samplerate
    PRIMARY_BITDEPTH: int = 16                              # Use 16-bit as the primary bitdepth
    PRIMARY_SAVE_SAMPLERATE: Optional[int] = 96000          # if None then save at Input Samplerate
    PRIMARY_FILE_FORMAT: str = "FLAC"                       # Use FLAC as the primary file format to save

    SAVE_HEADROOM_DB: float = 0.0                           # Use 0.0 dB as the headroom for saving

    AUDIO_MONITOR_SAMPLERATE: int = 48000                   # Use 48000 Hz as the audio monitor samplerate
    AUDIO_MONITOR_BITDEPTH: int = 16                        # Use 16-bit as the audio monitor bitdepth
    AUDIO_MONITOR_CHANNELS: int = 2                         # Use 2 channels for audio monitoring
    AUDIO_MONITOR_QUALITY: int = 256                        # Use 256 kbps as the audio monitor quality
    AUDIO_MONITOR_FORMAT: str = "MP3"                       # Use MP3 as the audio monitor format

    # Data roots
    win_data_drive: str = "G:\\"
    win_data_path: str = "My Drive\\eb_beehive_data"
    win_data_folders: List[str] = ("audio",)

    mac_data_drive: str = "~"
    mac_data_path: str = "data/eb_beehive_data"
    mac_data_folders: List[str] = ("audio",)

    linux_data_drive: str = "~"
    linux_data_path: str = "beedata/eb_beehive_data"
    linux_data_folders: List[str] = ("audio",)

    # UI/plot settings
    MIC_LOCATION: List[str] = ('1: upper--front', '2: upper--back', \
                               '3: lower w/queen--front', '4: lower w/queen--back')

    SOUND_IN_DEFAULT: int = 0
    SOUND_OUT_ID_DEFAULT: int = 3
    SOUND_OUT_CHS_DEFAULT: int = 2
    SOUND_OUT_SR_DEFAULT: int = 48000

    INTERCOM_SAMPLERATE: int = 48000

    TRACE_DURATION: float = 10.0
    OSCOPE_GAIN_DB: float = 12.0

    FFT_DURATION: float = 10.0
    FFT_GAIN: float = 12.0
    FFT_FREQ_MIN_HZ: float = 10.0
    FFT_FREQ_MAX_HZ: float = 10000.0

    SPECTROGRAM_DURATION: float = 10.0
    SPECTROGRAM_GAIN: float = 12.0
    SPECTROGRAM_DB_MIN: float = -70.0
    SPECTROGRAM_DB_MAX: float = 0.0

    # VU meter presentation controls
    VU_METER_LATENCY_MS: int = 30
    VU_METER_DAMPING: float = 0.5

    # --------------------------------------------------------------------------------------
    # end user defined parameters for dataclass
    # --------------------------------------------------------------------------------------

    # Preferred device name by platform (optional helper)
    def DEVICE_NAME_FOR_PLATFORM(self) -> Optional[str]:
        sysname = platform.system()
        if sysname == "Windows":
            return self.WINDOWS_DEVICE_NAME or None
        if sysname == "Darwin":
            return self.MACOS_DEVICE_NAME or None
        return self.LINUX_DEVICE_NAME or None

    # Compute base audio root for current platform
    def audio_root(self) -> Path:
        sysname = platform.system()
        if sysname == "Windows":
            base = Path((self.win_data_drive or "").strip()) / (self.win_data_path or "").lstrip("\\/").strip()
        elif sysname == "Darwin":
            base = Path(os.path.expanduser(self.mac_data_drive or "~")) / (self.mac_data_path or "")
        else:
            base = Path(os.path.expanduser(self.linux_data_drive or "~")) / (self.linux_data_path or "")
        return base / self.LOCATION_ID / self.HIVE_ID / "audio"

    def today_dirs(self, date: Optional[datetime.date] = None) -> Dict[str, Path]:
        d = date or datetime.date.today()
        day = d.strftime("%Y-%m-%d")
        root = self.audio_root()
        return {
            "raw": root / self.RAW_FOLDER_NAME / day,
            "monitor": root / self.MONITOR_FOLDER_NAME / day,
            "plots": root / self.PLOTS_FOLDER_NAME / day,
        }

    # --------------------------------------------------------------------------------------
    # end BMARConfig class
    # --------------------------------------------------------------------------------------

def default_config() -> BMARConfig:
    """Build a BMARConfig from the user configuration above."""
    return BMARConfig()

def get_platform_audio_config(platform_manager=None, config: Optional[BMARConfig] = None) -> Dict[str, object]:
    """
    Get platform-specific audio configuration (storage and device hints).
    Returns dict with keys:
      data_drive, data_path, folders, make_name, model_name, device_name,
      api_name, hostapi_name, hostapi_index, device_id
    """
    c = config or default_config()
    # Determine OS (prefer platform_manager if provided)
    sysname = platform.system()
    if platform_manager and hasattr(platform_manager, "is_macos") and platform_manager.is_macos():
        sysname = "Darwin"
    elif platform_manager and hasattr(platform_manager, "is_windows") and platform_manager.is_windows():
        sysname = "Windows"
    elif platform_manager and hasattr(platform_manager, "is_linux") and platform_manager.is_linux():
        sysname = "Linux"

    folders = {"raw": c.RAW_FOLDER_NAME, "monitor": c.MONITOR_FOLDER_NAME, "plots": c.PLOTS_FOLDER_NAME}

    if sysname == "Darwin":
        return {
            "data_drive": os.path.expanduser(c.mac_data_drive),
            "data_path": c.mac_data_path,
            "folders": folders,
            "make_name": c.MACOS_MAKE_NAME,
            "model_name": c.MACOS_MODEL_NAME,
            "device_name": c.MACOS_DEVICE_NAME,
            "api_name": c.MACOS_API_NAME,
            "hostapi_name": c.MACOS_HOSTAPI_NAME,
            "hostapi_index": c.MACOS_HOSTAPI_INDEX,
            "device_id": c.MACOS_DEVICE_ID,
        }
    if sysname == "Windows":
        return {
            "data_drive": c.win_data_drive,
            "data_path": c.win_data_path,
            "folders": folders,
            "make_name": c.WINDOWS_MAKE_NAME,
            "model_name": c.WINDOWS_MODEL_NAME,
            "device_name": c.WINDOWS_DEVICE_NAME,
            "api_name": c.WINDOWS_API_NAME,
            "hostapi_name": c.WINDOWS_HOSTAPI_NAME,
            "hostapi_index": c.WINDOWS_HOSTAPI_INDEX,
            "device_id": c.WINDOWS_DEVICE_ID,
        }
    # Linux/default
    return {
        "data_drive": os.path.expanduser(c.linux_data_drive),
        "data_path": c.linux_data_path,
        "folders": folders,
        "make_name": c.LINUX_MAKE_NAME,
        "model_name": c.LINUX_MODEL_NAME,
        "device_name": c.LINUX_DEVICE_NAME,
        "api_name": c.LINUX_API_NAME,
        "hostapi_name": c.LINUX_HOSTAPI_NAME,
        "hostapi_index": c.LINUX_HOSTAPI_INDEX,
        "device_id": c.LINUX_DEVICE_ID,
    }


def get_platform_config() -> Dict[str, str]:
    """Basic platform info (compatibility helper)."""
    return {'name': platform.system(), 'version': platform.version(), 'machine': platform.machine()}


def wire_today_dirs(cfg: BMARConfig) -> Tuple[BMARConfig, Dict[str, str]]:
    """
    Create today's raw/monitor/plots directories and wire them to:
      - module-level PRIMARY_DIRECTORY/MONITOR_DIRECTORY/PLOTS_DIRECTORY
      - cfg (via replace)
      - environment variables (BMAR_AUDIO_RAW_DIR, BMAR_AUDIO_MONITOR_DIR, BMAR_PLOTS_DIR)
    """
    dirs = cfg.today_dirs()
    raw = dirs["raw"]; mon = dirs["monitor"]; plt = dirs["plots"]
    raw.mkdir(parents=True, exist_ok=True)
    mon.mkdir(parents=True, exist_ok=True)
    plt.mkdir(parents=True, exist_ok=True)

    os.environ["BMAR_AUDIO_RAW_DIR"] = str(raw)
    os.environ["BMAR_AUDIO_MONITOR_DIR"] = str(mon)
    os.environ["BMAR_PLOTS_DIR"] = str(plt)

    new_cfg = replace(cfg, PRIMARY_DIRECTORY=raw, MONITOR_DIRECTORY=mon, PLOTS_DIRECTORY=plt)
    return new_cfg, {"raw": str(raw), "monitor": str(mon), "plots": str(plt)}

# --------------------------------------------------------------------------------------
# Compatibility helpers for device selection (expected by audio init)
# --------------------------------------------------------------------------------------

def _tokens_from(*vals) -> list[str]:
    toks: list[str] = []
    for v in vals:
        if v is None:
            continue
        if isinstance(v, (list, tuple, set)):
            for s in v:
                if s:
                    toks += re.findall(r"[A-Za-z0-9]+", str(s).lower())
        else:
            toks += re.findall(r"[A-Za-z0-9]+", str(v).lower())
    # de-dupe, preserve order
    seen = set()
    uniq = []
    for t in toks:
        if t not in seen:
            seen.add(t); uniq.append(t)
    return uniq

def device_search_criteria(strict: bool = True, platform_manager=None, cfg: Optional[BMARConfig] = None) -> Dict[str, object]:
    """
    Return device selection criteria expected by audio device initialization.
    Keys:
      - make_name, model_name, device_name, api_name,
        hostapi_name, hostapi_index, device_id
      - name_tokens (list[str]) for device matching
      - api_tokens (list[str]) derived from preferences and api_name
      - api_preference (list), fallback_enabled (bool), strict (bool)
    Values are sourced from the per-OS section of this config.
    """
    c = cfg or default_config()
    # Resolve OS (prefer platform_manager if provided)
    sysname = platform.system()
    if platform_manager and hasattr(platform_manager, "is_macos") and platform_manager.is_macos():
        sysname = "Darwin"
    elif platform_manager and hasattr(platform_manager, "is_windows") and platform_manager.is_windows():
        sysname = "Windows"
    elif platform_manager and hasattr(platform_manager, "is_linux") and platform_manager.is_linux():
        sysname = "Linux"

    if sysname == "Windows":
        crit = {
            "make_name": c.WINDOWS_MAKE_NAME,
            "model_name": c.WINDOWS_MODEL_NAME,
            "device_name": c.WINDOWS_DEVICE_NAME,
            "api_name": c.WINDOWS_API_NAME,
            "hostapi_name": c.WINDOWS_HOSTAPI_NAME,
            "hostapi_index": c.WINDOWS_HOSTAPI_INDEX,
            "device_id": c.WINDOWS_DEVICE_ID,
            "api_preference": c.AUDIO_API_PREFERENCE,
            "fallback_enabled": c.AUDIO_FALLBACK_ENABLED,
            "strict": bool(strict),
        }
        # Only require model/device tokens; exclude brand so "2- UMC204HD 192k" matches
        crit["name_tokens"] = _tokens_from(crit["model_name"], crit["device_name"])
        crit["api_tokens"] = _tokens_from(crit["api_name"], crit["api_preference"])
        return crit

    if sysname == "Darwin":
        crit = {
            "make_name": c.MACOS_MAKE_NAME,
            "model_name": c.MACOS_MODEL_NAME,
            "device_name": c.MACOS_DEVICE_NAME,
            "api_name": c.MACOS_API_NAME,
            "hostapi_name": c.MACOS_HOSTAPI_NAME,
            "hostapi_index": c.MACOS_HOSTAPI_INDEX,
            "device_id": c.MACOS_DEVICE_ID,
            "api_preference": c.AUDIO_API_PREFERENCE,
            "fallback_enabled": c.AUDIO_FALLBACK_ENABLED,
            "strict": bool(strict),
        }
        crit["name_tokens"] = _tokens_from(crit["model_name"], crit["device_name"])
        crit["api_tokens"] = _tokens_from(crit["api_name"], crit["api_preference"])
        return crit

    # Linux/default
    crit = {
        "make_name": c.LINUX_MAKE_NAME,
        "model_name": c.LINUX_MODEL_NAME,
        "device_name": c.LINUX_DEVICE_NAME,
        "api_name": c.LINUX_API_NAME,
        "hostapi_name": c.LINUX_HOSTAPI_NAME,
        "hostapi_index": c.LINUX_HOSTAPI_INDEX,
        "device_id": c.LINUX_DEVICE_ID,
        "api_preference": c.AUDIO_API_PREFERENCE,
        "fallback_enabled": c.AUDIO_FALLBACK_ENABLED,
        "strict": bool(strict),
    }
    crit["name_tokens"] = _tokens_from(crit["model_name"], crit["device_name"])
    crit["api_tokens"] = _tokens_from(crit["api_name"], crit["api_preference"])
    return crit
def api_preferences(cfg: Optional[BMARConfig] = None) -> List[str]:
    """Return ordered audio API preferences."""
    c = cfg or default_config()
    return list(c.AUDIO_API_PREFERENCE)

def fallback_enabled(cfg: Optional[BMARConfig] = None) -> bool:
    """Return whether device fallback is enabled."""
    c = cfg or default_config()
    return bool(c.AUDIO_FALLBACK_ENABLED)

def DEVICE_NAME_FOR_PLATFORM(cfg: Optional[BMARConfig] = None) -> Optional[str]:
    """
    Module-level compatibility helper for older callers that used a function instead
    of the dataclass method. Returns the preferred input device name for this OS.
    """
    c = cfg or default_config()
    return c.DEVICE_NAME_FOR_PLATFORM()
# --------------------------------------------------------------------------------------
