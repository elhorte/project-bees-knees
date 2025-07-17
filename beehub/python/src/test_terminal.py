def test_simple_output():
    """Minimal test to isolate terminal output issues."""
    print("=" * 50)
    print("TEST 1: Simple print statements")
    print("Line 1")
    print("Line 2") 
    print("Line 3")
    print("=" * 50)
    
    import sys
    print("TEST 2: sys.stdout.write")
    sys.stdout.write("Line A\n")
    sys.stdout.write("Line B\n")
    sys.stdout.write("Line C\n")
    sys.stdout.flush()
    
    print("=" * 50)
    print("TEST 3: Terminal info")
    print(f"Platform: {sys.platform}")
    print(f"stdout.isatty(): {sys.stdout.isatty()}")
    print(f"stdout.encoding: {sys.stdout.encoding}")
    
    import os
    print(f"TERM: {os.environ.get('TERM', 'None')}")
    print(f"TERM_PROGRAM: {os.environ.get('TERM_PROGRAM', 'None')}")
    print("=" * 50)

def show_detailed_device_list(app):
    import threading
    import sys
    
    # Debug: Check what's running when we try to print
    print(f"DEBUG: Active threads: {len(threading.enumerate())}")
    for thread in threading.enumerate():
        print(f"DEBUG: Thread: {thread.name}")
    
    print(f"DEBUG: stdout.isatty(): {sys.stdout.isatty()}")
    print(f"DEBUG: Is there output buffering? {sys.stdout.line_buffering}")
    
    # Rest of function...

if __name__ == "__main__":
    test_simple_output()