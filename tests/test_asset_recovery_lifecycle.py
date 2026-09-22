"""Discover lifecycle frontend contracts in the offline suite."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for lifecycle contracts')
class LifecycleFrontendTests(unittest.TestCase):
    def test_lifecycle_projection_and_read_observer(self):
        result=subprocess.run([shutil.which('node'),'--test',str(Path(__file__).with_name('asset_recovery_lifecycle.cjs'))],capture_output=True,text=True,timeout=40)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
