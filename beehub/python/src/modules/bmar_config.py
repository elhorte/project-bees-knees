"""
BMAR Configuration Module
Contains global constants, settings, and configuration validation.
"""

import os
import datetime
import platform
import subprocess

# #############################################################
# #### Control Panel ##########################################
# #############################################################

MONITOR_CH = 0                                  # channel to monitor for event (if > number of chs, all channels are monitored)

# instrumentation parms
FFT_BINS = 800                                  # number of bins for fft
FFT_BW = 1000                                   # bandwidth of each bucket in hertz
FFT_INTERVAL = 30                               # minutes between ffts

FULL_SCALE = 2 ** 16                            # just for cli vu meter level reference
BUFFER_SECONDS = 1000                           # time length of circular buffer 

# Global flags
testmode = False                                # True = run in test mode with lower than needed sample rate
KB_or_CP = 'KB'                                # use keyboard or control panel (PyQT5) to control program

# Dictionary to track active processes by key
ACTIVE_PROCESSES_TEMPLATE = {
    'v': None,  # VU meter
    'o': None,  # Oscilloscope
    's': None,  # Spectrogram 
    'f': None,  # FFT
    'i': None,  # Intercom
    'p': None,  # Performance monitor (one-shot)
    'P': None   # Performance monitor (continuous)
}

def get_date_folder():
    """Get current date folder in YYMMDD format."""
    current_date = datetime.datetime.now()
    yy = current_date.strftime('%y')  # 2-digit year (e.g., '23' for 2023)
    mm = current_date.strftime('%m')  # Month (01-12)
    dd = current_date.strftime('%d')  # Day (01-31)
    return f"{yy}{mm}{dd}"             # Format YYMMDD (e.g., '230516')

def validate_bit_depth(bit_depth):
    """Validate and return appropriate data type for bit depth."""
    if bit_depth == 16:
        return 'int16'
    elif bit_depth == 24:
        return 'int32'  # 24-bit audio is typically stored in 32-bit containers
    elif bit_depth == 32:
        return 'float32'
    else:
        raise ValueError(f"Unsupported bit depth: {bit_depth}")

def get_platform_audio_config(platform_manager, config):
    """Get platform-specific audio configuration."""
    if platform_manager.is_macos():
        return {
            'data_drive': os.path.expanduser(config.mac_data_drive),
            'data_path': config.mac_data_path,
            'folders': config.mac_data_folders,
            'make_name': config.MACOS_MAKE_NAME,
            'model_name': config.MACOS_MODEL_NAME,
            'device_name': config.MACOS_DEVICE_NAME,
            'api_name': config.MACOS_API_NAME,
            'hostapi_name': config.MACOS_HOSTAPI_NAME,
            'hostapi_index': config.MACOS_HOSTAPI_INDEX,
            'device_id': config.MACOS_DEVICE_ID
        }
    elif platform_manager.is_windows():
        return {
            'data_drive': config.win_data_drive,
            'data_path': config.win_data_path,
            'folders': config.win_data_folders,
            'make_name': config.WINDOWS_MAKE_NAME,
            'model_name': config.WINDOWS_MODEL_NAME,
            'device_name': config.WINDOWS_DEVICE_NAME,
            'api_name': config.WINDOWS_API_NAME,
            'hostapi_name': config.WINDOWS_HOSTAPI_NAME,
            'hostapi_index': config.WINDOWS_HOSTAPI_INDEX,
            'device_id': config.WINDOWS_DEVICE_ID
        }
    else:  # Linux or other Unix-like
        return {
            'data_drive': os.path.expanduser(config.linux_data_drive),
            'data_path': config.linux_data_path,
            'folders': config.linux_data_folders,
            'make_name': config.LINUX_MAKE_NAME,
            'model_name': config.LINUX_MODEL_NAME,
            'device_name': config.LINUX_DEVICE_NAME,
            'api_name': config.LINUX_API_NAME,
            'hostapi_name': config.LINUX_HOSTAPI_NAME,
            'hostapi_index': config.LINUX_HOSTAPI_INDEX,
            'device_id': config.LINUX_DEVICE_ID
        }

def validate_audio_config(config):
    """Validate audio configuration parameters."""
    errors = []
    
    # Validate sound input channels
    if hasattr(config, 'SOUND_IN_CHS'):
        sound_in_chs = int(config.SOUND_IN_CHS) if hasattr(config, 'SOUND_IN_CHS') else 1
        if sound_in_chs <= 0 or sound_in_chs > 64:
            errors.append(f"Invalid SOUND_IN_CHS value: {config.SOUND_IN_CHS}")
    
    # Validate bit depth
    if hasattr(config, 'PRIMARY_BITDEPTH'):
        try:
            validate_bit_depth(config.PRIMARY_BITDEPTH)
        except ValueError as e:
            errors.append(str(e))
    
    return errors

def construct_directory_paths(data_drive, data_path, location_id, hive_id, folders, date_folder):
    """Construct standardized directory paths."""
    primary_directory = os.path.join(data_drive, data_path, location_id, hive_id, 
                                   folders[0], "raw", date_folder, "")
    monitor_directory = os.path.join(data_drive, data_path, location_id, hive_id, 
                                   folders[0], "mp3", date_folder, "")
    plot_directory = os.path.join(data_drive, data_path, location_id, hive_id, 
                                 folders[1], date_folder, "")
    
    return {
        'primary': primary_directory,
        'monitor': monitor_directory,
        'plot': plot_directory
    }

def get_platform_config():
    """Get platform-specific configuration information."""
    config = {
        'name': platform.system(),
        'version': platform.version(),
        'machine': platform.machine(),
        'is_wsl': False,
        'pulse_server': None
    }
    
    # Check if running under WSL
    try:
        if platform.system() == 'Linux':
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                if 'microsoft' in version_info or 'wsl' in version_info:
                    config['is_wsl'] = True
                    # Check for PulseAudio server
                    pulse_server = os.environ.get('PULSE_SERVER')
                    if pulse_server:
                        config['pulse_server'] = pulse_server
    except:
        pass
    
    return config
