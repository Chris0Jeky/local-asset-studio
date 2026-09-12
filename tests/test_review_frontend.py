import shutil
import subprocess
import unittest
from pathlib import Path


class ReviewFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
    def test_helpers_and_existing_entry_point(self):
        root=Path(__file__).parents[1]
        for name in ('review.js','production.js'):
            subprocess.run(['node','--check',str(root/'app/static'/name)],check=True,capture_output=True,text=True)
        result=subprocess.run(['node',str(root/'tests/review_frontend.cjs')],check=True,capture_output=True,text=True)
        self.assertIn('contracts passed',result.stdout)
