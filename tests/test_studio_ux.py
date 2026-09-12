"""Dependency-light checks for the additive Studio workflow presentation layer."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StudioUXTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for UX policy checks')
    def test_pure_workflow_policy(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/studio_ux.cjs')],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Studio UX policy checks passed', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for JS syntax checks')
    def test_enhancement_scripts_parse(self):
        for file in (ROOT / 'app/static').glob('studio-*.js'):
            with self.subTest(file=file.name):
                result = subprocess.run([shutil.which('node'), '--check', str(file)],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_existing_tools_use_the_same_shell(self):
        for name in ['index.html', 'av.html', 'voice.html', 'review.html', 'prompt-lab.html']:
            with self.subTest(page=name):
                html = (ROOT / 'app/static' / name).read_text(encoding='utf-8')
                for asset in ['studio.css', 'studio-core.js', 'studio-shell.js']:
                    self.assertEqual(html.count('/static/' + asset), 1)
                self.assertLess(html.index('studio-core.js'), html.index('studio-shell.js'))
        html = (ROOT / 'app/static/index.html').read_text(encoding='utf-8')
        for legacy in ['app.js', 'workspace.js', 'references.js', 'production.js', 'backends.js']:
            self.assertLess(html.index('/static/' + legacy), html.index('studio-workbench.js'))

    def test_no_remote_assets_or_executable_storage_in_new_ui(self):
        for file in (ROOT / 'app/static').glob('studio*'):
            source = file.read_text(encoding='utf-8')
            with self.subTest(file=file.name):
                for forbidden in ['eval(', 'new Function(', '@import ', 'https://', 'http://']:
                    self.assertNotIn(forbidden, source)
