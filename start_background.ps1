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
$scriptPath = Join-Path $PSScriptRoot 'app.py'
$argsLine = '"' + $scriptPath + '" --background'
Start-Process -FilePath $pythonw -ArgumentList $argsLine -WorkingDirectory $PSScriptRoot
Write-Host 'AirLink started in the background. Look for its icon in the Windows system tray.'
