@echo off
REM Mouse Pointer FX - 단일 .exe 빌드 (PyInstaller)
REM 결과물: dist\MousePointerFX.exe

cd /d "%~dp0"

echo [1/3] 의존성 확인...
python -m pip install -r requirements.txt pyinstaller

echo [2/3] 아이콘 생성...
if not exist "assets\icon.ico" python tools\make_icon.py

echo [3/3] 빌드...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name MousePointerFX ^
  --paths src ^
  --icon assets\icon.ico ^
  --hidden-import win32api ^
  --hidden-import win32con ^
  --hidden-import win32gui ^
  run.py

echo.
echo 완료: dist\MousePointerFX.exe
pause
