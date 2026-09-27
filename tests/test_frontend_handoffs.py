import shutil
import subprocess
import unittest
from pathlib import Path


class GalleryHandoffTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_typed_reasons_and_one_shot_requests_survive_polls_and_double_clicks(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('create_input_drafts.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Create input drafts and one-shot requests survive', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_read_polling_is_bounded_and_visibility_aware(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('read_poller.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Read polling contracts passed', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_read_poller_loads_the_real_app_without_generation(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('read_poller_integration.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Read poller app integration passed', result.stdout, result.stdout + result.stderr)

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
    def test_pose_editor_geometry_and_guide_handoff(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('pose_editor_core.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('pose editor geometry checks passed', result.stdout, result.stdout + result.stderr)

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

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_exact_profile_blockers_use_actionable_wording(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('prompt_profile_blockers.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: exact-profile blocker wording', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_quick_review_checks_fit_the_route_and_count_owner_answers(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('review_checks.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Review check contracts passed', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_looks_offer_prepare_and_save_with_reasons(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('looks_frontend.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Look contracts passed', result.stdout, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_comparison_candidates_save_and_count_quick_checks(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('production_review_checks_frontend.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Comparison quick checks save one owner answer per press', result.stdout, result.stdout + result.stderr)


class ProductionClockFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_explicit_time_extension_does_not_resume_or_duplicate(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('production_clock_frontend.cjs'))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Production time extension controls preserve', result.stdout)
