# BMAR - Bioacoustic Monitoring and Recording System

A modular Python app| Key | Function | Description |
|-----|----------|-------------|
| `r` | Recording | Start/stop audio recording |
| `s` | Spectrogram | One-shot frequency analysis with GUI window |
| `o` | Oscilloscope | 10-second waveform capture with GUI window |
| `t` | Trigger | Triggered waveform capture |
| `v` | VU Meter | Audio level monitoring |
| `i` | Intercom | Audio monitoring/loopback |
| `d` | Current Device | Show currently selected audio device |
| `D` | All Devices | List all available audio devices with details |
| `p` | Performance | System performance monitor (one-time) |
| `P` | Performance | Continuous system performance monitor |
| `f` | Files | File browser and directory info |
| `c` | Configuration | Display current settings |
| `h` | Help | Show help message |
| `q` | Quit | Exit the application |l-time audio monitoring, recording, and analysis.

## 🚀 Quick Start

### Prerequisites
Make sure you have Python 3.7+ and the required packages installed:

```bash
run requirement.txt
pip install numpy scipy matplotlib sounddevice librosa pydub psutil
```

### Running the Application

Navigate to the source directory:
```bash
cd E:\git\earth_biometrics\project-bees-knees\beehub\python\src
```

#### Method 1: Simple Quick Start ⭐ (Recommended)
```bash
python run_bmar.py
```

#### Method 2: Windows Batch File
```cmd
run_bmar.bat
```
Or double-click `run_bmar.bat` in Windows Explorer.

#### Method 3: Full Command Line Interface
```bash
# Basic usage
python main.py

# List available audio devices first
python main.py --list-devices

# Run with specific device and sample rate
python main.py --device 1 --samplerate 48000

# Run with debug logging
python main.py --debug

# Show configuration
python main.py --config

# Get help
python main.py --help
```

#### Method 4: Linux/macOS Shell Script
```bash
./run_bmar.sh
```

## 🎛️ Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--device` / `-d` | Audio device index | `--device 1` |
| `--samplerate` / `-r` | Sample rate (8000-96000 Hz) | `--samplerate 48000` |
| `--blocksize` / `-b` | Audio buffer size | `--blocksize 2048` |
| `--max-file-size` / `-m` | Max file size in MB | `--max-file-size 200` |
| `--recording-dir` / `-o` | Output directory | `--recording-dir C:\Recordings` |
| `--list-devices` / `-l` | List audio devices and exit | `--list-devices` |
| `--config` / `-c` | Show configuration and exit | `--config` |
| `--test-audio` / `-t` | Test audio device | `--test-audio` |
| `--debug` | Enable debug logging | `--debug` |
| `--help` / `-h` | Show help | `--help` |

## 🎹 Application Controls

Once the application is running, use these keyboard commands:

| Key | Function | Description |
|-----|----------|-------------|
| `r` | Recording | Start/stop audio recording |
| `s` | Spectrogram | Real-time frequency analysis |
| `o` | Oscilloscope | 10-second waveform capture with GUI window |
| `t` | Trigger | Triggered waveform capture |
| `v` | VU Meter | Audio level monitoring |
| `i` | Intercom | Audio monitoring/loopback |
| `d` | Current Device | Show currently selected audio device |
| `D` | All Devices | List all available audio devices with details |
| `p` | Performance | System performance monitor (one-time) |
| `P` | Performance | Continuous system performance monitor |
| `f` | Files | File browser and directory info |
| `c` | Configuration | Display current settings |
| `h` | Help | Show help message |
| `q` | Quit | Exit the application |

## 📁 File Organization

The application automatically organizes files by date:

```
BMAR_Recordings/
├── 2025-07-14/
│   ├── recording_001.wav
│   ├── recording_002.wav
│   └── plots/
│       ├── spectrogram_20250714_143022_001.png
│       └── oscope_20250714_143055_001.png
└── 2025-07-15/
    └── ...
```

## 🔧 Configuration Examples

### Use a specific audio device:
```bash
# First, list available devices
python main.py --list-devices

# Then use a specific device (e.g., device 18)
python main.py --device 18
```

### High-quality recording setup:
```bash
python main.py --device 18 --samplerate 48000 --blocksize 2048 --max-file-size 500
```

### Debug mode with logging:
```bash
python main.py --debug --log-file bmar.log
```

## 🐛 Troubleshooting

### Audio Device Issues
1. **List devices first**: `python main.py --list-devices`
2. **Test a device**: `python main.py --test-audio --device X`
3. **Try different APIs**: Look for WASAPI devices (usually most reliable on Windows)

### Missing Dependencies
```bash
# Install all required packages
pip install numpy scipy matplotlib sounddevice librosa pydub psutil

# For audio format conversion (optional)
pip install ffmpeg-python
```

### WSL Audio Configuration
If running on Windows Subsystem for Linux, you may need to configure audio routing:
```bash
export PULSE_SERVER=tcp:localhost:4713
```

## 📦 Module Structure

The application is organized into focused modules:

- **`bmar_app.py`** - Main application class
- **`bmar_config.py`** - Configuration and constants
- **`audio_devices.py`** - Device discovery and management
- **`audio_processing.py`** - Recording and streaming
- **`audio_tools.py`** - VU meter, intercom, diagnostics
- **`plotting.py`** - Oscilloscope, spectrogram, triggers
- **`user_interface.py`** - Keyboard input and commands
- **`process_manager.py`** - Subprocess lifecycle management
- **`file_utils.py`** - File operations and organization
- **`system_utils.py`** - Platform utilities and terminal management
- **`platform_manager.py`** - OS detection and configuration

## 🚨 Exit and Cleanup

The application handles cleanup automatically when you:
- Press `q` to quit
- Press `Ctrl+C`
- Close the terminal window

All subprocesses are properly terminated and resources are cleaned up.

## 📈 Performance Tips

1. **Choose the right device**: WASAPI devices often perform better than MME on Windows
2. **Adjust block size**: Larger blocks (2048, 4096) = lower CPU usage but higher latency
3. **Monitor performance**: Press `p` for one-time check or `P` for continuous monitoring
4. **Device information**: Press `d` for basic list or `D` for detailed device information
5. **Multiple functions**: You can run recording, VU meter, and spectrogram simultaneously

### 🔤 Case-Sensitive Commands

Some commands have different behaviors based on case:
- `d` vs `D`: Current device info vs all available devices
- `p` vs `P`: One-time performance check vs continuous monitoring

## 🆘 Getting Help

- **In-app help**: Press `h` while the application is running
- **Command line help**: `python main.py --help`
- **Configuration info**: `python main.py --config`
- **Device info**: `python main.py --list-devices`

---

**Version**: 1.0.0  
**Platform Support**: Windows, Linux, macOS  
**Python Requirements**: 3.7+
