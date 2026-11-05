"""Executable frontend contracts included in the ordinary offline suite."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ProceduralFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_preparation_and_results(self):
        root=Path(__file__).resolve().parents[1]
        result=subprocess.run(['node','tests/procedural_frontend.cjs'],cwd=root,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
