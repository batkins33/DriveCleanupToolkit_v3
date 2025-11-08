@echo off
REM Drive Cleanup Toolkit - Windows CMD Launcher

echo ================================
echo Drive Cleanup Toolkit v3
echo ================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please run these commands first:
    echo   python -m venv venv
    echo   venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Virtual environment activated!
echo.
echo Available commands:
echo   python gui_toolkit.py           - Launch GUI
echo   python scan_storage.py --help   - Scan files
echo   python drive_organizer.py --help - Organize/dedupe
echo.
echo Type 'deactivate' to exit the virtual environment
echo.

REM Keep the window open in the activated environment
cmd /k
