import shutil
import subprocess
import unittest
from pathlib import Path


class GalleryHandoffTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_readiness_status_distinguishes_pending_offline_and_failure(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('frontend_health.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Readiness status distinguishes', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_gallery_lineage_and_reference_roles_survive_save_and_submit(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('frontend_handoffs.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Gallery handoff contracts passed', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_scene_editor_renders_contract_controls(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('av_frontend.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Scene editor updates drafts', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_voice_recovery_controls_follow_backend_eligibility(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('voice_frontend.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Voice recovery controls require', result.stdout, result.stdout + result.stderr)
