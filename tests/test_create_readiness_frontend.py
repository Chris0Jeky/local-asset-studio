"""Execute Create's shipped readiness and inspection code without a browser or GPU."""
import shutil
import subprocess
import unittest
from pathlib import Path


class CreateReadinessFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend contracts')
    def test_readiness_and_scoped_inspection(self):
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('create_readiness_contracts.cjs'))],capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Create readiness contracts: 12 passed, 0 failed',result.stdout)
