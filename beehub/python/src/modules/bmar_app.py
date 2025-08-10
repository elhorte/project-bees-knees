"""
BMAR Application Module
Main application class that coordinates all modules and manages the application state.
"""

import multiprocessing
import threading
import sys
import logging
import os
import numpy as np
import datetime

# Import core modules that should always be present
from .bmar_config import *
from .platform_manager import PlatformManager

# Try to import other modules with fallbacks
try:
    from .file_utils import setup_directories, get_today_dir
except ImportError:
    logging.warning("file_utils module not available")

try:
    from .audio_devices import get_audio_device_config, find_device_by_config
except ImportError:
    logging.warning("audio_devices module not available")

try:
    from .user_interface import keyboard_listener, cleanup_ui, background_keyboard_monitor
except ImportError:
    logging.warning("user_interface module not available")

class BmarApp:
    """Main BMAR Application class."""
    
    def __init__(self):
        """Initialize the BMAR application."""
        self.platform_manager = None
        self.recording_dir = None
        self.today_dir = None
        self.circular_buffer = None
        self.active_processes = {}
        
        # Add debug mode flag
        self.debug_mode = True  # ← Add this line here
        
        # Audio configuration attributes
        self.device_index = None
        self.sound_in_id = None
        self.sound_in_chs = 1
        self.samplerate = 48000
        self.PRIMARY_IN_SAMPLERATE = 48000
        self.channels = 1
        self._bit_depth = 16
        self.blocksize = 1024
        self.monitor_channel = 0
        # Default output device index for playback (intercom)
        self.output_device_index = None
        
        # Platform attributes
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
        
        # Audio streaming and recording attributes
        self.audio_stream = None
        self.pa_instance = None
        self.buffer = None
        self.buffer_index = 0
        self.buffer_size = 0
        self.buffer_wrap = False
        self.period_start_index = 0
        
        # Threading events for recording
        self.stop_recording_event = threading.Event()  # For manual recording only
        self.stop_auto_recording_event = threading.Event()  # For automatic recording
        self.buffer_wrap_event = threading.Event()
        
        # Initialize platform manager
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
            self.is_macos = self.platform_manager.is_macos()
            os_info = self.platform_manager.get_os_info()
            self.os_info = f"{os_info['platform']}"
            
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
            
            # Initialize audio
            audio_success = self.initialize_audio_with_fallback()
            if not audio_success:
                raise RuntimeError("No suitable audio device found")
            
            # Import and setup config for audio processing
            from . import bmar_config
            self.config = bmar_config
            
            # Initialize channel to monitor and default output device from config
            try:
                self.monitor_channel = int(getattr(self.config, 'MONITOR_CH', 0))
            except Exception:
                self.monitor_channel = 0
            try:
                self.output_device_index = getattr(self.config, 'SOUND_OUT_ID_DEFAULT', None)
            except Exception:
                self.output_device_index = None
            
            # Set up platform-specific directory configuration
            from .bmar_config import get_platform_audio_config
            platform_config = get_platform_audio_config(self.platform_manager, bmar_config)
            
            # Add platform-specific attributes needed by file_utils
            self.data_drive = platform_config['data_drive']
            self.data_path = platform_config['data_path']
            self.folders = platform_config['folders']
            
            # Set up audio processing attributes from config
            self.PRIMARY_IN_SAMPLERATE = getattr(bmar_config, 'PRIMARY_IN_SAMPLERATE', 48000)
            self.PRIMARY_BITDEPTH = getattr(bmar_config, 'PRIMARY_BITDEPTH', 16)
            self.PRIMARY_SAVE_SAMPLERATE = getattr(bmar_config, 'PRIMARY_SAVE_SAMPLERATE', None)
            self.BUFFER_SECONDS = getattr(bmar_config, 'BUFFER_SECONDS', 300)
            
            # Set up directory attributes for recording (these will be updated by check_and_create_date_folders)
            self.MONITOR_DIRECTORY = os.path.join(self.today_dir, 'monitor')
            self.PRIMARY_DIRECTORY = os.path.join(self.today_dir, 'primary')
            self.PLOT_DIRECTORY = os.path.join(self.today_dir, 'plots')
            
            # Ensure recording directories exist
            os.makedirs(self.MONITOR_DIRECTORY, exist_ok=True)
            os.makedirs(self.PRIMARY_DIRECTORY, exist_ok=True)
            os.makedirs(self.PLOT_DIRECTORY, exist_ok=True)
            
            # Set up data type based on bit depth
            if self.PRIMARY_BITDEPTH == 16:
                self._dtype = np.int16
            elif self.PRIMARY_BITDEPTH == 24:
                self._dtype = np.int32
            elif self.PRIMARY_BITDEPTH == 32:
                self._dtype = np.float32
            else:
                self._dtype = np.float32  # Default fallback
            
            # Initialize circular buffer if audio recording will be used
            if self.should_start_auto_recording():
                self.setup_audio_circular_buffer()
            
            # Initialize circular buffer
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
        """Initialize audio system using config-specified devices."""
        try:
            from .audio_devices import find_device_by_config, get_audio_device_config
            
            print("Searching for audio device specified in configuration...")
            
            # Try config-based device finding first
            try:
                if find_device_by_config(self):
                    print(f"Audio device configured: {self.device_index} at {self.samplerate}Hz ({self.channels} channels)")
                    return True
            except Exception as e:
                print(f"Config-based device configuration failed: {e}")
                logging.info(f"Config-based device configuration failed, trying fallback: {e}")
            
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
            
            # If we get here, no audio devices were found
            raise RuntimeError("No suitable audio devices found. Please check your audio hardware and drivers.")
            
        except Exception as e:
            logging.error(f"Audio initialization error: {e}")
            print(f"FATAL: Audio initialization failed - {e}")
            return False

    def should_start_auto_recording(self):
        """Check if automatic recording should be started based on config."""
        try:
            from . import bmar_config
            return (getattr(bmar_config, 'MODE_AUDIO_MONITOR', False) or 
                    getattr(bmar_config, 'MODE_PERIOD', False) or 
                    getattr(bmar_config, 'MODE_EVENT', False))
        except ImportError:
            return False

    def setup_audio_circular_buffer(self):
        """Set up the circular buffer for audio recording."""
        # Calculate buffer size and initialize buffer
        self.buffer_size = int(self.BUFFER_SECONDS * self.PRIMARY_IN_SAMPLERATE)
        self.buffer = np.zeros((self.buffer_size, self.sound_in_chs), dtype=self._dtype)
        self.buffer_index = 0
        self.buffer_wrap = False
        self.blocksize = 8196
        self.buffer_wrap_event.clear()
        
        print(f"\naudio buffer size: {sys.getsizeof(self.buffer)}\n")

    def start_auto_recording(self):
        """Start automatic recording if configured."""
        try:
            from .audio_processing import audio_stream
            
            print("Starting automatic audio recording based on configuration...")
            
            # Start audio stream in a separate thread
            self.audio_thread = threading.Thread(target=audio_stream, args=(self,), daemon=True)
            self.audio_thread.start()
            
            print("Automatic recording started successfully.")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start automatic recording: {e}")
            return False



    def run(self):
        """Main application run loop."""
        try:
            print("\nBMAR Audio Recording System")
            print("="*50)
            
            # Set the keyboard listener to running state
            self.keyboard_listener_running = True
            
            # Start automatic recording if configured
            if self.should_start_auto_recording():
                self.start_auto_recording()
                print("Note: Automatic recording is active based on configuration.")
                print("You can still use manual controls (press 'h' for help).")
            else:
                print("No automatic recording configured. Use 'r' to start manual recording.")
            
            # Start the user interface using the CORRECT function name
            
            # Start background keyboard monitor in a separate thread (for '^' key)
            monitor_thread = threading.Thread(target=background_keyboard_monitor, args=(self,), daemon=True)
            monitor_thread.start()
            
            # Start main keyboard listener (this will block until quit)
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
            
            # Stop recording if active
            if hasattr(self, 'stop_recording_event'):
                self.stop_recording_event.set()
            
            # Stop automatic recording if active
            if hasattr(self, 'stop_auto_recording_event'):
                self.stop_auto_recording_event.set()
            
            # Stop audio stream if active
            if hasattr(self, 'audio_stream') and self.audio_stream:
                try:
                    self.audio_stream.stop()
                    self.audio_stream.close()
                except Exception as e:
                    logging.warning(f"Error stopping audio stream: {e}")
            
            # Wait for audio thread to finish
            if hasattr(self, 'audio_thread') and self.audio_thread.is_alive():
                try:
                    self.audio_thread.join(timeout=5)
                except Exception as e:
                    logging.warning(f"Error waiting for audio thread: {e}")
            
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
        if prefix_newline:
            print("")
        print(text)
        if suffix_newline:
            print("")

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
    sys.exit(run_bmar_application())
