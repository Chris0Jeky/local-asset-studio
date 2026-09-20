"""Discover deferred reference availability contracts in the offline suite."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for reference contracts')
class ReferenceRestoreObservationTests(unittest.TestCase):
    def test_reference_restore_observations(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which('node'), '--test', 'tests/reference_restore_observations.cjs'],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('# fail 0', result.stdout)
        self.assertIn('# tests 12', result.stdout)
