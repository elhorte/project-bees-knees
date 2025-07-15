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

def keyboard_listener(app):
    """Keyboard input listener thread function."""
    
    # Platform-specific imports
    from .system_utils import get_key, setup_terminal_for_input
    
    try:
        print("\nBMAR Controls:")
        print("  'r' - Start/stop recording")
        print("  's' - Spectrogram (one-shot with GUI)")
        print("  'o' - Oscilloscope (10s capture with GUI)")
        print("  't' - Threads (list all)")
        print("  'v' - VU meter")
        print("  'i' - Intercom")
        print("  'd' - Current audio device")
        print("  'D' - List detailed audio devices")
        print("  'p' - Performance monitor")
        print("  'P' - Continuous performance monitor")
        print("  'f' - FFT analysis (10s with progress bar)")
        print("  'c' - Configuration")
        print("  'h' - Help")
        print("  'q' - Quit")
        print("\nReady for commands...")
        
        # Setup terminal for character input
        setup_terminal_for_input(app)
        
        while app.keyboard_listener_running:
            try:
                # Get single character input
                key = get_key()
                
                if key and app.keyboard_listener_running:
                    # Process the command (preserve case for D vs d)
                    process_command(app, key)
                    
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received")
                break
            except Exception as e:
                logging.error(f"Error in keyboard listener: {e}")
                time.sleep(0.1)
                
    except Exception as e:
        print(f"Keyboard listener error: {e}")
        logging.error(f"Keyboard listener error: {e}")
    
    print("Keyboard listener stopped")

def process_command(app, command):
    """Process a user command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_devices import list_audio_devices_detailed
    
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
            
        elif command == 't' or command == 'T':
            handle_thread_list_command(app)
            
        elif command == 'v' or command == 'V':
            handle_vu_meter_command(app)
            
        elif command == 'i' or command == 'I':
            handle_intercom_command(app)
            
        elif command == 'd':
            print("\nShowing current audio device...")
            from .audio_devices import show_current_audio_devices
            show_current_audio_devices(app)
            
        elif command == 'D':
            handle_detailed_device_list_command(app)
            
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
            
        elif command == 'l' or command == 'L':
            handle_thread_list_command(app)
            
        else:
            print(f"Unknown command: '{command}'. Press 'h' for help.")
            
    except Exception as e:
        print(f"Error processing command '{command}': {e}")
        import traceback
        print(f"Traceback: ")
        traceback.print_exc()
        logging.error(f"Error processing command '{command}': {e}")

def handle_recording_command(app):
    """Handle recording start/stop command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_processing import recording_worker_thread
    
    try:
        if 'r' in app.active_processes and app.active_processes['r'] is not None:
            if app.active_processes['r'].is_alive():
                print("Stopping recording...")
                cleanup_process(app, 'r')
                if hasattr(app, 'stop_recording_event'):
                    app.stop_recording_event.set()
            else:
                print("Starting recording...")
                app.active_processes['r'] = None  # Clear dead process
                start_new_recording(app)
        else:
            print("Starting recording...")
            start_new_recording(app)
            
    except Exception as e:
        print(f"Recording command error: {e}")

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
            args=(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod),
            process_key='r',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Recording started (PID: {process.pid})")
        
    except Exception as e:
        print(f"Error starting recording: {e}")

def handle_spectrogram_command(app):
    """Handle spectrogram command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import plot_spectrogram
    
    try:
        if 's' in app.active_processes and app.active_processes['s'] is not None:
            if app.active_processes['s'].is_alive():
                print("Stopping spectrogram...")
                cleanup_process(app, 's')
            else:
                print("Starting spectrogram...")
                app.active_processes['s'] = None
                start_spectrogram(app)
        else:
            print("Starting spectrogram...")
            start_spectrogram(app)
            
    except Exception as e:
        print(f"Spectrogram command error: {e}")
        import traceback
        traceback.print_exc()

def start_spectrogram(app):
    """Start one-shot spectrogram plotting."""
    
    from .process_manager import create_subprocess
    from .plotting import plot_spectrogram
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
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
            'capture_duration': 5.0,  # Capture 5 seconds of audio
            'freq_range': [0, app.samplerate // 2],
            'plots_dir': plots_dir
        }
        
        print(f"Starting one-shot spectrogram (device {app.device_index}, {app.samplerate}Hz)")
        
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
        print(f"Spectrogram started (PID: {process.pid})")
        
        # Note: The process will finish automatically after capturing and displaying
        
    except Exception as e:
        print(f"Error starting spectrogram: {e}")
        import traceback
        traceback.print_exc()

def handle_oscilloscope_command(app):
    """Handle oscilloscope command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import plot_oscope
    from .audio_devices import ensure_valid_device_for_operation
    
    try:
        if 'o' in app.active_processes and app.active_processes['o'] is not None:
            if app.active_processes['o'].is_alive():
                print("Stopping oscilloscope...")
                cleanup_process(app, 'o')
            else:
                print("Starting oscilloscope...")
                app.active_processes['o'] = None
                start_oscilloscope(app)
        else:
            print("Starting oscilloscope...")
            start_oscilloscope(app)
            
    except Exception as e:
        print(f"Oscilloscope command error: {e}")
        import traceback
        traceback.print_exc()

def start_oscilloscope(app):
    """Start one-shot oscilloscope plotting."""
    
    from .process_manager import create_subprocess
    from .plotting import plot_oscope
    from .audio_devices import ensure_valid_device_for_operation
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Ensure we have a valid audio device for the oscilloscope
        audio_config = ensure_valid_device_for_operation(app, "oscilloscope")
        if audio_config is None:
            print("Cannot start oscilloscope - no valid audio device available")
            return
        
        # Use the validated configuration
        device_index = audio_config['device_id']
        samplerate = audio_config['sample_rate']
        channels = audio_config['channels']
        
        # Ensure required directory exists
        plots_dir = os.path.join(app.today_dir, 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
            
        # Create oscilloscope configuration for one-shot capture
        oscope_config = {
            'device_index': device_index,  # Use validated device ID
            'samplerate': samplerate,
            'channels': channels,
            'blocksize': getattr(app, 'blocksize', 1024),
            'plot_duration': 10.0,  # Capture 10 seconds of audio
            'plots_dir': plots_dir
        }
        
        print(f"Starting one-shot oscilloscope (device {device_index}, {samplerate}Hz)")
        
        # Create and start oscilloscope process
        # Note: This will be a short-lived process that captures, plots, and exits
        process = create_subprocess(
            target_function=plot_oscope,
            args=(oscope_config,),
            process_key='o',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Oscilloscope started (PID: {process.pid})")
        
        # Note: The process will finish automatically after capturing and displaying
        
    except Exception as e:
        print(f"Error starting oscilloscope: {e}")
        import traceback
        traceback.print_exc()

def handle_trigger_command(app):
    """Handle trigger plotting command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import trigger
    
    try:
        if 't' in app.active_processes and app.active_processes['t'] is not None:
            if app.active_processes['t'].is_alive():
                print("Stopping trigger plotting...")
                cleanup_process(app, 't')
            else:
                print("Starting trigger plotting...")
                app.active_processes['t'] = None
                start_trigger_plotting(app)
        else:
            print("Starting trigger plotting...")
            start_trigger_plotting(app)
            
    except Exception as e:
        print(f"Trigger command error: {e}")

def start_trigger_plotting(app):
    """Start trigger plotting."""
    
    from .process_manager import create_subprocess
    from .plotting import trigger
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Ensure required directory exists
        plots_dir = os.path.join(app.today_dir, 'plots')
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
            
        # Create trigger configuration
        trigger_config = {
            'device_index': app.device_index,
            'samplerate': app.samplerate,
            'channels': app.channels,
            'blocksize': app.blocksize,
            'trigger_level': 0.1,
            'trigger_mode': 'rising',
            'pre_trigger_samples': 1024,
            'post_trigger_samples': 2048,
            'plots_dir': plots_dir
        }
        
        print(f"Starting trigger plotting (device {app.device_index}, {app.samplerate}Hz)")
        
        # Create and start trigger process
        process = create_subprocess(
            target_function=trigger,
            args=(trigger_config,),
            process_key='t',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Trigger plotting started (PID: {process.pid})")
        
    except Exception as e:
        print(f"Error starting trigger plotting: {e}")
        import traceback
        traceback.print_exc()

def handle_vu_meter_command(app):
    """Handle VU meter command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_tools import vu_meter
    
    try:
        if 'v' in app.active_processes and app.active_processes['v'] is not None:
            if app.active_processes['v'].is_alive():
                print("Stopping VU meter...")
                cleanup_process(app, 'v')
            else:
                print("Starting VU meter...")
                app.active_processes['v'] = None
                start_vu_meter(app)
        else:
            print("Starting VU meter...")
            start_vu_meter(app)
            
    except Exception as e:
        print(f"VU meter command error: {e}")

def start_vu_meter(app):
    """Start VU meter."""
    
    from .process_manager import create_subprocess
    from .audio_tools import vu_meter
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Create VU meter configuration to match original BMAR_class.py format
        vu_config = {
            'sound_in_id': app.device_index,
            'sound_in_chs': app.channels,
            'monitor_channel': app.monitor_channel,
            'PRIMARY_IN_SAMPLERATE': app.samplerate,
            'is_wsl': app.is_wsl,
            'is_macos': app.is_macos,
            'os_info': app.os_info,
            'DEBUG_VERBOSE': app.DEBUG_VERBOSE
        }
        
        print(f"Starting VU meter on channel {app.monitor_channel + 1} of {app.channels}")
        
        # Create and start VU meter process
        process = create_subprocess(
            target_function=vu_meter,
            args=(vu_config,),
            process_key='v',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"VU meter started (PID: {process.pid})")
        
    except Exception as e:
        print(f"Error starting VU meter: {e}")
        import traceback
        traceback.print_exc()

def handle_intercom_command(app):
    """Handle intercom command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_tools import intercom_m
    
    try:
        if 'i' in app.active_processes and app.active_processes['i'] is not None:
            if app.active_processes['i'].is_alive():
                print("Stopping intercom...")
                cleanup_process(app, 'i')
            else:
                print("Starting intercom...")
                app.active_processes['i'] = None
                start_intercom(app)
        else:
            print("Starting intercom...")
            start_intercom(app)
            
    except Exception as e:
        print(f"Intercom command error: {e}")

def start_intercom(app):
    """Start intercom monitoring."""
    
    from .process_manager import create_subprocess
    from .audio_tools import intercom_m
    from .bmar_config import SOUND_IN_CHS, MONITOR_CH
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Use SOUND_IN_CHS from config instead of app.channels to ensure correct channel count
        input_channels = SOUND_IN_CHS if SOUND_IN_CHS > 0 else 1
        
        # Validate and set monitor channel
        monitor_channel = MONITOR_CH if MONITOR_CH < input_channels else 0
        
        # Create intercom configuration
        intercom_config = {
            'input_device': app.device_index,
            'output_device': app.device_index,  # Use same device for loopback
            'samplerate': app.samplerate,
            'channels': input_channels,  # Use SOUND_IN_CHS from config
            'blocksize': app.blocksize,
            'gain': 1.0,
            'monitor_channel': monitor_channel
        }
        
        print(f"Starting intercom (device {app.device_index}, {app.samplerate}Hz, {input_channels} channels)")
        
        # Create and start intercom process
        process = create_subprocess(
            target_function=intercom_m,
            args=(intercom_config,),
            process_key='i',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Intercom started (PID: {process.pid})")
        
    except Exception as e:
        print(f"Error starting intercom: {e}")
        import traceback
        traceback.print_exc()

def handle_performance_monitor_command(app):
    """Handle performance monitor command."""
    
    try:
        from .process_manager import list_active_processes
        
        print("\nPerformance Monitor:")
        print("-" * 40)
        
        # Show active processes
        list_active_processes(app)
        
        # Show system stats
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        print(f"\nSystem Resources:")
        print(f"  CPU Usage: {cpu_percent:.1f}%")
        print(f"  Memory Usage: {memory.percent:.1f}% ({memory.used//1024//1024}MB used)")
        print(f"  Available Memory: {memory.available//1024//1024}MB")
        
        # Show audio buffer status
        if hasattr(app, 'circular_buffer') and app.circular_buffer is not None:
            buffer_usage = (app.buffer_pointer[0] / len(app.circular_buffer)) * 100
            print(f"  Audio Buffer Usage: {buffer_usage:.1f}%")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"Performance monitor error: {e}")

def handle_file_browser_command(app):
    """Handle file browser command."""
    
    try:
        from .file_utils import list_recent_files
        
        print(f"\nFile Browser - {app.today_dir}")
        print("-" * 60)
        
        # List files in today's directory
        if os.path.exists(app.today_dir):
            recent_files = list_recent_files(app.today_dir, limit=10)
            
            if recent_files:
                print("Recent files:")
                for i, (filepath, size, mtime) in enumerate(recent_files, 1):
                    filename = os.path.basename(filepath)
                    size_mb = size / (1024 * 1024)
                    time_str = time.strftime("%H:%M:%S", time.localtime(mtime))
                    print(f"  {i:2d}. {filename:<30} {size_mb:6.1f}MB {time_str}")
            else:
                print("No files found in today's directory")
        else:
            print("Today's directory does not exist yet")
        
        # Show directory structure
        print(f"\nDirectory structure:")
        print(f"  Recording dir: {app.recording_dir}")
        print(f"  Today's dir:   {app.today_dir}")
        
        plots_dir = os.path.join(app.today_dir, 'plots')
        if os.path.exists(plots_dir):
            plot_count = len([f for f in os.listdir(plots_dir) if f.endswith('.png')])
            print(f"  Plots dir:     {plots_dir} ({plot_count} plots)")
        
        print("-" * 60)
        
    except Exception as e:
        print(f"File browser error: {e}")

def handle_configuration_command(app):
    """Handle configuration display command."""
    
    try:
        from .bmar_config import get_platform_config
        
        print("\nCurrent Configuration:")
        print("-" * 50)
        print(f"Audio Device: {app.device_index}")
        print(f"Sample Rate: {app.samplerate} Hz")
        print(f"Block Size: {app.blocksize}")
        print(f"Channels: 1 (mono)")
        print(f"Max File Size: {app.max_file_size_mb} MB")
        print(f"Recording Directory: {app.recording_dir}")
        print(f"Today's Directory: {app.today_dir}")
        
        # Platform-specific info
        platform_config = get_platform_config()
        print(f"\nPlatform: {platform_config['name']}")
        if platform_config['is_wsl']:
            print("WSL Audio Configuration:")
            print(f"  Pulse Server: {platform_config.get('pulse_server', 'default')}")
        
        # Buffer info
        if hasattr(app, 'circular_buffer') and app.circular_buffer is not None:
            buffer_size_mb = len(app.circular_buffer) * 4 / (1024 * 1024)  # 4 bytes per float32
            print(f"\nBuffer Size: {buffer_size_mb:.1f} MB")
            print(f"Buffer Duration: {len(app.circular_buffer) / app.samplerate:.1f} seconds")
        
        print("-" * 50)
        
    except Exception as e:
        print(f"Configuration display error: {e}")

def show_help():
    """Display help information with proper line endings for all platforms."""
    
    # Clear any lingering progress indicators or status messages
    print("\r" + " " * 120 + "\r", end="", flush=True)  # Clear wider area
    print()  # Add a clean newline to separate from previous output
    
    # Print each line individually with explicit line endings for Linux/WSL
    print("BMAR (Bioacoustic Monitoring and Recording) Help\r")
    print("============================================================\r")
    print("\r")
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
    print("\r")
    print("1-9 - Channel:     Switch monitoring channel (while VU/Intercom active)\r")
    print("\r")
    print("Tips:\r")
    print("- Press any command key to toggle that function on/off\r")
    print("- Multiple functions can run simultaneously\r")
    print("- Files are automatically organized by date\r")
    print("- Use 'p' for one-time performance check, 'P' for continuous monitoring\r")
    print("- Use 'd' for current device info, 'D' for all available devices\r")
    print("- Press 1-9 to switch audio channel while VU meter or Intercom is running\r")
    print("============================================================\r")
    print()  # Add final newline for clean separation

def get_user_input(prompt, default=None, input_type=str, validator=None):
    """Get validated user input with optional default value."""
    
    while True:
        try:
            if default is not None:
                display_prompt = f"{prompt} [{default}]: "
            else:
                display_prompt = f"{prompt}: "
            
            user_input = input(display_prompt).strip()
            
            # Use default if no input provided
            if not user_input and default is not None:
                user_input = str(default)
            
            # Convert to desired type
            if input_type == int:
                value = int(user_input)
            elif input_type == float:
                value = float(user_input)
            else:
                value = user_input
            
            # Apply validator if provided
            if validator is not None:
                if not validator(value):
                    print("Invalid input. Please try again.")
                    continue
            
            return value
            
        except ValueError:
            print(f"Please enter a valid {input_type.__name__}.")
        except KeyboardInterrupt:
            print("\nInput cancelled.")
            return None
        except Exception as e:
            print(f"Input error: {e}")

def confirm_action(message, default=True):
    """Get yes/no confirmation from user."""
    
    default_text = "Y/n" if default else "y/N"
    prompt = f"{message} ({default_text}): "
    
    try:
        response = input(prompt).strip().lower()
        
        if not response:
            return default
        
        return response in ['y', 'yes', 'true', '1']
        
    except KeyboardInterrupt:
        print("\nCancelled.")
        return False
    except Exception:
        return default

def display_status_line(app):
    """Display a status line with current system state."""
    
    try:
        # Count active processes
        active_count = 0
        if hasattr(app, 'active_processes') and app.active_processes:
            for process in app.active_processes.values():
                if process is not None and process.is_alive():
                    active_count += 1
        
        # Get system time
        current_time = time.strftime("%H:%M:%S")
        
        # Build status line
        status_parts = [
            f"Time: {current_time}",
            f"Active: {active_count}",
            f"Device: {app.device_index}",
            f"Rate: {app.samplerate}Hz"
        ]
        
        status_line = " | ".join(status_parts)
        print(f"\r{status_line}", end="", flush=True)
        
    except Exception as e:
        logging.debug(f"Status line display error: {e}")

def cleanup_ui(app):
    """Clean up user interface resources."""
    
    try:
        # Stop keyboard listener
        app.keyboard_listener_running = False
        
        # Restore terminal settings
        from .system_utils import restore_terminal_settings
        if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
            restore_terminal_settings(app, app.original_terminal_settings)
        
        print("\nUser interface cleanup completed.")
        
    except Exception as e:
        logging.error(f"UI cleanup error: {e}")

def handle_detailed_device_list_command(app):
    """Handle detailed device list command (uppercase D)."""
    
    try:
        from .audio_devices import show_detailed_device_list
        
        print("\nDetailed Audio Device Information:")
        print("=" * 60)
        show_detailed_device_list(app)
        
    except Exception as e:
        print(f"Detailed device list error: {e}")

def handle_continuous_performance_monitor_command(app):
    """Handle continuous performance monitor command (uppercase P)."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .system_utils import monitor_system_performance_continuous_standalone
    
    try:
        if 'P' in app.active_processes and app.active_processes['P'] is not None:
            if app.active_processes['P'].is_alive():
                print("Stopping continuous performance monitor...")
                
                # Signal the process to stop using the shared dictionary
                if hasattr(app, 'performance_monitor_stop_dict'):
                    app.performance_monitor_stop_dict['stop'] = True
                
                cleanup_process(app, 'P')
            else:
                print("Starting continuous performance monitor...")
                app.active_processes['P'] = None  # Clear dead process
                start_continuous_performance_monitor(app)
        else:
            print("Starting continuous performance monitor...")
            start_continuous_performance_monitor(app)
            
    except Exception as e:
        print(f"Continuous performance monitor command error: {e}")
        import traceback
        traceback.print_exc()

def start_continuous_performance_monitor(app):
    """Start continuous performance monitoring."""
    
    from .process_manager import create_subprocess
    from .system_utils import monitor_system_performance_continuous_standalone
    import multiprocessing
    
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
        print(f"Continuous performance monitor started (PID: {process.pid})")
        
    except Exception as e:
        print(f"Error starting continuous performance monitor: {e}")
        import traceback
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
            print(f"\nInvalid channel selection: Device has only {app.channels} channel(s) (1-{app.channels})")
            return
            
        # Update monitor channel
        old_channel = app.monitor_channel
        app.monitor_channel = key_int
        print(f"\nNow monitoring channel: {app.monitor_channel+1} (of {app.channels})")
        
        # Restart VU meter if running
        if hasattr(app, 'active_processes') and 'v' in app.active_processes and app.active_processes['v'] is not None:
            if app.active_processes['v'].is_alive():
                print(f"Restarting VU meter on channel: {app.monitor_channel+1}")
                
                try:
                    # Stop current VU meter
                    app.active_processes['v'].terminate()
                    app.active_processes['v'].join(timeout=1)
                    app.active_processes['v'] = None
                    
                    # Start VU meter with new channel
                    time.sleep(0.1)
                    start_vu_meter(app)
                except Exception as e:
                    print(f"Error restarting VU meter: {e}")
        
        # Handle intercom channel change if running
        if hasattr(app, 'active_processes') and 'i' in app.active_processes and app.active_processes['i'] is not None:
            if app.active_processes['i'].is_alive():
                print(f"Channel change for intercom on channel: {app.monitor_channel+1}")
                # For intercom, we would need to implement channel change signaling
                # This would require updating the intercom implementation
                
    except ValueError:
        print(f"Invalid channel number: {command}")
    except Exception as e:
        print(f"Channel switch error: {e}")
        import traceback
        traceback.print_exc()
        logging.error(f"Channel switch error: {e}")

def timed_input(app, prompt, timeout=3, default='n'):
    """
    Get user input with a timeout and default value for headless operation.
    
    Args:
        app: Application instance (contains headless flag)
        prompt: The prompt to display to the user
        timeout: Timeout in seconds (default: 3)
        default: Default response if timeout or Enter is pressed (default: 'n')
    
    Returns:
        str: User input or default value
    """
    
    # Check if running in headless mode
    if hasattr(app, 'headless') and app.headless:
        print(f"[Headless mode] Using default: '{default}'")
        return default
    
    print(prompt, end='', flush=True)
    start_time = time.time()
    
    try:
        import sys
        import select
        
        if sys.platform == 'win32':
            # Windows doesn't have select.select for stdin, use a different approach
            try:
                import msvcrt
                
                # Check for input character by character with timeout
                while (time.time() - start_time) < timeout:
                    if msvcrt.kbhit():
                        char = msvcrt.getch().decode('utf-8', errors='ignore')
                        if char == '\r' or char == '\n':
                            print()  # New line after Enter
                            return default
                        elif char.isprintable():
                            print(char)  # Echo the character
                            # Read the rest of the line
                            remaining = input()
                            return char + remaining
                    time.sleep(0.1)
                
                # Windows fallback - use a different approach since input() blocks
                # If we can't get character input, just use the timeout
                remaining_time = timeout - (time.time() - start_time)
                
                # For Windows, we'll just do a simple timeout since threading with input() 
                # doesn't work properly for timeout scenarios
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time > 0:
                    # Just wait for timeout since Windows stdin handling is complex
                    time.sleep(remaining_time)
                    
            except ImportError:
                # If msvcrt is not available, fall back to basic timeout
                while (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                    
        else:
            # Unix/Linux - use select
            while (time.time() - start_time) < timeout:
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    response = sys.stdin.readline().strip()
                    return response if response else default
                    
    except Exception as e:
        # If select fails, fall back to basic timeout
        print(f"\n[Input method failed, using timeout fallback]: {e}")
        remaining_time = timeout - (time.time() - start_time)
        if remaining_time > 0:
            time.sleep(remaining_time)
    
    # Timeout occurred
    print(f"\n[Timeout after {timeout}s] Using default: '{default}'")
    return default

def ensure_app_attributes(app):
    """Ensure the app object has all required attributes for audio processing."""
    
    try:
        # Import audio device functions
        from .audio_devices import sync_app_audio_attributes, get_current_audio_config
        
        # Import config values
        from .bmar_config import SOUND_IN_CHS, MONITOR_CH
        
        # First try to sync from existing audio configuration
        if sync_app_audio_attributes(app):
            logging.info("App attributes synced from audio configuration")
        else:
            # Set fallback values if no audio config is available
            logging.warning("Using fallback audio configuration")
            
            # Try to get a working device
            config = get_current_audio_config(app)
            if config['device_id'] is not None:
                app.device_index = config['device_id']
                app.sound_in_id = config['device_id']
                app.samplerate = config['sample_rate']
                app.PRIMARY_IN_SAMPLERATE = config['sample_rate']
                app.channels = config['channels']
                app.sound_in_chs = config['channels']
                app._bit_depth = config['bit_depth']
            else:
                # Last resort fallback values
                app.device_index = None
                app.sound_in_id = None
                app.samplerate = 44100
                app.PRIMARY_IN_SAMPLERATE = 44100
                app.channels = SOUND_IN_CHS if SOUND_IN_CHS > 0 else 1
                app.sound_in_chs = app.channels
                app._bit_depth = 16
        
        # Set other required attributes with defaults
        if not hasattr(app, 'monitor_channel'):
            app.monitor_channel = MONITOR_CH
        if not hasattr(app, 'blocksize'):
            app.blocksize = 1024
        if not hasattr(app, 'DEBUG_VERBOSE'):
            app.DEBUG_VERBOSE = False
        if not hasattr(app, 'testmode'):
            app.testmode = False
            
        # Platform detection
        if not hasattr(app, 'is_wsl'):
            from .platform_manager import PlatformManager
            platform_manager = PlatformManager()
            app.is_wsl = platform_manager.is_wsl()
        if not hasattr(app, 'is_macos'):
            from .platform_manager import PlatformManager
            platform_manager = PlatformManager()
            app.is_macos = platform_manager.is_macos()
        if not hasattr(app, 'os_info'):
            from .platform_manager import PlatformManager
            platform_manager = PlatformManager()
            app.os_info = platform_manager.get_os_info()
            
        # Validate monitor channel is within bounds
        if hasattr(app, 'channels') and app.monitor_channel >= app.channels:
            print(f"Warning: Monitor channel {app.monitor_channel + 1} exceeds available channels ({app.channels}). Using channel 1.")
            app.monitor_channel = 0
            
    except Exception as e:
        print(f"Warning: Error setting app attributes: {e}")
        logging.error(f"Error in ensure_app_attributes: {e}")
        
        # Emergency fallback values
        if not hasattr(app, 'device_index'):
            app.device_index = None
        if not hasattr(app, 'channels') or app.channels <= 0:
            app.channels = 1
        if not hasattr(app, 'samplerate'):
            app.samplerate = 44100
        if not hasattr(app, 'blocksize'):
            app.blocksize = 1024
        if not hasattr(app, 'monitor_channel'):
            app.monitor_channel = 0

def list_all_threads():
    """List all currently running threads."""
    
    import threading
    
    print("\n=== Currently Running Threads ===")
    for thread in threading.enumerate():
        print(f"Thread name: {thread.name}, Thread ID: {thread.ident}, Alive: {thread.is_alive()}")
    print("=" * 35)

def handle_thread_list_command(app):
    """Handle thread listing command."""
    
    try:
        list_all_threads()
    except Exception as e:
        print(f"Error listing threads: {e}")
        logging.error(f"Error listing threads: {e}")

def handle_fft_command(app):
    """Handle FFT command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import plot_fft
    
    try:
        if 'f' in app.active_processes and app.active_processes['f'] is not None:
            if app.active_processes['f'].is_alive():
                print("Stopping FFT analysis...")
                cleanup_process(app, 'f')
            else:
                print("Starting FFT analysis...")
                app.active_processes['f'] = None
                start_fft_analysis(app)
        else:
            print("Starting FFT analysis...")
            start_fft_analysis(app)
            
    except Exception as e:
        print(f"FFT command error: {e}")
        import traceback
        traceback.print_exc()

def start_fft_analysis(app):
    """Start one-shot FFT analysis."""
    
    from .process_manager import create_subprocess
    from .plotting import plot_fft
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
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
            'monitor_channel': getattr(app, 'monitor_channel', 0)
        }
        
        print(f"Starting FFT analysis (device {app.device_index}, {app.samplerate}Hz)")
        print(f"  Channel: {app.monitor_channel + 1} of {app.channels}")
        
        # Create and start FFT process
        # Note: This will be a short-lived process that captures, analyzes, and exits
        process = create_subprocess(
            target_function=plot_fft,
            args=(fft_config,),
            process_key='f',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"FFT analysis started (PID: {process.pid})")
        
        # Note: The process will finish automatically after capturing and displaying
        
    except Exception as e:
        print(f"Error starting FFT analysis: {e}")
        import traceback
        traceback.print_exc()
