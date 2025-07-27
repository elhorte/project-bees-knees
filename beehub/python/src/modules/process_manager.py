"""
BMAR Process Manager Module
Handles subprocess lifecycle management, cleanup, and process tracking.
"""

import multiprocessing
import threading
import time
import logging
import os

def cleanup_process(app, command):
    """Clean up a specific command's process or thread."""
    
    try:
        # Check if the command key exists in active_processes
        if command in app.active_processes:
            process_or_thread = app.active_processes[command]
            if process_or_thread is not None:
                try:
                    if process_or_thread.is_alive():
                        # Check if it's a thread or process
                        if isinstance(process_or_thread, threading.Thread):
                            logging.info(f"Stopping thread for command '{command}'\r")
                            
                            # For VU meter threads, we need special cleanup
                            if command == 'v' and hasattr(app, 'vu_stop_event'):
                                app.vu_stop_event.set()
                                # Give VU meter more time to clean up its display
                                process_or_thread.join(timeout=3)
                                
                                if process_or_thread.is_alive():
                                    logging.warning(f"VU meter thread did not stop gracefully\r")
                                else:
                                    # Clear any remaining VU meter display artifacts
                                    print("\r" + " " * 80 + "\r", end="", flush=True)
                                    time.sleep(0.1)  # Brief pause for display cleanup
                            else:
                                # Other threads - standard cleanup
                                process_or_thread.join(timeout=2)
                                if process_or_thread.is_alive():
                                    logging.warning(f"Thread for command '{command}' did not stop gracefully\r")
                                    
                        else:
                            # It's a process
                            logging.info(f"Terminating process for command '{command}'\r")
                            process_or_thread.terminate()
                            process_or_thread.join(timeout=5)  # Wait up to 5 seconds
                            
                            if process_or_thread.is_alive():
                                logging.warning(f"Force killing process for command '{command}'\r")
                                process_or_thread.kill()
                                process_or_thread.join()
                            
                except Exception as e:
                    logging.error(f"Error stopping {type(process_or_thread).__name__.lower()} for command '{command}': {e}\r")
                
                # Reset the process/thread reference
                app.active_processes[command] = None
                print(f"{type(process_or_thread).__name__} for command '{command}' has been cleaned up")
        else:
            # The command doesn't exist in our tracking dictionary
            logging.warning(f"Warning: No process tracking for command '{command}'\r")
    except Exception as e:
        logging.error(f"Error in cleanup_process for command '{command}': {e}\r")

def _set_stop_events(app):
    """Helper function to set all stop events."""
    # Set stop flags
    app.stop_program[0] = True
    app.keyboard_listener_running = False
    
    # Stop recording events
    if hasattr(app, 'stop_recording_event'):
        app.stop_recording_event.set()
    
    # Stop other events
    if hasattr(app, 'stop_tod_event'):
        app.stop_tod_event.set()
    if hasattr(app, 'stop_vu_event'):
        app.stop_vu_event.set()
    if hasattr(app, 'stop_intercom_event'):
        app.stop_intercom_event.set()
    if hasattr(app, 'stop_fft_periodic_plot_event'):
        app.stop_fft_periodic_plot_event.set()
    
    # Stop performance monitor
    if hasattr(app, 'stop_performance_monitor_event'):
        app.stop_performance_monitor_event.set()
    
    # Signal buffer wrap event to unblock any waiting threads
    if hasattr(app, 'buffer_wrap_event'):
        app.buffer_wrap_event.set()

def stop_all(app):
    """Stop all processes and threads."""
    
    logging.info("Stopping all processes and threads...\r")

    # Set all stop events
    _set_stop_events(app)
    
    # Clean up active processes
    if hasattr(app, 'active_processes') and app.active_processes is not None:
        for key in app.active_processes:
            cleanup_process(app, key)
    
    # Give threads a moment to finish
    time.sleep(0.5)
    
    print("All processes stopped.\r")

def cleanup(app):
    """Clean up and exit."""
    
    print("\nPerforming cleanup...")
    
    # Set all stop events and clean up processes
    _set_stop_events(app)
    
    # Clean up active processes
    if hasattr(app, 'active_processes') and app.active_processes is not None:
        for key in app.active_processes:
            cleanup_process(app, key)

    # PyAudio streams are cleaned up individually by their processes
    # No global sounddevice cleanup needed since we use PyAudio exclusively

    # Restore terminal settings
    from .system_utils import restore_terminal_settings, reset_terminal_settings
    if hasattr(app, 'original_terminal_settings') and app.original_terminal_settings:
        restore_terminal_settings(app, app.original_terminal_settings)
    else:
        reset_terminal_settings(app)
    
    logging.info("Cleanup completed.")
    
    # Force exit to prevent hanging
    os._exit(0)

def create_subprocess(target_function, args, process_key, app, daemon=True):
    """
    Create and manage a subprocess with proper tracking.
    
    Args:
        target_function: The function to run in the subprocess
        args: Arguments to pass to the target function
        process_key: Key to store the process in active_processes dict
        app: BmarApp instance
        daemon: Whether to make the process a daemon process
        
    Returns:
        multiprocessing.Process: The created process
    """
    # Clean up any existing process with this key
    cleanup_process(app, process_key)
    
    # Create new process
    process = multiprocessing.Process(target=target_function, args=args)
    process.daemon = daemon
    
    # Store in active processes
    app.active_processes[process_key] = process
    
    return process

def list_active_processes(app):
    """List all currently active processes."""
    if not hasattr(app, 'active_processes') or app.active_processes is None:
        print("No process tracking available")
        return
    
    print("\nActive Processes:")
    print("-" * 40)
    
    for key, process in app.active_processes.items():
        if process is not None:
            try:
                status = "RUNNING" if process.is_alive() else f"STOPPED (exit code: {process.exitcode})"
                pid = process.pid if process.is_alive() else "N/A"
                print(f"  {key}: {status} (PID: {pid})")
            except Exception as e:
                print(f"  {key}: ERROR - {e}")
        else:
            print(f"  {key}: None")
    
    print("-" * 40)
