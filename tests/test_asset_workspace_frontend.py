"""Run actual browser-script scope contracts without a browser/GPU."""
import shutil
import subprocess
import unittest
from pathlib import Path

class AssetWorkspaceFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_scope_contracts(self):
        r=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('asset_workspace_scope.cjs'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('Asset Workspace scope contracts passed: 11',r.stdout)
