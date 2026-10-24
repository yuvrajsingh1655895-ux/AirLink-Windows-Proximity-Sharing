@echo off
set "AIRLINK_SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AirLink.lnk"
if exist "%AIRLINK_SHORTCUT%" (
  del "%AIRLINK_SHORTCUT%"
  echo AirLink has been removed from Windows Startup.
) else (
  echo No AirLink startup shortcut was found.
)
pause
