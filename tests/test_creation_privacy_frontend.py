"""Execute privacy boundaries in the shipped browser owners with inert I/O."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend contracts')
class CreationPrivacyFrontendTests(unittest.TestCase):
    def test_recovery_and_workspace_privacy(self):
        for name in ('creation_privacy_recovery.cjs','creation_privacy_workspace.cjs','creation_privacy_async.cjs'):
            with self.subTest(name=name):
                result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name(name))],
                                      capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
