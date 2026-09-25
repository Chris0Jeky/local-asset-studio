"""Run library context contracts over the shipped JavaScript without a browser."""
import shutil
import subprocess
import unittest
from pathlib import Path


class AssetLibraryFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_selection_and_filter_contracts(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('asset_library_contracts.cjs'))],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Asset library contracts: 32 passed, 0 failed', result.stdout)
