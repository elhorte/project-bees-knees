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
import numpy as np

# Import all our modules
from .bmar_config import *
from .platform_manager import PlatformManager
from .system_utils import setup_logging, setup_signal_handlers
from .file_utils import setup_directories, get_today_dir
from .audio_devices import get_audio_device_config, configure_audio_device_interactive
from .process_manager import stop_all, cleanup
from .user_interface import keyboard_listener, cleanup_ui
from .class_PyAudio import *

class BmarApp:
    """Main BMAR application class."""
    
    def __init__(self):
        """Initialize the BMAR application."""
        
        # Core application state
        self.stop_program = multiprocessing.Array('i', [0])  # Shared stop flag
        self.keyboard_listener_running = True
        self.headless = False  # Interactive mode by default
        
        # Audio configuration
        self.device_index = None
        self.samplerate = 44100  # Will be updated from config
        self.blocksize = 1024    # Will be updated from config
        self.max_file_size_mb = 100  # Will be updated from config
        self.channels = SOUND_IN_CHS  # Load from config
        self.monitor_channel = MONITOR_CH  # Monitor channel from config
        
        # Platform-specific attributes
        self.is_wsl = False
        self.is_macos = False
        self.os_info = ""
        
        # Directory paths
        self.recording_dir = None
        self.today_dir = None
        
        # Audio processing
        self.circular_buffer = None
        self.buffer_pointer = multiprocessing.Array('i', [0])
        
        # Process tracking
        self.active_processes = {}
        
        # Threading events
        self.stop_recording_event = threading.Event()
        self.stop_tod_event = threading.Event()
        self.stop_vu_event = threading.Event()
        self.stop_intercom_event = threading.Event()
        self.stop_fft_periodic_plot_event = threading.Event()
        self.stop_performance_monitor_event = threading.Event()
        self.buffer_wrap_event = threading.Event()
        
        # Terminal state
        self.original_terminal_settings = None
        
        # Platform manager
        self.platform_manager = PlatformManager()
        
        # Initialize logging
        setup_logging()
        logging.info("BMAR Application initializing...")
    
    def initialize(self):
        """Initialize the application components."""
        
        try:
            print("Initializing BMAR...")
            
            # Setup signal handlers
            setup_signal_handlers(self)
            
            # Initialize platform-specific settings
            self.platform_manager.setup_environment()
            
            # Set platform attributes for VU meter compatibility
            self.is_wsl = self.platform_manager.is_wsl()
            self.is_macos = self.platform_manager.is_macos()
            os_info = self.platform_manager.get_os_info()
            self.os_info = f"{os_info['platform']}"
            
            # Setup directories
            self.recording_dir = setup_directories()
            self.today_dir = get_today_dir(self.recording_dir)
            
            print(f"Recording directory: {self.recording_dir}")
            print(f"Today's directory: {self.today_dir}")
            
            # Get audio device configuration with interactive prompts
            if configure_audio_device_interactive(self):
                print(f"Audio device: {self.device_index} at {self.samplerate}Hz ({self.channels} channels)")
            else:
                # Fall back to simple configuration
                device_config = get_audio_device_config()
                if device_config:
                    self.device_index = device_config['device_index']
                    self.samplerate = device_config['samplerate']
                    self.channels = device_config['channels']
                    print(f"Audio device: {self.device_index} at {self.samplerate}Hz ({self.channels} channels)")
                else:
                    raise RuntimeError("No suitable audio device found")
            
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
    
    def run(self):
        """Run the main application loop."""
        
        try:
            if not self.initialize():
                print("Failed to initialize application")
                return 1
            
            print("\nStarting BMAR application...")
            
            # Start keyboard listener thread
            keyboard_thread = threading.Thread(
                target=keyboard_listener,
                args=(self,),
                daemon=True
            )
            keyboard_thread.start()
            
            # Main application loop
            while not self.stop_program[0]:
                try:
                    # Check if keyboard thread is still running
                    if not keyboard_thread.is_alive() and self.keyboard_listener_running:
                        print("Keyboard listener thread stopped unexpectedly")
                        break
                    
                    # Brief sleep to prevent busy waiting
                    time.sleep(0.1)
                    
                except KeyboardInterrupt:
                    print("\nKeyboard interrupt received")
                    break
                except Exception as e:
                    logging.error(f"Main loop error: {e}")
                    time.sleep(1.0)
            
            print("\nShutting down application...")
            return 0
            
        except Exception as e:
            print(f"Application error: {e}")
            logging.error(f"Application error: {e}")
            return 1
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up application resources."""
        
        try:
            print("Cleaning up BMAR application...")
            
            # Stop all processes and threads
            stop_all(self)
            
            # Clean up UI
            cleanup_ui(self)
            
            # Final cleanup
            cleanup(self)
            
        except Exception as e:
            print(f"Cleanup error: {e}")
            logging.error(f"Cleanup error: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle system signals."""
        
        print(f"\nReceived signal {signum}")
        self.stop_program[0] = True
        self.keyboard_listener_running = False
    
    def get_status_summary(self):
        """Get a summary of the current application status."""
        
        status = {
            'running': not self.stop_program[0],
            'device_index': self.device_index,
            'samplerate': self.samplerate,
            'recording_dir': self.recording_dir,
            'today_dir': self.today_dir,
            'active_processes': {}
        }
        
        # Count active processes
        if self.active_processes:
            for key, process in self.active_processes.items():
                if process is not None:
                    status['active_processes'][key] = {
                        'alive': process.is_alive(),
                        'pid': process.pid if process.is_alive() else None
                    }
                else:
                    status['active_processes'][key] = {'alive': False, 'pid': None}
        
        return status
    
    def restart_component(self, component_key):
        """Restart a specific component/process."""
        
        from .process_manager import cleanup_process
        from .user_interface import process_command
        
        try:
            print(f"Restarting component: {component_key}")
            
            # Stop the component
            cleanup_process(self, component_key)
            
            # Brief delay
            time.sleep(0.5)
            
            # Restart the component
            process_command(self, component_key)
            
            print(f"Component {component_key} restarted")
            
        except Exception as e:
            print(f"Error restarting component {component_key}: {e}")
            logging.error(f"Error restarting component {component_key}: {e}")
    
    def update_audio_config(self, device_index=None, samplerate=None):
        """Update audio configuration and restart affected components."""
        
        try:
            restart_needed = False
            
            if device_index is not None and device_index != self.device_index:
                self.device_index = device_index
                restart_needed = True
                print(f"Audio device updated to: {device_index}")
            
            if samplerate is not None and samplerate != self.samplerate:
                self.samplerate = samplerate
                restart_needed = True
                print(f"Sample rate updated to: {samplerate}Hz")
            
            if restart_needed:
                # Restart all audio-related components
                audio_components = ['r', 's', 'o', 't', 'v', 'i']
                for component in audio_components:
                    if (component in self.active_processes and 
                        self.active_processes[component] is not None and
                        self.active_processes[component].is_alive()):
                        self.restart_component(component)
                
                print("Audio configuration updated and components restarted")
            
        except Exception as e:
            print(f"Error updating audio config: {e}")
            logging.error(f"Error updating audio config: {e}")
    
    def get_buffer_stats(self):
        """Get statistics about the circular buffer usage."""
        
        try:
            if self.circular_buffer is None:
                return None
            
            buffer_size = len(self.circular_buffer)
            current_position = self.buffer_pointer[0]
            
            # Calculate buffer usage
            usage_percent = (current_position / buffer_size) * 100
            
            # Get buffer content statistics
            buffer_data = np.frombuffer(self.circular_buffer.get_obj(), dtype=np.float32)
            
            if np.any(buffer_data != 0):
                rms = np.sqrt(np.mean(buffer_data**2))
                peak = np.max(np.abs(buffer_data))
                zero_crossings = len(np.where(np.diff(np.signbit(buffer_data)))[0])
            else:
                rms = peak = zero_crossings = 0
            
            return {
                'size': buffer_size,
                'position': current_position,
                'usage_percent': usage_percent,
                'rms_level': rms,
                'peak_level': peak,
                'zero_crossings': zero_crossings,
                'duration_seconds': buffer_size / self.samplerate
            }
            
        except Exception as e:
            logging.error(f"Error getting buffer stats: {e}")
            return None
    
    def export_configuration(self):
        """Export current configuration to a dictionary."""
        
        config = {
            'audio': {
                'device_index': self.device_index,
                'samplerate': self.samplerate,
                'blocksize': self.blocksize,
                'max_file_size_mb': self.max_file_size_mb
            },
            'directories': {
                'recording_dir': self.recording_dir,
                'today_dir': self.today_dir
            },
            'platform': self.platform_manager.get_platform_info(),
            'buffer': {
                'duration_seconds': 300,  # 5 minutes
                'size_samples': len(self.circular_buffer) if self.circular_buffer else 0
            }
        }
        
        return config
    
    def import_configuration(self, config):
        """Import configuration from a dictionary."""
        
        try:
            # Update audio settings
            audio_config = config.get('audio', {})
            if 'device_index' in audio_config:
                self.device_index = audio_config['device_index']
            if 'samplerate' in audio_config:
                self.samplerate = audio_config['samplerate']
            if 'blocksize' in audio_config:
                self.blocksize = audio_config['blocksize']
            if 'max_file_size_mb' in audio_config:
                self.max_file_size_mb = audio_config['max_file_size_mb']
            
            # Update directories if provided
            dir_config = config.get('directories', {})
            if 'recording_dir' in dir_config:
                self.recording_dir = dir_config['recording_dir']
            if 'today_dir' in dir_config:
                self.today_dir = dir_config['today_dir']
            
            print("Configuration imported successfully")
            
        except Exception as e:
            print(f"Error importing configuration: {e}")
            logging.error(f"Error importing configuration: {e}")

def create_bmar_app():
    """Factory function to create a new BMAR application instance."""
    
    try:
        app = BmarApp()
        return app
        
    except Exception as e:
        print(f"Error creating BMAR application: {e}")
        logging.error(f"Error creating BMAR application: {e}")
        return None

def run_bmar_application():
    """Entry point function to run the BMAR application."""
    
    try:
        # Set multiprocessing start method
        if hasattr(multiprocessing, 'set_start_method'):
            try:
                multiprocessing.set_start_method('spawn', force=True)
            except RuntimeError:
                pass  # Already set
        
        # Create and run application
        app = create_bmar_app()
        if app is None:
            return 1
        
        return app.run()
        
    except Exception as e:
        print(f"Application startup error: {e}")
        logging.error(f"Application startup error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0

if __name__ == "__main__":
    """Allow the module to be run directly for testing."""
    sys.exit(run_bmar_application())
