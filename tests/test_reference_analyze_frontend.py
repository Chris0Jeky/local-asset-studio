"""Browser Analyze contracts use actual source, simulated transport, and real job fixtures."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ReferenceAnalyzeFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_explicit_analysis_and_recovery_no_replay(self):
        import test_reference_jobs as fixtures
        fixture=fixtures.ReferenceJobTests();fixture.setUp();fixture.start.stop()
        try:
            # Windows subprocess pipes use reader threads. Fixture worker blocking
            # must not suppress those threads (POSIX selectors hid this failure).
            import threading
            ran=threading.Event();reader=threading.Thread(target=ran.set);reader.start();reader.join(2)
            self.assertTrue(ran.is_set(),'Subprocess reader threads must be able to start')
            caps=fixture.service.capabilities();fixture.create();fixture.run_one()
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'fixture.json'
                path.write_text(json.dumps({'capabilities':caps,'completed':fixture.get(),'images':fixture.images}),encoding='utf-8')
                result=subprocess.run([shutil.which('node'),str(ROOT/'tests/reference_analyze_panel.cjs'),str(path)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('storage refusal passed',result.stdout)
        finally:fixture.tearDown();fixture.doCleanups()

    def test_analyze_loads_after_existing_draft_and_review_owners(self):
        page=(ROOT/'app/static/prompt-lab.html').read_text(encoding='utf-8')
        self.assertIn('id="ra-start"',page)
        self.assertLess(page.index('src="/reference-review.js"'),page.index('src="/reference-analyze.js"'))
        source=(ROOT/'app/static/reference-review.js').read_text(encoding='utf-8')
        self.assertIn('StudioReferenceReview',source)

if __name__=='__main__':unittest.main()
