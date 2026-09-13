"""Offline browser-core and actual-script wiring contracts (Node, not a browser)."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required for UI contracts')
class SavedRunUIContracts(unittest.TestCase):
    def test_exact_review_and_ui_wiring(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', '--test', 'tests/workflow_saved_run_core.cjs',
                                 'tests/workflow_saved_runs_ui.cjs'], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
