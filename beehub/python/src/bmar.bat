@echo off
REM BMAR Mode Control Script
REM Usage: bmar on|off|status

cd /d "%~dp0"

if "%1"=="on" (
    .\auntbee\Scripts\python.exe bmar_toggle.py on
) else if "%1"=="off" (
    .\auntbee\Scripts\python.exe bmar_toggle.py off
) else if "%1"=="status" (
    .\auntbee\Scripts\python.exe bmar_toggle.py status
) else (
    echo Usage: bmar [on^|off^|status]
    echo.
    echo   on     - Enable BMAR single-key command mode
    echo   off    - Disable BMAR mode (normal terminal)
    echo   status - Show current BMAR mode status
)
