import shutil
import subprocess
import unittest
from pathlib import Path

class PromptProjectFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_saved_briefs_use_existing_draft_and_review_owners(self):
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('prompt_projects_state.cjs'))],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_panel_journals_before_dispatch_and_preserves_newer_edits(self):
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('prompt_projects_panel.cjs'))],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_project_panel_loads_after_its_draft_owners(self):
        page=(Path(__file__).resolve().parents[1]/'app/static/prompt-lab.html').read_text(encoding='utf-8')
        self.assertIn('id="prompt-projects"',page)
        self.assertGreater(page.index('src="/prompt-projects.js"'),page.index('src="/reference-review.js"'))
if __name__=='__main__':unittest.main()
