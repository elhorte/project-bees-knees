#!/bin/bash
# BMAR Linux/macOS Launcher
# This script runs the BMAR application on Linux or macOS

echo "BMAR - Bioacoustic Monitoring and Recording"
echo "=========================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.7+ using your package manager"
    exit 1
fi

# Change to the script directory
cd "$(dirname "$0")"

# Run the BMAR application
echo "Starting BMAR application..."
echo
python3 main.py "$@"

# Check exit code
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo
    echo "Application exited with error code $exit_code"
    read -p "Press Enter to continue..."
fi

exit $exit_code
