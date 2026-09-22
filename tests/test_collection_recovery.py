"""Bounded collection recovery and exact receipt identity, no browser required."""
from pathlib import Path
import shutil
import subprocess
import unittest


class CollectionRecovery(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_journal_contracts(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('collection_recovery_contracts.cjs'))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"passed":21', result.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_editor_recovery_contracts(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('collection_recovery_editor_contracts.cjs'))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"passed":19', result.stdout)
