"""Run the dependency-free browser tuning policy through the normal test gate."""
from pathlib import Path
import shutil
import subprocess
import unittest


class BundleTuningTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for browser policy tests')
    def test_policy(self):
        result = subprocess.run([shutil.which('node'), '--test', 'tests/bundle_tuning.cjs'],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
