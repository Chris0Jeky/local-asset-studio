"""Discover the shelf's causal Node contracts in the ordinary offline suite."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend contracts')
class AssetRecoveryShelfContracts(unittest.TestCase):
    def test_codec_storage_and_session(self):
        result = subprocess.run(
            [shutil.which('node'), '--test',
             str(Path(__file__).with_name('asset_recovery_shelf.cjs')),
             str(Path(__file__).with_name('asset_recovery_shelf_session.cjs')),
             str(Path(__file__).with_name('asset_recovery_checkpoint.cjs'))],
            capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
