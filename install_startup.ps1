$ErrorActionPreference = 'Stop'
$python = (Get-Command python.exe -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }
$script = Join-Path $PSScriptRoot 'app.py'
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'AirLink Glass UI.lnk'
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + $script + '" --background'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = 'Start AirLink wallpaper-adaptive glass sharing UI in the system tray'
$shortcut.IconLocation = $pythonw
$shortcut.Save()
Write-Host "AirLink startup shortcut installed: $shortcutPath"
