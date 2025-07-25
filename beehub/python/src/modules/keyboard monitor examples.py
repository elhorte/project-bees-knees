#!/usr/bin/env python3
# This script provides a simple interactive terminal control mechanism
# that allows toggling between interactive mode and normal terminal input.
# for linux systems.


import sys
import termios
import tty
import select
import threading
import os

# Toggle state
interactive_mode = True
toggle_key = '^'

# Save original terminal settings
orig_settings = termios.tcgetattr(sys.stdin)

def enable_raw_mode():
    tty.setraw(sys.stdin.fileno())

def restore_terminal():
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)

def keyboard_listener():
    global interactive_mode
    try:
        enable_raw_mode()
        while True:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch == toggle_key:
                    interactive_mode = not interactive_mode
                    print(f"\n[{'Resumed' if interactive_mode else 'Paused'} interactive mode]")
                elif interactive_mode:
                    handle_interactive_command(ch)
                else:
                    # Echo behavior – allow terminal input to behave normally
                    restore_terminal()
                    os.system('stty echo')  # Ensure echo is on
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    enable_raw_mode()  # Re-enable raw mode after echoing
    finally:
        restore_terminal()

def handle_interactive_command(ch):
    if ch == 'm':
        print("[Memory usage displayed]")
    elif ch == 'p':
        print("[Processor load shown]")
    else:
        print(f"[Unrecognized command: {ch}]")

if __name__ == "__main__":
    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()

    # Main app logic (e.g., subprocesses, timers)
    print("Program started. Press '^' to toggle terminal control.")
    while True:
        pass  # Your main threaded app logic here


# 🧪 Notes for Improvement
# - This approach uses tty.setraw() which disables line buffering and echo. In passive mode, we restore some echoing for natural terminal feel.
# - If you're integrating this with subprocesses that also use stdin/stdout, some stream redirection logic may be needed.
# - You could expand this by adding:
# - Logging of passive input
# - A shell-like console in active mode
# - Optional timeout to switch modes


# ############################################
# Windows version of the same
# ##############################################

import msvcrt
import threading
import time

# Toggle control
interactive_mode = True
toggle_key = b'^'  # msvcrt.getch() returns bytes

def keyboard_listener():
    global interactive_mode
    while True:
        if msvcrt.kbhit():  # Check for keypress
            ch = msvcrt.getch()
            if ch == toggle_key:
                interactive_mode = not interactive_mode
                print(f"\n[{'Resumed' if interactive_mode else 'Paused'} interactive mode]")
            elif interactive_mode:
                handle_interactive_command(ch)
            else:
                # Pass-through mode; optionally echo to screen
                print(ch.decode(errors='ignore'), end='', flush=True)
        time.sleep(0.05)  # Prevent CPU hogging

def handle_interactive_command(ch):
    command = ch.decode(errors='ignore')
    if command == 'm':
        print("[Memory usage displayed]")
    elif command == 'p':
        print("[Processor load shown]")
    else:
        print(f"[Unrecognized command: {command}]")

if __name__ == "__main__":
    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()

    print("Program started. Press '^' to toggle terminal control.")
    while True:
        # Your threaded or subprocess logic goes here
        pass

# 🧩 Key Notes for Windows
# - msvcrt.kbhit() checks if a key was pressed.
# - msvcrt.getch() gets one character at a time in raw mode, no need for Enter.
# - It’s a byte string, so we decode it before handling or echoing.
# - You can customize the toggle key or even define other control characters.

