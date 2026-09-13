"""Node contracts for retained tickets and the actual UI event wiring."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required for UI contracts')
class ExecutionUITests(unittest.TestCase):
    def run_contract(self, filename):
        result = subprocess.run(['node', str(Path(__file__).with_name(filename))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    def test_ticket_state(self): self.run_contract('workflow_ticket_state.cjs')
    def test_actual_ui_wiring(self): self.run_contract('workflow_execution_ui.cjs')
