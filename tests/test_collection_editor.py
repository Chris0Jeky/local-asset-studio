"""Run real-script collection session contracts without a browser."""
import shutil
import subprocess
import unittest
from pathlib import Path

class CollectionEditor(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_session(self):
        self.assertTrue(Path(__file__).with_name('collection_editor_fixture.cjs').is_file(),'the contract requires its inert DOM fixture')
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('collection_editor_contracts.cjs'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('"passed":20',result.stdout)
