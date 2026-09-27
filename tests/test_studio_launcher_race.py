"""Launcher startup-race PID ownership and exclusive-bind browser fixtures.

The PowerShell cases run the real scripts/Start-Studio.ps1 with every runtime
action replaced by inert doubles, so they never bind 8191 or contact a Studio.
The static cases only read fixture sources.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe') or shutil.which('pwsh')

PLAIN_SHARED_BIND = re.compile(r"ThreadingHTTPServer\(\s*\(\s*['\"]127\.0\.0\.1['\"]\s*,\s*8191")
RACE_FIXTURES = (
    'asset_conflict_envelope_browser.py',
    'asset_library_browser.py',
    'asset_metadata_browser.py',
    'asset_recovery_lifecycle_browser.py',
    'asset_recovery_refusal_browser.py',
    'asset_recovery_session_browser.py',
    'asset_workspace_browser.py',
)

WRAPPER = r'''
$ErrorActionPreference = 'Stop'
$global:RaceProbe = @{ failed = $false; message = '' }
$global:RaceWorkspace = $PSScriptRoot
$global:RaceStarted = $false
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    if ($Uri -like '*/system_stats') {
        return @{ system = @{ comfyui_version = 'inert' } }
    }
    if ($Uri.EndsWith('/api/identity')) {
        if (-not $global:RaceStarted) { throw 'Inert offline endpoint' }
        __IDENTITY__
    }
    throw 'Inert offline endpoint'
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
          $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    $global:RaceStarted = $true
    return [pscustomobject]@{ Id = 999; HasExited = __HASEXITED__ }
}
function Start-Sleep { param($Seconds) }
function Get-NetTCPConnection {
    param($LocalAddress, $LocalPort, $State, $ErrorAction)
    return [pscustomobject]@{ OwningProcess = __OWNING__ }
}
function Get-CimInstance {
    param($ClassName, $Filter, $ErrorAction)
    return [pscustomobject]@{ ParentProcessId = __PARENT__ }
}
function powershell.exe { $global:LASTEXITCODE = 0 }
try { & (Join-Path $PSScriptRoot 'scripts/Start-Studio.ps1') -NoBrowser -Detached }
catch { $global:RaceProbe.failed = $true; $global:RaceProbe.message = ($_ | Out-String) }
$global:RaceProbe | ConvertTo-Json -Compress
'''

READY_IDENTITY = "return @{ app = 'local-asset-studio'; workspace = $global:RaceWorkspace }"
NEVER_IDENTITY = "throw 'Inert offline endpoint'"


@unittest.skipUnless(POWERSHELL, 'PowerShell executable required for inert launcher race')
class LauncherRaceTests(unittest.TestCase):
    def run_launcher(self, has_exited, owning, identity, parent=1):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ('scripts', 'app', 'config', 'examples/references', 'comfy/input', '.runtime'):
                (root / folder).mkdir(parents=True, exist_ok=True)
            for relative in ('scripts/Start-Studio.ps1', 'scripts/studio-gpu-lease-gate.py', 'app/gpu_lease.py'):
                shutil.copyfile(ROOT / relative, root / relative)
            (root / 'comfy/launcher.ps1').write_text('# inert', encoding='utf-8')
            (root / 'config/local.json').write_text(json.dumps({'python': sys.executable,
                'comfy_root': str(root / 'comfy'), 'comfy_url': 'http://127.0.0.1:8188',
                'comfy_launcher': str(root / 'comfy/launcher.ps1')}), encoding='utf-8')
            (root / '.runtime/studio-gpu-lease.json').write_text('{"record":null}', encoding='utf-8')
            wrapper = root / 'test.ps1'
            wrapper.write_text(WRAPPER.replace('__HASEXITED__', '$true' if has_exited else '$false')
                                      .replace('__OWNING__', str(owning))
                                      .replace('__PARENT__', str(parent))
                                      .replace('__IDENTITY__', identity), encoding='utf-8')
            result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(wrapper)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            outcome = json.loads(result.stdout.strip().splitlines()[-1])
            pidfile = root / '.runtime/server.pid'
            pid_text = pidfile.read_text(encoding='utf-8').strip() if pidfile.is_file() else None
            # The temp root is removed on exit; snapshot the evidence before returning.
            return outcome, pid_text

    def test_lost_race_records_no_pid(self):
        outcome, pid_text = self.run_launcher(True, 4242, READY_IDENTITY)
        self.assertFalse(outcome['failed'], outcome)
        self.assertIsNone(pid_text, 'The loser must not overwrite the winner server.pid')

    def test_won_race_records_child_pid(self):
        outcome, pid_text = self.run_launcher(False, 999, READY_IDENTITY)
        self.assertFalse(outcome['failed'], outcome)
        self.assertEqual(pid_text, '999')

    def test_listener_owned_by_the_childs_child_records_the_child_pid(self):
        # A venv python.exe redirector: the listener belongs to its child process.
        outcome, pid_text = self.run_launcher(False, 5555, READY_IDENTITY, parent=999)
        self.assertFalse(outcome['failed'], outcome)
        self.assertEqual(pid_text, '999')

    def test_unrelated_listener_records_no_pid(self):
        outcome, pid_text = self.run_launcher(False, 5555, READY_IDENTITY, parent=1)
        self.assertFalse(outcome['failed'], outcome)
        self.assertIsNone(pid_text)

    def test_dead_child_with_no_server_fails(self):
        outcome, pid_text = self.run_launcher(True, 4242, NEVER_IDENTITY)
        self.assertTrue(outcome['failed'], outcome)
        self.assertIn('Asset Studio exited', outcome['message'])
        self.assertIsNone(pid_text)


class BrowserExclusiveBindTests(unittest.TestCase):
    def source(self, name):
        return (ROOT / 'tests' / name).read_text(encoding='utf-8')

    def test_asset_fixtures_never_share_8191(self):
        for name in RACE_FIXTURES:
            with self.subTest(fixture=name):
                source = self.source(name)
                self.assertIsNone(PLAIN_SHARED_BIND.search(source), name)
                self.assertIn('StudioHTTPServer', source, name)

    def test_bundle_factory_uses_exclusive_server(self):
        source = self.source('bundle_guidance_browser.py')
        self.assertIsNone(PLAIN_SHARED_BIND.search(source))
        self.assertNotRegex(source, r'return\s+ThreadingHTTPServer\(')
        self.assertIn('server.StudioHTTPServer', source)


if __name__ == '__main__':
    unittest.main()
