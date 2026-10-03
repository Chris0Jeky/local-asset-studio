"""The actual Look click handler must not publish a delayed response into a new draft."""
from pathlib import Path
import shutil
import subprocess
import unittest


class LookPreparationOwnershipTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for shipped JavaScript checks')
    def test_shipped_preparation_handler_and_shared_admission(self):
        script = Path(__file__).with_name('looks_preparation_ownership.cjs')
        result = subprocess.run([shutil.which('node'), str(script)], capture_output=True,
                                text=True, timeout=30, cwd=script.parent.parent)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('12 passed, 0 failed', result.stdout)
