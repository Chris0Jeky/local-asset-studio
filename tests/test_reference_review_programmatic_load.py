"""Programmatic reference-review loads suspend stale evidence until they commit."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ReferenceReviewProgrammaticLoadTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_programmatic_load_suspends_restores_and_commits_evidence(self):
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
            'Programmatic reference-review loads suspend, restore, and commit evidence correctly',
            result.stdout,
        )


if __name__ == '__main__':
    unittest.main()
