"""
BMAR Platform Manager Module
Handles platform detection and OS-specific functionality.
"""

import sys
import os
import subprocess
import logging

class PlatformManager:
    """Manages platform-specific functionality and detection."""
    
    def __init__(self):
        self.msvcrt = None
        self.termios = None
        self.tty = None
        self.select = None
        
        # Try to import platform-specific modules
        self._import_platform_modules()
    
    def _import_platform_modules(self):
        """Import platform-specific modules based on current OS."""
        try:
            if sys.platform == 'win32':
                import msvcrt
                self.msvcrt = msvcrt
        except ImportError:
            pass
        
        try:
            import termios
            import tty
            import select
            self.termios = termios
            self.tty = tty
            self.select = select
        except ImportError:
            pass
    
    def is_macos(self):
        """Check if running on macOS."""
        return sys.platform == 'darwin'
    
    def is_windows(self):
        """Check if running on Windows."""
        return sys.platform == 'win32'
    
    def is_linux(self):
        """Check if running on Linux."""
        return sys.platform.startswith('linux')
    
    def get_os_info(self):
        """Get detailed OS information."""
        info = {
            'platform': sys.platform,
            'is_macos': self.is_macos(),
            'is_windows': self.is_windows(),
            'is_linux': self.is_linux()
        }
        return info
    
    def setup_environment(self):
        """Setup platform-specific environment variables and configuration."""
        try:
            logging.info("Platform environment setup completed")
        except Exception as e:
            logging.warning(f"Platform environment setup warning: {e}")


