"""Run causal Library paging contracts against the shipped Workspace script."""
import pathlib
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js is required")
class LibraryPageFrontendTests(unittest.TestCase):
    def test_library_page_contracts(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", str(root / "tests/library_page_frontend.cjs")],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"Library page contracts: \d+ passed, 0 failed")


if __name__ == "__main__":
    unittest.main()
