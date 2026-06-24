@echo off
cd /d "%~dp0"
title Mouse Pointer FX (debug)

rem Keeps the console open so you can read error messages.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed. Install it from https://www.python.org
  pause
  exit /b 1
)

python -c "import PyQt6, pynput, win32api" >nul 2>nul
if errorlevel 1 (
  echo Installing required packages...
  python -m pip install -r requirements.txt
  if errorlevel 1 python -m pip install --user -r requirements.txt
)

echo Running... close this window to stop the program.
python "%~dp0run.py"
echo.
echo Program exited.
pause
