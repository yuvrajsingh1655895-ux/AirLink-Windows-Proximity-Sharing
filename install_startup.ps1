$ErrorActionPreference = 'Stop'
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $pythonw) {
    $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pythonCmd) {
        $candidate = Join-Path (Split-Path $pythonCmd.Source) 'pythonw.exe'
        if (Test-Path $candidate) { $pythonw = $candidate }
    }
}
if (-not $pythonw) {
    $pythonPath = (& python -c "import sys; print(sys.executable)" 2>$null).Trim()
    if ($pythonPath) {
        $candidate = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
        if (Test-Path $candidate) { $pythonw = $candidate }
    }
}
if (-not $pythonw) { throw 'Could not find pythonw.exe. Run setup_and_run.bat first and check your Python installation.' }
$startup = [Environment]::GetFolderPath('Startup')
$scriptPath = Join-Path $PSScriptRoot 'app.py'
$shortcutPath = Join-Path $startup 'AirLink.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + $scriptPath + '" --background'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Start AirLink background drag-to-share prototype'
$shortcut.Save()
Write-Host "Startup shortcut installed: $shortcutPath"
Write-Host 'AirLink will run at sign-in. Remove it with remove_startup.bat.'
