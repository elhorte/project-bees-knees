"""
BMAR User Interface Module
Handles keyboard input, command processing, and user interaction.
"""

import threading
import time
import logging
import sys
import os
import multiprocessing
import platform
import traceback

# Platform-specific imports for terminal control
WINDOWS_AVAILABLE = False
UNIX_AVAILABLE = False
orig_settings = None
msvcrt = None
termios = None
tty = None
select = None

if platform.system() == "Windows":
    try:
        import msvcrt
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
else:
    try:
        import termios
        import tty
        import select
        UNIX_AVAILABLE = True
        # Save original terminal settings
        if sys.stdin.isatty():
            orig_settings = termios.tcgetattr(sys.stdin)
    except ImportError:
        UNIX_AVAILABLE = False

# Global variable to track the state of the keyboard listener toggle
# Store interactive mode on the app instance instead of using a module-level global
# interactive_mode = True  # removed in favor of app.interactive_mode
toggle_key = '^'

def enable_raw_mode():
    """Enable raw mode for Unix/Linux systems."""
    if platform.system() != "Windows" and UNIX_AVAILABLE and orig_settings:
        tty.setraw(sys.stdin.fileno())

def restore_terminal():
    """Restore original terminal settings for Unix/Linux systems."""
    if platform.system() != "Windows" and UNIX_AVAILABLE and orig_settings:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)

def ensure_app_attributes(app):
    """Ensure app has all required attributes."""
    if not hasattr(app, 'monitor_channel'):
        app.monitor_channel = 0
    if not hasattr(app, 'is_macos'):
        app.is_macos = False
    if not hasattr(app, 'os_info'):
        app.os_info = {}
    if not hasattr(app, 'DEBUG_VERBOSE'):
        app.DEBUG_VERBOSE = False
    # Store interactive keyboard mode on the app to avoid module-level global
    if not hasattr(app, 'interactive_mode'):
        app.interactive_mode = True

def background_keyboard_monitor(app):
    """Background thread to monitor for application state."""
    print("Background keyboard monitor started.")
    
    # Simple monitoring - just sleep and stay alive
    while getattr(app, 'keyboard_listener_running', True):
        time.sleep(1.0)

def keyboard_listener(app):
    """
    Keyboard input listener thread function with toggle functionality.
    In interactive mode: Captures single keystrokes for BMAR commands
    In pass-through mode: Sleeps and doesn't interfere with terminal input
    """
    # Use app.interactive_mode instead of module-level global
    
    # Ensure required attributes exist to avoid AttributeError on first access
    ensure_app_attributes(app)
    
    try:
        print_controls()
        print("\nNote: Press '^' to toggle between BMAR keyboard mode and normal terminal.")
        print("In normal terminal mode, the program continues running in background.")
        
        while app.keyboard_listener_running:
            try:
                if app.interactive_mode:
                    # Interactive mode: Set up terminal for raw mode and capture individual keys
                    if platform.system() != "Windows" and UNIX_AVAILABLE:
                        enable_raw_mode()
                    
                    # Get character input for BMAR commands
                    if platform.system() == "Windows" and WINDOWS_AVAILABLE:
                        # Windows implementation
                        if msvcrt.kbhit():
                            ch = msvcrt.getch()
                            if isinstance(ch, bytes):
                                ch = ch.decode('utf-8', errors='ignore')
                            
                            if ch == toggle_key:
                                app.interactive_mode = False
                                # Restore normal terminal behavior immediately
                                if platform.system() != "Windows" and UNIX_AVAILABLE:
                                    restore_terminal()
                                print("\n[BMAR keyboard mode OFF - Terminal now operates normally]")
                                print("All keystrokes are now visible and functional in the terminal.")
                                print("BMAR processes continue running in background.")
                                print("Press '^' again to return to BMAR keyboard mode.")
                                # Flush output to ensure messages are visible
                                sys.stdout.flush()
                            else:
                                # Process BMAR command
                                process_command(app, ch)
                        else:
                            time.sleep(0.05)  # Small delay to prevent CPU hogging
                    
                    else:
                        # Unix/Linux/macOS implementation  
                        if UNIX_AVAILABLE and select.select([sys.stdin], [], [], 0.1)[0]:
                            ch = sys.stdin.read(1)
                            
                            if ch == toggle_key:
                                app.interactive_mode = False
                                print("\n[BMAR keyboard mode OFF - Terminal now operates normally]")
                                print("All keystrokes are now visible and functional in the terminal.")
                                print("BMAR processes continue running in background.")
                                print("Press '^' again to return to BMAR keyboard mode.")
                                # Restore normal terminal behavior
                                restore_terminal()
                                # Flush output to ensure messages are visible
                                sys.stdout.flush()
                            else:
                                # Process BMAR command
                                process_command(app, ch)
                        else:
                            # No input available, small delay
                            time.sleep(0.05)
                
                else:
                    # Pass-through mode: Don't interfere with terminal input at all
                    # Just sleep and check occasionally if we should return to interactive mode
                    
                    # Ensure terminal is in normal mode
                    if platform.system() != "Windows" and UNIX_AVAILABLE:
                        restore_terminal()
                    
                    # Sleep for a longer period to avoid interfering with terminal
                    time.sleep(0.5)
                    
                    # Check if user wants to return to interactive mode
                    # We'll look for the toggle key in a non-blocking way
                    if platform.system() == "Windows" and WINDOWS_AVAILABLE:
                        if msvcrt.kbhit():
                            ch = msvcrt.getch()
                            if isinstance(ch, bytes):
                                ch = ch.decode('utf-8', errors='ignore')
                            if ch == toggle_key:
                                app.interactive_mode = True
                                print("\n[BMAR keyboard mode ON - Single-key commands active]")
                                print("BMAR single-key commands are now active. Press 'h' for help.")
                                sys.stdout.flush()
                    else:
                        # For Unix systems, we need to be very careful not to interfere
                        # We'll use a very short timeout to check for our toggle key
                        if UNIX_AVAILABLE:
                            ready, _, _ = select.select([sys.stdin], [], [], 0.01)
                            if ready:
                                ch = sys.stdin.read(1)
                                if ch == toggle_key:
                                    app.interactive_mode = True
                                    print("\n[BMAR keyboard mode ON - Single-key commands active]")
                                    print("BMAR single-key commands are now active. Press 'h' for help.")
                                    sys.stdout.flush()
                                # If it's not our toggle key, we unfortunately consumed it
                                # This is a limitation of this approach

            except KeyboardInterrupt:
                print("\nKeyboard interrupt received")
                break
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logging.error("Error in keyboard listener loop: %s", e)
                time.sleep(0.1)

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        print(f"Keyboard listener failed to start: {e}")
        logging.error("Keyboard listener failed to start: %s", e)
    finally:
        # Restore terminal to normal mode
        if platform.system() != "Windows" and UNIX_AVAILABLE:
            restore_terminal()
        print("\nKeyboard listener stopped.")
        print("Terminal restored to normal mode.")

def print_controls():
    """Prints the available controls."""
    print("\nBMAR Controls:")
    print("  'r' - Start/stop recording")
    print("  's' - Spectrogram (one-shot with GUI)")
    print("  'o' - Oscilloscope (10s capture with GUI)")
    print("  't' - Threads (list all)")
    print("  'v' - VU meter (independent, start before intercom for combo mode)")
    print("  'i' - Intercom (audio monitoring)")
    print("  'd' - Current audio device")
    print("  'D' - List detailed audio devices")
    print("  'p' - Performance monitor")
    print("  'P' - Continuous performance monitor")
    print("  'f' - FFT analysis (10s with progress bar)")
    print("  'c' - Configuration")
    print("  'h' - Help")
    print("  'q' - Quit")
    print("  '^' - Toggle between BMAR keyboard mode and normal terminal")
    print("\nReady for commands...")
    print("Note: Press '^' to toggle between BMAR keyboard mode and normal terminal.")

def process_command(app, command):
    """Process a user command."""
    
    # removed unused imports
    
    try:
        # Ensure app has basic attributes for command processing
        if not hasattr(app, 'active_processes'):
            app.active_processes = {}
        if not hasattr(app, 'stop_program'):
            app.stop_program = [False]
        if not hasattr(app, 'keyboard_listener_running'):
            app.keyboard_listener_running = True
            
        if command == 'q' or command == 'Q':
            print("\nQuitting...")
            app.stop_program[0] = True
            app.keyboard_listener_running = False
            
        elif command == 'r' or command == 'R':
            handle_recording_command(app)
            
        elif command == 's' or command == 'S':
            handle_spectrogram_command(app)
            
        elif command == 'o' or command == 'O':
            handle_oscilloscope_command(app)
            
        elif command == 't':
            handle_thread_list_command(app)
            
        elif command == 'v' or command == 'V':
            # Check if intercom is running - if so, suppress VU meter command
            if 'i' in app.active_processes and app.active_processes['i'] is not None:
                if hasattr(app.active_processes['i'], 'is_alive') and app.active_processes['i'].is_alive():
                    print("VU meter command suppressed while intercom is active.\r")
                    print("Stop intercom first ('i') or start VU meter before intercom for combo mode.\r")
                else:
                    handle_vu_meter_command(app)
            else:
                handle_vu_meter_command(app)
            
        elif command == 'i' or command == 'I':
            handle_intercom_command(app)
            
        elif command == 'd':
            print("\nShowing current audio device...\r")
            from .audio_devices import show_current_audio_devices
            show_current_audio_devices(app)
            
        elif command == 'D':  # List all available audio devices
            print("\nShowing all available audio devices...\r")
            from .audio_devices import list_audio_devices_detailed
            list_audio_devices_detailed(app)
            
        elif command == 'p':
            handle_performance_monitor_command(app)
            
        elif command == 'P':
            handle_continuous_performance_monitor_command(app)
            
        elif command == 'f' or command == 'F':
            handle_fft_command(app)
            
        elif command == 'c' or command == 'C':
            handle_configuration_command(app)
            
        elif command == 'h' or command == 'H' or command == '?':
            show_help()
            
        elif command.isdigit():
            # Handle channel switching (1-9)
            handle_channel_switch_command(app, command)
            
        elif command == '^':
            # Toggle is handled directly in keyboard_listener function
            print("Toggle functionality is built into the keyboard listener. This message should not appear.")

        else:
            print(f"Unknown command: '{command}'. Press 'h' for help.\r")  # Added \r
            
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Error processing command '{command}': {e}\r")  # Added \r
        print("Traceback: \r")  # Added \r
        traceback.print_exc()
        logging.error("Error processing command '%s': %s", command, e)

def handle_recording_command(app):
    """Handle recording start/stop command."""
    
    from .process_manager import cleanup_process
    
    try:
        if 'r' in app.active_processes and app.active_processes['r'] is not None:
            if app.active_processes['r'].is_alive():
                print("Stopping recording...\r")  # Added \r
                cleanup_process(app, 'r')
                if hasattr(app, 'stop_recording_event'):
                    app.stop_recording_event.set()
            else:
                print("Starting recording...\r")  # Added \r
                app.active_processes['r'] = None  # Clear dead process
                start_new_recording(app)
        else:
            print("Starting recording...\r")  # Added \r
            start_new_recording(app)
            
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Recording command error: {e}\r")  # Added \r

def start_new_recording(app):
    """Start a new recording session."""
    
    from .process_manager import create_subprocess
    from .audio_processing import recording_worker_thread
    
    try:
        # Reset recording event
        if hasattr(app, 'stop_recording_event'):
            app.stop_recording_event.clear()
        
        # Parameters for recording_worker_thread
        record_period = 300  # 5 minutes per file
        interval = 1.0  # Check interval
        thread_id = 'manual_recording'
        file_format = 'wav'
        target_sample_rate = app.samplerate
        start_tod = None  # No time of day restriction
        end_tod = None
        
        # Create and start recording process
        process = create_subprocess(
            target_function=recording_worker_thread,
            args=(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod, app.stop_recording_event),
            process_key='r',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Recording started (PID: {process.pid})\r")  # Added \r
        
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Error starting recording: {e}\r")  # Added \r

def handle_spectrogram_command(app):
    """Handle spectrogram command."""
    
    from .process_manager import cleanup_process
    
    try:
        if 's' in app.active_processes and app.active_processes['s'] is not None:
            if app.active_processes['s'].is_alive():
                print("Stopping spectrogram...\r")  # Added \r
                cleanup_process(app, 's')
            else:
                print("Starting spectrogram...\r")  # Added \r
                app.active_processes['s'] = None
                start_spectrogram(app)
        else:
            print("Starting spectrogram...\r")  # Added \r
            start_spectrogram(app)
            
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Spectrogram command error: {e}\r")  # Added \r
        traceback.print_exc()

def start_spectrogram(app):
    """Start spectrogram plotting."""
    
    from .process_manager import create_subprocess
    from .plotting import plot_spectrogram
    
    try:
        # Ensure required directory exists
        plots_dir = os.path.join(app.today_dir, 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
            
        # Create spectrogram configuration for one-shot capture
        spectrogram_config = {
            'device_index': app.device_index,
            'samplerate': app.samplerate,
            'channels': app.channels,
            'blocksize': app.blocksize,
            'fft_size': 2048,
            'overlap': 0.75,
            # Allow optional override; otherwise plotting will use SPECTROGRAM_DURATION
            'capture_duration': getattr(app, 'override_spectrogram_duration', None),
            'freq_range': [0, app.samplerate // 2],
            'plots_dir': plots_dir
        }
        
        # Remove None entries so plotting uses config default
        spectrogram_config = {k: v for k, v in spectrogram_config.items() if v is not None}
        
        print(f"Starting spectrogram (device {app.device_index}, {app.samplerate}Hz)\r")  # Added \r
        
        # Create and start spectrogram process
        # Note: This will be a short-lived process that captures, analyzes, and exits
        process = create_subprocess(
            target_function=plot_spectrogram,
            args=(spectrogram_config,),
            process_key='s',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Spectrogram started (PID: {process.pid})\r")  # Added \r
        
        # Note: The process will finish automatically after capturing and displaying
        
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Error starting spectrogram: {e}\r")  # Added \r
        traceback.print_exc()

def handle_oscilloscope_command(app):
    """Handle oscilloscope command."""
    
    from .process_manager import cleanup_process
    
    try:
        if 'o' in app.active_processes and app.active_processes['o'] is not None:
            if app.active_processes['o'].is_alive():
                print("Stopping oscilloscope...\r")
                cleanup_process(app, 'o')
            else:
                print("Starting oscilloscope...\r")
                app.active_processes['o'] = None
                start_oscilloscope(app)
        else:
            print("Starting oscilloscope...\r")
            start_oscilloscope(app)
            
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Oscilloscope command error: {e}\r")
        traceback.print_exc()

def start_oscilloscope(app):
    """Start one-shot oscilloscope plotting."""
    
    from .process_manager import create_subprocess
    from .plotting import plot_oscope
    
    try:
        # Ensure required directory exists
        plots_dir = os.path.join(app.today_dir, 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
            
        # Create oscilloscope configuration for one-shot capture
        oscope_config = {
            'device_index': app.device_index,
            'samplerate': app.samplerate,
            'channels': app.channels,
            'blocksize': getattr(app, 'blocksize', 1024),
            # Use TRACE_DURATION from config as default; allow app.override_trace_duration
            'plot_duration': getattr(app, 'override_trace_duration', None),
            'plots_dir': plots_dir,
            'monitor_channel': getattr(app, 'monitor_channel', 0)
        }
        
        # Remove None values to allow plotting to fall back to TRACE_DURATION
        oscope_config = {k: v for k, v in oscope_config.items() if v is not None}
        
        print(f"Starting oscilloscope (device {app.device_index}, {app.samplerate}Hz)\r")
        
        # Create and start oscilloscope process
        process = create_subprocess(
            target_function=plot_oscope,
            args=(oscope_config,),
            process_key='o',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Oscilloscope started (PID: {process.pid})\r")
        
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Error starting oscilloscope: {e}\r")
        traceback.print_exc()

def handle_vu_meter_command(app):
    """Handle VU meter command."""
    
    from .process_manager import cleanup_process
    
    try:
        # Check if VU meter process exists and is running
        if 'v' in app.active_processes and app.active_processes['v'] is not None:
            vu_process = app.active_processes['v']
            
            # Check if it's actually alive
            if hasattr(vu_process, 'is_alive') and vu_process.is_alive():
                print("Stopping VU meter...\r")
                
                # Set stop event for the VU meter
                if hasattr(app, 'vu_stop_event'):
                    app.vu_stop_event.set()
                
                # Give the VU meter thread time to clean up its display
                time.sleep(0.2)
                
                # Clean up the process reference
                cleanup_process(app, 'v')
                
                # Clear any remaining VU meter display artifacts
                print("\r" + " " * 80 + "\r", end="", flush=True)
                print("VU meter stopped.")
                
            else:
                # Thread is dead, clean up and start new one
                app.active_processes['v'] = None
                print("Starting VU meter...\r")
                start_vu_meter(app)
        else:
            # No existing VU meter, start new one
            print("Starting VU meter...\r")
            start_vu_meter(app)
            
    except (RuntimeError, OSError, ValueError) as e:
        print(f"VU meter command error: {e}\r")
        # Clean up any artifacts and reset
        print("\r" + " " * 80 + "\r", end="", flush=True)
        app.active_processes['v'] = None

def start_vu_meter(app):
    """Start VU meter using threading instead of multiprocessing."""
    
    from .audio_tools import vu_meter
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Clean up any existing VU meter thread and stop event
        if hasattr(app, 'vu_stop_event'):
            app.vu_stop_event.set()  # Stop any existing VU meter
            time.sleep(0.1)  # Brief pause for cleanup
        
        # Create a fresh stop event for the VU meter
        app.vu_stop_event = threading.Event()
        
        # Create VU meter configuration
        vu_config = {
            'device_index': app.device_index,
            'samplerate': app.samplerate,
            'channels': app.channels,
            'blocksize': getattr(app, 'blocksize', 1024),
            'monitor_channel': app.monitor_channel,
            'sound_in_id': app.device_index,
            'sound_in_chs': app.channels,
            'PRIMARY_IN_SAMPLERATE': app.samplerate,
            'is_macos': getattr(app, 'is_macos', False),
            'os_info': getattr(app, 'os_info', {}),
            'DEBUG_VERBOSE': getattr(app, 'DEBUG_VERBOSE', False)
        }
        
        # Inform which channel will be monitored
        print(f"Now monitoring channel: {app.monitor_channel+1} (of {app.channels})\r")
        
        # Create and start VU meter thread
        vu_thread = threading.Thread(
            target=vu_meter,
            args=(vu_config, app.vu_stop_event),
            daemon=True,
            name=f"VU-Meter-{app.device_index}"
        )
        
        # Store the thread in active_processes
        app.active_processes['v'] = vu_thread
        
        # Start the thread
        vu_thread.start()
        
        # Brief delay to let the thread initialize
        time.sleep(0.1)
        
        # Verify thread started successfully
        if not vu_thread.is_alive():
            print("Warning: VU meter thread failed to start")
            app.active_processes['v'] = None
        
    except (RuntimeError, OSError, ValueError) as e:
        print(f"Error starting VU meter: {e}\r")
        # Clean up display and reset state
        print("\r" + " " * 80 + "\r", end="", flush=True)
        app.active_processes['v'] = None
        traceback.print_exc()

def handle_intercom_command(app):
    """Handle intercom command."""
    
    from .process_manager import cleanup_process
    
    try:
        # Check if VU meter is active to decide whether to print status
        vu_thread = None
        if hasattr(app, 'active_processes'):
            vu_thread = app.active_processes.get('v')
        vu_meter_active = bool(vu_thread and getattr(vu_thread, 'is_alive', lambda: False)())
        
        if 'i' in app.active_processes and app.active_processes['i'] is not None:
            if app.active_processes['i'].is_alive():
                if not vu_meter_active:
                    print("Stopping intercom...\r")  # Added \r
                cleanup_process(app, 'i')
            else:
                if not vu_meter_active:
                    print("Starting intercom...\r")  # Added \r
                app.active_processes['i'] = None
                start_intercom(app)
        else:
            if not vu_meter_active:
                print("Starting intercom...\r")  # Added \r
            start_intercom(app)
            
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        # Compute VU status safely without broad excepts
        vu_thread = None
        if hasattr(app, 'active_processes'):
            vu_thread = app.active_processes.get('v')
        vu_meter_active = bool(vu_thread and getattr(vu_thread, 'is_alive', lambda: False)())
        
        if not vu_meter_active:
            print(f"Intercom command error: {e}\r")  # Added \r

def start_intercom(app):
    """Start intercom monitoring."""
    
    from .process_manager import create_subprocess
    from .audio_tools import intercom_m
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Check if VU meter is active
        vu_thread = None
        if hasattr(app, 'active_processes'):
            vu_thread = app.active_processes.get('v')
        vu_meter_active = bool(vu_thread and getattr(vu_thread, 'is_alive', lambda: False)())
        
        # Create intercom configuration
        # Prefer explicit INTERCOM_SAMPLERATE, then SOUND_OUT_SR_DEFAULT, else fallback 48000
        intercom_sr = getattr(app.config, 'INTERCOM_SAMPLERATE', None)
        if not intercom_sr:
            intercom_sr = getattr(app.config, 'SOUND_OUT_SR_DEFAULT', 48000)
        
        # Resolve output device: prefer app.output_device_index, else config default
        out_dev_idx = getattr(app, 'output_device_index', None)
        if out_dev_idx is None:
            out_dev_idx = getattr(app.config, 'SOUND_OUT_ID_DEFAULT', None)
        
        # Decide if buffer path is available (same process memory)
        buffer_available = getattr(app, 'buffer', None) is not None
        
        intercom_config = {
            'output_device': out_dev_idx,
            'samplerate': int(intercom_sr),
            'channels': app.channels,
            'blocksize': app.blocksize,
            'gain': 1.0,
            'monitor_channel': app.monitor_channel,
            'bit_depth': getattr(app, 'bit_depth', 16),
            'vu_meter_active': vu_meter_active
        }
        
        # For subprocess path (no buffer), include input device; for thread path, include app
        if not buffer_available:
            intercom_config['input_device'] = app.device_index
        else:
            intercom_config['app'] = app  # safe only in-thread
        
        # Only print status if VU meter is not active to avoid interfering with display
        if not vu_meter_active:
            print(f"Starting intercom (device {intercom_config['output_device']}, {intercom_config['samplerate']}Hz)\r")
        
        # Start as thread if using buffer (needs in-process memory); else use subprocess
        if buffer_available:
            th = threading.Thread(target=intercom_m, args=(intercom_config,), daemon=True)
            th.start()
            app.active_processes['i'] = th
            if not vu_meter_active:
                print("Intercom started (thread)\r")
        else:
            process = create_subprocess(
                target_function=intercom_m,
                args=(intercom_config,),
                process_key='i',
                app=app,
                daemon=True
            )
            process.start()
            if not vu_meter_active:
                print(f"Intercom started (PID: {process.pid})\r")
        
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Error starting intercom: {e}\r")
        traceback.print_exc()

def handle_performance_monitor_command(app):
    """Handle performance monitor command."""
    
    try:
        from .process_manager import list_active_processes
        
        print("\nPerformance Monitor:\r")  # Added \r
        print("-" * 40 + "\r")  # Added \r
        
        # Show active processes
        list_active_processes(app)
        
        # Show system stats
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        print("\nSystem Resources:\r")  # Added \r
        print(f"  CPU Usage: {cpu_percent:.1f}%\r")  # Added \r
        print(f"  Memory Usage: {memory.percent:.1f}% ({memory.used//1024//1024}MB used)\r")  # Added \r
        print(f"  Available Memory: {memory.available//1024//1024}MB\r")  # Added \r
        
        # Show audio buffer status
        if hasattr(app, 'circular_buffer') and app.circular_buffer is not None:
            buffer_usage = (app.buffer_pointer[0] / len(app.circular_buffer)) * 100
            print(f"  Audio Buffer Usage: {buffer_usage:.1f}%\r")  # Added \r
        
        print("-" * 40 + "\r")  # Added \r
        
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Performance monitor error: {e}\r")  # Added \r

def handle_configuration_command(app):
    """Handle configuration display command."""
    
    try:
        from .bmar_config import get_platform_config
        
        print("\nCurrent Configuration:\r")  # Added \r
        print("-" * 50 + "\r")  # Added \r
        print(f"Audio Device: {app.device_index}\r")  # Added \r
        print(f"Sample Rate: {app.samplerate} Hz\r")  # Added \r
        print(f"Block Size: {app.blocksize}\r")  # Added \r
        print("Channels: 1 (mono)\r")  # Fixed syntax and added \r
        print(f"Max File Size: {app.max_file_size_mb} MB\r")  # Added \r
        print(f"Recording Directory: {app.recording_dir}\r")  # Added \r
        print(f"Today's Directory: {app.today_dir}\r")  # Added \r
        
        # Platform-specific info
        platform_config = get_platform_config()
        print(f"\nPlatform: {platform_config['name']}\r")  # Added \r
        
        # Buffer info
        if hasattr(app, 'circular_buffer') and app.circular_buffer is not None:
            buffer_size_mb = len(app.circular_buffer) * 4 / (1024 * 1024)  # 4 bytes per float32
            print(f"\nBuffer Size: {buffer_size_mb:.1f} MB\r")  # Added \r
            print(f"Buffer Duration: {len(app.circular_buffer) / app.samplerate:.1f} seconds\r")  # Added \r
        
        print("-" * 50 + "\r")  # Added \r
        
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Configuration display error: {e}\r")  # Added \r

def handle_continuous_performance_monitor_command(app):
    """Handle continuous performance monitor command (uppercase P)."""
    
    from .process_manager import cleanup_process
    
    try:
        if 'P' in app.active_processes and app.active_processes['P'] is not None:
            if app.active_processes['P'].is_alive():
                print("Stopping continuous performance monitor...\r")  # Added \r
                
                # Signal the process to stop using the shared dictionary
                if hasattr(app, 'performance_monitor_stop_dict'):
                    app.performance_monitor_stop_dict['stop'] = True
                
                cleanup_process(app, 'P')
            else:
                print("Starting continuous performance monitor...\r")  # Added \r
                app.active_processes['P'] = None  # Clear dead process
                start_continuous_performance_monitor(app)
        else:
            print("Starting continuous performance monitor...\r")  # Added \r
            start_continuous_performance_monitor(app)
            
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Continuous performance monitor command error: {e}\r")  # Added \r
        traceback.print_exc()

def start_continuous_performance_monitor(app):
    """Start continuous performance monitoring."""
    
    from .process_manager import create_subprocess
    from .system_utils import monitor_system_performance_continuous_standalone

    
    try:
        # Create a shared dictionary to control the stop signal
        manager = multiprocessing.Manager()
        stop_event_dict = manager.dict()
        stop_event_dict['stop'] = False
        
        # Store the stop control in app for later cleanup
        app.performance_monitor_stop_dict = stop_event_dict
        
        # Create and start continuous performance monitor process
        process = create_subprocess(
            target_function=monitor_system_performance_continuous_standalone,
            args=(stop_event_dict,),
            process_key='P',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Continuous performance monitor started (PID: {process.pid})\r")  # Added \r
        
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Error starting continuous performance monitor: {e}\r")  # Added \r
        traceback.print_exc()

def handle_channel_switch_command(app, command):
    """Handle channel switching command (1-9)."""
    
    try:
        # Ensure app has required attributes
        ensure_app_attributes(app)
        
        # Convert to zero-based channel index
        key_int = int(command) - 1
        
        # Validate channel number is within range
        if key_int < 0 or key_int >= app.channels:
            print(f"\nInvalid channel selection: Device has only {app.channels} channel(s) (1-{app.channels})\r")  # Added \r
            return
            
        # Update monitor channel
        app.monitor_channel = key_int
        print(f"\nNow monitoring channel: {app.monitor_channel+1} (of {app.channels})\r")  # Added \r
        
        # Restart VU meter if running
        if hasattr(app, 'active_processes') and 'v' in app.active_processes and app.active_processes['v'] is not None:
            if app.active_processes['v'].is_alive():
                print(f"Restarting VU meter on channel: {app.monitor_channel+1}\r")  # Added \r
                
                try:
                    # Stop current VU meter thread cleanly
                    from .process_manager import cleanup_process
                    cleanup_process(app, 'v')
                    
                    # Start VU meter with new channel
                    time.sleep(0.1)
                    start_vu_meter(app)
                except (RuntimeError, OSError, ValueError) as e:
                    print(f"Error restarting VU meter: {e}\r")  # Added \r
        
        # Handle intercom channel change if running
        if hasattr(app, 'active_processes') and 'i' in app.active_processes and app.active_processes['i'] is not None:
            if app.active_processes['i'].is_alive():
                print(f"Channel change for intercom on channel: {app.monitor_channel+1}\r")  # Added \r
                
    except ValueError:
        print(f"Invalid channel number: {command}\r")  # Added \r
    except (RuntimeError, OSError) as e:
        print(f"Channel switch error: {e}\r")  # Added \r
        traceback.print_exc()
        logging.error("Channel switch error: %s", e)

def cleanup_ui(app):
    """Clean up user interface resources."""
    
    try:
        # Stop keyboard listener
        app.keyboard_listener_running = False
        
        # Restore terminal settings
        from .system_utils import restore_terminal_settings
        if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
            restore_terminal_settings(app, app.original_terminal_settings)
        
        print("\nUser interface cleanup completed.\r")  # Added \r
        
    except (RuntimeError, OSError) as e:
        logging.error("UI cleanup error: %s", e)

def handle_thread_list_command(app):
    """Handle thread listing command."""
    
    from .process_manager import list_active_processes
    
    try:
        print("\nActive Threads:\r")  # Added \r
        print("=" * 40 + "\r")  # Added \r
        
        # List all active threads with details
        threads = threading.enumerate()
        if len(threads) > 0:
            for i, thread in enumerate(threads):
                status = "Alive" if thread.is_alive() else "Dead"
                daemon_status = " (Daemon)" if thread.daemon else ""
                print(f"  [{i+1}] {thread.name} - ID: {thread.ident} - {status}{daemon_status}\r")
        else:
            print("  No active threads found\r")
        
        print("-" * 40 + "\r")
        
        # Also show active processes for comparison
        print("Active Processes:\r")
        print("-" * 40 + "\r")
        list_active_processes(app)
        print("-" * 40 + "\r")  # Added \r
        
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Error listing threads: {e}\r")  # Added \r
        traceback.print_exc()
        logging.error("Error listing threads: %s", e)

def show_help():
    """Display help information with proper line endings for all platforms."""
    
    # Clear any lingering progress indicators or status messages
    print("\r" + " " * 120 + "\r", end="", flush=True)  # Clear wider area
    print()  # Add a clean newline to separate from previous output
    
    # Remove ALL \r characters - use normal print() statements
    print("BMAR (Bioacoustic Monitoring and Recording) Help")
    print("============================================================")
    print()
    print("Commands:\r")
    print("r - Recording:     Start/stop audio recording\r")
    print("s - Spectrogram:   One-shot frequency analysis with GUI window\r")
    print("o - Oscilloscope:  10-second waveform capture with GUI window\r")
    print("t - Threads:       List all currently running threads\r")
    print("v - VU Meter:      Audio level monitoring\r")
    print("i - Intercom:      Audio monitoring of remote microphones\r")
    print("d - Current Device: Show currently selected audio device\r")
    print("D - All Devices:    List all available audio devices with details\r")
    print("p - Performance:   System performance monitor (once)\r")
    print("P - Performance:   Continuous system performance monitor\r")
    print("f - FFT:           Show frequency analysis plot\r")
    print("c - Configuration: Display current settings\r")
    print("h - Help:          This help message\r")
    print("q - Quit:          Exit the application\r")
    print("^ - Toggle:        Toggle between BMAR keyboard mode and normal terminal\r")
    print()
    print("1-9 - Channel:     Switch monitoring channel (while VU/Intercom active)")
    print()
    print("Tips:")
    print("- Press any command key to toggle that function on/off")
    print("- Multiple functions can run simultaneously")
    print("- Files are automatically organized by date")
    print("- Use 'p' for one-time performance check, 'P' for continuous monitoring")
    print("- Use 'd' for current device info, 'D' for all available devices")
    print("- Press 1-9 to switch audio channel while VU meter or Intercom is running")
    print("============================================================")
    print()  # Add final newline for clean separation

def start_fft_analysis(app):
    """Start one-shot FFT analysis."""

    from .process_manager import create_subprocess
    from .plotting import plot_fft
    
    try:
        # Ensure required directory exists
        plots_dir = os.path.join(app.today_dir, 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
            
        # Create FFT configuration for one-shot analysis
        fft_config = {
            'device_index': app.device_index,
            'samplerate': app.samplerate,
            'channels': app.channels,
            'blocksize': app.blocksize,
            'plots_dir': plots_dir,
            'monitor_channel': getattr(app, 'monitor_channel', 0),
            # Optional per-run override
            'capture_duration': getattr(app, 'override_fft_duration', None)
        }
        
        # Remove None so plotting uses config default
        fft_config = {k: v for k, v in fft_config.items() if v is not None}
        
        print(f"Starting FFT analysis (device {app.device_index}, {app.samplerate}Hz)\r")
        print(f"  Channel: {app.monitor_channel + 1} of {app.channels}\r")
        
        # Create and start FFT process
        process = create_subprocess(
            target_function=plot_fft,
            args=(fft_config,),
            process_key='f',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"FFT analysis started (PID: {process.pid})\r")
        
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"Error starting FFT analysis: {e}\r")
        traceback.print_exc()

def handle_fft_command(app):
    """Handle FFT command."""
    
    from .process_manager import cleanup_process
    
    try:
        if 'f' in app.active_processes and app.active_processes['f'] is not None:
            if app.active_processes['f'].is_alive():
                print("Stopping FFT analysis...\r")
                cleanup_process(app, 'f')
            else:
                print("Starting FFT analysis...\r")
                app.active_processes['f'] = None
                start_fft_analysis(app)
        else:
            print("Starting FFT analysis...\r")
            start_fft_analysis(app)
            
    except (RuntimeError, OSError, ValueError) as e:  # noqa: BLE001
        print(f"FFT command error: {e}\r")
        traceback.print_exc()
