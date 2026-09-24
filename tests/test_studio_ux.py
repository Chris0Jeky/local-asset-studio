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

    def test_profile_recipes_name_real_catalog_presets(self):
        import json
        profiles = json.loads((ROOT / 'research/prompt-studio/profiles.json').read_text(encoding='utf-8'))['profiles']
        known = {p['id'] for p in json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']}
        for profile in profiles:
            with self.subTest(profile=profile['id']):
                self.assertTrue(profile['summary'].strip(), 'Every profile explains itself in one sentence')
                self.assertLessEqual(len(profile['recipes']), 8, 'The transfer carries at most eight recipe names')
                self.assertEqual(len(set(profile['recipes'])), len(profile['recipes']))
                for recipe in profile['recipes']:
                    self.assertIn(recipe, known, 'A named recipe must exist in the catalog')

    def test_no_remote_assets_or_executable_storage_in_new_ui(self):
        for file in (ROOT / 'app/static').glob('studio*'):
            source = file.read_text(encoding='utf-8')
            with self.subTest(file=file.name):
                for forbidden in ['eval(', 'new Function(', '@import ', 'https://', 'http://']:
                    self.assertNotIn(forbidden, source)


class StudioUXLoadOrderTests(unittest.TestCase):
    def test_pages_load_studio_core_before_scripts_that_use_it(self):
        # prompt-lab.js used to load first; its profile fetch could resolve before studio-core.js arrived
        # and leave "StudioUX is not defined" as the page status (24 Sep 2026 QA).
        import re
        static = ROOT / 'app/static'
        for page in sorted(static.glob('*.html')):
            scripts = re.findall(r'<script src="([^"]+)"', page.read_text(encoding='utf-8'))
            names = [s.rsplit('/', 1)[-1] for s in scripts]
            # Direct `StudioUX.x` uses need the core first; `window.StudioUX?.x` tolerates its absence. Pages without
            # the core (workflow-studio) reach studio-shell's use only on the main page, so only ordering is checked.
            users = [n for n in names if n != 'studio-core.js' and (static / n).is_file() and re.search(r'(?<![\w.])StudioUX\.', (static / n).read_text(encoding='utf-8'))]
            if not users or 'studio-core.js' not in names: continue
            with self.subTest(page=page.name):
                self.assertLess(names.index('studio-core.js'), min(names.index(n) for n in users), names)
