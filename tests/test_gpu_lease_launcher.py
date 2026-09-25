"""Read-only launcher lease admission; temporary files and inert PowerShell doubles."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts' / 'studio-gpu-lease-gate.py'
POWERSHELL = shutil.which('powershell.exe') or shutil.which('pwsh')


class LauncherLeaseGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / '.runtime' / 'studio-gpu-lease.json'
        self.path.parent.mkdir()

    def write(self, value):
        self.path.write_text(json.dumps(value), encoding='utf-8')

    def invoke(self, code, state):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, '-s', str(GATE), '--root', str(self.root)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['state'], state)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'The launch gate must never rewrite state or create a lease')
        return value

    def test_missing_state_allows_without_creating_runtime_records(self):
        self.path.parent.rmdir()
        self.invoke(0, 'available')
        self.assertFalse(self.path.parent.exists())

    def test_active_lease_is_held_without_clamping_or_renewal(self):
        self.write({'record': {'holder': 'local-qwen', 'expires_at': time.time() + 600}, 'last_release': None})
        value = self.invoke(10, 'held')
        self.assertEqual(value['holder'], 'local-qwen')
        self.assertIn('ComfyUI', value['message'])

    def test_extreme_integer_deadline_is_held_without_overflow_or_rewrite(self):
        self.write({'record': {'holder': 'local-qwen', 'expires_at': 10 ** 400}})
        self.invoke(10, 'held')

    def test_expired_and_explicit_released_records_allow_without_mutation(self):
        for record in ({'holder': 'local-qwen', 'expires_at': time.time() - 1}, None):
            with self.subTest(record=record):
                self.write({'record': record, 'last_release': {'reason': 'released'}})
                self.invoke(0, 'available')

    def test_legacy_coordination_file_never_authorizes_or_blocks(self):
        (self.path.parent / 'gpu-lease.json').write_text('{"holder":"someone"}', encoding='utf-8')
        self.invoke(0, 'available')

    def test_malformed_envelopes_and_holder_deadlines_fail_closed(self):
        for value in ([], {}, {'record': []}, {'record': {'holder': 'Bad Holder', 'expires_at': 1}},
                      {'record': {'holder': 'qwen', 'expires_at': True}},
                      {'record': {'holder': 'qwen', 'expires_at': '123'}}):
            with self.subTest(value=value):
                self.write(value); self.invoke(20, 'unknown')

    def test_non_finite_and_duplicate_values_fail_closed(self):
        for raw in ('{"record":{"holder":"qwen","expires_at":NaN}}',
                    '{"record":{"holder":"qwen","expires_at":1e9999}}',
                    '{"record":null,"record":{"holder":"qwen","expires_at":1}}',
                    '{"record":{"holder":"qwen","holder":"other","expires_at":1}}', '{'):
            with self.subTest(raw=raw):
                self.path.write_text(raw, encoding='utf-8'); self.invoke(20, 'unknown')

    def test_oversized_and_non_utf8_records_fail_closed(self):
        for raw in (b' ' * (64 * 1024 + 1), b'\xff'):
            self.path.write_bytes(raw); self.invoke(20, 'unknown')

    def test_directory_in_place_of_record_fails_closed(self):
        self.path.mkdir(); self.invoke(20, 'unknown')

    def test_symbolic_record_is_not_followed(self):
        target = self.root / 'target.json'; target.write_text('{"record":null}', encoding='utf-8')
        try: self.path.symlink_to(target)
        except OSError: self.skipTest('Symbolic links unavailable')
        self.invoke(20, 'unknown')

    def test_unreadable_state_is_unknown_not_available(self):
        self.assertTrue(GATE.is_file(), 'Launcher needs a read-only GPU lease admission helper')
        spec = importlib.util.spec_from_file_location('lease_launch_gate_test', GATE)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.write({'record': None})
        with patch.object(Path, 'open', side_effect=PermissionError('inert access denied')):
            code, value = module.observe(self.root)
        self.assertEqual((code, value['state']), (20, 'unknown'))

    def test_launcher_checks_before_backend_and_studio_launch_and_rechecks_at_spawn(self):
        source = (ROOT / 'scripts' / 'Start-Studio.ps1').read_text()
        self.assertIn('studio-gpu-lease-gate.py', source)
        self.assertLess(source.index('$gpuAvailable = Test-StudioGpuLeaseAvailable'),
                        source.index("$inputRoot ="))
        self.assertIn('if (Test-StudioGpuLeaseAvailable)', source)
        self.assertLess(source.index('if (Test-StudioGpuLeaseAvailable)'),
                        source.index('& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $studioConfig.comfy_launcher'))


@unittest.skipUnless(POWERSHELL, 'PowerShell executable required for inert launcher integration')
class LauncherPowerShellTests(unittest.TestCase):
    def test_actual_launcher_with_all_runtime_actions_replaced(self):
        for state, expected_comfy, expected_studio in (('held', 0, 1), ('unknown', 0, 0),
                ('missing', 1, 1), ('expired', 1, 1), ('released', 1, 1), ('late', 0, 1)):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for folder in ('scripts', 'app', 'config', 'examples/references', 'comfy/input', '.runtime'):
                    (root / folder).mkdir(parents=True, exist_ok=True)
                for relative in ('scripts/Start-Studio.ps1', 'scripts/studio-gpu-lease-gate.py', 'app/gpu_lease.py'):
                    shutil.copyfile(ROOT / relative, root / relative)
                (root / 'comfy/launcher.ps1').write_text('ArgumentsFile' if state == 'late' else '# inert', encoding='utf-8')
                (root / 'config/local.json').write_text(json.dumps({'python': sys.executable,
                    'comfy_root': str(root / 'comfy'), 'comfy_url': 'http://127.0.0.1:8188',
                    'comfy_launcher': str(root / 'comfy/launcher.ps1')}), encoding='utf-8')
                lease = root / '.runtime/studio-gpu-lease.json'
                held = {'record': {'holder': 'local-qwen', 'expires_at': time.time() + 600}}
                if state == 'held': lease.write_text(json.dumps(held), encoding='utf-8')
                elif state == 'expired': lease.write_text(json.dumps({'record': {'holder': 'local-qwen', 'expires_at': 1}}))
                elif state == 'released': lease.write_text('{"record":null}')
                elif state == 'unknown': lease.write_text('{')
                if state == 'late':
                    (root / 'scripts/primary-comfy-args.py').write_text(
                        'from pathlib import Path\nimport json\n'
                        f'Path({str(lease)!r}).write_text({json.dumps(held)!r}, encoding="utf-8")\n'
                        'print(json.dumps({"arguments": []}))\n', encoding='utf-8')
                wrapper = root / 'test.ps1'
                wrapper.write_text(r'''
$ErrorActionPreference = 'Stop'
# The launcher is a nested script scope: share one explicit probe object.
$global:LauncherProbe = @{ comfy = 0; studio = 0; failed = $false }
$global:LauncherWorkspace = $PSScriptRoot
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    if ($global:LauncherProbe.studio -gt 0 -and $Uri.EndsWith('/api/identity')) {
        return @{ app = 'local-asset-studio'; workspace = $global:LauncherWorkspace }
    }
    throw 'Inert offline endpoint'
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
          $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    $global:LauncherProbe.studio += 1
    return [pscustomobject]@{ Id = 999; HasExited = $false }
}
function Start-Sleep { param($Seconds) }
function powershell.exe { $global:LauncherProbe.comfy += 1; $global:LASTEXITCODE = 0 }
try { & (Join-Path $PSScriptRoot 'scripts/Start-Studio.ps1') -NoBrowser -Detached }
catch { $global:LauncherProbe.failed = $true; Write-Host ($_ | Out-String) }
$global:LauncherProbe | ConvertTo-Json -Compress
''', encoding='utf-8')
                result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                         '-File', str(wrapper)], capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outcome = json.loads(result.stdout.strip().splitlines()[-1])
                self.assertEqual(outcome, {'comfy': expected_comfy, 'studio': expected_studio, 'failed': state == 'unknown'}, result.stdout + result.stderr)
