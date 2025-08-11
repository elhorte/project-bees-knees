from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional, List, Dict
import datetime
import platform

# -----------------------------
# BMAR configuration dataclass
# -----------------------------
@dataclass(frozen=True)
class BMARConfig:
    # Location and hive
    LOCATION_ID: str = "Zeev-Berkeley"
    HIVE_ID: str = "Z1_4mic"
    HIVE_CONFIG: str = "dual-mic, sensor"

    # Modes
    MODE_AUDIO_MONITOR: bool = True
    MODE_PERIOD: bool = True
    MODE_EVENT: bool = False
    MODE_FFT_PERIODIC_RECORD: bool = True

    # Circular buffer
    BUFFER_SECONDS: int = 600

    # Recording windows and parameters
    AUDIO_MONITOR_START: Optional[datetime.time] = None
    AUDIO_MONITOR_END: Optional[datetime.time] = datetime.time(23, 0, 0)
    AUDIO_MONITOR_RECORD: int = BUFFER_SECONDS
    AUDIO_MONITOR_INTERVAL: float = 0.1

    PERIOD_START: Optional[datetime.time] = None
    PERIOD_END: Optional[datetime.time] = datetime.time(20, 0, 0)
    PERIOD_RECORD: int = BUFFER_SECONDS
    PERIOD_SPECTROGRAM: int = 120
    PERIOD_INTERVAL: float = 0.1

    EVENT_START: Optional[datetime.time] = datetime.time(4, 0, 0)
    EVENT_END: Optional[datetime.time] = datetime.time(22, 0, 0)
    SAVE_BEFORE_EVENT: int = 30
    SAVE_AFTER_EVENT: int = 30
    EVENT_THRESHOLD: int = 20000

    # Monitoring channel
    MONITOR_CH: int = 0

    # Mic enable flags and derived input channels
    MIC_1: bool = True
    MIC_2: bool = True
    MIC_3: bool = False
    MIC_4: bool = False
    SOUND_IN_CHS: int = 2  # will be recomputed from MIC_* in default_config()

    # Instrumentation
    FFT_INTERVAL: int = 30  # minutes
    LOG_AUDIO_CALLBACK: bool = False
    DEBUG_VERBOSE: bool = False

    # Enhanced audio configuration
    ENABLE_ENHANCED_AUDIO: bool = True
    AUDIO_API_PREFERENCE_LIST: List[str] = field(default_factory=lambda: ["WASAPI", "DirectSound", "MME"])
    AUDIO_FALLBACK_ENABLED: bool = False  # if False and a selector is provided, do not fallback

    # Per-OS device selection (selectors allow partial match on name/model/make)
    # Linux
    linux_make_name: str = ""
    linux_model_name: List[str] = field(default_factory=lambda: ["pipewire"])
    linux_device_name: str = "pipewire"
    linux_api_name: str = "ALSA"
    linux_hostapi_name: str = "ALSA"
    linux_hostapi_index: Optional[int] = 0
    linux_device_id: Optional[int] = None

    # Windows
    windows_make_name: str = "Behringer"
    windows_model_name: str = "UMC204HD"
    windows_device_name: str = "UMC204HD"
    windows_api_name: str = "WASAPI"
    windows_hostapi_name: str = "WASAPI"
    windows_hostapi_index: Optional[int] = 15
    windows_device_id: Optional[int] = 15

    # macOS (Darwin)
    mac_make_name: str = ""
    mac_model_name: List[str] = field(default_factory=lambda: ["Built-in"])
    mac_device_name: str = "Built-in"
    mac_api_name: str = "CoreAudio"
    mac_hostapi_name: str = "CoreAudio"
    mac_hostapi_index: Optional[int] = 0
    mac_device_id: Optional[int] = 0

    # Audio parameters
    PRIMARY_IN_SAMPLERATE: int = 192000
    PRIMARY_BITDEPTH: int = 16
    PRIMARY_SAVE_SAMPLERATE: Optional[int] = 96000  # None => save at input SR
    PRIMARY_FILE_FORMAT: str = "FLAC"  # 'WAV' or 'FLAC'
    SAVE_HEADROOM_DB: float = 0.0

    AUDIO_MONITOR_SAMPLERATE: int = 48000
    AUDIO_MONITOR_BITDEPTH: int = 16
    AUDIO_MONITOR_CHANNELS: int = 2
    AUDIO_MONITOR_QUALITY: int = 256  # kbps for MP3 when used
    AUDIO_MONITOR_FORMAT: str = "MP3"  # 'mp3', 'flac', or 'wav'

    # Data roots
    win_data_drive: str = "G:\\\\"
    win_data_path: str = "My Drive\\eb_beehive_data"
    win_data_folders: List[str] = field(default_factory=lambda: ["audio", "plots"])

    mac_data_drive: str = "~"
    mac_data_path: str = "data/eb_beehive_data"
    mac_data_folders: List[str] = field(default_factory=lambda: ["audio", "plots"])

    linux_data_drive: str = "~"
    linux_data_path: str = "beedata/eb_beehive_data"
    linux_data_folders: List[str] = field(default_factory=lambda: ["audio", "plots"])

    # Mic location map
    MIC_LOCATION: List[str] = field(default_factory=lambda: [
        '1: upper--front', '2: upper--back', '3: lower w/queen--front', '4: lower w/queen--back'
    ])

    # Windows MME defaults
    SOUND_IN_DEFAULT: int = 0
    SOUND_OUT_ID_DEFAULT: Optional[int] = 3
    SOUND_OUT_CHS_DEFAULT: int = 1
    SOUND_OUT_SR_DEFAULT: int = 48000

    # Intercom/local monitor
    INTERCOM_SAMPLERATE: int = 48000

    # Display parameters
    TRACE_DURATION: float = 10.0
    OSCOPE_GAIN_DB: float = 12.0
    FFT_DURATION: float = 10.0
    FFT_GAIN: float = 12.0
    FFT_FREQ_MIN_HZ: float = 0.0
    FFT_FREQ_MAX_HZ: float = 10000.0
    SPECTROGRAM_DURATION: float = 10.0
    SPECTROGRAM_GAIN: float = 12.0
    SPECTROGRAM_DB_MIN: float = -70.0
    SPECTROGRAM_DB_MAX: float = 0.0

    # VU meter presentation controls
    VU_METER_LATENCY_MS: int = 30       # msec
    VU_METER_DAMPING: float = 0.50

    # Directories (wired by main/file_utils at runtime)
    PRIMARY_DIRECTORY: Optional[Path] = None
    MONITOR_DIRECTORY: Optional[Path] = None
    PLOTS_DIRECTORY: Optional[Path] = None

# Default config factory
def default_config() -> BMARConfig:
    cfg = BMARConfig()
    in_chs = int(cfg.MIC_1) + int(cfg.MIC_2) + int(cfg.MIC_3) + int(cfg.MIC_4)
    return replace(cfg, SOUND_IN_CHS=in_chs or cfg.SOUND_IN_CHS)

# -----------------------------
# Runtime overrides (CLI only)
# -----------------------------
_runtime: Dict[str, Dict[str, object]] = {"Windows": {}, "Darwin": {}, "Linux": {}}

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

# -----------------------------
# Device search spec for audio_devices
# -----------------------------
def _tokens(x) -> List[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x else []
    return [t for t in x if t]

def device_search_criteria(cfg: Optional[BMARConfig] = None) -> dict:
    cfg = cfg or default_config()
    sysname = platform.system()
    if sysname == "Windows":
        name = cfg.windows_device_name
        model_tokens = _tokens(cfg.windows_model_name)
        make_tokens = _tokens(cfg.windows_make_name)
        hostapi = cfg.windows_hostapi_name
        hostapi_idx = cfg.windows_hostapi_index
        dev_id = cfg.windows_device_id
    elif sysname == "Darwin":
        name = cfg.mac_device_name
        model_tokens = _tokens(cfg.mac_model_name)
        make_tokens = _tokens(cfg.mac_make_name)
        hostapi = cfg.mac_hostapi_name
        hostapi_idx = cfg.mac_hostapi_index
        dev_id = cfg.mac_device_id
    else:
        name = cfg.linux_device_name
        model_tokens = _tokens(cfg.linux_model_name)
        make_tokens = _tokens(cfg.linux_make_name)
        hostapi = cfg.linux_hostapi_name
        hostapi_idx = cfg.linux_hostapi_index
        dev_id = cfg.linux_device_id

    # Apply runtime overrides
    ov = _runtime.get(sysname, {})
    if ov.get("device_name"): name = ov["device_name"]  # type: ignore
    if ov.get("hostapi_name"): hostapi = ov["hostapi_name"]  # type: ignore
    if "hostapi_index" in ov: hostapi_idx = ov["hostapi_index"]  # type: ignore

    # Strict only when device selector is provided; hostapi is a preference
    strict = any([name, model_tokens, make_tokens, dev_id is not None])

    return {
        "name_tokens": _tokens(name),
        "model_tokens": model_tokens,
        "make_tokens": make_tokens,
        "hostapi_name": hostapi or None,
        "hostapi_index": hostapi_idx,
        "device_id": dev_id,
        "strict": strict,
    }

# -----------------------------
# Audio API preferences
# -----------------------------
AUDIO_API_PREFERENCE_BY_OS: Dict[str, List[str]] = {
    "Windows": ["WASAPI", "DirectSound", "MME"],
    "Darwin":  ["CoreAudio"],
    "Linux":   ["ALSA", "JACK", "PulseAudio", "OSS"],
}
def API_PREFERENCE_FOR_PLATFORM() -> List[str]:
    return AUDIO_API_PREFERENCE_BY_OS.get(platform.system(), [])

# -----------------------------
# Platform config and legacy exports
# -----------------------------
def get_platform_audio_config(platform_manager=None, config: Optional[BMARConfig] = None) -> dict:
    cfg = config or default_config()
    sysname = platform.system()
    if sysname == "Windows":
        data_drive = cfg.win_data_drive
        data_path = cfg.win_data_path
        folders = cfg.win_data_folders
        make_name = cfg.windows_make_name
        model_name = cfg.windows_model_name
        device_name = cfg.windows_device_name
        api_name = cfg.windows_api_name
        hostapi_name = cfg.windows_hostapi_name
        hostapi_index = cfg.windows_hostapi_index
        device_id = cfg.windows_device_id
    elif sysname == "Darwin":
        data_drive = cfg.mac_data_drive
        data_path = cfg.mac_data_path
        folders = cfg.mac_data_folders
        make_name = cfg.mac_make_name
        model_name = cfg.mac_model_name
        device_name = cfg.mac_device_name
        api_name = cfg.mac_api_name
        hostapi_name = cfg.mac_hostapi_name
        hostapi_index = cfg.mac_hostapi_index
        device_id = cfg.mac_device_id
    else:
        data_drive = cfg.linux_data_drive
        data_path = cfg.linux_data_path
        folders = cfg.linux_data_folders
        make_name = cfg.linux_make_name
        model_name = cfg.linux_model_name
        device_name = cfg.linux_device_name
        api_name = cfg.linux_api_name
        hostapi_name = cfg.linux_hostapi_name
        hostapi_index = cfg.linux_hostapi_index
        device_id = cfg.linux_device_id

    d = {
         "data_drive": data_drive,
         "data_path": data_path,
         "folders": folders,
         "make_name": make_name,
         "model_name": model_name,
         "device_name": device_name,
         "api_name": api_name,
         "hostapi_name": hostapi_name,
         "hostapi_index": hostapi_index,
         "device_id": device_id,
    }
    # Legacy aliases expected by some UI paths
    d.update({
        "name": device_name,
        "api": api_name,
        "hostapi": hostapi_name,
        "hostapiIndex": hostapi_index,
        "id": device_id,
    })
    return d

# Legacy alias for older callers (e.g., UI 'p' command)
def get_platform_config(platform_manager=None, config: Optional[BMARConfig] = None) -> dict:
    """Back-compat: returns the same dict as get_platform_audio_config."""
    return get_platform_audio_config(platform_manager, config)

# Snapshot constants for legacy imports
def _derive_legacy_constants(c: BMARConfig) -> Dict[str, object]:
    return {
        "LOCATION_ID": c.LOCATION_ID,
        "HIVE_ID": c.HIVE_ID,
        "HIVE_CONFIG": c.HIVE_CONFIG,
        "MODE_AUDIO_MONITOR": c.MODE_AUDIO_MONITOR,
        "MODE_PERIOD": c.MODE_PERIOD,
        "MODE_EVENT": c.MODE_EVENT,
        "MODE_FFT_PERIODIC_RECORD": c.MODE_FFT_PERIODIC_RECORD,
        "BUFFER_SECONDS": c.BUFFER_SECONDS,
        "AUDIO_MONITOR_START": c.AUDIO_MONITOR_START,
        "AUDIO_MONITOR_END": c.AUDIO_MONITOR_END,
        "AUDIO_MONITOR_RECORD": c.AUDIO_MONITOR_RECORD,
        "AUDIO_MONITOR_INTERVAL": c.AUDIO_MONITOR_INTERVAL,
        "PERIOD_START": c.PERIOD_START,
        "PERIOD_END": c.PERIOD_END,
        "PERIOD_RECORD": c.PERIOD_RECORD,
        "PERIOD_SPECTROGRAM": c.PERIOD_SPECTROGRAM,
        "PERIOD_INTERVAL": c.PERIOD_INTERVAL,
        "EVENT_START": c.EVENT_START,
        "EVENT_END": c.EVENT_END,
        "SAVE_BEFORE_EVENT": c.SAVE_BEFORE_EVENT,
        "SAVE_AFTER_EVENT": c.SAVE_AFTER_EVENT,
        "EVENT_THRESHOLD": c.EVENT_THRESHOLD,
        "MIC_1": c.MIC_1, "MIC_2": c.MIC_2, "MIC_3": c.MIC_3, "MIC_4": c.MIC_4,
        "SOUND_IN_CHS": c.SOUND_IN_CHS,
        "FFT_INTERVAL": c.FFT_INTERVAL,
        "LOG_AUDIO_CALLBACK": c.LOG_AUDIO_CALLBACK,
        "DEBUG_VERBOSE": c.DEBUG_VERBOSE,
        "ENABLE_ENHANCED_AUDIO": c.ENABLE_ENHANCED_AUDIO,
        "AUDIO_API_PREFERENCE": c.AUDIO_API_PREFERENCE_LIST,
        "AUDIO_FALLBACK_ENABLED": c.AUDIO_FALLBACK_ENABLED,
        # Linux selectors
        "LINUX_MAKE_NAME": c.linux_make_name,
        "LINUX_MODEL_NAME": c.linux_model_name,
        "LINUX_DEVICE_NAME": c.linux_device_name,
        "LINUX_API_NAME": c.linux_api_name,
        "LINUX_HOSTAPI_NAME": c.linux_hostapi_name,
        "LINUX_HOSTAPI_INDEX": c.linux_hostapi_index,
        "LINUX_DEVICE_ID": c.linux_device_id,
        # Windows selectors
        "WINDOWS_MAKE_NAME": c.windows_make_name,
        "WINDOWS_MODEL_NAME": c.windows_model_name,
        "WINDOWS_DEVICE_NAME": c.windows_device_name,
        "WINDOWS_API_NAME": c.windows_api_name,
        "WINDOWS_HOSTAPI_NAME": c.windows_hostapi_name,
        "WINDOWS_HOSTAPI_INDEX": c.windows_hostapi_index,
        "WINDOWS_DEVICE_ID": c.windows_device_id,
        # macOS selectors
        "MACOS_MAKE_NAME": c.mac_make_name,
        "MACOS_MODEL_NAME": c.mac_model_name,
        "MACOS_DEVICE_NAME": c.mac_device_name,
        "MACOS_API_NAME": c.mac_api_name,
        "MACOS_HOSTAPI_NAME": c.mac_hostapi_name,
        "MACOS_HOSTAPI_INDEX": c.mac_hostapi_index,
        "MACOS_DEVICE_ID": c.mac_device_id,
        # Audio params
        "PRIMARY_IN_SAMPLERATE": c.PRIMARY_IN_SAMPLERATE,
        "PRIMARY_BITDEPTH": c.PRIMARY_BITDEPTH,
        "PRIMARY_SAVE_SAMPLERATE": c.PRIMARY_SAVE_SAMPLERATE,
        "PRIMARY_FILE_FORMAT": c.PRIMARY_FILE_FORMAT,
        "SAVE_HEADROOM_DB": c.SAVE_HEADROOM_DB,
        "AUDIO_MONITOR_SAMPLERATE": c.AUDIO_MONITOR_SAMPLERATE,
        "AUDIO_MONITOR_BITDEPTH": c.AUDIO_MONITOR_BITDEPTH,
        "AUDIO_MONITOR_CHANNELS": c.AUDIO_MONITOR_CHANNELS,
        "AUDIO_MONITOR_QUALITY": c.AUDIO_MONITOR_QUALITY,
        "AUDIO_MONITOR_FORMAT": c.AUDIO_MONITOR_FORMAT,
        # Data roots
        "win_data_drive": c.win_data_drive,
        "win_data_path": c.win_data_path,
        "win_data_folders": c.win_data_folders,
        "mac_data_drive": c.mac_data_drive,
        "mac_data_path": c.mac_data_path,
        "mac_data_folders": c.mac_data_folders,
        "linux_data_drive": c.linux_data_drive,
        "linux_data_path": c.linux_data_path,
        "linux_data_folders": c.linux_data_folders,
        # Misc
        "MIC_LOCATION": c.MIC_LOCATION,
        "SOUND_IN_DEFAULT": c.SOUND_IN_DEFAULT,
        "SOUND_OUT_ID_DEFAULT": c.SOUND_OUT_ID_DEFAULT,
        "SOUND_OUT_CHS_DEFAULT": c.SOUND_OUT_CHS_DEFAULT,
        "SOUND_OUT_SR_DEFAULT": c.SOUND_OUT_SR_DEFAULT,
        "INTERCOM_SAMPLERATE": c.INTERCOM_SAMPLERATE,
        "TRACE_DURATION": c.TRACE_DURATION,
        "OSCOPE_GAIN_DB": c.OSCOPE_GAIN_DB,
        "FFT_DURATION": c.FFT_DURATION,
        "FFT_GAIN": c.FFT_GAIN,
        "FFT_FREQ_MIN_HZ": c.FFT_FREQ_MIN_HZ,
        "FFT_FREQ_MAX_HZ": c.FFT_FREQ_MAX_HZ,
        "SPECTROGRAM_DURATION": c.SPECTROGRAM_DURATION,
        "SPECTROGRAM_GAIN": c.SPECTROGRAM_GAIN,
        "SPECTROGRAM_DB_MIN": c.SPECTROGRAM_DB_MIN,
        "SPECTROGRAM_DB_MAX": c.SPECTROGRAM_DB_MAX,
        # VU
        "VU_METER_LATENCY_MS": c.VU_METER_LATENCY_MS,
        "VU_METER_DAMPING": c.VU_METER_DAMPING,
    }

# Export legacy uppercase names
globals().update(_derive_legacy_constants(default_config()))

# Lowercase back-compat aliases (module-level) for direct attribute access
_dc = default_config()
globals().update({
    # windows
    "windows_make_name": _dc.windows_make_name,
    "windows_model_name": _dc.windows_model_name,
    "windows_device_name": _dc.windows_device_name,
    "windows_api_name": _dc.windows_api_name,
    "windows_hostapi_name": _dc.windows_hostapi_name,
    "windows_hostapi_index": _dc.windows_hostapi_index,
    "windows_device_id": _dc.windows_device_id,
    # linux
    "linux_make_name": _dc.linux_make_name,
    "linux_model_name": _dc.linux_model_name,
    "linux_device_name": _dc.linux_device_name,
    "linux_api_name": _dc.linux_api_name,
    "linux_hostapi_name": _dc.linux_hostapi_name,
    "linux_hostapi_index": _dc.linux_hostapi_index,
    "linux_device_id": _dc.linux_device_id,
    # mac
    "mac_make_name": _dc.mac_make_name,
    "mac_model_name": _dc.mac_model_name,
    "mac_device_name": _dc.mac_device_name,
    "mac_api_name": _dc.mac_api_name,
    "mac_hostapi_name": _dc.mac_hostapi_name,
    "mac_hostapi_index": _dc.mac_hostapi_index,
    "mac_device_id": _dc.mac_device_id,
})
