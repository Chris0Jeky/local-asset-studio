"""Register the pose-editor redo Node contract with the required unittest suite."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'tests' / 'pose_editor_redo.cjs'


class PoseEditorRedoContractTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for pose editor contracts')
    def test_pose_editor_redo_contract(self):
        result = subprocess.run(
            [shutil.which('node'), str(CONTRACT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('9 pose editor redo contracts passed.', result.stdout)


if __name__ == '__main__':
    unittest.main()
