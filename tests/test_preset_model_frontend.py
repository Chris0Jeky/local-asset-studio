"""Run the production-JS dependency contracts in ordinary unittest discovery."""
from pathlib import Path
import shutil
import subprocess
import unittest


class PresetModelFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is not installed')
    def test_dependency_and_library_install_controls(self):
        result = subprocess.run(['node', str(Path(__file__).with_name('preset_model_readiness.cjs'))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__': unittest.main()
