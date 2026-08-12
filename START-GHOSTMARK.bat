@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo Python 3.11+ is required but was not found.
    echo Download it from https://www.python.org/downloads/ and run this file again.
    echo.
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo GhostMark needs Python 3.11 or newer.
    echo Download it from https://www.python.org/downloads/ and run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Setting up GhostMark for the first time. This can take a minute...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Could not create a Python virtual environment.
        echo.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -e "%~dp0."
if errorlevel 1 (
    echo.
    echo GhostMark could not install its dependencies. See the messages above for details.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting GhostMark at http://127.0.0.1:8765
echo Your files never leave this computer.
echo.
".venv\Scripts\ghostmark.exe" ui
pause
