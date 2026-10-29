"""Execute Archive contracts against the shipped Library and recovery scripts."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
class AssetArchiveFrontendTests(unittest.TestCase):
    def test_library_archive_contracts(self):
        result = subprocess.run([shutil.which('node'), '--test', 'tests/asset_archive_frontend.cjs'],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
