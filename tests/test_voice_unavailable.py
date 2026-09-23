"""Offline contracts for conservative Voice capability and request failure UX."""
from pathlib import Path
import shutil
import subprocess
import unittest


class VoiceUnavailableTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_unavailable_and_recovery(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', '--test', 'tests/voice_unavailable.cjs'], cwd=root,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
