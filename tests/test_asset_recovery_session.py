"""Run real editor/journal ownership contracts with controllable asynchronous I/O."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for editor contracts')
class AssetRecoverySessionTests(unittest.TestCase):
    def test_request_workspace_and_replacement_ownership(self):
        result = subprocess.run([shutil.which('node'), '--test', str(Path(__file__).with_name('asset_recovery_session.cjs'))], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
