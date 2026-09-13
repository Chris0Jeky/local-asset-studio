"""Node DOM contracts for saved-document ownership; no model runtime."""
from pathlib import Path
import shutil
import subprocess
import unittest


class HistoryScopeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the UI contract')
    def test_copied_and_late_history_are_scoped_to_document(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root / 'tests/workflow_history_scope.cjs')],
                                cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for the UI contract')
    def test_open_response_cannot_rebind_an_inflight_save(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root / 'tests/workflow_open_save_race.cjs')],
                                cwd=root, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
