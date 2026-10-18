"""Run the shipped tutorial tools against disposable public fixtures; never generate."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'docs/adaptive-studio/assets/production'
RECOVER = PRODUCTION / '20261014-recover-fixture-tutorial/seed_recover_tutorial.py'
EXPORT = PRODUCTION / '20261014-export-fixture-tutorial/record_export_tutorial.py'


class TutorialWorkspaceGuards(unittest.TestCase):
    def test_recover_creates_missing_runtime_parent_and_refuses_existing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); repo = root / 'repo'; repo.mkdir()
            (repo / 'config').mkdir(); (repo / 'presets').mkdir()
            (repo / 'config/local.json').write_text('{}')
            (repo / 'presets/catalog.json').write_text(json.dumps({'presets': [
                {'id': 'anima-portrait', 'graph': 'graph.json'}]}))
            (repo / 'graph.json').write_text('{}')
            command = [sys.executable, str(RECOVER), '--repo-root', str(repo),
                       '--evidence', str(root / 'evidence')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            runtime = repo / '.runtime/recover-tutorial'
            snapshot = {p.relative_to(repo): p.read_bytes() for p in repo.rglob('*') if p.is_file()}
            self.assertTrue(runtime.is_dir())
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Never overwrite retained state', result.stderr)
            self.assertEqual(snapshot, {p.relative_to(repo): p.read_bytes() for p in repo.rglob('*') if p.is_file()})

    def run_export(self, repo, output, identity):
        (output.parent / 'PREFLIGHT.json').write_text('{}')
        response = io.BytesIO(json.dumps(identity).encode())
        with patch.object(sys, 'argv', [str(EXPORT), '--repo-root', str(repo), '--output', str(output)]), \
             patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                 'playwright.sync_api': types.SimpleNamespace(sync_playwright=lambda: self.fail('Recording must not start'))}), \
             patch('urllib.request.urlopen', return_value=response) as get, \
             patch('subprocess.check_output', side_effect=RuntimeError('GIT_CHECK_REACHED')) as git, \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(Exception) as caught:
                runpy.run_path(str(EXPORT), run_name='__main__')
            return caught.exception, get.call_args_list, git.call_count

    def test_export_rejects_wrong_workspace_before_files_or_git(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory); output = repo / 'recording'
            error, calls, git_calls = self.run_export(repo, output, {
                'app': 'local-asset-studio', 'workspace': str(repo / 'other'),
                'version': 'production-workspace-1'})
            self.assertIn('workspace', str(error).lower())
            self.assertEqual(git_calls, 0)
            self.assertFalse(output.exists())
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0].args[0].endswith('/api/identity'))

    def test_export_rejects_wrong_app_or_protocol_before_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for app, version in [('other-app', 'production-workspace-1'),
                                 ('local-asset-studio', 'unknown')]:
                with self.subTest(app=app, version=version):
                    output = repo / 'recording'
                    error, _, git_calls = self.run_export(repo, output, {
                        'app': app, 'workspace': str(repo), 'version': version})
                    self.assertIn('identity', str(error).lower())
                    self.assertFalse(output.exists()); self.assertEqual(git_calls, 0)

    def test_export_matching_identity_reaches_source_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory); output = repo / 'recording'
            error, calls, git_calls = self.run_export(repo, output, {
                'app': 'local-asset-studio', 'workspace': str(repo),
                'version': 'production-workspace-1'})
            self.assertEqual(str(error), 'GIT_CHECK_REACHED')
            self.assertEqual(git_calls, 1); self.assertEqual(len(calls), 1)

    def test_export_malformed_or_relative_identity_cannot_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for identity in [None, [], {}, {'app': 'local-asset-studio',
                    'version': 'production-workspace-1', 'workspace': 'relative'}]:
                with self.subTest(identity=identity):
                    output = repo / 'recording'
                    _, calls, git_calls = self.run_export(repo, output, identity)
                    self.assertFalse(output.exists()); self.assertEqual(git_calls, 0)
                    self.assertEqual(len(calls), 1)

    def test_export_unavailable_identity_cannot_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory); output = repo / 'recording'
            with patch.object(sys, 'argv', [str(EXPORT), '--repo-root', str(repo), '--output', str(output)]), \
                 patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'),
                     'playwright.sync_api': types.SimpleNamespace(sync_playwright=lambda: self.fail('Recording must not start'))}), \
                 patch('urllib.request.urlopen', side_effect=OSError('identity unavailable')):
                with self.assertRaisesRegex(OSError, 'identity unavailable'):
                    runpy.run_path(str(EXPORT), run_name='__main__')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
