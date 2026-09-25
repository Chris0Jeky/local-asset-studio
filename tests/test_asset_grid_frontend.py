"""Grid identity/focus rules; real DOM behavior lives in asset_grid_browser.py."""
import shutil
import subprocess
import unittest
from pathlib import Path


class AssetGridFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required')
    def test_projection_contracts(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('asset_grid_contracts.cjs'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Asset grid contracts: 11 passed', result.stdout)
