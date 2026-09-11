$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $repoRoot 'config\local.json'
if (-not (Test-Path -LiteralPath $configPath)) { $configPath = Join-Path $repoRoot 'config\example.json' }
$studioConfig = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$exampleRoot = Join-Path $repoRoot 'examples\lanternkeeper'
$url = 'http://127.0.0.1:8193'
try {
    $response = Invoke-WebRequest "$url/index.html" -UseBasicParsing -TimeoutSec 2
    if ($response.Content -match 'Lanternkeeper') { Start-Process $url; exit 0 }
} catch { }
Start-Process -FilePath $studioConfig.python -ArgumentList @('-m','http.server','8193','--bind','127.0.0.1') -WorkingDirectory $exampleRoot -WindowStyle Hidden
Start-Sleep -Seconds 1
Start-Process $url
