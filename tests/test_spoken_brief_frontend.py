"""Execute the actual frontend state machine in Node."""
from pathlib import Path
import shutil
import subprocess
import unittest

# A hang guard, not a speed bound. Both scripts finish in about 0.3 s on a warm
# machine, but a hosted Windows runner starts node cold: passing run 36188556409
# took 10.8 s and 4.6 s for them, and run 36185207741 went past 20 s for both
# with nothing hung.
NODE_HANG_SECONDS = 120

class SpokenFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_request_ownership_contracts(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'tests/spoken_brief_session.cjs'], cwd=root,
                                capture_output=True, text=True, timeout=NODE_HANG_SECONDS)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_review_and_playback_races(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', 'tests/spoken_brief_review_races.cjs'], cwd=root,
                                capture_output=True, text=True, timeout=NODE_HANG_SECONDS)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
