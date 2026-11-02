"""Recorded runtime patch drift: temporary files, no installed ComfyUI or generation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts/check-runtime-patches.py'
POWERSHELL = shutil.which('powershell.exe') or shutil.which('pwsh')
TARGET = 'comfy_extras/nodes_mesh_postprocess.py'
ORIGINAL = b'original = "CPU UV patch absent"\r\n'
PATCHED = b'raise AssertionError("Patch checking must never import this source")\r\n'


class RuntimePatchFiles:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        # Windows may provide an 8.3 TEMP alias while PowerShell and the checker
        # resolve its long name. Keep every fixture identity on that same path.
        self.root = Path(temporary.name).resolve()
        self.comfy = self.root / 'comfy'
        self.target = self.comfy / TARGET
        self.target.parent.mkdir(parents=True)
        self.records = self.root / 'runtime-patches'; self.records.mkdir()
        self.record = self.records / 'comfyui-cpu-uv.json'
        self.metadata = {'file': TARGET, 'original_sha256': hashlib.sha256(ORIGINAL).hexdigest(),
                         'patched_sha256': hashlib.sha256(PATCHED).hexdigest()}
        self.record.write_text(json.dumps(self.metadata), encoding='utf-8')

    def checker(self):
        self.assertTrue(CHECKER.is_file(), 'Studio startup needs a read-only recorded-patch checker')
        spec = importlib.util.spec_from_file_location('runtime_patch_warning_test', CHECKER)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def observe(self, expected):
        rows = self.checker().observe(self.root, self.comfy)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]['status'], expected, rows)
        self.assertEqual(rows[0]['patch'], self.record.name)
        self.assertEqual(rows[0]['target'], TARGET)
        return rows[0]

    def invoke(self):
        self.assertTrue(CHECKER.is_file(), 'Studio startup needs a read-only recorded-patch checker')
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, '-s', str(CHECKER), '--root', str(self.root),
                                 '--comfy-root', str(self.comfy)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'Diagnostics must not write patch records or runtime files')
        return result.stdout


class RuntimePatchWarningTests(RuntimePatchFiles, unittest.TestCase):
    def test_original_bytes_warn_that_the_recorded_patch_is_not_applied(self):
        self.target.write_bytes(ORIGINAL)
        row = self.observe('unapplied')
        self.assertEqual(row['actual_sha256'], self.metadata['original_sha256'])
        output = self.invoke()
        self.assertIn(self.record.name, output); self.assertIn(TARGET, output)
        self.assertIn('not applied', output); self.assertIn('original SHA-256', output)

    def test_patched_bytes_are_quiet_and_are_never_imported(self):
        self.target.write_bytes(PATCHED)
        row = self.observe('applied')
        self.assertEqual(row['actual_sha256'], self.metadata['patched_sha256'])
        self.assertEqual(self.invoke(), '')

    def test_changed_bytes_warn_without_exposing_source_content(self):
        content = b'raise RuntimeError("PRIVATE_SOURCE_SENTINEL")\n'
        self.target.write_bytes(content)
        row = self.observe('unexpected')
        self.assertEqual(row['actual_sha256'], hashlib.sha256(content).hexdigest())
        output = self.invoke()
        self.assertIn('unexpected SHA-256', output)
        self.assertNotIn('PRIVATE_SOURCE_SENTINEL', output)

    def test_missing_target_is_distinct_and_not_created(self):
        self.observe('missing')
        self.assertIn('target is missing', self.invoke())
        self.assertFalse(self.target.exists())

    def test_unreadable_target_is_distinct_and_error_details_are_not_exposed(self):
        self.target.write_bytes(ORIGINAL)
        module = self.checker(); original_open = Path.open
        def denied(path, *args, **kwargs):
            if path == self.target: raise PermissionError('PRIVATE_ERROR_SENTINEL')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', denied):
            rows = module.observe(self.root, self.comfy)
        self.assertEqual(rows[0]['status'], 'unreadable')
        self.assertEqual(rows[0]['target'], TARGET)
        self.assertNotIn('PRIVATE_ERROR_SENTINEL', json.dumps(rows))

    def test_directory_target_is_not_opened_or_called_missing(self):
        self.target.mkdir()
        self.observe('unreadable')

    def test_large_target_is_bounded_and_not_misclassified_as_drift(self):
        module = self.checker()
        with self.target.open('wb') as stream: stream.truncate(module.MAX_TARGET_BYTES + 1)
        self.observe('unreadable')
        self.assertIn('read limit', self.invoke())

    def test_malformed_or_incomplete_records_warn_without_echoing_metadata(self):
        module = self.checker()
        for raw in ('{"PRIVATE_RECORD_SENTINEL":', '[]', '{}',
                    json.dumps({**self.metadata, 'patched_sha256': 'invalid'}),
                    json.dumps({**self.metadata, 'patched_sha256': self.metadata['original_sha256']})):
            with self.subTest(raw=raw):
                self.record.write_text(raw, encoding='utf-8')
                rows = module.observe(self.root, self.comfy)
                self.assertEqual(rows[0]['status'], 'invalid-record')
                self.assertNotIn('PRIVATE_RECORD_SENTINEL', json.dumps(rows))

    def test_large_record_has_a_bounded_read(self):
        module = self.checker()
        self.record.write_bytes(b' ' * (module.MAX_RECORD_BYTES + 1))
        self.assertEqual(module.observe(self.root, self.comfy)[0]['status'], 'invalid-record')

    def test_record_target_cannot_escape_comfy_root(self):
        module = self.checker()
        for target in ('../outside.py', '/outside.py', 'C:/outside.py', r'..\outside.py', 'a/../outside.py'):
            with self.subTest(target=target):
                self.record.write_text(json.dumps({**self.metadata, 'file': target}), encoding='utf-8')
                self.assertEqual(module.observe(self.root, self.comfy)[0]['status'], 'invalid-record')

    def test_symbolic_target_outside_comfy_root_is_not_read(self):
        outside = self.root / 'outside.py'; outside.write_bytes(PATCHED)
        try: self.target.symlink_to(outside)
        except OSError: self.skipTest('Symbolic links unavailable')
        self.observe('unreadable')

    def test_record_count_is_bounded_with_an_explicit_warning(self):
        module = self.checker()
        self.target.write_bytes(PATCHED)
        for number in range(module.MAX_RECORDS):
            (self.records / f'extra-{number}.json').write_text(json.dumps(self.metadata), encoding='utf-8')
        rows = module.observe(self.root, self.comfy)
        self.assertEqual(len(rows), module.MAX_RECORDS + 1)
        self.assertEqual(rows[-1]['status'], 'record-limit')

    def test_missing_record_directory_is_reported_without_creating_it(self):
        self.record.unlink(); self.records.rmdir()
        module = self.checker()
        self.assertEqual(module.observe(self.root, self.comfy)[0]['status'], 'records-unavailable')
        self.assertFalse(self.records.exists())

    def test_launcher_checks_before_startup_admission(self):
        source = (ROOT / 'scripts/Start-Studio.ps1').read_text()
        self.assertIn('check-runtime-patches.py', source)
        self.assertLess(source.index('check-runtime-patches.py'),
                        source.index('$gpuAvailable = Test-StudioGpuLeaseAvailable'))
        self.assertIn('--comfy-root $studioConfig.comfy_root', source)

    def test_detached_warning_contract_uses_a_unique_literal_log_without_piping_the_child(self):
        source = (ROOT / 'scripts/Start-Studio.ps1').read_text()
        self.assertIn('[string]$PatchWarningLog', source)
        warning_path = next(line for line in source.splitlines() if '$detachedWarningLog = ' in line)
        self.assertIn('[guid]::NewGuid()', warning_path)
        command = next(line for line in source.splitlines() if line.strip().startswith('$command ='))
        child_call, failure = command.split(' } catch ', 1)
        self.assertIn('-Detached -PatchWarningLog', child_call)
        self.assertIn('$detachedWarningLog.Replace("\'", "\'\'")', child_call)
        self.assertNotIn('|', child_call); self.assertNotIn('>', child_call)
        self.assertIn("Set-Content -LiteralPath", failure)
        self.assertIn('$detachLog.Replace("\'", "\'\'")', failure)
        self.assertIn('Get-Content -LiteralPath $detachedWarningLog -Encoding UTF8', source)
        self.assertIn('Add-Content -LiteralPath $PatchWarningLog', source)


@unittest.skipUnless(POWERSHELL, 'PowerShell executable required for inert launcher integration')
class RuntimePatchLauncherTests(RuntimePatchFiles, unittest.TestCase):
    def test_warning_does_not_change_launches_and_failed_check_is_nonblocking(self):
        for state in ('original', 'patched', 'unexpected', 'missing', 'checker-failed', 'log-failed'):
            with self.subTest(state=state):
                for directory in ('scripts', 'app', 'config', 'examples/references', 'comfy/input', '.runtime'):
                    (self.root / directory).mkdir(parents=True, exist_ok=True)
                for relative in ('scripts/Start-Studio.ps1', 'scripts/studio-gpu-lease-gate.py',
                                 'scripts/check-runtime-patches.py', 'app/gpu_lease.py'):
                    shutil.copyfile(ROOT / relative, self.root / relative)
                self.target.unlink(missing_ok=True)
                if state != 'missing':
                    self.target.write_bytes({'original': ORIGINAL, 'patched': PATCHED}.get(state, b'changed'))
                if state == 'checker-failed':
                    (self.root / 'scripts/check-runtime-patches.py').write_text('raise SystemExit(1)\n')
                (self.comfy / 'launcher.ps1').write_text('# inert', encoding='utf-8')
                (self.root / 'config/local.json').write_text(json.dumps({'python': sys.executable,
                    'comfy_root': str(self.comfy), 'comfy_url': 'http://127.0.0.1:8188',
                    'comfy_launcher': str(self.comfy / 'launcher.ps1')}), encoding='utf-8')
                wrapper = self.root / 'test.ps1'
                wrapper.write_text(r'''
$ErrorActionPreference = 'Stop'
$global:PatchProbe = @{ comfy = 0; studio = 0; failed = $false; warnings = @() }
$global:PatchWorkspace = $PSScriptRoot
function Write-Warning { param($Message) $global:PatchProbe.warnings += [string]$Message }
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    if ($global:PatchProbe.studio -gt 0 -and $Uri.EndsWith('/api/identity')) {
        return @{ app = 'local-asset-studio'; workspace = $global:PatchWorkspace }
    }
    throw 'Inert offline endpoint'
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
          $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    $global:PatchProbe.studio += 1
    return [pscustomobject]@{ Id = 999; HasExited = $false }
}
function Start-Sleep { param($Seconds) }
function Get-NetTCPConnection { param($LocalAddress, $LocalPort, $State, $ErrorAction) return @() }
function powershell.exe { $global:PatchProbe.comfy += 1; $global:LASTEXITCODE = 0 }
__LOG_FAILURE__
try { & (Join-Path $PSScriptRoot 'scripts/Start-Studio.ps1') -NoBrowser -Detached -PatchWarningLog (Join-Path $PSScriptRoot 'warnings-__STATE__.log') }
catch { $global:PatchProbe.failed = $true }
$global:PatchProbe | ConvertTo-Json -Compress
'''.replace('__STATE__', state).replace('__LOG_FAILURE__',
                    "function Add-Content { throw 'Inert log access failure' }" if state == 'log-failed' else ''), encoding='utf-8')
                before = self.target.read_bytes() if self.target.exists() else None
                result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                         '-File', str(wrapper)], capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outcome = json.loads(result.stdout.strip().splitlines()[-1])
                self.assertEqual((outcome['comfy'], outcome['studio'], outcome['failed']), (1, 1, False), outcome)
                self.assertEqual(bool(outcome['warnings']), state != 'patched', outcome)
                if state not in ('patched', 'checker-failed'):
                    self.assertIn('comfyui-cpu-uv.json', ' '.join(outcome['warnings']))
                    self.assertIn(TARGET, ' '.join(outcome['warnings']))
                log = self.root / f'warnings-{state}.log'
                if state in ('patched', 'log-failed'): self.assertFalse(log.exists())
                else: self.assertEqual(log.read_text(encoding='utf-8-sig').splitlines(), outcome['warnings'])
                self.assertEqual(self.target.read_bytes() if self.target.exists() else None, before)

    def test_hidden_parent_relays_only_this_invocations_warning_log_and_keeps_failure_evidence(self):
        root = self.root / "owner's workspace"  # Both script and log paths must survive single-quoted command literals.
        (root / 'scripts').mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/Start-Studio.ps1', root / 'scripts/Start-Studio.ps1')
        warning = f'ComfyUI runtime patch "comfyui-cpu-uv.json" ("{TARGET}"): patch is not applied.'
        paths = []
        for state in ('warning', 'quiet', 'failure'):
            with self.subTest(state=state):
                wrapper = root / 'test-detached.ps1'
                wrapper.write_text(r'''
$ErrorActionPreference = 'Stop'
$global:FixtureRoot = $PSScriptRoot
$global:ProbeFile = Join-Path $PSScriptRoot 'probe.json'
$global:WmiProbe = @{ warning_path = ''; failure_path = ''; warnings = @(); host_messages = @(); command = '' }
function Save-Probe { [IO.File]::WriteAllText($global:ProbeFile, ($global:WmiProbe | ConvertTo-Json -Depth 5)) }
function Write-Warning { param($Message) $global:WmiProbe.warnings += [string]$Message; Save-Probe }
function Write-Host { param($Object) $global:WmiProbe.host_messages += [string]$Object; Save-Probe }
# Replace only Windows job detection; the real launcher's WMI branch builds and relays its command.
Microsoft.PowerShell.Utility\Add-Type -TypeDefinition @'
namespace StudioLaunch {
    public static class Job {
        public static bool IsProcessInJob(System.IntPtr process, System.IntPtr job, out bool result) { result = true; return true; }
        public static System.IntPtr GetCurrentProcess() { return System.IntPtr.Zero; }
    }
}
'@
function Add-Type { param($Namespace, $Name, $MemberDefinition) }
function New-CimInstance { param($ClassName, [switch]$ClientOnly, $Property) return $Property }
function Get-Process { param($Id, $ErrorAction) return $null }
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    return @{ app = 'local-asset-studio'; workspace = $global:FixtureRoot }
}
function Get-LiteralArgument {
    param($Command, $Parameter)
    for ($i = 0; $i -lt $Command.CommandElements.Count - 1; $i++) {
        $element = $Command.CommandElements[$i]
        if ($element -is [System.Management.Automation.Language.CommandParameterAst] -and $element.ParameterName -eq $Parameter) {
            $value = $Command.CommandElements[$i + 1]
            if ($value -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) { throw 'Log path is not a literal' }
            return $value.Value
        }
    }
    throw ('Missing command parameter: ' + $Parameter)
}
function Invoke-CimMethod {
    param($ClassName, $MethodName, $Arguments)
    $encoded = ($Arguments.CommandLine -split ' ')[-1]
    $command = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($encoded))
    $global:WmiProbe.command = $command
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($command, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw 'Detached command did not parse' }
    $launches = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.CommandAst] -and
        $node.GetCommandName() -eq (Join-Path $global:FixtureRoot 'scripts/Start-Studio.ps1')
    }, $true))
    if ($launches.Count -ne 1 -or $launches[0].Parent.PipelineElements.Count -ne 1 -or $launches[0].Redirections.Count) {
        throw 'Detached child must be one command without an output pipe or redirection'
    }
    $global:WmiProbe.warning_path = Get-LiteralArgument $launches[0] 'PatchWarningLog'
    $failures = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Set-Content'
    }, $true))
    $global:WmiProbe.failure_path = Get-LiteralArgument $failures[0] 'LiteralPath'
    if ('__STATE__' -ne 'quiet') {
        [IO.File]::WriteAllText($global:WmiProbe.warning_path, '__WARNING__' + [Environment]::NewLine)
    }
    if ('__STATE__' -eq 'failure') {
        [IO.File]::WriteAllText($global:WmiProbe.failure_path, 'INERT_CHILD_FAILURE_RETAINED' + [Environment]::NewLine)
    }
    Save-Probe
    # An inert, already-exited hidden child: it emitted nothing to the parent console.
    return @{ ReturnValue = 0; ProcessId = 999 }
}
Save-Probe
& (Join-Path $PSScriptRoot 'scripts/Start-Studio.ps1') -NoBrowser
'''.replace('__STATE__', state).replace('__WARNING__', warning), encoding='utf-8')
                result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                         '-File', str(wrapper)], capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outcome = json.loads((root / 'probe.json').read_text(encoding='utf-8-sig'))
                self.assertEqual(outcome['warnings'], [] if state == 'quiet' else [warning], outcome)
                log = Path(outcome['warning_path']); paths.append(log)
                self.assertEqual(log.parent, root / '.runtime')
                self.assertNotEqual(log, Path(outcome['failure_path']))
                self.assertEqual(log.exists(), state != 'quiet')
                self.assertIn('Asset Studio ready:', ' '.join(outcome['host_messages']))
                if state == 'failure':
                    self.assertIn('INERT_CHILD_FAILURE_RETAINED', ' '.join(outcome['host_messages']))
                    self.assertIn('INERT_CHILD_FAILURE_RETAINED', Path(outcome['failure_path']).read_text())
        self.assertEqual(len(set(paths)), 3, 'Each invocation needs its own warning log; a quiet retry must not repeat stale warnings')
