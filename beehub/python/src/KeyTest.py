
import sys
try:
    # windows
    import msvcrt

    def getkey():
        return msvcrt.getch().decode('utf-8')
except ImportError:
    # mac, linux
    import termios
    import tty

    def getkey():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def main():
    # t = threading.Thread(target=doKeyboard)
    # t.start()
    doKeyboard()


def stop_all():
    pass


def doKeyboard():
    try:
        while True:
            print("Key please ")
            key = getkey()
            if key == "c":
                print("c  typed")
            elif key == "q":
                stop_all(); break  # usage: press q to stop all processes
            else :
                print("Unknown key " + key)

    except KeyboardInterrupt:  # ctrl-c in windows
        print('\nCtrl-C: Recording process stopped by user.')
        ##stop_all()


if __name__ == "__main__":
    main()
