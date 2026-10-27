$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'AirLink Glass UI.lnk'
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host 'AirLink startup shortcut removed.'
} else {
    Write-Host 'No AirLink Glass UI startup shortcut was found.'
}
