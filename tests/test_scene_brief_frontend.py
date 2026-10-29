"""Run browser-independent recovery and navigation contracts in the full gate."""
from pathlib import Path
import shutil
import subprocess
import unittest


class BriefFrontendTests(unittest.TestCase):
    def test_recovery_and_navigation(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node is unavailable')
        result=subprocess.run([node,str(Path(__file__).with_name('scene_brief_core.cjs'))],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
