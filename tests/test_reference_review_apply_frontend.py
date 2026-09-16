"""Successful reference Apply retains its evidence and resets across analyses."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ReferenceReviewApplyFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_apply_retains_diff_and_new_analysis_disarms_old_receipt(self):
        from test_reference_review import ReferenceReviewTests

        fixture = ReferenceReviewTests()
        fixture.setUp()
        payload = {
            'report': fixture.report,
            'review': fixture.review,
            'images': fixture.images,
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'fixture.json'
            source.write_text(json.dumps(payload), encoding='utf-8')
            result = subprocess.run(
                [shutil.which('node'), str(Path(__file__).with_name('reference_review_apply.cjs')), str(source)],
                capture_output=True,
                text=True,
                timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Reference review apply diff and context reset passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
