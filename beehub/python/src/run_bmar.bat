@echo off
REM BMAR Windows Launcher
REM This batch file runs the BMAR application on Windows

echo BMAR - Bioacoustic Monitoring and Recording
echo ==========================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

REM Change to the script directory
cd /d "%~dp0"

REM Run the BMAR application
echo Starting BMAR application...
echo.
python main.py %*

REM Pause if there was an error
if errorlevel 1 (
    echo.
    echo Application exited with error code %errorlevel%
    pause
)
