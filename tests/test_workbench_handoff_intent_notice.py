"""Workbench handoff-intent picture lifecycle; no browser, server, model or generation."""
from pathlib import Path
import shutil
import subprocess
import unittest


class WorkbenchHandoffIntentNoticeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend behavior checks")
    def test_handoff_intent_notice_contract(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/workbench_handoff_intent_notice.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
