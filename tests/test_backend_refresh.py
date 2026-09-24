"""Wire the bounded frontend catalogue reconciliation contracts into discovery."""
import shutil
import subprocess
import unittest
from pathlib import Path


class BackendRefreshContracts(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend contracts')
    def test_current_editor_and_observation_ownership(self):
        result = subprocess.run([shutil.which('node'), '--test', str(Path(__file__).with_name('backend_refresh.cjs'))], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('# fail 0', result.stdout)
