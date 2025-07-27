"""
BMAR System Utilities Module
Contains platform-specific utilities, terminal management, and system operations.
"""

import sys
import time
import threading
import logging
import signal
import subprocess
import os

# Terminal management functions for keyboard input handling
def get_key():
    """
    Get a single character from the keyboard without pressing Enter.
    Returns None if no key is pressed (non-blocking).
    """
    if sys.platform == 'win32':
        try:
            import msvcrt
            if msvcrt.kbhit():
                char = msvcrt.getch()
                if isinstance(char, bytes):
                    return char.decode('utf-8', errors='ignore')
                return char
        except ImportError:
            pass
    else:
        # Unix/Linux/macOS
        try:
            import termios
            import tty
            import select
            
            # Check if input is available
            if select.select([sys.stdin], [], [], 0)[0]:
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    char = sys.stdin.read(1)
                    return char
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except ImportError:
            pass
    
    return None

def setup_terminal_for_input(app):
    """
    Set up terminal for single character input (raw mode).
    """
    if sys.platform == 'win32':
        # On Windows, msvcrt handles this automatically
        pass
    else:
        # Unix/Linux/macOS
        try:
            import termios
            import tty
            
            fd = sys.stdin.fileno()
            # Save original settings
            if not hasattr(app, 'original_terminal_settings'):
                app.original_terminal_settings = termios.tcgetattr(fd)
            
            # Set raw mode
            tty.setraw(fd)
        except ImportError:
            pass

def restore_terminal_settings(app, settings=None):
    """
    Restore terminal to normal mode.
    """
    if sys.platform == 'win32':
        # On Windows, no special restoration needed
        pass
    else:
        # Unix/Linux/macOS
        try:
            import termios
            
            fd = sys.stdin.fileno()
            if settings:
                termios.tcsetattr(fd, termios.TCSADRAIN, settings)
            elif hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
                termios.tcsetattr(fd, termios.TCSADRAIN, app.original_terminal_settings)
        except ImportError:
            pass

def timed_input(app, prompt, timeout=3, default='n'):
    """
    Get user input with a timeout and default value for headless operation.
    
    Args:
        app: BmarApp instance containing platform manager
        prompt: The prompt to display to the user
        timeout: Timeout in seconds (default: 3)
        default: Default response if timeout or Enter is pressed (default: 'n')
        
    Returns:
        User input string or default value
    """
    
    # Print the prompt
    print(prompt, end='', flush=True)
    
    # Check if stdin is available (not redirected/piped)
    if not sys.stdin.isatty():
        print(f"[Headless mode] Using default: '{default}'")
        return default
    
    start_time = time.time()
    windows_method_failed = False
    
    # Platform-specific input handling
    if sys.platform == 'win32' and not app.platform_manager.is_wsl():
        try:
            while True:
                if app.platform_manager.msvcrt.kbhit():
                    char = app.platform_manager.msvcrt.getch().decode('utf-8')
                    if char == '\r':  # Enter key
                        print()
                        return default
                    elif char == '\x03':  # Ctrl+C
                        raise KeyboardInterrupt
                    else:
                        print(char)
                        return char
                
                if time.time() - start_time > timeout:
                    break
                time.sleep(0.1)
        except Exception as e:
            print(f"\nError with Windows input method: {e}")
            windows_method_failed = True
    
    # Unix/Linux/macOS implementation (or Windows fallback)
    if (sys.platform != 'win32' or app.platform_manager.is_wsl() or windows_method_failed):
        # Reset start time if we're falling back from Windows method
        if windows_method_failed:
            start_time = time.time()
        
        # Check if we can use select on this platform
        try:
            import select
            
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    line = sys.stdin.readline().strip()
                    return line if line else default
                
                if time.time() - start_time > timeout:
                    break
        except Exception as e:
            print(f"\nError with Unix input method: {e}")
            # Final fallback - just return default
    
    # Timeout occurred
    print(f"\n[Timeout after {timeout}s] Using default: '{default}'")
    return default

def clear_input_buffer(app):
    """Clear the keyboard input buffer. Handles both Windows and non-Windows platforms."""
    if sys.platform == 'win32' and not app.platform_manager.is_wsl():
        try:
            while app.platform_manager.msvcrt is not None and app.platform_manager.msvcrt.kbhit():
                app.platform_manager.msvcrt.getch()
        except Exception as e:
            print(f"Warning: Could not clear input buffer: {e}")
    else:
        # For macOS and Linux/WSL
        if app.platform_manager.termios is not None and app.platform_manager.tty is not None:
            fd = sys.stdin.fileno()
            old_settings = None
            try:
                old_settings = app.platform_manager.termios.tcgetattr(fd)
                app.platform_manager.tty.setraw(sys.stdin.fileno())
                # Drain the input buffer
                while app.platform_manager.select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    sys.stdin.read(1)
            finally:
                if old_settings is not None:
                    app.platform_manager.termios.tcsetattr(fd, app.platform_manager.termios.TCSADRAIN, old_settings)
        else:
            # Silent fail or fallback - do NOT use stty on Windows
            if not sys.platform == 'win32':
                safe_stty("sane")

def safe_stty(command):
    """Safely execute stty command without raising exceptions."""
    try:
        subprocess.run(f"stty {command}", shell=True, check=False, 
                      capture_output=True, text=True, timeout=2)
    except Exception as e:
        logging.warning("stty command failed: %s", e)

def reset_terminal_settings(app):
    """Reset terminal settings to default state without clearing the screen."""
    try:
        if app.platform_manager.termios is not None:
            fd = sys.stdin.fileno()
            old_settings = app.platform_manager.termios.tcgetattr(fd)
            app.platform_manager.termios.tcsetattr(fd, app.platform_manager.termios.TCSANOW, old_settings)
    except Exception as e:
        logging.warning("Could not reset terminal settings: %s", e)

def interruptable_sleep(seconds, stop_sleep_event):
    """Sleep for specified duration but can be interrupted by an event."""
    # Convert to integer iterations, with minimum of 1 to avoid range(0)
    iterations = max(1, int(seconds * 2))
    sleep_duration = seconds / iterations
    
    for _ in range(iterations):
        if stop_sleep_event.is_set():
            return
        time.sleep(sleep_duration)

def signal_handler(_sig, _frame):
    """Handle interrupt signals gracefully."""
    print('\nStopping all threads...\r')
    # This will be connected to the main app's stop function
    sys.exit(0)

def setup_signal_handlers(_app):
    """Setup signal handlers for graceful shutdown."""
    
    try:
        # Handle common termination signals
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request
        
        # Windows-specific signals
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)  # Ctrl+Break on Windows
            
        logging.info("Signal handlers installed")
        
    except Exception as e:
        logging.error("Error setting up signal handlers: %s", e)

def list_all_threads():
    """Debug function to list all active threads."""
    for thread in threading.enumerate():
        print(f"Thread name: {thread.name}, Thread ID: {thread.ident}, Alive: {thread.is_alive()}")

def setup_logging(log_level=logging.INFO, log_file=None):
    """Setup logging configuration for the application."""
    
    # Create logs directory if logging to file
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Setup logging
    logging.basicConfig(
        level=log_level,
        format=log_format,
        filename=log_file,
        filemode='a' if log_file else None
    )
    
    # If logging to file, also add console handler
    if log_file:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(log_format)
        console_handler.setFormatter(console_formatter)
        logging.getLogger('').addHandler(console_handler)
    
    logging.info("Logging initialized")

def get_system_performance():
    """Get a single snapshot of system performance."""
    import psutil
    
    # Get CPU usage for each core
    cpu_percents = psutil.cpu_percent(interval=1, percpu=True)
    
    # Get memory usage
    memory = psutil.virtual_memory()
    
    # Build the output string
    output = "\n=== System Performance Monitor ===\n"
    
    # Add CPU information
    output += "CPU Usage by Core:\n"
    for i, percent in enumerate(cpu_percents):
        output += f"Core {i}: {percent:5.1f}%\n"
    
    # Add memory information
    output += "\nMemory Usage:\n"
    output += f"Total: {memory.total / (1024**3):5.1f} GB\n"
    output += f"Used:  {memory.used / (1024**3):5.1f} GB\n"
    output += f"Free:  {memory.available / (1024**3):5.1f} GB\n"
    output += f"Used%: {memory.percent}%\n"
    output += "=" * 30 + "\n"
    
    return output

def monitor_system_performance_once():
    """Display a single snapshot of system performance."""
    try:
        output = get_system_performance()
        print(output, flush=True)
    except Exception as e:
        print(f"\nError in performance monitor: {e}", end='\r')

def monitor_system_performance_continuous(app):
    """Continuously monitor and display CPU and RAM usage."""
    try:
        while not app.stop_performance_monitor_event.is_set():
            output = get_system_performance()
            print(output, flush=True)
            
            # Use event wait with timeout instead of sleep for better responsiveness
            if app.stop_performance_monitor_event.wait(timeout=2):
                break
    except Exception as e:
        print(f"\nError in continuous performance monitor: {e}", end='\r')
    finally:
        print("\nContinuous performance monitor stopped.", end='\r')

def monitor_system_performance_continuous_standalone(stop_event_dict):
    """Standalone continuous performance monitor for multiprocessing."""
    
    try:
        print("Continuous performance monitor started...")
        while not stop_event_dict.get('stop', False):
            output = get_system_performance()
            print(output, flush=True)
            
            # Check every 2 seconds
            for _ in range(20):  # 2 seconds in 0.1 second increments
                if stop_event_dict.get('stop', False):
                    break
                time.sleep(0.1)
                
    except Exception as e:
        print(f"\nError in continuous performance monitor: {e}", end='\r')
    finally:
        print("\nContinuous performance monitor stopped.", end='\r')
