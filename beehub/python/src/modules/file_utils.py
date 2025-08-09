"""
BMAR File Management Module
Handles file operations, directory management, and file discovery.
"""

import os
import logging
import datetime
import platform
import time

def _platform_base_root(cfg) -> str:
    """Build base root strictly from BMAR_config platform fields; no fallbacks."""
    sysname = platform.system()
    if sysname == "Windows":
        base = os.path.join(cfg.win_data_drive, cfg.win_data_path)
    elif sysname == "Darwin":
        base = os.path.join(os.path.expanduser(cfg.mac_data_drive), cfg.mac_data_path)
    else:
        base = os.path.join(os.path.expanduser(cfg.linux_data_drive), cfg.linux_data_path)
    return os.path.normpath(base)

def ensure_directories_exist(directories):
    """
    Check if directories exist and create them if necessary.
    
    Args:
        directories: List of directory paths to check and create
        
    Returns:
        bool: True if all directories exist or were created, False otherwise
    """
    # Expand any home directory tildes
    expanded_dirs = [os.path.expanduser(d) for d in directories]
    
    # Check which directories don't exist
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
            
            # Verify directory was created
            if os.path.exists(d):
                logging.info(f"Created directory: {d}")
            else:
                logging.error(f"Failed to create directory: {d} (Unknown error)")
                success = False
        except Exception as e:
            logging.error(f"Error creating directory {d}: {e}")
            success = False
            # Additional debugging for permission issues
            if "Permission denied" in str(e):
                logging.error(f"  This appears to be a permissions issue. Current user may not have write access.")
                logging.error(f"  Current working directory: {os.getcwd()}")
                try:
                    parent_dir = os.path.dirname(d)
                    logging.error(f"  Parent directory permissions: {oct(os.stat(parent_dir).st_mode)}")
                except Exception as e2:
                    logging.error(f"  Could not check parent directory permissions: {e2}")
    return success

def check_and_create_date_folders(cfg):
    """
    Create and return dict of config-based recording folders.
    Uses only BMAR_config fields: win/mac/linux *_data_drive, *_data_path and *_data_folders.
    Returns:
      {
        'base_dir': <root>,
        'audio_base': <root>/audio,
        'plots_base': <root>/plots,
        'today': YYYY-MM-DD,
        'audio_dir': <root>/audio/YYYY-MM-DD,
        'plots_dir': <root>/plots/YYYY-MM-DD,
      }
    """
    root = _platform_base_root(cfg)

    # Determine folder names list from platform
    sysname = platform.system()
    if sysname == "Windows":
        folders = getattr(cfg, "win_data_folders", ["audio", "plots"])
    elif sysname == "Darwin":
        folders = getattr(cfg, "mac_data_folders", ["audio", "plots"])
    else:
        folders = getattr(cfg, "linux_data_folders", ["audio", "plots"])

    # Ensure bases exist
    os.makedirs(root, exist_ok=True)
    subdirs = {name: os.path.join(root, name) for name in folders}
    for p in subdirs.values():
        os.makedirs(p, exist_ok=True)

    # Per-day subfolders
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    dated = {name: os.path.join(path, today) for name, path in subdirs.items()}
    for p in dated.values():
        os.makedirs(p, exist_ok=True)

    audio_base = subdirs.get("audio") or subdirs.get("AUDIO") or list(subdirs.values())[0]
    plots_base = subdirs.get("plots") or subdirs.get("PLOTS") or list(subdirs.values())[1 if len(subdirs) > 1 else 0]
    audio_dir = dated.get("audio") or dated.get("AUDIO") or audio_base
    plots_dir = dated.get("plots") or dated.get("PLOTS") or plots_base

    info = {
        "base_dir": root,
        "audio_base": audio_base,
        "plots_base": plots_base,
        "today": today,
        "audio_dir": os.path.normpath(audio_dir),
        "plots_dir": os.path.normpath(plots_dir),
    }
    logging.info("Recording root (config): %s", info["base_dir"])
    logging.info("Audio dir (config): %s", info["audio_dir"])
    logging.info("Plots dir (config): %s", info["plots_dir"])
    return info

def find_file_of_type_with_offset(app, offset):
    """
    Return the most recent audio file in the directory minus offset (next most recent, etc.)
    
    Args:
        app: BmarApp instance containing configuration
        offset: Number of files to skip from most recent
        
    Returns:
        str: Filename if found, None otherwise
    """
    # Expand path if it contains a tilde
    expanded_dir = os.path.expanduser(app.config.PRIMARY_DIRECTORY)
    
    print(f"\nSearching for {app.config.PRIMARY_FILE_FORMAT} files in: {expanded_dir}")
    
    # Ensure directory exists
    if not os.path.exists(expanded_dir):
        print(f"Directory does not exist: {expanded_dir}")
        return None
        
    try:
        # List all files in the directory first
        all_files = os.listdir(expanded_dir)
        print(f"All files in directory: {all_files}")
        
        # List all files of the specified type in the directory (case-insensitive)
        files_of_type = [f for f in all_files if os.path.isfile(os.path.join(expanded_dir, f)) 
                        and f.lower().endswith(f".{app.config.PRIMARY_FILE_FORMAT.lower()}")]
        
        if not files_of_type:
            print(f"No {app.config.PRIMARY_FILE_FORMAT} files found in directory: {expanded_dir}")
            print(f"Looking for files ending with: .{app.config.PRIMARY_FILE_FORMAT.lower()} (case-insensitive)")
            return None
            
        # Sort files alphabetically - most recent first
        files_of_type.sort(reverse=True)
        print(f"Found {len(files_of_type)} {app.config.PRIMARY_FILE_FORMAT} files: {files_of_type}")
        
        if offset < len(files_of_type):
            selected_file = files_of_type[offset]
            print(f"Selected file at offset {offset}: {selected_file}")
            return selected_file
        else:
            print(f"Offset {offset} is out of range. Found {len(files_of_type)} {app.config.PRIMARY_FILE_FORMAT} files.")
            return None
    except Exception as e:
        print(f"Error listing files in {expanded_dir}: {e}")
    
    return None

def find_file_of_type_with_offset_simple(directory, file_format, offset=0):
    """
    Simplified version for subprocess use - finds files without app dependency.
    
    Args:
        directory: Directory to search in
        file_format: File format/extension to search for
        offset: Number of files to skip from most recent
        
    Returns:
        str: Full path to file if found, None otherwise
    """
    # Expand path if it contains a tilde
    expanded_dir = os.path.expanduser(directory)
    
    # Ensure directory exists
    if not os.path.exists(expanded_dir):
        print(f"Directory does not exist: {expanded_dir}")
        return None
        
    try:
        # List all files of the specified type in the directory (case-insensitive)
        all_files = os.listdir(expanded_dir)
        files_of_type = [f for f in all_files if os.path.isfile(os.path.join(expanded_dir, f)) 
                        and f.lower().endswith(f".{file_format.lower()}")]
        
        if not files_of_type:
            return None
            
        # Sort files alphabetically - most recent first
        files_of_type.sort(reverse=True)
        
        if offset < len(files_of_type):
            return os.path.join(expanded_dir, files_of_type[offset])
        else:
            return None
    except Exception as e:
        print(f"Error listing files in {expanded_dir}: {e}")
        return None

def time_between():
    """
    Creates a closure function that tracks time differences between calls.
    
    Returns:
        function: A function that returns time difference since last call
    """
    # Using a list to store the last called time because lists are mutable 
    # and can be modified inside the nested function.
    # This will act like a "nonlocal" variable.
    last_called = [None]
    
    def helper():
        current_time = time.time()
        if last_called[0] is None:
            last_called[0] = current_time
            return 1800  # Return large value for first call
        diff = current_time - last_called[0]
        last_called[0] = current_time
        return min(diff, 1800)  # Cap at 30 minutes
    
    # Return the helper function, NOT A VALUE.
    return helper

# Initialize the function 'time_diff()', which will return a value.
time_diff = time_between()

def setup_directories(base_path=None):
    """
    Setup the main recording directory structure.
    
    Args:
        base_path: Optional base path for recordings (defaults to user's home)
        
    Returns:
        str: Path to the main recording directory
    """
    if base_path is None:
        # Use user's home directory by default
        base_path = os.path.expanduser("~")
    
    # Create main recording directory
    recording_dir = os.path.join(base_path, "BMAR_Recordings")
    
    try:
        os.makedirs(recording_dir, exist_ok=True)
        logging.info(f"Recording directory setup: {recording_dir}")
        return recording_dir
    except Exception as e:
        logging.error(f"Error setting up recording directory: {e}")
        # Fallback to current directory
        fallback_dir = os.path.join(os.getcwd(), "recordings")
        os.makedirs(fallback_dir, exist_ok=True)
        logging.info(f"Using fallback recording directory: {fallback_dir}")
        return fallback_dir

def get_today_dir(base_recording_dir):
    """
    Get or create today's recording directory.
    
    Args:
        base_recording_dir: Base recording directory path
        
    Returns:
        str: Path to today's recording directory
    """
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    today_dir = os.path.join(base_recording_dir, today_str)
    
    try:
        os.makedirs(today_dir, exist_ok=True)
        logging.info(f"Today's directory: {today_dir}")
        return today_dir
    except Exception as e:
        logging.error(f"Error creating today's directory: {e}")
        # Return base directory as fallback
        return base_recording_dir

def list_recent_files(directory, limit=10, extensions=None):
    """
    List recent files in a directory.
    
    Args:
        directory: Directory path to search
        limit: Maximum number of files to return
        extensions: List of file extensions to filter (e.g., ['.wav', '.mp3'])
        
    Returns:
        list: List of tuples (filepath, size, mtime) sorted by modification time
    """
    try:
        if not os.path.exists(directory):
            return []
        
        files = []
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            
            # Skip directories
            if os.path.isdir(filepath):
                continue
            
            # Filter by extensions if provided
            if extensions:
                if not any(filename.lower().endswith(ext.lower()) for ext in extensions):
                    continue
            
            try:
                stat = os.stat(filepath)
                files.append((filepath, stat.st_size, stat.st_mtime))
            except OSError:
                continue
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x[2], reverse=True)
        
        return files[:limit]
        
    except Exception as e:
        logging.error(f"Error listing recent files in {directory}: {e}")
        return []

def log_saved_file(path: str, prefix: str = "") -> None:
    """
    Log the absolute path of a saved file.
    Use prefix like 'Audio' or 'Image' if desired.
    """
    try:
        abspath = os.path.abspath(os.path.expanduser(path))
        if prefix:
            logging.info("%s saved: %s", prefix, abspath)
        else:
            logging.info("Saved file: %s", abspath)
    except Exception as e:
        logging.warning("Could not log saved file path for %s: %s", path, e)
