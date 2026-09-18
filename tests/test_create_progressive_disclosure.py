"""Create progressive-disclosure contracts; Node is optional outside browser CI."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / 'app/static/create-progressive-disclosure.css'


class CreateProgressiveDisclosureTests(unittest.TestCase):
    def test_shell_loads_the_main_page_assets_once(self):
        shell = (ROOT / 'app/static/studio-shell.js').read_text(encoding='utf-8')
        self.assertEqual(shell.count('/static/create-progressive-disclosure.css'), 1)
        self.assertEqual(shell.count('/static/create-progressive-disclosure.js'), 1)
        self.assertIn('if(isMain)', shell)

    def test_existing_dom_owners_move_into_closed_idempotent_details(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is not available')
        result = subprocess.run([node, str(ROOT / 'tests/create_progressive_disclosure.cjs')], cwd=ROOT,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('contracts passed', result.stdout)

    def test_closed_create_help_is_removed_from_layout(self):
        style = STYLE.read_text(encoding='utf-8')
        self.assertIn('.create-context-help:not([open])>:not(summary)', style)
        self.assertIn('display:none!important', style)


if __name__ == '__main__':
    unittest.main()
