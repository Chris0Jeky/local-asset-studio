from pathlib import Path
import json
import shutil
import subprocess
import unittest

from app import server


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

    @unittest.skipUnless(shutil.which("node"), "Node required for bundle key contract")
    def test_bundle_keys_cover_server_controls_except_lineage_inputs(self):
        result = subprocess.run(
            [
                shutil.which("node"),
                "-e",
                "console.log(JSON.stringify(require('./app/static/bundle-core.js').KEYS))",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        bundle_keys = set(json.loads(result.stdout))
        # Reference inputs require the existing asset-lineage handoff and are intentionally
        # rejected by the detached bundle projection rather than silently copied.
        projected_server_keys = set(server.CONTROL_KEYS) - {"reference", "last_reference"}
        self.assertEqual(projected_server_keys - bundle_keys, set())


if __name__ == "__main__":
    unittest.main()
