"""The recipe list shows a health pin mismatch without blocking Generate."""
import shutil
import subprocess
import unittest
from pathlib import Path


class PinMismatchBadgeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_pin_mismatch_badges_the_recipe_and_stays_nonblocking(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [shutil.which("node"), "tests/pin_mismatch_badge.cjs"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pin mismatch badge passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
