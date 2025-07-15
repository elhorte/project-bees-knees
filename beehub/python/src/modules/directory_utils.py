"""
Directory Utilities Module
Handles creation and management of recording directories.
"""

import os
import logging
from datetime import datetime

def setup_directories():
    """Set up the main recording directory."""
    try:
        # Get the user's home directory
        home_dir = os.path.expanduser("~")
        
        # Create the main BMAR recordings directory
        recording_dir = os.path.join(home_dir, "BMAR_Recordings")
        os.makedirs(recording_dir, exist_ok=True)
        
        logging.info(f"Recording directory setup: {recording_dir}")
        return recording_dir
        
    except Exception as e:
        logging.error(f"Error setting up recording directory: {e}")
        # Fallback to current directory
        return os.getcwd()

def get_today_dir(recording_dir):
    """Get today's recording directory."""
    try:
        # Create directory for today's date
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = os.path.join(recording_dir, today)
        os.makedirs(today_dir, exist_ok=True)
        
        logging.info(f"Today's directory: {today_dir}")
        return today_dir
        
    except Exception as e:
        logging.error(f"Error setting up today's directory: {e}")
        # Fallback to recording directory
        return recording_dir

def ensure_directory_exists(directory_path):
    """Ensure a directory exists, creating it if necessary."""
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Error creating directory {directory_path}: {e}")
        return False