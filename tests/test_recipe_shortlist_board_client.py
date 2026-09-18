"""Browser response contracts for Restyle style-board candidates."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RestyleBoardClientTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for shortlist browser contracts")
    def test_board_candidate_contract(self):
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/recipe_shortlist_board_client.cjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
