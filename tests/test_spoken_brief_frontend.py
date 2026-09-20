"""Execute the actual frontend state machine in Node."""
from pathlib import Path
import shutil
import subprocess
import unittest


class SpokenFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_request_ownership_contracts(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'tests/spoken_brief_session.cjs'], cwd=root,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_review_and_playback_races(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'tests/spoken_brief_review_races.cjs'], cwd=root,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
