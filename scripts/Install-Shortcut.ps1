$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath 'Asset Studio.lnk'
if (Test-Path -LiteralPath $shortcutPath) { throw 'Asset Studio shortcut already exists; inspect before replacing it.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $repoRoot 'scripts\Start-Studio.ps1') + '"'
$shortcut.WorkingDirectory = $repoRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Open your local image generation presets, experiments and gallery'
$shortcut.Save()
Write-Host "Created $shortcutPath"
