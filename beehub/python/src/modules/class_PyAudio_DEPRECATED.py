"""
DEPRECATED: class_PyAudio.py Module

This module has been DEPRECATED in favor of sounddevice-based audio management.

MIGRATION NOTICE:
================
This PyAudio-based AudioPortManager class has been replaced with direct sounddevice 
implementations in the following modules:

REPLACEMENT MODULES:
- audio_devices.py - Device discovery and configuration using sounddevice
- audio_processing.py - Audio streaming using sounddevice  
- audio_tools.py - VU meter and intercom using sounddevice

MIGRATION BENEFITS:
- Eliminated PyAudio installation issues
- Better cross-platform compatibility  
- Simplified dependency management
- More reliable audio device detection
- Native numpy integration

DEPRECATED FUNCTIONALITY:
- AudioPortManager class -> Replaced with sounddevice functions
- PyAudio stream management -> Replaced with sounddevice streams
- Device enumeration -> Replaced with sd.query_devices()
- Audio format handling -> Replaced with sounddevice dtypes

DO NOT USE THIS MODULE IN NEW CODE.

If you need audio functionality, use:
- from .audio_devices import list_audio_devices, get_audio_device_config
- from .audio_processing import audio_stream  
- from .audio_tools import vu_meter, intercom_m

For migration assistance, see the sounddevice-based implementations in the above modules.

Last maintained: July 2025
Deprecated in: BMAR sounddevice migration  
"""

import warnings

def _deprecated_warning():
    warnings.warn(
        "class_PyAudio.py is deprecated. Use audio_devices.py, audio_processing.py, "
        "and audio_tools.py with sounddevice instead.",
        DeprecationWarning,
        stacklevel=3
    )

class AudioPortManager:
    """DEPRECATED: Use sounddevice-based functions in audio_devices.py instead."""
    
    def __init__(self, *args, **kwargs):
        _deprecated_warning()
        raise RuntimeError(
            "AudioPortManager is deprecated. Use functions in audio_devices.py instead. "
            "See class_PyAudio_DEPRECATED.py for migration guidance."
        )

# Prevent imports from this deprecated module
def __getattr__(name):
    _deprecated_warning()
    raise AttributeError(
        f"'{name}' from class_PyAudio is deprecated. "
        "Use audio_devices.py, audio_processing.py, or audio_tools.py instead."
    )

if __name__ == "__main__":
    print(__doc__)
