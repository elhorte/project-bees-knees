"""
BMAR Modules Package
Modular components for the Bioacoustic Monitoring and Recording system.
"""

# Import main application class
from .bmar_app import BmarApp, create_bmar_app, run_bmar_application

# Import configuration
from .bmar_config import *

# Import core modules
from .platform_manager import PlatformManager
from .system_utils import *
from .file_utils import *
from .audio_devices import *
from .audio_conversion import *
from .audio_processing import *
from .audio_tools import *
from .plotting import *
from .user_interface import *
from .process_manager import *

__version__ = "1.0.0"
__author__ = "BMAR Development Team"
__description__ = "Modular Bioacoustic Monitoring and Recording System"

# Export main components
__all__ = [
    # Main application
    'BmarApp',
    'create_bmar_app', 
    'run_bmar_application',
    
    # Core modules
    'PlatformManager',
    
    # Configuration constants
    'DEFAULT_SAMPLERATE',
    'DEFAULT_BLOCKSIZE', 
    'DEFAULT_MAX_FILE_SIZE_MB',
    'CIRCULAR_BUFFER_DURATION_SECONDS',
    
    # Key functions from each module
    'setup_directories',
    'get_audio_device_config',
    'list_audio_devices_detailed',
    'show_current_audio_devices',
    'show_detailed_device_list',
    'list_all_threads',
    'start_recording_worker',
    'plot_oscope',
    'plot_spectrogram', 
    'trigger',
    'vu_meter',
    'intercom_m',
    'keyboard_listener',
    'process_command',
    'cleanup_process',
    'stop_all',
    'cleanup'
]
