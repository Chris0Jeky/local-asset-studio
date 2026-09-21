"""Node contracts for the browser compatibility selector presenter."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SetupCompatibilitySelectorTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for selector policy contracts")
    def test_selector_policy_contracts(self):
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/setup_compatibility_selector.cjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
