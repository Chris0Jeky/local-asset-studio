"""Node presentation contracts, included in the normal offline suite."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

class WorkshopFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is unavailable')
    def test_presentation_contracts(self):
        result = subprocess.run(['node', '--test', 'tests/workshop_contracts.cjs'], cwd=ROOT,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
