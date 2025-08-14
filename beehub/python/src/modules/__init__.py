"""
BMAR Modules Package
Modular components for the Bioacoustic Monitoring and Recording system.
"""
import importlib
import types

__version__ = "1.0.0"
__author__ = "BMAR Development Team"
__description__ = "Modular Biometric Monitoring and Recording System"

# Lazy attribute resolution to avoid circular imports at package import time
_SUBMODULES = (
    "modules.bmar_app",
    "modules.bmar_config",
    "modules.platform_manager",
    "modules.file_utils",
    "modules.audio_devices",
    "modules.audio_conversion",
    "modules.audio_processing",
    "modules.audio_tools",
    "modules.plotting",
    "modules.user_interface",
    "modules.process_manager",
    "modules.system_utils",
)

def __getattr__(name: str):
    for modname in _SUBMODULES:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        if hasattr(mod, name):
            return getattr(mod, name)
    raise AttributeError(f"module 'modules' has no attribute '{name}'")

def __dir__():
    names = set(globals().keys())
    for modname in _SUBMODULES:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        names.update(getattr(mod, "__all__", []) or dir(mod))
    return sorted(names)

'''
__init__.py no longer triggers bmar_app at package import time, so importing modules.file_utils doesn’t re-enter bmar_app.
bmar_app imports file_utils in a package-qualified way and doesn’t suppress real import-time errors.
file_utils.py is now complete and importable.
'''