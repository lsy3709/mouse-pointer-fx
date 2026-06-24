@echo off
cd /d "%~dp0"
title Mouse Pointer FX

rem --- Check Python ---
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed.
  echo Install it from https://www.python.org and enable "Add Python to PATH".
  pause
  exit /b 1
)

rem --- Install required packages on first run ---
python -c "import PyQt6, pynput, win32api" >nul 2>nul
if errorlevel 1 (
  echo First run: installing required packages, please wait...
  python -m pip install -r requirements.txt
  if errorlevel 1 python -m pip install --user -r requirements.txt
)

rem --- Launch without a console window ---
set "PYW=pythonw"
where pythonw >nul 2>nul || set "PYW=python"
start "" %PYW% "%~dp0run.py"
exit /b 0
