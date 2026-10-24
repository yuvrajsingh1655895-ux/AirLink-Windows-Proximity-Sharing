@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_background.ps1"
if errorlevel 1 goto failed
goto end
:failed
echo Background launch failed. Copy the error above.
pause
:end
