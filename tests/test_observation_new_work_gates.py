"""Public domain commands retain resource admission after #608's read-only split."""
import copy
import shutil
import unittest
from unittest.mock import patch

import test_production as production_fixtures
import test_voice_baseline as voice_fixtures
import test_av_projects as scene_fixtures
import test_reference_jobs as reference_fixtures
from test_reference_hold_observation_admission import HeldReferenceJobs
from test_server import FakeStudio


class NewWorkAdmissionTests(unittest.TestCase):
    def fixture(self, case):
        instance = case()
        instance.setUp()
        self.addCleanup(instance.doCleanups)
        # ReferenceJobTests delegates teardown through ServerTests only in cleanup.
        if case is reference_fixtures.ReferenceJobTests:
            self.addCleanup(reference_fixtures.fixtures.ServerTests.tearDown, instance)
        else:
            self.addCleanup(instance.tearDown)
        return instance

    def test_production_start_and_continuation_keep_hold_and_budget(self):
        fixture = self.fixture(production_fixtures.ProductionTests)
        studio = FakeStudio(fixture.root, [])
        production = studio.production
        project = production.create(fixture.intent())
        studio.reference_jobs = HeldReferenceJobs()
        before = production.get(project['id'])
        with self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
            production.start(project['id'])
        self.assertEqual(production.get(project['id']), before)
        production._mutate(project['id'], status='interrupted')
        before = production.get(project['id'])
        with self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
            production.resume(project['id'])
        self.assertEqual(production.get(project['id']), before)
        self.assertEqual(before['budget']['reserved'], 0)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(studio.requests, [])

    def test_unstarted_voice_resume_is_still_inference_admission(self):
        fixture = self.fixture(voice_fixtures.VoiceTests)
        project = fixture.prepare()
        fixture.production._mutate(project['id'], status='interrupted')
        fixture.studio.reference_jobs = HeldReferenceJobs()
        before = fixture.production.get(project['id'])
        with patch('voice_baseline._run_owned', side_effect=AssertionError('no producer may run')):
            with self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
                fixture.production.resume(project['id'])
        self.assertEqual(fixture.production.get(project['id']), before)
        self.assertTrue(fixture.studio.queue.empty())
        self.assertEqual(fixture.studio.requests, [])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Configured FFmpeg fixture required')
    def test_scene_render_refuses_without_a_new_render_or_queue_item(self):
        fixture = self.fixture(scene_fixtures.SceneTests)
        document = fixture.create()
        fixture.studio.reference_jobs = HeldReferenceJobs()
        before = fixture.studio.production.get(document['id'])
        with self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
            fixture.scenes.request_render(document['id'], {'expected_revision': document['revision']})
        self.assertEqual(fixture.studio.production.get(document['id']), before)
        with fixture.studio.production.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM av_renders').fetchone()[0], 0)
        self.assertTrue(fixture.studio.queue.empty())

    def test_analysis_creation_refuses_a_real_retained_hold(self):
        fixture = self.fixture(reference_fixtures.ReferenceJobTests)
        fixture.create()
        fixture.studio_instance.queue.get_nowait()
        # The real ReferenceJobs writer hashes and retains this state; no helper
        # transport or analysis inference is called by this fixture.
        with fixture.studio_instance.lock, fixture.studio_instance.assets.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = fixture.service._row(db, fixture.payload['request_id'])
            state = fixture.service._state(row)
            state.update(status='uncertain', resource_hold=True)
            fixture.service._save_state(db, fixture.payload['request_id'], state)
        before = fixture.get()
        fixture.payload = copy.deepcopy(fixture.payload)
        fixture.payload['request_id'] = 'second-analysis-request'
        with self.assertRaises(ValueError):
            fixture.create()
        self.assertTrue(fixture.studio_instance.queue.empty())
        self.assertEqual(fixture.calls, [])
        fixture.payload['request_id'] = 'analysis-request-0001'
        self.assertEqual(fixture.get(), before)


if __name__ == '__main__':
    unittest.main()
