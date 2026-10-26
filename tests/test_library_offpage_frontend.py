"""Exercise Library consumers against off-page, missing and racing observations."""
import shutil
import subprocess
import unittest
from pathlib import Path


class LibraryOffPageFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_off_page_consumers(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('library_offpage_frontend.cjs'))],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'Library off-page contracts: \d+ passed, 0 failed')
