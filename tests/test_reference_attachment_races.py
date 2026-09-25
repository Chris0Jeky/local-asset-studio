"""Discover the real reference owner's deferred attachment regressions."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js is required for reference contracts")
class ReferenceAttachmentRaceTests(unittest.TestCase):
    def test_reference_attachment_races(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", "--test-reporter=tap", "tests/reference_attachment_races.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("# fail 0", result.stdout)
        self.assertIn("# tests 16", result.stdout)
