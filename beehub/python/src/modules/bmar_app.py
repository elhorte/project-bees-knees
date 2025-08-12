"""
BMAR Application Module
Main application class that coordinates all modules and manages the application state.
"""

import logging
import os
import sys
import datetime
import threading
import multiprocessing
import numpy as np
import sounddevice as sd
from collections import deque

from .bmar_config import default_config, get_platform_audio_config, wire_today_dirs
from .platform_manager import PlatformManager
from .audio_devices import find_device_by_config, get_audio_device_config
from .audio_tools import set_global_flac_target_samplerate, save_flac_with_target_sr
from .user_interface import keyboard_listener, cleanup_ui, background_keyboard_monitor

# Optional; keep None if unavailable
try:
    from .file_utils import check_and_create_date_folders  # not required at init
except Exception:
    check_and_create_date_folders = None

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
        # Use float32 internally for buffers/processing; saving handles bit depth separately
        self._dtype = np.int16
        self.blocksize = 1024
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
        
        # VU meter state
        self.vu_level_db = -120.0         # latest raw block dBFS
        self.vu_level_db_smooth = -120.0  # smoothed dBFS for UI
        self._vu_window = deque()         # rolling window of recent dB values
        self._vu_window_len = 0           # target number of blocks in window
        
        # Initialize platform manager
        self.platform_manager = PlatformManager()

        # Use a BMARConfig dataclass instance (no module globals)
        self.config = default_config()

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
            
            # Load audio-related settings from BMAR_config BEFORE initializing audio
            self.PRIMARY_IN_SAMPLERATE = int(getattr(self.config, 'PRIMARY_IN_SAMPLERATE', 48000))
            self.PRIMARY_BITDEPTH = int(getattr(self.config, 'PRIMARY_BITDEPTH', 16))
            self.PRIMARY_SAVE_SAMPLERATE = getattr(self.config, 'PRIMARY_SAVE_SAMPLERATE', None)

            # Preferred input channels from config (used as desired_ch)
            try:
                self.channels = int(getattr(self.config, 'SOUND_IN_CHS', 1))
                self.sound_in_chs = self.channels
            except Exception:
                self.channels = self.sound_in_chs = 1

            # Ensure all FLAC writes honor PRIMARY_SAVE_SAMPLERATE
            set_global_flac_target_samplerate(self.PRIMARY_SAVE_SAMPLERATE)

            # Initialize audio (config is already set on self)
            audio_success = self.initialize_audio_with_fallback()
            if not audio_success:
                logging.error("Failed to initialize audio")
                return False

            # Initialize channel to monitor and default output device from config
            try:
                self.monitor_channel = int(getattr(self.config, 'MONITOR_CH', 0))
            except Exception:
                self.monitor_channel = 0
            try:
                self.output_device_index = int(getattr(self.config, 'SOUND_OUT_ID_DEFAULT', 0))
            except Exception:
                self.output_device_index = None

            # Set up platform-specific directory configuration
            platform_config = get_platform_audio_config(self.platform_manager, self.config)

            # Add platform-specific attributes needed by file_utils
            self.data_drive = platform_config['data_drive']
            self.data_path = platform_config['data_path']
            self.folders = platform_config['folders']

            # Create today's directories and wire them into config and globals
            try:
                self.config, dir_info = wire_today_dirs(self.config)
                # Optional: keep for convenience
                self.recording_dir = str(self.config.PRIMARY_DIRECTORY)
                self.today_dir = str(self.config.PRIMARY_DIRECTORY)
                logging.info("Wired directories (raw/monitor/plots): %s", dir_info)
            except Exception as e:
                logging.warning("Failed to wire today dirs via bmar_config; falling back: %s", e)
                self.setup_basic_directories()

            # Other timing/buffer settings
            self.BUFFER_SECONDS = getattr(self.config, 'BUFFER_SECONDS', 300)

            # Initialize circular buffer if audio recording will be used
            if self.should_start_auto_recording():
                self.setup_audio_circular_buffer()

            # Initialize circular buffer (legacy int16 shared buffer for other uses)
            buffer_duration = 300  # 5 minutes default
            buffer_size = int(self.samplerate * buffer_duration)
            self.circular_buffer = multiprocessing.Array('h', buffer_size)  # int16
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
        """
        Initialize audio input. Honor PRIMARY_IN_SAMPLERATE from config if possible.
        Falls back to device default when the requested rate is not supported.
        """
        configured_name = None
        try:
            configured_name = getattr(self.config, "DEVICE_NAME_FOR_PLATFORM", lambda: None)()
        except Exception:
            configured_name = None

        # Desired params from config (prefer module config first)
        cfg_mod = getattr(self, "config", None)
        desired_rate = int(getattr(cfg_mod, "PRIMARY_IN_SAMPLERATE",
                                   getattr(self, "PRIMARY_IN_SAMPLERATE", 44100)) if cfg_mod else getattr(self, "PRIMARY_IN_SAMPLERATE", 44100))
        desired_ch = int(getattr(cfg_mod, "SOUND_IN_CHS",
                                 getattr(self, "SOUND_IN_CHS", 1)) if cfg_mod else getattr(self, "SOUND_IN_CHS", 1))

        # 1) Select a device (do not trust samplerate/channels from selection)
        try:
            info = find_device_by_config(
                strict=bool(configured_name),
                desired_samplerate=desired_rate,
                desired_channels=desired_ch,
            )
        except Exception as e:
            if configured_name:
                logging.error("Config-based device configuration failed (strict): %s", e)
                return False
            logging.info("Config-based device configuration failed, trying fallback: %s", e)
            info = None

        if not info and not configured_name:
            try:
                info = get_audio_device_config(
                    strict=False,
                    desired_samplerate=desired_rate,
                    desired_channels=desired_ch,
                )
            except Exception as e:
                logging.error("Fallback audio configuration failed: %s", e)
                info = None

        if not info:
            logging.error("Audio initialization error: No suitable audio devices found. Please check your audio hardware and drivers.")
            return False

        # 2) Enforce desired sample rate if the device supports it; else fallback
        idx = int(info["index"])
        self.device_index = idx
        self.channels = desired_ch  # prefer config channels
        effective_rate = desired_rate

        try:
            # Validate requested rate against the device
            sd.check_input_settings(device=idx, samplerate=desired_rate, channels=desired_ch, dtype='int16')
        except Exception as e:
            # Fallback to device default rate when requested is unsupported
            try:
                dev = sd.query_devices(idx)
                dev_default_rate = int(dev.get("default_samplerate") or 0)
            except Exception:
                dev_default_rate = 0
            fallback_rate = dev_default_rate if dev_default_rate > 0 else int(info.get("samplerate", 48000))
            logging.warning("Requested samplerate %d not supported on device %s. Falling back to %d. Error: %s",
                            desired_rate, info.get("name", idx), fallback_rate, e)
            effective_rate = int(fallback_rate)

        # Persist final selection
        self.samplerate = effective_rate
        # Keep legacy and new channel fields in sync for downstream buffer usage
        self.sound_in_chs = int(self.channels)

        # 3) Log final choice using our effective params (not selection defaults)
        try:
            dev = sd.query_devices(idx)
            hostapis = sd.query_hostapis()
            hostapi_name = None
            try:
                hostapi_idx = int(dev.get("hostapi", -1))
                hostapi_name = hostapis[hostapi_idx]["name"] if 0 <= hostapi_idx < len(hostapis) else None
            except Exception:
                hostapi_name = None
            logging.info("Using input device [%d] %s via %s @ %d Hz (%d ch)",
                         idx,
                         dev.get("name", info.get("name", "Unknown")),
                         hostapi_name or info.get("api_name", "Unknown API"),
                         self.samplerate,
                         self.channels)
        except Exception:
            logging.info("Using input device [%d] %s @ %d Hz (%d ch)",
                         idx, info.get("name", "Unknown"), self.samplerate, self.channels)

        return True

    def should_start_auto_recording(self):
        """Check if automatic recording should be started based on config."""
        c = getattr(self, "config", None)
        if not c:
            return False
        return bool(getattr(c, 'MODE_AUDIO_MONITOR', False) or
                    getattr(c, 'MODE_PERIOD', False) or
                    getattr(c, 'MODE_EVENT', False))

    def setup_audio_circular_buffer(self):
        """Set up the circular buffer for audio recording."""
        # Use actual selected samplerate/channels
        self.buffer_size = int(self.BUFFER_SECONDS * int(self.samplerate))
        self.buffer = np.zeros((self.buffer_size, int(self.sound_in_chs)), dtype=np.int16)
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

    def _ensure_vu_window_len(self, block_len: int):
        """
        Ensure the VU window length matches config latency and current block duration.
        Called on first update and whenever block size changes.
        """
        try:
            latency_ms = int(getattr(self.config, "VU_METER_LATENCY_MS", 120))
        except Exception:
            latency_ms = 120
        sr = max(1, int(self.samplerate or 48000))
        block_len = max(1, int(block_len or self.blocksize or 1024))
        block_dt = block_len / float(sr)
        # number of blocks to roughly match latency_ms
        target_len = max(1, int(round((latency_ms / 1000.0) / block_dt)))
        if target_len != self._vu_window_len:
            self._vu_window = deque(maxlen=target_len)
            self._vu_window_len = target_len

    @staticmethod
    def _rms_dbfs(samples: np.ndarray) -> float:
        """Compute RMS in dBFS from floating samples (-1..1)."""
        if samples is None or samples.size == 0:
            return -120.0
        # If int types, convert to float -1..1
        if np.issubdtype(samples.dtype, np.integer):
            info = np.iinfo(samples.dtype)
            x = samples.astype(np.float32) / max(1.0, float(info.max))
        else:
            x = samples.astype(np.float32)
        # Avoid NaN/Inf
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        rms = np.sqrt(np.mean(np.square(x))) if x.size else 0.0
        if rms <= 1e-9:
            return -120.0
        db = 20.0 * np.log10(min(1.0, max(1e-9, float(rms))))
        return float(db)

    def update_vu_from_block(self, block: np.ndarray) -> float:
        """
        Update the VU meter from an audio block and return smoothed dBFS for UI.
        - Averages recent block dB values over VU_METER_LATENCY_MS.
        - Applies exponential dampening using VU_METER_DAMPING.
        """
        # Ensure we know target window length from this block size
        try:
            block_len = block.shape[0] if hasattr(block, "shape") and len(block.shape) > 0 else len(block)
        except Exception:
            block_len = self.blocksize or 1024
        self._ensure_vu_window_len(block_len)

        # Compute block dBFS (mono RMS across channels)
        try:
            if block.ndim == 2 and block.shape[1] > 1:
                # mixdown to mono for VU
                mono = np.mean(block, axis=1)
            else:
                mono = block.reshape(-1)
        except Exception:
            mono = np.asarray(block, dtype=np.float32).reshape(-1)

        current_db = self._rms_dbfs(mono)
        self.vu_level_db = current_db

        # Windowed average for latency
        self._vu_window.append(current_db)
        avg_db = float(np.mean(self._vu_window)) if len(self._vu_window) > 0 else current_db

        # Exponential dampening
        try:
            damping = float(getattr(self.config, "VU_METER_DAMPING", 0.85))
        except Exception:
            damping = 0.85
        damping = min(0.99, max(0.0, damping))
        alpha = 1.0 - damping
        self.vu_level_db_smooth = (damping * self.vu_level_db_smooth) + (alpha * avg_db)
        return self.vu_level_db_smooth

    def vu_percent(self, floor_db: float = -60.0) -> float:
        """
        Convert the current smoothed VU dBFS to 0..1 for UI bars.
        floor_db defines the lowest visible value (e.g., -60 dBFS).
        """
        db = float(self.vu_level_db_smooth)
        if db <= floor_db:
            return 0.0
        if db >= 0.0:
            return 1.0
        return (db - floor_db) / (0.0 - floor_db)

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
            today = datetime.datetime.now().strftime("%Y-%m-%d")
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

    def _save_raw_capture(self, filepath: str, audio_block: np.ndarray, block_sr: int):
        """Save a raw audio capture to file with optional resampling and bit depth conversion."""
        try:
            # Resample and convert bit depth if target settings are defined
            target_sr = getattr(self, "PRIMARY_SAVE_SAMPLERATE",
                                getattr(self.config, "PRIMARY_SAVE_SAMPLERATE", None))
            bitdepth = getattr(self, "PRIMARY_BITDEPTH",
                               getattr(self.config, "PRIMARY_BITDEPTH", 16))
            save_flac_with_target_sr(filepath, audio_block, in_samplerate=block_sr,
                                     target_samplerate=target_sr, bitdepth=bitdepth)
        except Exception as e:
            logging.error(f"Error saving raw capture to {filepath}: {e}")
            raise

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

'''
__init__.py no longer triggers bmar_app at package import time, so importing modules.file_utils doesn’t re-enter bmar_app.
bmar_app imports file_utils in a package-qualified way and doesn’t suppress real import-time errors.
file_utils.py is now complete and importable.
'''
