"""Run the shipped picture undo logic without a browser or generation engine."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class PictureWayBackTests(unittest.TestCase):
    def test_races_template_identity_and_click_edits(self):
        script = Path(__file__).with_name('picture_wayback.cjs')
        result = subprocess.run([shutil.which('node'), str(script)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('4 picture way-back checks passed', result.stdout)
