"""Run no-browser state contracts in the regular offline suite."""
import shutil
import subprocess
import unittest
from pathlib import Path


class AssetDetailContracts(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend contracts')
    def test_asset_detail_session_contracts(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('asset_detail_contracts.cjs'))],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Asset detail contracts passed: 17', result.stdout)
