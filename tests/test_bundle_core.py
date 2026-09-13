"""Pure bundle policy checks; no ComfyUI, browser or model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class BundleCoreTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend policy tests")
    def test_frontend_bundle_policy(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/bundle_core.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
