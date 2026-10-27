@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if errorlevel 1 (
  start "AirLink" python app.py --background
) else (
  start "AirLink" pythonw.exe "%~dp0app.py" --background
)
