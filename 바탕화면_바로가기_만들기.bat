@echo off
cd /d "%~dp0"
title Mouse Pointer FX - Create Desktop Shortcut

rem Create a Desktop shortcut named "Mouse Pointer FX".

if not exist "%~dp0assets\icon.ico" (
  python "%~dp0tools\make_icon.py" >nul 2>nul
)

set "PYW=pythonw"
where pythonw >nul 2>nul || set "PYW=python"
for /f "delims=" %%i in ('where %PYW% 2^>nul') do set "PYWPATH=%%i"
if not defined PYWPATH set "PYWPATH=%PYW%"

set "ICON=%~dp0assets\icon.ico"
if not exist "%ICON%" set "ICON=%PYWPATH%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Mouse Pointer FX.lnk'); $lnk.TargetPath='%PYWPATH%'; $lnk.Arguments='\"%~dp0run.py\"'; $lnk.WorkingDirectory='%~dp0'; $lnk.IconLocation='%ICON%'; $lnk.Description='Mouse Pointer FX'; $lnk.Save()"

if errorlevel 1 (
  echo [ERROR] Failed to create the shortcut.
) else (
  echo Done. A "Mouse Pointer FX" shortcut was created on your Desktop.
)
pause
