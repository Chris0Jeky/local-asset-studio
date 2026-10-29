import shutil
import subprocess
import sys
import unittest
from pathlib import Path


class ReviewFrontendTests(unittest.TestCase):
    def test_browser_accepts_only_its_deliberately_stale_save_diagnostic(self):
        from review_matrix_browser import expected_stale_save_only
        url='http://127.0.0.1:1234/api/production/fixture/review'
        error={'url':url,'text':'Failed to load resource: the server responded with a status of 400 (Bad Request)'}
        response={'url':url,'status':400}
        self.assertTrue(expected_stale_save_only([],[],[response],url))
        self.assertTrue(expected_stale_save_only([],[error],[response],url))
        for errors,console,responses in ((['TypeError'],[error],[response]),
                ([],[{**error,'url':url+'/other'}],[response]),
                ([],[{**error,'text':'Unexpected console exception'}],[response]),
                ([],[error,error],[response]),([],[],[]),
                ([],[error],[response,response]),([],[],[{**response,'status':500}])):
            with self.subTest(errors=errors,console=console,responses=responses):
                self.assertFalse(expected_stale_save_only(errors,console,responses,url))

    def test_grid_browser_driver_starts_as_a_standalone_script(self):
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('review_matrix_browser.py')),'--help'],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('--out',result.stdout)

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
