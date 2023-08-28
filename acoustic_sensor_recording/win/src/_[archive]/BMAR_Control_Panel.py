#Here's a basic example of how you could add a settings button and a new settings window with some controls. The settings window is quite basic for now, but you could extend it with more sophisticated controls (e.g., checkboxes, dropdown menus, sliders, etc.) as needed.

from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QGridLayout,QMenu, QAction, QSystemTrayIcon
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, QSize, QObject, pyqtSignal, QDateTime, QDate, QTime, QTimer
from utils import showNotification, screenshot, getDateTime

import os; os.chdir(os.path.dirname(sys.argv[0]))

class SettingsWindow(QMainWindow):
    def __init__(self):
        super(SettingsWindow, self).__init__()

        self.setWindowTitle("Settings")

        layout = QGridLayout()

        self.continuous_mode_button = QPushButton("Continuous Mode On/Off")
        self.continuous_mode_tod_button = QPushButton("Continuous Mode TOD")
        self.continuous_mode_format_button = QPushButton("Continuous Mode Format")
        self.periodic_mode_button = QPushButton("Periodic Mode On/Off")
        self.periodic_mode_tod_button = QPushButton("Periodic Mode TOD")
        self.periodic_mode_format_button = QPushButton("Periodic Mode Format")
        self.event_mode_button = QPushButton("Event Mode On/Off")
        self.event_mode_threshold_button = QPushButton("Event Mode Threshold")
        self.event_mode_tod_button = QPushButton("Event Mode TOD")
        self.event_mode_format_button = QPushButton("Event Mode Format")
        self.input_configuration_button = QPushButton("Input Configuration")

        layout.addWidget(self.continuous_mode_button, 0, 0)
        layout.addWidget(self.continuous_mode_tod_button, 1, 0)
        layout.addWidget(self.continuous_mode_format_button, 2, 0)
        layout.addWidget(self.periodic_mode_button, 3, 0)
        layout.addWidget(self.periodic_mode_tod_button, 4, 0)
        layout.addWidget(self.periodic_mode_format_button, 5, 0)
        layout.addWidget(self.event_mode_button, 6, 0)
        layout.addWidget(self.event_mode_threshold_button, 7, 0)
        layout.addWidget(self.event_mode_tod_button, 8, 0)
        layout.addWidget(self.event_mode_format_button, 9, 0)
        layout.addWidget(self.input_configuration_button, 10, 0)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("PyQT Buttons Example")

        # Create the settings window
        self.settings_window = SettingsWindow()

        # Create the buttons
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon('gear_icon.png'))
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.clicked.connect(self.settings_window.show)

        # Create the buttons
        self.vu_meter_button = QPushButton("Toggle VU Meter")
        self.intercom_button = QPushButton("Toggle Intercom")
        self.oscope_button = QPushButton("Plot Osclloscope")
        self.fft_button = QPushButton("Plot FFT")
        self.quit_button = QPushButton("Quit")

        # Connect the buttons to their corresponding functions
        self.vu_meter_button.clicked.connect(self.toggle_vu_meter)
        self.intercom_button.clicked.connect(self.toggle_intercom)
        self.oscope_button.clicked.connect(self.plot_oscope)
        self.fft_button.clicked.connect(self.plot_fft)
        self.quit_button.clicked.connect(self.close)

        # Create the channel selection buttons
        self.channel_buttons = [QPushButton(str(i)) for i in range(4)]

        # Connect the channel buttons to their corresponding functions
        for i, button in enumerate(self.channel_buttons):
            button.clicked.connect(lambda checked, i=i: self.select_channel(i))

        # Arrange the main buttons vertically
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.vu_meter_button)
        vlayout.addWidget(self.intercom_button)
        vlayout.addWidget(self.oscope_button)
        vlayout.addWidget(self.fft_button)

        # Arrange the channel buttons horizontally
        hlayout = QHBoxLayout()
        for button in self.channel_buttons:
            hlayout.addWidget(button)

        # Create the label for the channel buttons
        channel_label = QLabel("Channel Select")
        channel_label.setAlignment(Qt.AlignCenter)  # Center the label

        # Add the label and the channel buttons to a layout
        channel_layout = QVBoxLayout()
        channel_layout.addWidget(channel_label)
        channel_layout.addLayout(hlayout)

        # Add the quit button to the layout
        channel_layout.addWidget(self.quit_button)

        # Add both layouts to the main layout
        layout = QVBoxLayout()
        layout.addLayout(vlayout)
        layout.addLayout(channel_layout)

        # Create a central widget (required for QMainWindow)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Set the layout on the central widget
        central_widget.setLayout(layout)

        # Add the settings button to the layout
        layout.addWidget(self.settings_button)
        
    def toggle_vu_meter(self):
        print("Toggling VU Meter")
        # Replace with your actual function

    def toggle_intercom(self):
        print("Toggling Intercom")
        # Replace with your actual function

    def plot_oscope(self):
        print("Plotting Oscope")
        # Replace with your actual function

    def plot_fft(self):
        print("Plotting FFT")
        # Replace with your actual function

    def select_channel(self, i):
        print(f"Selected channel {i}")
        # Replace with your actual function

# Create the Qt Application
app = QApplication([])

# Create and show the main window
window = MainWindow()
window.show()


# #####################################################
# start up stuff
# #####################################################

QApplication.setQuitOnLastWindowClosed(False)
qIcon = QIcon('icons/bmar.png')
app.setWindowIcon(qIcon)

bmar = BMARFullscreen()

showNotification('BMAR', 'Running in the background')

tray = QSystemTrayIcon()
if tray.isSystemTrayAvailable():
    tray.setIcon(QIcon('icons/bmar.png'))
    tray.setVisible(True)
    tray.show()



# Run the main Qt loop
#app.exec()

# rest of your code ...

#Please replace `'gear_icon.png'` with the path to your gear icon image. If you don't have an image, you can download one from an online resource or create your own. Please also ensure that the image file is located in the same directory as your Python script, or provide the full path to the image file.

#This code adds a new `SettingsWindow` class that represents the settings window. In the `MainWindow` class, an instance of `SettingsWindow` is created, and the `show` method of this instance is connected to the `clicked` signal of the settings button. This means that when the settings button is clicked, the settings window will be displayed. Note that the settings window is quite simple for now, and doesn't actually control any settings; it just displays some labels. You could replace these labels with other types of widgets (e.g., checkboxes, text fields, sliders, etc.) to allow the user to actually change the settings.

#Also, this example assumes that the gear icon for the settings button is stored in a file named `gear_icon.png` in the same directory as the script. You will need to replace `'gear_icon.png'` with the actual path to your gear icon. If you don't have a gear icon, you can find free ones online, or create your own.

#Now, each setting is represented by a QPushButton object. You can connect each button to a specific function that performs the corresponding action when the button is clicked. Just add a clicked.connect line for each button, as you did for the settings button. For example:

#python
#Copy code

#    self.continuous_mode_button.clicked.connect(self.set_continuous_mode)

#And then define the set_continuous_mode function (or whatever function you want to call when the button is clicked) in your SettingsWindow class. This function will contain the code to perform the corresponding action.

#Note: As previously mentioned, replace 'gear_icon.png' with the actual path to your gear icon. If you don't have an icon, you can find free ones online, or create your own. Also, ensure the image file is in the same directory as your Python script, or provide the full path to the image file.