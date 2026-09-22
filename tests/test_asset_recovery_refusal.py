"""Exercise the actual editor and journal across refused exact retries."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend contracts')
class AssetRecoveryRefusalTests(unittest.TestCase):
    def test_refused_retry_evidence(self):
        result = subprocess.run([shutil.which('node'), '--test', str(Path(__file__).with_name('asset_recovery_refusal.cjs'))], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
