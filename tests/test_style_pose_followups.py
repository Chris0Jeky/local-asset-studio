from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StylePoseFollowupTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for Style + Pose client contracts")
    def test_bundle_and_variant_contracts(self):
        result = subprocess.run(
            [shutil.which("node"), "--test", "tests/style_pose_followups.cjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
