@echo off
cd /d "%~dp0"
echo This adds AirLink to your Windows Startup folder for this user.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_startup.ps1"
if errorlevel 1 echo Startup setup failed. Check the message above.
pause
