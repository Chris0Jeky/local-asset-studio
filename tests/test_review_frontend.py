import shutil
import subprocess
import unittest
from pathlib import Path


class ReviewFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
    def test_grid_uses_existing_revisioned_assessments(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('review_matrix_frontend.cjs'))],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Review matrix interactions passed',result.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for frontend contracts')
    def test_helpers_and_existing_entry_point(self):
        root=Path(__file__).parents[1]
        for name in ('review.js','production.js'):
            subprocess.run(['node','--check',str(root/'app/static'/name)],check=True,capture_output=True,text=True)
        result=subprocess.run(['node',str(root/'tests/review_frontend.cjs')],check=True,capture_output=True,text=True)
        self.assertIn('contracts passed',result.stdout)
