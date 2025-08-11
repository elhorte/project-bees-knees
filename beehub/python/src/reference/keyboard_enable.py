import threading
import keyboard  # Requires the `keyboard` library. Install with `pip install keyboard`.

# Global variable to track the state of the keyboard watcher
keyboard_watcher_enabled = False

def keyboard_watcher():
    global keyboard_watcher_enabled
    while True:
        if keyboard_watcher_enabled:
            print("Keyboard watcher is active...")
            # Add your BMAR function logic here
        else:
            # Sleep briefly to avoid high CPU usage when disabled
            threading.Event().wait(0.5)

def toggle_keyboard_watcher():
    global keyboard_watcher_enabled
    keyboard_watcher_enabled = not keyboard_watcher_enabled
    state = "enabled" if keyboard_watcher_enabled else "disabled"
    print(f"Keyboard watcher {state}.")

def main():
    # Start the keyboard watcher thread
    watcher_thread = threading.Thread(target=keyboard_watcher, daemon=True)
    watcher_thread.start()

    print("Press '^' to toggle the keyboard watcher.")
    while True:
        # Listen for the '^' key to toggle the watcher
        if keyboard.is_pressed('^'):
            toggle_keyboard_watcher()
            # Wait briefly to avoid multiple toggles from a single key press
            threading.Event().wait(0.5)

if __name__ == "__main__":
    main()