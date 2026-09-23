"""Canonical storage key order must not change editor value equality."""
from pathlib import Path
import shutil
import subprocess
import unittest


class CollectionRecoveryFieldOrder(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_reloaded_values_use_field_equality(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('collection_recovery_field_order.cjs'))],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"passed":2', result.stdout)
