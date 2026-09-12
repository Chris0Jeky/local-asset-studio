import shutil
import subprocess
import unittest
from pathlib import Path


class GalleryHandoffTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_gallery_lineage_and_reference_roles_survive_save_and_submit(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('frontend_handoffs.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
