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
            
        elif command == 't':
            handle_thread_list_command(app)
            
        elif command == 'v' or command == 'V':
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
            
        elif command == 'l' or command == 'L':
            handle_thread_list_command(app)

        # No imports, no dependencies, just pure print statements

        else:
            print(f"Unknown command: '{command}'. Press 'h' for help.\r")  # Added \r
            
    except Exception as e:
        print(f"Error processing command '{command}': {e}\r")  # Added \r
        import traceback
        print(f"Traceback: \r")  # Added \r
        traceback.print_exc()
        logging.error(f"Error processing command '{command}': {e}")

def handle_recording_command(app):
    """Handle recording start/stop command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_processing import recording_worker_thread
    
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
            
    except Exception as e:
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
            args=(app, record_period, interval, thread_id, file_format, target_sample_rate, start_tod, end_tod),
            process_key='r',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Recording started (PID: {process.pid})\r")  # Added \r
        
    except Exception as e:
        print(f"Error starting recording: {e}\r")  # Added \r

def handle_spectrogram_command(app):
    """Handle spectrogram command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import plot_spectrogram
    
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
            
    except Exception as e:
        print(f"Spectrogram command error: {e}\r")  # Added \r
        import traceback
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
            'capture_duration': 5.0,
            'freq_range': [0, app.samplerate // 2],
            'plots_dir': plots_dir
        }
        
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
        
    except Exception as e:
        print(f"Error starting spectrogram: {e}\r")  # Added \r
        import traceback
        traceback.print_exc()

def handle_oscilloscope_command(app):
    """Handle oscilloscope command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import plot_oscope
    
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
            
    except Exception as e:
        print(f"Oscilloscope command error: {e}\r")
        import traceback
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
            'plot_duration': 10.0,  # Capture 10 seconds of audio
            'plots_dir': plots_dir
        }
        
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
        
    except Exception as e:
        print(f"Error starting oscilloscope: {e}\r")
        import traceback
        traceback.print_exc()

def handle_trigger_command(app):
    """Handle trigger plotting command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import trigger
    
    try:
        if 't' in app.active_processes and app.active_processes['t'] is not None:
            if app.active_processes['t'].is_alive():
                print("Stopping trigger plotting...\r")  # Added \r
                cleanup_process(app, 't')
            else:
                print("Starting trigger plotting...\r")  # Added \r
                app.active_processes['t'] = None
                start_trigger_plotting(app)
        else:
            print("Starting trigger plotting...\r")  # Added \r
            start_trigger_plotting(app)
            
    except Exception as e:
        print(f"Trigger command error: {e}\r")  # Added \r

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
        
        print(f"Starting trigger plotting (device {app.device_index}, {app.samplerate}Hz)\r")  # Added \r
        
        # Create and start trigger process
        process = create_subprocess(
            target_function=trigger,
            args=(trigger_config,),
            process_key='t',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Trigger plotting started (PID: {process.pid})\r")  # Added \r
        
    except Exception as e:
        print(f"Error starting trigger plotting: {e}\r")  # Added \r
        import traceback
        traceback.print_exc()

def handle_vu_meter_command(app):
    """Handle VU meter command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_tools import vu_meter
    
    try:
        if 'v' in app.active_processes and app.active_processes['v'] is not None:
            if app.active_processes['v'].is_alive():
                print("Stopping VU meter...\r")  # Added \r
                cleanup_process(app, 'v')
            else:
                print("Starting VU meter...\r")  # Added \r
                app.active_processes['v'] = None
                start_vu_meter(app)
        else:
            print("Starting VU meter...\r")  # Added \r
            start_vu_meter(app)
            
    except Exception as e:
        print(f"VU meter command error: {e}\r")  # Added \r

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
            'is_macos': getattr(app, 'is_macos', False),
            'os_info': getattr(app, 'os_info', {}),
            'DEBUG_VERBOSE': getattr(app, 'DEBUG_VERBOSE', False)
        }
        
        print(f"Starting VU meter on channel {app.monitor_channel + 1} of {app.channels}\r")  # Added \r
        
        # Create and start VU meter process
        process = create_subprocess(
            target_function=vu_meter,
            args=(vu_config,),
            process_key='v',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"VU meter started (PID: {process.pid})\r")  # Added \r
        
    except Exception as e:
        print(f"Error starting VU meter: {e}\r")  # Added \r
        import traceback
        traceback.print_exc()

def handle_intercom_command(app):
    """Handle intercom command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .audio_tools import intercom_m
    
    try:
        if 'i' in app.active_processes and app.active_processes['i'] is not None:
            if app.active_processes['i'].is_alive():
                print("Stopping intercom...\r")  # Added \r
                cleanup_process(app, 'i')
            else:
                print("Starting intercom...\r")  # Added \r
                app.active_processes['i'] = None
                start_intercom(app)
        else:
            print("Starting intercom...\r")  # Added \r
            start_intercom(app)
            
    except Exception as e:
        print(f"Intercom command error: {e}\r")  # Added \r

def start_intercom(app):
    """Start intercom monitoring."""
    
    from .process_manager import create_subprocess
    from .audio_tools import intercom_m
    
    try:
        # Ensure app has all required attributes
        ensure_app_attributes(app)
        
        # Create intercom configuration
        intercom_config = {
            'input_device': app.device_index,
            'output_device': app.device_index,
            'samplerate': app.samplerate,
            'channels': app.channels,
            'blocksize': app.blocksize,
            'gain': 1.0,
            'monitor_channel': app.monitor_channel
        }
        
        print(f"Starting intercom (device {app.device_index}, {app.samplerate}Hz)\r")  # Added \r
        
        # Create and start intercom process
        process = create_subprocess(
            target_function=intercom_m,
            args=(intercom_config,),
            process_key='i',
            app=app,
            daemon=True
        )
        
        process.start()
        print(f"Intercom started (PID: {process.pid})\r")  # Added \r
        
    except Exception as e:
        print(f"Error starting intercom: {e}\r")  # Added \r
        import traceback
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
        
        print(f"\nSystem Resources:\r")  # Added \r
        print(f"  CPU Usage: {cpu_percent:.1f}%\r")  # Added \r
        print(f"  Memory Usage: {memory.percent:.1f}% ({memory.used//1024//1024}MB used)\r")  # Added \r
        print(f"  Available Memory: {memory.available//1024//1024}MB\r")  # Added \r
        
        # Show audio buffer status
        if hasattr(app, 'circular_buffer') and app.circular_buffer is not None:
            buffer_usage = (app.buffer_pointer[0] / len(app.circular_buffer)) * 100
            print(f"  Audio Buffer Usage: {buffer_usage:.1f}%\r")  # Added \r
        
        print("-" * 40 + "\r")  # Added \r
        
    except Exception as e:
        print(f"Performance monitor error: {e}\r")  # Added \r

def handle_file_browser_command(app):
    """Handle file browser command."""
    
    try:
        from .file_utils import list_recent_files
        
        print(f"\nFile Browser - {app.today_dir}\r")  # Added \r
        print("-" * 60 + "\r")  # Added \r
        
        # List files in today's directory
        if os.path.exists(app.today_dir):
            recent_files = list_recent_files(app.today_dir, limit=10)
            
            if recent_files:
                print("Recent files:\r")  # Added \r
                for i, (filepath, size, mtime) in enumerate(recent_files, 1):
                    filename = os.path.basename(filepath)
                    size_mb = size / (1024 * 1024)
                    time_str = time.strftime("%H:%M:%S", time.localtime(mtime))
                    print(f"  {i:2d}. {filename:<30} {size_mb:6.1f}MB {time_str}\r")  # Added \r
            else:
                print("No files found in today's directory\r")  # Added \r
        else:
            print("Today's directory does not exist yet\r")  # Added \r
        
        # Show directory structure
        print(f"\nDirectory structure:\r")  # Added \r
        print(f"  Recording dir: {app.recording_dir}\r")  # Added \r
        print(f"  Today's dir:   {app.today_dir}\r")  # Added \r
        
        plots_dir = os.path.join(app.today_dir, 'plots')
        if os.path.exists(plots_dir):
            plot_count = len([f for f in os.listdir(plots_dir) if f.endswith('.png')])
            print(f"  Plots dir:     {plots_dir} ({plot_count} plots)\r")  # Added \r
        
        print("-" * 60 + "\r")  # Added \r
        
    except Exception as e:
        print(f"File browser error: {e}\r")  # Added \r

def handle_configuration_command(app):
    """Handle configuration display command."""
    
    try:
        from .bmar_config import get_platform_config
        
        print("\nCurrent Configuration:\r")  # Added \r
        print("-" * 50 + "\r")  # Added \r
        print(f"Audio Device: {app.device_index}\r")  # Added \r
        print(f"Sample Rate: {app.samplerate} Hz\r")  # Added \r
        print(f"Block Size: {app.blocksize}\r")  # Added \r
        print(f"Channels: 1 (mono)\r")  # Fixed syntax and added \r
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
        
    except Exception as e:
        print(f"Configuration display error: {e}\r")  # Added \r

def handle_continuous_performance_monitor_command(app):
    """Handle continuous performance monitor command (uppercase P)."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .system_utils import monitor_system_performance_continuous_standalone
    
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
            
    except Exception as e:
        print(f"Continuous performance monitor command error: {e}\r")  # Added \r
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
        print(f"Continuous performance monitor started (PID: {process.pid})\r")  # Added \r
        
    except Exception as e:
        print(f"Error starting continuous performance monitor: {e}\r")  # Added \r
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
            print(f"\nInvalid channel selection: Device has only {app.channels} channel(s) (1-{app.channels})\r")  # Added \r
            return
            
        # Update monitor channel
        old_channel = app.monitor_channel
        app.monitor_channel = key_int
        print(f"\nNow monitoring channel: {app.monitor_channel+1} (of {app.channels})\r")  # Added \r
        
        # Restart VU meter if running
        if hasattr(app, 'active_processes') and 'v' in app.active_processes and app.active_processes['v'] is not None:
            if app.active_processes['v'].is_alive():
                print(f"Restarting VU meter on channel: {app.monitor_channel+1}\r")  # Added \r
                
                try:
                    # Stop current VU meter
                    app.active_processes['v'].terminate()
                    app.active_processes['v'].join(timeout=1)
                    app.active_processes['v'] = None
                    
                    # Start VU meter with new channel
                    time.sleep(0.1)
                    start_vu_meter(app)
                except Exception as e:
                    print(f"Error restarting VU meter: {e}\r")  # Added \r
        
        # Handle intercom channel change if running
        if hasattr(app, 'active_processes') and 'i' in app.active_processes and app.active_processes['i'] is not None:
            if app.active_processes['i'].is_alive():
                print(f"Channel change for intercom on channel: {app.monitor_channel+1}\r")  # Added \r
                
    except ValueError:
        print(f"Invalid channel number: {command}\r")  # Added \r
    except Exception as e:
        print(f"Channel switch error: {e}\r")  # Added \r
        import traceback
        traceback.print_exc()
        logging.error(f"Channel switch error: {e}")

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
        
    except Exception as e:
        logging.error(f"UI cleanup error: {e}")

def handle_detailed_device_list_command(app):
    """Handle detailed device list command (uppercase D)."""
    
    try:
        from .audio_devices import show_detailed_device_list
        
        print("\nDetailed Audio Device Information:\r")  # Added \r
        print("=" * 60 + "\r")  # Added \r
        show_detailed_device_list(app)
        
    except Exception as e:
        logging.error(f"Detailed device list error: {e}")

def handle_thread_list_command(app):
    """Handle thread listing command."""
    
    from .process_manager import list_active_processes
    
    try:
        print("\nActive Threads:\r")  # Added \r
        print("=" * 40 + "\r")  # Added \r
        
        # List all active threads with details
        list_active_processes(app)
        
        print("-" * 40 + "\r")  # Added \r
        
    except Exception as e:
        print(f"Error listing threads: {e}\r")  # Added \r
        import traceback
        traceback.print_exc()
        logging.error(f"Error listing threads: {e}")

def show_help():
    """Display help information with proper line endings for all platforms."""
    
    # Clear any lingering progress indicators or status messages
    print("\r" + " " * 120 + "\r", end="", flush=True)  # Clear wider area
    print()  # Add a clean newline to separate from previous output
    
    # Remove ALL \r characters - use normal print() statements
    print("BMAR (Bioacoustic Monitoring and Recording) Help")
    print("============================================================")
    print()
    print("Commands:")
    print("r - Recording:     Start/stop audio recording")
    print("s - Spectrogram:   One-shot frequency analysis with GUI window")
    print("o - Oscilloscope:  10-second waveform capture with GUI window")
    print("t - Threads:       List all currently running threads")
    print("v - VU Meter:      Audio level monitoring")
    print("i - Intercom:      Audio monitoring of remote microphones")
    print("d - Current Device: Show currently selected audio device")
    print("D - All Devices:    List all available audio devices with details")
    print("p - Performance:   System performance monitor (once)")
    print("P - Performance:   Continuous system performance monitor")
    print("f - FFT:           Show frequency analysis plot")
    print("c - Configuration: Display current settings")
    print("h - Help:          This help message")
    print("q - Quit:          Exit the application")
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

def handle_quit_command(app):
    """Handle quit command with proper cleanup."""
    
    try:
        print("Shutting down BMAR...\r")
        
        # Stop all active processes
        from .process_manager import cleanup_all_processes
        cleanup_all_processes(app)
        
        # Set running flag to False
        app.running = False
        
        # Additional cleanup
        if hasattr(app, 'stop_recording_event'):
            app.stop_recording_event.set()
        
        print("BMAR shutdown complete.\r")
        
    except Exception as e:
        print(f"Error during shutdown: {e}\r")
        app.running = False


def handle_fft_command(app):
    """Handle FFT command."""
    
    from .process_manager import cleanup_process, create_subprocess
    from .plotting import plot_fft
    
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
            
    except Exception as e:
        print(f"FFT command error: {e}\r")
        import traceback
        traceback.print_exc()

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
            'monitor_channel': getattr(app, 'monitor_channel', 0)
        }
        
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
        
    except Exception as e:
        print(f"Error starting FFT analysis: {e}\r")
        import traceback
        traceback.print_exc()
