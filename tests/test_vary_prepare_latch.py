"""Vary prepare latch, readiness busy flag, and recipe check. Offline."""
import shutil
import subprocess
import unittest
from pathlib import Path


class VaryPrepareLatchTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_vary_prepare_does_not_stick_or_skip_the_recipe_check(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/vary_prepare_latch.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("fail 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
