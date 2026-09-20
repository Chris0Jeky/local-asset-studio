"""Discover the real reference-owner structural observation contracts."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReferenceStructuralObservationsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend contracts")
    def test_retained_reference_observations(self):
        result = subprocess.run(
            ["node", "--test", "tests/reference_structural_observations.cjs"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, check=False,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        # An empty/self-skipped runner must not vouch for this state-machine contract.
        for summary in ("# tests 15", "# pass 15", "# fail 0", "# skipped 0"):
            self.assertIn(summary, output, output)


if __name__ == "__main__":
    unittest.main()
