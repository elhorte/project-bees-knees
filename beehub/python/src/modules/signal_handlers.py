"""
Signal Handlers Module
Handles system signals for graceful shutdown and process management.
"""

import signal
import sys
import logging
import threading
import time

def setup_signal_handlers(app):
    """Set up signal handlers for graceful shutdown."""
    
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}")
        logging.info(f"Received signal {signum}, initiating shutdown...")
        
        try:
            # Set a flag to indicate shutdown is in progress
            app.shutdown_requested = True
            
            # Give processes a moment to notice the shutdown flag
            time.sleep(0.1)
            
            # Clean up application
            if hasattr(app, 'cleanup'):
                app.cleanup()
            else:
                print("No cleanup method available")
            
            print("Shutdown complete")
            sys.exit(0)
            
        except Exception as e:
            print(f"Error during shutdown: {e}")
            logging.error(f"Error during signal handling: {e}")
            sys.exit(1)
    
    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request
        
        # Add shutdown flag to app
        app.shutdown_requested = False
        
        logging.info("Signal handlers registered successfully")
        
    except Exception as e:
        logging.warning(f"Could not register all signal handlers: {e}")

def cleanup_signal_handlers():
    """Reset signal handlers to default."""
    try:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        logging.info("Signal handlers reset to default")
    except Exception as e:
        logging.warning(f"Error resetting signal handlers: {e}")