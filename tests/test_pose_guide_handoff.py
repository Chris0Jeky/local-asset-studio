"""Pure browser policy checks; real page transport is in pose_editor_handoff_browser.py."""
from pathlib import Path
import shutil
import subprocess
import unittest


class PoseGuideHandoffTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required')
    def test_explicit_replacement_and_response_contract(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('pose_guide_handoff.cjs'))],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('pose guide handoff contracts passed', result.stdout)
