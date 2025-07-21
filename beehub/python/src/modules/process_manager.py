"""
BMAR Process Manager Module
Handles subprocess lifecycle management, cleanup, and process tracking.
"""

import multiprocessing
import time
import logging
import os

def cleanup_process(app, command):
    """Clean up a specific command's process or thread."""
    import threading
    
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
                            
                            # For threads, we need to use stop events
                            if command == 'v' and hasattr(app, 'vu_stop_event'):
                                app.vu_stop_event.set()
                                # Give thread a bit more time to stop gracefully and clean up output
                                process_or_thread.join(timeout=2)
                                
                                if process_or_thread.is_alive():
                                    logging.warning(f"Thread for command '{command}' did not stop gracefully\r")
                                else:
                                    # Small delay to let VU meter clean up its output
                                    time.sleep(0.1)
                                    
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

def stop_all(app):
    """Stop all processes and threads."""
    
    logging.info("Stopping all processes and threads...\r")

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
    
    # Stop all processes first (but don't print duplicate messages)
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

def wait_for_process_completion(process, timeout=None, process_name="Process"):
    """
    Wait for a process to complete with optional timeout.
    
    Args:
        process: The multiprocessing.Process to wait for
        timeout: Maximum time to wait in seconds (None for no timeout)
        process_name: Name for logging purposes
        
    Returns:
        bool: True if process completed normally, False if timeout or error
    """
    try:
        process.join(timeout=timeout)
        
        if process.is_alive():
            logging.warning(f"{process_name} did not complete within {timeout}s timeout")
            return False
        else:
            logging.info(f"{process_name} completed successfully")
            return True
            
    except Exception as e:
        logging.error(f"Error waiting for {process_name}: {e}")
        return False

def terminate_process_gracefully(process, timeout=5, process_name="Process"):
    """
    Terminate a process gracefully with escalating methods.
    
    Args:
        process: The multiprocessing.Process to terminate
        timeout: Maximum time to wait for graceful shutdown
        process_name: Name for logging purposes
        
    Returns:
        bool: True if process was terminated successfully
    """
    if not process.is_alive():
        return True
        
    try:
        # First try graceful termination
        logging.info(f"Attempting graceful termination of {process_name}")
        process.terminate()
        process.join(timeout=timeout)
        
        if not process.is_alive():
            logging.info(f"{process_name} terminated gracefully")
            return True
        
        # If still alive, force kill
        logging.warning(f"{process_name} did not respond to termination, force killing")
        process.kill()
        process.join(timeout=2)
        
        if not process.is_alive():
            logging.info(f"{process_name} force killed successfully")
            return True
        else:
            logging.error(f"Failed to kill {process_name}")
            return False
            
    except Exception as e:
        logging.error(f"Error terminating {process_name}: {e}")
        return False

def get_process_status(app, process_key):
    """
    Get the status of a tracked process.
    
    Args:
        app: BmarApp instance
        process_key: Key of the process to check
        
    Returns:
        dict: Status information about the process
    """
    if process_key not in app.active_processes:
        return {'exists': False, 'status': 'not_tracked'}
    
    process = app.active_processes[process_key]
    if process is None:
        return {'exists': False, 'status': 'none'}
    
    try:
        is_alive = process.is_alive()
        exit_code = process.exitcode
        
        status = {
            'exists': True,
            'is_alive': is_alive,
            'exit_code': exit_code,
            'pid': process.pid if is_alive else None
        }
        
        if is_alive:
            status['status'] = 'running'
        elif exit_code == 0:
            status['status'] = 'completed_successfully'
        elif exit_code is not None:
            status['status'] = f'exited_with_code_{exit_code}'
        else:
            status['status'] = 'unknown'
            
        return status
        
    except Exception as e:
        return {
            'exists': True,
            'status': 'error',
            'error': str(e)
        }

def cleanup_all_processes(app):
    """Clean up all tracked processes."""
    if not hasattr(app, 'active_processes') or app.active_processes is None:
        return
    
    logging.info("Cleaning up all tracked processes...")
    
    for key in list(app.active_processes.keys()):
        cleanup_process(app, key)
    
    logging.info("All tracked processes cleaned up")

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
