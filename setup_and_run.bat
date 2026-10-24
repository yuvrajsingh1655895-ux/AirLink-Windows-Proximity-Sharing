@echo off
cd /d "%~dp0"
echo Installing AirLink drag-and-drop dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Starting AirLink dashboard. Close/minimize it to keep AirLink in the tray.
python app.py
if errorlevel 1 goto failed
goto end
:failed
echo.
echo Setup or launch failed. Copy the error shown above and send it to ChatGPT.
pause
:end
