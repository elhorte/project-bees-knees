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
            if sys.platform == 'win32' and not self.is_wsl():
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
    
    def is_wsl(self):
        """Check if running in Windows Subsystem for Linux."""
        try:
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                return 'microsoft' in version_info or 'wsl' in version_info
        except (FileNotFoundError, IOError):
            return False
    
    def is_macos(self):
        """Check if running on macOS."""
        return sys.platform == 'darwin'
    
    def is_windows(self):
        """Check if running on Windows (not WSL)."""
        return sys.platform == 'win32' and not self.is_wsl()
    
    def is_linux(self):
        """Check if running on Linux (including WSL)."""
        return sys.platform.startswith('linux')
    
    def get_os_info(self):
        """Get detailed OS information."""
        info = {
            'platform': sys.platform,
            'is_wsl': self.is_wsl(),
            'is_macos': self.is_macos(),
            'is_windows': self.is_windows(),
            'is_linux': self.is_linux()
        }
        return info
    
    def setup_environment(self):
        """Setup platform-specific environment variables and configuration."""
        try:
            if self.is_wsl():
                # Setup WSL-specific audio environment
                if 'PULSE_SERVER' not in os.environ:
                    os.environ['PULSE_SERVER'] = 'unix:/mnt/wslg/PulseServer'
                logging.info("WSL audio environment configured")
            else:
                logging.info("Platform environment setup completed")
        except Exception as e:
            logging.warning(f"Platform environment setup warning: {e}")

def check_wsl_audio():
    """Check WSL audio configuration and provide setup instructions."""
    try:       
        # Set PulseAudio server to use TCP
        os.environ['PULSE_SERVER'] = 'tcp:localhost'
        
        # Check if PulseAudio is running
        result = subprocess.run(['pulseaudio', '--check'], capture_output=True, text=True)
        if result.returncode != 0:
            logging.info("\nPulseAudio is not running. Starting it...")
            subprocess.run(['pulseaudio', '--start'], capture_output=True)
        
        # Check if ALSA is configured
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        print("\nALSA devices:")
        print(result.stdout)
        
        # Check if PulseAudio is configured
        result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
        print("\nPulseAudio info:")
        print(result.stdout)
        
        # Check if we can list audio devices through PulseAudio
        result = subprocess.run(['pactl', 'list', 'sources'], capture_output=True, text=True)
        print("\nPulseAudio sources:")
        print(result.stdout)
        
        return True
    except Exception as e:
        print(f"\nError checking audio configuration: {e}")
        print("\nPlease ensure your WSL audio is properly configured:")
        print("1. Install required packages:")
        print("   sudo apt-get update")
        print("   sudo apt-get install -y pulseaudio libasound2-plugins")
        print("\n2. Configure PulseAudio:")
        print("   echo 'export PULSE_SERVER=tcp:localhost' >> ~/.bashrc")
        print("   source ~/.bashrc")
        print("\n3. Create PulseAudio configuration:")
        print("   mkdir -p ~/.config/pulse")
        print("   echo 'load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1' > ~/.config/pulse/default.pa")
        print("\n4. Start PulseAudio:")
        print("   pulseaudio --start")
        print("\n5. Test audio:")
        print("   speaker-test -t sine -f 1000 -l 1")
        return False
