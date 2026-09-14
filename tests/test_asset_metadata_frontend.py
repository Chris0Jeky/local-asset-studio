"""Run the real-script metadata client contracts in the offline suite."""
import shutil
import subprocess
import unittest
from pathlib import Path

class AssetMetadataFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_revision_and_receipt_contracts(self):
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('asset_metadata_frontend.cjs'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Asset metadata frontend contracts passed: 18',result.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_reload_recovery_contracts(self):
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('asset_recovery_contracts.cjs'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Asset reload recovery contracts passed: 14',result.stdout)
