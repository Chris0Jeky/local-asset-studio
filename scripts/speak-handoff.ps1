[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Pack,

    [string] $BaseUrl = 'http://127.0.0.1:8191',
    [string] $SpeakerId = 'brief-narrator',
    [double] $PollSeconds = 1,
    [double] $DeadlineMinutes = 60,
    [switch] $PlanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$python = $null
if ($env:LAS_PYTHON -and (Test-Path -LiteralPath $env:LAS_PYTHON -PathType Leaf)) {
    $python = (Resolve-Path -LiteralPath $env:LAS_PYTHON).Path
}
else {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $python = $venvPython
    }
    else {
        $resolved = Get-Command python -ErrorAction SilentlyContinue
        if ($resolved) { $python = $resolved.Source }
    }
}

if (-not $python) {
    throw 'Python was not found. Set LAS_PYTHON to the Python executable used for Local Asset Studio.'
}

$command = 'run'
if ($PlanOnly) { $command = 'plan' }
$script = Join-Path $PSScriptRoot 'spoken_brief.py'
$arguments = @($script, $command, $Pack, '--speaker-id', $SpeakerId)
if (-not $PlanOnly) {
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    $arguments += @(
        '--base-url', $BaseUrl,
        '--poll-seconds', $PollSeconds.ToString($culture),
        '--deadline-minutes', $DeadlineMinutes.ToString($culture)
    )
}

& $python @arguments
exit $LASTEXITCODE
