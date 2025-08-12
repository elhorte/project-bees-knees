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

# location and hive ID
LOCATION_ID = "Zeev-Berkeley"
HIVE_ID = "Z1_4mic"
HIVE_CONFIG = "dual-mic, sensor"

# mode controls
MODE_AUDIO_MONITOR = True                       # recording continuously to mp3 files
MODE_PERIOD = True                              # period recording
MODE_EVENT = False                              # event recording
MODE_FFT_PERIODIC_RECORD = True                 # record fft periodically

# circular buffer size
BUFFER_SECONDS = 900                            # time length of circular buffer

# recording types controls:
AUDIO_MONITOR_START = None  # datetime.time(4, 0, 0)  # None = continuous
AUDIO_MONITOR_END = datetime.time(23, 0, 0)
AUDIO_MONITOR_RECORD = BUFFER_SECONDS           # must be <= BUFFER_SECONDS
AUDIO_MONITOR_INTERVAL = 0.1                    # seconds between recordings

PERIOD_START = None  # datetime.time(4, 0, 0)  # None = continuous
PERIOD_END = datetime.time(20, 0, 0)
PERIOD_RECORD = BUFFER_SECONDS                  # must be <= BUFFER_SECONDS
PERIOD_SPECTROGRAM = 120                        # seconds for saved PNG spectrograms
PERIOD_INTERVAL = 0.1                           # seconds (must be > period, of course)

EVENT_START = datetime.time(4, 0, 0)
EVENT_END = datetime.time(22, 0, 0)
SAVE_BEFORE_EVENT = 30                          # seconds to save before the event
SAVE_AFTER_EVENT = 30                           # seconds to save after the event
EVENT_THRESHOLD = 20000                         # audio level threshold

MONITOR_CH = 0                                  # channel to monitor for event

# Audio input configuration
MIC_1 = True
MIC_2 = True
MIC_3 = False
MIC_4 = False

SOUND_IN_CHS = int(MIC_1) + int(MIC_2) + int(MIC_3) + int(MIC_4)  # count of input channels

# instrumentation parms
FFT_INTERVAL = 30                               # minutes between ffts

LOG_AUDIO_CALLBACK = False  # set True to see per-callback audio stats

# Global flags
DEBUG_VERBOSE = False                           # Enable verbose debug output

# Enhanced audio configuration
ENABLE_ENHANCED_AUDIO = True                    # Enable sounddevice-based device testing
AUDIO_API_PREFERENCE = ["WASAPI", "DirectSound", "MME"]  # Preferred APIs in order
AUDIO_FALLBACK_ENABLED = False                  # Allow fallback to default device if specified fails

# input device parameters--linux:
LINUX_MAKE_NAME = ""                             # Leave empty for Linux default
LINUX_MODEL_NAME: List[str] = ["pipewire"]       # Use pipewire as the audio system
LINUX_DEVICE_NAME = "pipewire"                   # Use pipewire device
LINUX_API_NAME = "ALSA"                          # Use ALSA API for Linux
LINUX_HOSTAPI_NAME = "ALSA"                      # Use ALSA host API
LINUX_HOSTAPI_INDEX = 0                          # ALSA is typically index 0
LINUX_DEVICE_ID: Optional[int] = None            # Use pipewire device ID

# input device parameters--windows:
WINDOWS_MAKE_NAME = "Behringer"                  # Audio interface make
WINDOWS_MODEL_NAME = "UMC204HD"                  # Audio interface model
WINDOWS_DEVICE_NAME = "UMC204HD"                 # Device name
WINDOWS_API_NAME = "WASAPI"                      # Windows audio API
WINDOWS_HOSTAPI_NAME = "WASAPI"                  # Host API name
WINDOWS_HOSTAPI_INDEX = 15                       # Default host API index
WINDOWS_DEVICE_ID: Optional[int] = None          # Device ID if needed

# input device parameters--macos:
MACOS_MAKE_NAME = ""                             # Leave empty for macOS default
MACOS_MODEL_NAME: List[str] = ["Built-in"]       # Built-in audio
MACOS_DEVICE_NAME = "Built-in"                   # Built-in device
MACOS_API_NAME = "CoreAudio"                     # macOS audio API
MACOS_HOSTAPI_NAME = "CoreAudio"                 # Host API name
MACOS_HOSTAPI_INDEX = 0                          # Default host API index
MACOS_DEVICE_ID = 0                              # Default device ID

# audio parameters:
PRIMARY_IN_SAMPLERATE = 192000                  # Audio sample rate
PRIMARY_BITDEPTH = 16                           # Audio bit depth
PRIMARY_SAVE_SAMPLERATE: Optional[int] = 96000  # if None then save at Input Samplerate
PRIMARY_FILE_FORMAT = "FLAC"                    # 'WAV' or 'FLAC'

# Apply pre-write attenuation to avoid clipping in saved files (dB)
# 0 = no attenuation; try 3 for a little headroom
SAVE_HEADROOM_DB = 0.0

AUDIO_MONITOR_SAMPLERATE = 48000                # For continuous audio
AUDIO_MONITOR_BITDEPTH = 16                     # Audio bit depth
AUDIO_MONITOR_CHANNELS = 2                      # Number of channels
AUDIO_MONITOR_QUALITY = 256                     # mp3: 0-9 vbr; 64-320 cbr kbps
AUDIO_MONITOR_FORMAT = "MP3"                    # accepts mp3, flac, or wav

# Canonical subfolder names under the audio root
RAW_FOLDER_NAME = "raw"
MONITOR_FOLDER_NAME = "monitor"  # mp3/continuous recordings
PLOTS_FOLDER_NAME = "plots"
#
# Windows storage roots
win_data_drive = "G:\\"   # D is internal and limited; G is Google Drive
win_data_path = "My Drive\\eb_beehive_data"
# Top-level (under data_path) contains location/hive/audio; plots lives under audio
win_data_folders = ["audio"]  # kept for compatibility; not used for subfolder names
# macOS storage roots
mac_data_drive = "~"
mac_data_path = "data/eb_beehive_data"
mac_data_folders = ["audio"]
# Linux storage roots
linux_data_drive = "~"                          # Use home directory
linux_data_path = "beedata/eb_beehive_data"     # Store in ~/beedata
linux_data_folders = ["audio"]

# mic location map channel to position
MIC_LOCATION = [
    '1: upper--front', '2: upper--back', '3: lower w/queen--front', '4: lower w/queen--back'
]

# Windows mme defaults
SOUND_IN_DEFAULT = 0                            # default input device id
SOUND_OUT_ID_DEFAULT = 3                        # default output device id
SOUND_OUT_CHS_DEFAULT = 1                       # default number of output channels
SOUND_OUT_SR_DEFAULT = 48000                    # default sample rate

# Intercom (local monitor) parameters
INTERCOM_SAMPLERATE = 48000                     # Sample rate for local monitoring playback

# audio display parameters:
TRACE_DURATION = 10.0                            # seconds
OSCOPE_GAIN_DB = 12                              # Gain in dB of audio level for oscilloscope
FFT_DURATION = 10.0                              # seconds
FFT_GAIN = 12                                    # Gain in dB of audio level for fft
# FFT frequency axis limits (Hz). Set max to None to use Nyquist (samplerate/2)
FFT_FREQ_MIN_HZ = 0.0
FFT_FREQ_MAX_HZ = 10000.0  # 10 kHz max for audio
SPECTROGRAM_DURATION = 10.0                      # seconds
SPECTROGRAM_GAIN = 12                            # Gain in dB of audio level for spectrogram
# Spectrogram display scaling (dBFS)
SPECTROGRAM_DB_MIN = -70.0
SPECTROGRAM_DB_MAX = 0.0

# VU meter presentation controls
VU_METER_LATENCY_MS = 30       # msec
VU_METER_DAMPING = 0.50

# --------------------------------------------------------------------------------------
# RUNTIME SUPPORT (dataclass, helpers, wiring)
# --------------------------------------------------------------------------------------

# Runtime directories (wired at startup so modules like plotting can use them)
PRIMARY_DIRECTORY: Optional[Path] = None
MONITOR_DIRECTORY: Optional[Path] = None
PLOTS_DIRECTORY: Optional[Path] = None

@dataclass(frozen=True)
class BMARConfig:
    # Identity
    LOCATION_ID: str
    HIVE_ID: str
    HIVE_CONFIG: str

    # Modes and timing
    MODE_AUDIO_MONITOR: bool
    MODE_PERIOD: bool
    MODE_EVENT: bool
    MODE_FFT_PERIODIC_RECORD: bool
    BUFFER_SECONDS: int
    AUDIO_MONITOR_START: Optional[datetime.time]
    AUDIO_MONITOR_END: Optional[datetime.time]
    AUDIO_MONITOR_RECORD: int
    AUDIO_MONITOR_INTERVAL: float
    PERIOD_START: Optional[datetime.time]
    PERIOD_END: Optional[datetime.time]
    PERIOD_RECORD: int
    PERIOD_SPECTROGRAM: int
    PERIOD_INTERVAL: float
    EVENT_START: datetime.time
    EVENT_END: datetime.time
    SAVE_BEFORE_EVENT: int
    SAVE_AFTER_EVENT: int
    EVENT_THRESHOLD: int
    MONITOR_CH: int

    # Audio input and instrumentation
    MIC_1: bool
    MIC_2: bool
    MIC_3: bool
    MIC_4: bool
    SOUND_IN_CHS: int
    FFT_INTERVAL: int
    LOG_AUDIO_CALLBACK: bool
    DEBUG_VERBOSE: bool

    ENABLE_ENHANCED_AUDIO: bool
    AUDIO_API_PREFERENCE: List[str]
    AUDIO_FALLBACK_ENABLED: bool

    # Per-OS device prefs
    LINUX_MAKE_NAME: str
    LINUX_MODEL_NAME: List[str]
    LINUX_DEVICE_NAME: str
    LINUX_API_NAME: str
    LINUX_HOSTAPI_NAME: str
    LINUX_HOSTAPI_INDEX: int
    LINUX_DEVICE_ID: Optional[int]

    WINDOWS_MAKE_NAME: str
    WINDOWS_MODEL_NAME: str
    WINDOWS_DEVICE_NAME: str
    WINDOWS_API_NAME: str
    WINDOWS_HOSTAPI_NAME: str
    WINDOWS_HOSTAPI_INDEX: int
    WINDOWS_DEVICE_ID: Optional[int]

    MACOS_MAKE_NAME: str
    MACOS_MODEL_NAME: List[str]
    MACOS_DEVICE_NAME: str
    MACOS_API_NAME: str
    MACOS_HOSTAPI_NAME: str
    MACOS_HOSTAPI_INDEX: int
    MACOS_DEVICE_ID: int

    # Audio parameters
    PRIMARY_IN_SAMPLERATE: int
    PRIMARY_BITDEPTH: int
    PRIMARY_SAVE_SAMPLERATE: Optional[int]
    PRIMARY_FILE_FORMAT: str
    SAVE_HEADROOM_DB: float

    AUDIO_MONITOR_SAMPLERATE: int
    AUDIO_MONITOR_BITDEPTH: int
    AUDIO_MONITOR_CHANNELS: int
    AUDIO_MONITOR_QUALITY: int
    AUDIO_MONITOR_FORMAT: str

    # Data roots
    win_data_drive: str
    win_data_path: str
    win_data_folders: List[str]
    mac_data_drive: str
    mac_data_path: str
    mac_data_folders: List[str]
    linux_data_drive: str
    linux_data_path: str
    linux_data_folders: List[str]

    # UI/plot settings
    MIC_LOCATION: List[str]
    SOUND_IN_DEFAULT: int
    SOUND_OUT_ID_DEFAULT: int
    SOUND_OUT_CHS_DEFAULT: int
    SOUND_OUT_SR_DEFAULT: int
    INTERCOM_SAMPLERATE: int
    TRACE_DURATION: float
    OSCOPE_GAIN_DB: float
    FFT_DURATION: float
    FFT_GAIN: float
    FFT_FREQ_MIN_HZ: float
    FFT_FREQ_MAX_HZ: float
    SPECTROGRAM_DURATION: float
    SPECTROGRAM_GAIN: float
    SPECTROGRAM_DB_MIN: float
    SPECTROGRAM_DB_MAX: float

    # VU meter presentation controls
    VU_METER_LATENCY_MS: int = 30       # msec
    VU_METER_DAMPING: float = 0.50

    # Directories (wired by main/file_utils at runtime)
    PRIMARY_DIRECTORY: Optional[Path] = None
    MONITOR_DIRECTORY: Optional[Path] = None
    PLOTS_DIRECTORY: Optional[Path] = None

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
            "raw": root / RAW_FOLDER_NAME / day,
            "monitor": root / MONITOR_FOLDER_NAME / day,
            "plots": root / PLOTS_FOLDER_NAME / day,
        }


def default_config() -> BMARConfig:
    """Build a BMARConfig from the user configuration above."""
    return BMARConfig(
        LOCATION_ID=LOCATION_ID,
        HIVE_ID=HIVE_ID,
        HIVE_CONFIG=HIVE_CONFIG,
        MODE_AUDIO_MONITOR=MODE_AUDIO_MONITOR,
        MODE_PERIOD=MODE_PERIOD,
        MODE_EVENT=MODE_EVENT,
        MODE_FFT_PERIODIC_RECORD=MODE_FFT_PERIODIC_RECORD,
        BUFFER_SECONDS=BUFFER_SECONDS,
        AUDIO_MONITOR_START=AUDIO_MONITOR_START,
        AUDIO_MONITOR_END=AUDIO_MONITOR_END,
        AUDIO_MONITOR_RECORD=AUDIO_MONITOR_RECORD,
        AUDIO_MONITOR_INTERVAL=AUDIO_MONITOR_INTERVAL,
        PERIOD_START=PERIOD_START,
        PERIOD_END=PERIOD_END,
        PERIOD_RECORD=PERIOD_RECORD,
        PERIOD_SPECTROGRAM=PERIOD_SPECTROGRAM,
        PERIOD_INTERVAL=PERIOD_INTERVAL,
        EVENT_START=EVENT_START,
        EVENT_END=EVENT_END,
        SAVE_BEFORE_EVENT=SAVE_BEFORE_EVENT,
        SAVE_AFTER_EVENT=SAVE_AFTER_EVENT,
        EVENT_THRESHOLD=EVENT_THRESHOLD,
        MONITOR_CH=MONITOR_CH,
        MIC_1=MIC_1,
        MIC_2=MIC_2,
        MIC_3=MIC_3,
        MIC_4=MIC_4,
        SOUND_IN_CHS=SOUND_IN_CHS,
        FFT_INTERVAL=FFT_INTERVAL,
        LOG_AUDIO_CALLBACK=LOG_AUDIO_CALLBACK,
        DEBUG_VERBOSE=DEBUG_VERBOSE,
        ENABLE_ENHANCED_AUDIO=ENABLE_ENHANCED_AUDIO,
        AUDIO_API_PREFERENCE=AUDIO_API_PREFERENCE,
        AUDIO_FALLBACK_ENABLED=AUDIO_FALLBACK_ENABLED,
        LINUX_MAKE_NAME=LINUX_MAKE_NAME,
        LINUX_MODEL_NAME=LINUX_MODEL_NAME,
        LINUX_DEVICE_NAME=LINUX_DEVICE_NAME,
        LINUX_API_NAME=LINUX_API_NAME,
        LINUX_HOSTAPI_NAME=LINUX_HOSTAPI_NAME,
        LINUX_HOSTAPI_INDEX=LINUX_HOSTAPI_INDEX,
        LINUX_DEVICE_ID=LINUX_DEVICE_ID,
        WINDOWS_MAKE_NAME=WINDOWS_MAKE_NAME,
        WINDOWS_MODEL_NAME=WINDOWS_MODEL_NAME,
        WINDOWS_DEVICE_NAME=WINDOWS_DEVICE_NAME,
        WINDOWS_API_NAME=WINDOWS_API_NAME,
        WINDOWS_HOSTAPI_NAME=WINDOWS_HOSTAPI_NAME,
        WINDOWS_HOSTAPI_INDEX=WINDOWS_HOSTAPI_INDEX,
        WINDOWS_DEVICE_ID=WINDOWS_DEVICE_ID,
        MACOS_MAKE_NAME=MACOS_MAKE_NAME,
        MACOS_MODEL_NAME=MACOS_MODEL_NAME,
        MACOS_DEVICE_NAME=MACOS_DEVICE_NAME,
        MACOS_API_NAME=MACOS_API_NAME,
        MACOS_HOSTAPI_NAME=MACOS_HOSTAPI_NAME,
        MACOS_HOSTAPI_INDEX=MACOS_HOSTAPI_INDEX,
        MACOS_DEVICE_ID=MACOS_DEVICE_ID,
        PRIMARY_IN_SAMPLERATE=PRIMARY_IN_SAMPLERATE,
        PRIMARY_BITDEPTH=PRIMARY_BITDEPTH,
        PRIMARY_SAVE_SAMPLERATE=PRIMARY_SAVE_SAMPLERATE,
        PRIMARY_FILE_FORMAT=PRIMARY_FILE_FORMAT,
        SAVE_HEADROOM_DB=SAVE_HEADROOM_DB,
        AUDIO_MONITOR_SAMPLERATE=AUDIO_MONITOR_SAMPLERATE,
        AUDIO_MONITOR_BITDEPTH=AUDIO_MONITOR_BITDEPTH,
        AUDIO_MONITOR_CHANNELS=AUDIO_MONITOR_CHANNELS,
        AUDIO_MONITOR_QUALITY=AUDIO_MONITOR_QUALITY,
        AUDIO_MONITOR_FORMAT=AUDIO_MONITOR_FORMAT,
        win_data_drive=win_data_drive,
        win_data_path=win_data_path,
        win_data_folders=win_data_folders,
        mac_data_drive=mac_data_drive,
        mac_data_path=mac_data_path,
        mac_data_folders=mac_data_folders,
        linux_data_drive=linux_data_drive,
        linux_data_path=linux_data_path,
        linux_data_folders=linux_data_folders,
        MIC_LOCATION=MIC_LOCATION,
        SOUND_IN_DEFAULT=SOUND_IN_DEFAULT,
        SOUND_OUT_ID_DEFAULT=SOUND_OUT_ID_DEFAULT,
        SOUND_OUT_CHS_DEFAULT=SOUND_OUT_CHS_DEFAULT,
        SOUND_OUT_SR_DEFAULT=SOUND_OUT_SR_DEFAULT,
        INTERCOM_SAMPLERATE=INTERCOM_SAMPLERATE,
        TRACE_DURATION=TRACE_DURATION,
        OSCOPE_GAIN_DB=OSCOPE_GAIN_DB,
        FFT_DURATION=FFT_DURATION,
        FFT_GAIN=FFT_GAIN,
        FFT_FREQ_MIN_HZ=FFT_FREQ_MIN_HZ,
        FFT_FREQ_MAX_HZ=FFT_FREQ_MAX_HZ,
        SPECTROGRAM_DURATION=SPECTROGRAM_DURATION,
        SPECTROGRAM_GAIN=SPECTROGRAM_GAIN,
        SPECTROGRAM_DB_MIN=SPECTROGRAM_DB_MIN,
        SPECTROGRAM_DB_MAX=SPECTROGRAM_DB_MAX,
        VU_METER_LATENCY_MS=VU_METER_LATENCY_MS,
        VU_METER_DAMPING=VU_METER_DAMPING
    )


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
    try:
        if platform_manager and hasattr(platform_manager, "is_macos") and platform_manager.is_macos():
            sysname = "Darwin"
        elif platform_manager and hasattr(platform_manager, "is_windows") and platform_manager.is_windows():
            sysname = "Windows"
        elif platform_manager and hasattr(platform_manager, "is_linux") and platform_manager.is_linux():
            sysname = "Linux"
    except Exception:
        pass

    folders = {"raw": RAW_FOLDER_NAME, "monitor": MONITOR_FOLDER_NAME, "plots": PLOTS_FOLDER_NAME}

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

    global PRIMARY_DIRECTORY, MONITOR_DIRECTORY, PLOTS_DIRECTORY
    PRIMARY_DIRECTORY = raw
    MONITOR_DIRECTORY = mon
    PLOTS_DIRECTORY = plt

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
    try:
        if platform_manager and hasattr(platform_manager, "is_macos") and platform_manager.is_macos():
            sysname = "Darwin"
        elif platform_manager and hasattr(platform_manager, "is_windows") and platform_manager.is_windows():
            sysname = "Windows"
        elif platform_manager and hasattr(platform_manager, "is_linux") and platform_manager.is_linux():
            sysname = "Linux"
    except Exception:
        pass

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
