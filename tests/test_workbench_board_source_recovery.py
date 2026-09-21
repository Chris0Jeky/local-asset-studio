"""Board continuation draft and picker lifecycle guards; no browser, ComfyUI or model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class WorkbenchBoardSourceRecoveryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend behavior checks")
    def test_board_source_recovery_contract(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/workbench_board_source_recovery.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
