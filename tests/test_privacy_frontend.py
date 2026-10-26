"""Run the shipped privacy controller's causal browser contracts in discovery."""
import pathlib
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for browser contracts')
class PrivacyFrontendTests(unittest.TestCase):
    def test_privacy_contracts(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root / 'tests/privacy_frontend.cjs')],
                                cwd=root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Privacy browser contracts passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
