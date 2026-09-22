param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $repoRoot 'config\local.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot 'config\example.json') -Destination $configPath
}
$studioConfig = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$studioUrl = 'http://127.0.0.1:8191'
$existingStudio = $null
try { $existingStudio = Invoke-RestMethod ($studioUrl + '/api/identity') -TimeoutSec 2 } catch { }
if ($existingStudio.app -eq 'local-asset-studio') {
    if ($existingStudio.workspace -ne $repoRoot) { throw "Another Asset Studio workspace is using ${studioUrl}: '$($existingStudio.workspace)'." }
    Write-Host "Asset Studio ready: $studioUrl"
    if (-not $NoBrowser) { Start-Process $studioUrl }
    return
}
if (-not (Test-Path -LiteralPath $studioConfig.python)) { throw 'Python not found. Update config/local.json with this computer''s runtime paths.' }
if (-not (Test-Path -LiteralPath $studioConfig.comfy_root)) { throw 'ComfyUI not found. Update config/local.json.' }
$inputRoot = Join-Path $studioConfig.comfy_root 'input'
foreach ($reference in Get-ChildItem -LiteralPath (Join-Path $repoRoot 'examples\references') -File) {
    $targetPath = Join-Path $inputRoot $reference.Name
    if (-not (Test-Path -LiteralPath $targetPath)) { Copy-Item -LiteralPath $reference.FullName -Destination $targetPath }
}
$comfyReady = $false
try { $stats = Invoke-RestMethod ($studioConfig.comfy_url + '/system_stats') -TimeoutSec 3; $comfyReady = [bool]$stats.system.comfyui_version } catch { }
$isolatedReady = $false
try { $isolatedStats = Invoke-RestMethod 'http://127.0.0.1:8192/system_stats' -TimeoutSec 2; $isolatedReady = [bool]$isolatedStats.system } catch { }
try { $h3Stats = Invoke-RestMethod 'http://127.0.0.1:8194/system_stats' -TimeoutSec 2; $isolatedReady = $isolatedReady -or [bool]$h3Stats.system } catch { }
try { $qwen21Stats = Invoke-RestMethod 'http://127.0.0.1:8196/system_stats' -TimeoutSec 2; $isolatedReady = $isolatedReady -or [bool]$qwen21Stats.system } catch { }
$backendStatePath = Join-Path $repoRoot '.runtime\backend-state.json'
$savedBackend = $null
if (Test-Path -LiteralPath $backendStatePath) { $savedBackend = Get-Content -LiteralPath $backendStatePath -Raw | ConvertFrom-Json }
if (-not $comfyReady -and -not $isolatedReady -and $savedBackend.active -notin @('hidream','h3','qwen21')) {
    if (-not (Test-Path -LiteralPath $studioConfig.comfy_launcher)) { throw 'ComfyUI is offline and its launcher is missing. Check config/local.json.' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $studioConfig.comfy_launcher -NoBrowser
    if ($LASTEXITCODE -ne 0) { throw 'ComfyUI did not start; inspect its logs.' }
}
$studioUrl = 'http://127.0.0.1:8191'
$ready = $false
try { $health = Invoke-RestMethod ($studioUrl + '/api/identity') -TimeoutSec 2; $ready = $health.app -eq 'local-asset-studio' } catch { }
if ($ready -and $health.workspace -ne $repoRoot) {
    throw "Another Asset Studio workspace is using $studioUrl. Its workspace is '$($health.workspace)'. Finish its active jobs before restarting with this launcher."
}
if (-not $ready) {
    $logRoot = Join-Path $repoRoot '.runtime'
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $serverPath = Join-Path $repoRoot 'app\server.py'
    $process = Start-Process -FilePath $studioConfig.python -ArgumentList @('"' + $serverPath + '"') -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot "$stamp-out.log") -RedirectStandardError (Join-Path $logRoot "$stamp-error.log") -PassThru
    $process.Id | Set-Content -LiteralPath (Join-Path $logRoot 'server.pid')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        if ($process.HasExited) { throw "Asset Studio exited. See $logRoot" }
        try { $health = Invoke-RestMethod ($studioUrl + '/api/identity') -TimeoutSec 2; $ready = $health.app -eq 'local-asset-studio'; if ($ready) { break } } catch { }
    }
    if (-not $ready) { throw "Asset Studio did not become ready. See $logRoot" }
}
Write-Host "Asset Studio ready: $studioUrl"
if (-not $NoBrowser) { Start-Process $studioUrl }
