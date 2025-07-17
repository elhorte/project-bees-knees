"""
BMAR Application Module
Main application class that coordinates all modules and manages the application state.
"""

import multiprocessing
import threading
import signal
import sys
import logging
import time
import os
import numpy as np

# Import core modules that should always be present
from .bmar_config import *
from .platform_manager import PlatformManager

# Try to import other modules with fallbacks
try:
    from .system_utils import setup_logging, setup_signal_handlers
except ImportError:
    logging.warning("system_utils module not available")

try:
    from .file_utils import setup_directories, get_today_dir
except ImportError:
    logging.warning("file_utils module not available")

try:
    from .audio_devices import get_audio_device_config, configure_audio_device_interactive
except ImportError:
    logging.warning("audio_devices module not available")

try:
    from .process_manager import stop_all, cleanup
except ImportError:
    logging.warning("process_manager module not available")

try:
    from .user_interface import keyboard_listener, cleanup_ui
except ImportError:
    logging.warning("user_interface module not available")

try:
    from .class_PyAudio import *
except ImportError:
    logging.warning("class_PyAudio module not available")

class BmarApp:
    """Main BMAR Application class."""
    
    def __init__(self):
        """Initialize the BMAR application."""
        self.platform_manager = None
        self.recording_dir = None
        self.today_dir = None
        self.circular_buffer = None
        self.active_processes = {}
        self.virtual_device = False
        
        # Audio configuration attributes
        self.device_index = None
        self.sound_in_id = None
        self.sound_in_chs = 1
        self.samplerate = 44100
        self.PRIMARY_IN_SAMPLERATE = 44100
        self.channels = 1
        self._bit_depth = 16
        self.blocksize = 1024
        self.monitor_channel = 0
        self.testmode = True
        
        # Platform attributes
        self.is_wsl = False
        self.is_macos = False
        self.os_info = ""
        
        # User interface attributes (required by your keyboard_listener function)
        self.keyboard_listener_running = False
        self.shutdown_requested = False
        self.stop_program = [False]  # Your code expects this as a list
        
        # Other attributes your functions might need
        self.DEBUG_VERBOSE = False
        self.max_file_size_mb = 100
        self.buffer_pointer = [0]  # For circular buffer tracking
        
        # Initialize platform manager
        from .platform_manager import PlatformManager
        self.platform_manager = PlatformManager()

    def initialize(self):
        """Initialize the application components."""
        
        try:
            print("Initializing BMAR...")
            
            # Setup signal handlers (with fallback if module missing)
            try:
                from .signal_handlers import setup_signal_handlers
                setup_signal_handlers(self)
            except ImportError:
                logging.warning("Signal handlers module not available, using basic signal handling")
                self.setup_basic_signal_handlers()
            
            # Initialize platform-specific settings
            self.platform_manager.setup_environment()
            
            # Set platform attributes for VU meter compatibility
            self.is_wsl = self.platform_manager.is_wsl()
            self.is_macos = self.platform_manager.is_macos()
            os_info = self.platform_manager.get_os_info()
            self.os_info = f"{os_info['platform']}"
            
            # Handle WSL-specific setup early
            if self.is_wsl:
                print("WSL environment detected - setting up WSL audio...")
                self.setup_wsl_environment()
            
            # Setup directories (with fallback if module missing)
            try:
                from .directory_utils import setup_directories, get_today_dir
                self.recording_dir = setup_directories()
                self.today_dir = get_today_dir(self.recording_dir)
            except ImportError:
                logging.warning("Directory utils module not available, using fallback")
                self.setup_basic_directories()
            
            print(f"Recording directory: {self.recording_dir}")
            print(f"Today's directory: {self.today_dir}")
            
            # Initialize audio with WSL-aware logic
            audio_success = self.initialize_audio_with_fallback()
            if not audio_success:
                raise RuntimeError("No suitable audio device found")
            
            # Initialize circular buffer
            import multiprocessing
            buffer_duration = 300  # 5 minutes default
            buffer_size = int(self.samplerate * buffer_duration)
            self.circular_buffer = multiprocessing.Array('f', buffer_size)
            
            print(f"Circular buffer: {buffer_duration}s ({buffer_size} samples)")
            
            # Initialize process tracking
            command_keys = ['r', 's', 'o', 't', 'v', 'i', 'p', 'P']
            for key in command_keys:
                self.active_processes[key] = None
            
            print("BMAR initialization completed successfully")
            return True
            
        except Exception as e:
            print(f"Initialization error: {e}")
            logging.error(f"Initialization error: {e}")
            return False

    def initialize_audio_with_fallback(self) -> bool:
        """Initialize audio system with proper WSL fallback handling."""
        try:
            from .audio_devices import configure_audio_device_interactive, get_audio_device_config
            
            # Try standard audio configuration first (but don't fail hard)
            if not self.is_wsl:
                print("Attempting standard audio device configuration...")
                try:
                    if configure_audio_device_interactive(self):
                        print(f"Audio device: {self.device_index} at {self.samplerate}Hz ({self.channels} channels)")
                        return True
                except Exception as e:
                    print(f"Standard audio configuration failed: {e}")
                    logging.info(f"Standard audio configuration failed, trying fallback: {e}")
            
            # Try fallback configuration
            print("Attempting fallback audio configuration...")
            device_config = get_audio_device_config()
            if device_config and device_config.get('default_device'):
                device = device_config['default_device']
                self.device_index = device['index']
                self.samplerate = int(device['default_sample_rate'])
                self.channels = min(2, device['input_channels'])
                self.sound_in_id = device['index']
                self.sound_in_chs = self.channels
                self.PRIMARY_IN_SAMPLERATE = self.samplerate
                print(f"Fallback audio device: {self.device_index} at {self.samplerate}Hz ({self.channels} channels)")
                return True
            
            # WSL-specific fallback
            if self.is_wsl:
                print("Attempting WSL audio fallback...")
                success = self.initialize_wsl_audio_fallback()
                if success:
                    print(f"WSL audio device: {self.device_index} at {self.samplerate}Hz ({self.channels} channels)")
                    return True
            
            # Last resort: create a minimal virtual device
            print("Creating virtual audio device as last resort...")
            self.create_virtual_audio_device()
            return True
            
        except Exception as e:
            logging.error(f"Audio initialization error: {e}")
            return False

    def create_virtual_audio_device(self):
        """Create a virtual audio device for testing when no real devices are available."""
        try:
            print("No audio devices found - creating virtual device for testing")
            print("Warning: No actual audio will be recorded with virtual device")
            
            # Set minimal virtual device configuration
            self.device_index = 0
            self.samplerate = 44100
            self.channels = 1
            self.sound_in_chs = 1
            self.PRIMARY_IN_SAMPLERATE = 44100
            self._bit_depth = 16
            self.blocksize = 1024
            self.monitor_channel = 0
            self.virtual_device = True  # Flag to indicate this is virtual
            self.testmode = False  # Allow operations with virtual device
            
            print("Virtual audio device created successfully")
            print("  Device ID: 0 (virtual)")
            print("  Sample rate: 44100 Hz")
            print("  Channels: 1")
            print("  Note: Interface will work but no audio will be recorded")
            
        except Exception as e:
            logging.error(f"Error creating virtual audio device: {e}")
            raise

    def setup_wsl_environment(self):
        """Set up WSL-specific environment."""
        try:
            logging.info("Setting up WSL environment...")
            
            # Set up matplotlib for WSL (non-interactive backend)
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            logging.info("Matplotlib configured for WSL (Agg backend)")
            
            # Set up audio environment variables
            import os
            os.environ['PULSE_RUNTIME_PATH'] = '/mnt/wslg/runtime-dir/pulse'
            
            # Try to start PulseAudio if available
            try:
                import subprocess
                subprocess.run(['pulseaudio', '--check'], capture_output=True, timeout=2)
                logging.info("PulseAudio is running")
            except:
                try:
                    subprocess.run(['pulseaudio', '--start'], capture_output=True, timeout=5)
                    logging.info("Started PulseAudio")
                except:
                    logging.info("PulseAudio not available or failed to start")
            
            logging.info("WSL environment setup completed")
            
        except Exception as e:
            logging.warning(f"WSL environment setup warning: {e}")

    def initialize_wsl_audio_fallback(self) -> bool:
        """Initialize audio system with WSL fallback."""
        try:
            from .audio_devices import setup_wsl_audio_fallback
            
            logging.info("Attempting WSL audio fallback...")
            success = setup_wsl_audio_fallback(self)
            
            if success:
                logging.info("WSL audio fallback successful")
                return True
            else:
                logging.warning("WSL audio fallback failed")
                return False
                
        except ImportError:
            logging.warning("WSL audio manager not available")
            return False
        except Exception as e:
            logging.error(f"WSL audio fallback error: {e}")
            return False

    def run(self):
        """Main application run loop."""
        try:
            print("\nBMAR Audio Recording System")
            print("="*50)
            
            if hasattr(self, 'virtual_device') and self.virtual_device:
                print("⚠ RUNNING WITH VIRTUAL AUDIO DEVICE")
                print("  Interface is functional but no audio will be recorded")
                print("  This is normal in WSL or systems without audio hardware")
                print()
            
            # Set the keyboard listener to running state
            self.keyboard_listener_running = True
            
            # Start the user interface using the CORRECT function name
            from .user_interface import keyboard_listener
            keyboard_listener(self)
            
        except KeyboardInterrupt:
            print("\nShutdown requested by user")
        except Exception as e:
            print(f"Application error: {e}")
            logging.error(f"Application run error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up application resources."""
        try:
            print("Cleaning up BMAR application...")
            logging.info("Stopping all processes and threads...")
            
            # Stop all active processes
            if hasattr(self, 'active_processes'):
                for key, process in self.active_processes.items():
                    if process is not None:
                        try:
                            if hasattr(process, 'terminate'):
                                process.terminate()
                                process.join(timeout=2)
                            elif hasattr(process, 'stop'):
                                process.stop()
                        except Exception as e:
                            logging.warning(f"Error stopping process {key}: {e}")
                
                print("All processes stopped.")
            
            # Clean up user interface using the CORRECT function name
            try:
                from .user_interface import cleanup_ui
                cleanup_ui(self)
                print("User interface cleanup completed.")
            except Exception as e:
                logging.error(f"User interface cleanup error: {e}")
            
            # Final cleanup
            print("Performing cleanup...")
            logging.info("Cleanup completed.")
            
        except Exception as e:
            logging.error(f"Cleanup error: {e}")
            print(f"Cleanup error: {e}")

    def setup_basic_signal_handlers(self):
        """Set up basic signal handlers when signal_handlers module is not available."""
        try:
            import signal
            
            def basic_signal_handler(signum, frame):
                print(f"\nReceived signal {signum}, shutting down...")
                self.shutdown_requested = True
                if hasattr(self, 'cleanup'):
                    self.cleanup()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, basic_signal_handler)
            signal.signal(signal.SIGTERM, basic_signal_handler)
            self.shutdown_requested = False
            
            logging.info("Basic signal handlers set up")
            
        except Exception as e:
            logging.warning(f"Could not set up basic signal handlers: {e}")

    def setup_basic_directories(self):
        """Set up basic directories when directory_utils module is not available."""
        try:
            import os
            from datetime import datetime
            
            # Create basic recording directory
            home_dir = os.path.expanduser("~")
            self.recording_dir = os.path.join(home_dir, "BMAR_Recordings")
            os.makedirs(self.recording_dir, exist_ok=True)
            
            # Create today's directory
            today = datetime.now().strftime("%Y-%m-%d")
            self.today_dir = os.path.join(self.recording_dir, today)
            os.makedirs(self.today_dir, exist_ok=True)
            
            logging.info(f"Basic directories set up: {self.recording_dir}")
            
        except Exception as e:
            logging.error(f"Error setting up basic directories: {e}")
            # Fallback to current directory
            self.recording_dir = os.getcwd()
            self.today_dir = os.getcwd()

    def print_line(self, text, prefix_newline=True, suffix_newline=False):
        """Print with proper line endings for cross-platform compatibility."""
        import os
        
        # Build the output string
        output = ""
        
        # Add prefix newline if requested
        if prefix_newline:
            output += "\n"  # Use simple \n instead of os.linesep for now
        
        # Add the main text
        output += text
        
        # Add suffix newline if requested
        if suffix_newline:
            output += "\n"
        
        # Print with explicit newline and flush
        print(output)
        
        # Ensure output is flushed immediately
        import sys
        sys.stdout.flush()

def create_bmar_app():
    """Create and initialize a BMAR application instance."""
    try:
        app = BmarApp()
        
        if app.initialize():
            logging.info("BMAR Application created successfully")
            return app
        else:
            logging.error("Failed to initialize BMAR application")
            return None
            
    except Exception as e:
        logging.error(f"Error creating BMAR application: {e}")
        return None

def run_bmar_application():
    """Main entry point for running the BMAR application."""
    import sys
    
    try:
        # Create and run the application
        app = create_bmar_app()
        
        if app is None:
            logging.error("Failed to initialize application")
            return 1
        
        # Run the application
        app.run()
        return 0
        
    except Exception as e:
        logging.error(f"Fatal application error: {e}")
        print(f"Fatal error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0

if __name__ == "__main__":
    """Allow the module to be run directly for testing."""
    import sys
    sys.exit(run_bmar_application())
