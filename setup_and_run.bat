@echo off
setlocal
cd /d "%~dp0"
echo ======================================
echo AirLink Glass UI - First-time setup
echo ======================================
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Dependency installation failed. Confirm Python is installed and try again.
  pause
  exit /b 1
)
echo.
echo Starting AirLink dashboard...
python app.py
if errorlevel 1 pause
