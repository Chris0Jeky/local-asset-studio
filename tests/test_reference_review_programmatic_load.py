"""Programmatic reference-review loads immediately revoke stale mutation evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ReferenceReviewProgrammaticLoadTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_programmatic_load_disarms_prior_undo_and_receipt_before_await(self):
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
                [
                    shutil.which('node'),
                    str(Path(__file__).with_name('reference_review_programmatic_load.cjs')),
                    str(source),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            'Programmatic reference-review load disarmed prior mutation evidence',
            result.stdout,
        )


if __name__ == '__main__':
    unittest.main()
