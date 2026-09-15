import shutil
import subprocess
import unittest
from pathlib import Path


class AddressableFiguresFrontend(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required')
    def test_frontend_contracts(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('addressable_figures_frontend.cjs'))],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Addressable figure frontend contracts: 8 passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
