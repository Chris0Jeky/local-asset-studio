"""Known-prompt observation is not new-work admission (#608); no real backend."""
import copy
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

import test_server as fixtures

FakeStudio, server = fixtures.FakeStudio, fixtures.server
from test_reference_hold_observation_admission import HeldReferenceJobs, Worker


class OrdinaryObservationAdmissionTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    tearDown = fixtures.ServerTests.tearDown

    def fixture(self, status='uncertain', submission_status='observing', batch=1):
        studio = FakeStudio(self.root, [])
        job = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {}, 'batch_count': batch}, enqueue=False)['id']]
        job.update(status=status, message='Retained original outcome', prompt_ids=['retained'],
                   submissions=[{'index': 0, 'prompt_id': 'retained', 'seed': 1,
                                 'graph': job['graph'], 'status': submission_status}])
        studio._save(job)
        studio.reference_jobs = HeldReferenceJobs()
        return studio, job

    def test_ordinary_known_observation_bypasses_hold_and_only_reads_history(self):
        for state in ('uncertain', 'partial'):
            with self.subTest(state=state):
                studio, job = self.fixture(state)
                studio.replies = iter([{'retained': {'status': {'status_str': 'success'}, 'outputs': {}}}])
                result = studio.resume_job(job['id'])
                self.assertEqual(result['status'], 'queued')
                self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
                with patch.object(studio, 'host_commit_preflight', side_effect=AssertionError('observation is not admission')):
                    studio._resume(job)
                self.assertEqual(job['status'], 'completed')
                self.assertEqual(studio.reference_jobs.calls, 0)
                self.assertEqual(studio.requests, [(('/history/retained',), {'timeout': 15, 'base_url': 'http://127.0.0.1:8188'})])
                self.assertEqual(job['prompt_ids'], ['retained'])
                self.assertNotIn('pending_submission', job)

    def test_terminal_receipts_reconcile_under_hold_without_backend_requests(self):
        for batch, expected in ((1, 'completed'), (3, 'partial')):
            with self.subTest(batch=batch):
                studio, job = self.fixture('partial', 'completed', batch)
                studio.resume_job(job['id'])
                self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
                studio._resume(job)
                self.assertEqual(job['status'], expected)
                if expected == 'partial':
                    self.assertEqual(job['message'], 'Retained original outcome')
                self.assertEqual(studio.requests, [])
                self.assertEqual(studio.reference_jobs.calls, 0)

    def test_restart_and_lost_history_preserve_known_identity_without_replay(self):
        studio, job = self.fixture()
        restarted = FakeStudio(self.root, [URLError('history unavailable')])
        restarted.reference_jobs = HeldReferenceJobs()
        restarted.resume_job(job['id'])
        self.assertEqual(restarted.queue.get_nowait(), ('observe', job['id']))
        restored = restarted.jobs[job['id']]
        restarted._resume(restored)
        self.assertEqual(restored['status'], 'uncertain')
        self.assertEqual(restored['prompt_ids'], ['retained'])
        self.assertEqual(restarted.requests, [(('/history/retained',), {'timeout': 15, 'base_url': 'http://127.0.0.1:8188'})])
        self.assertEqual(restarted.reference_jobs.calls, 0)

    def test_unsafe_or_unknown_records_do_not_bypass_the_hold(self):
        cases = [
            {'pending_submission': {}}, {'pending_submission': None},
            {'status': 'abandoned'}, {'status': 'queued'}, {'status': 'running'},
            {'prompt_ids': []}, {'prompt_ids': ['other']}, {'prompt_ids': ['retained', 'retained']},
            {'submissions': []}, {'submissions': [None]},
            {'submissions': [{'prompt_id': ''}]},
            {'submissions': [{'prompt_id': 'retained'}, {'prompt_id': 'retained'}]},
            {'status': 'completed', 'submissions': [{'prompt_id': 'retained', 'status': 'completed'}]},
        ]
        for changed in cases:
            with self.subTest(changed=changed):
                studio, job = self.fixture()
                job.update(copy.deepcopy(changed))
                before = copy.deepcopy(job)
                with self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
                    studio.resume_job(job['id'])
                self.assertEqual(studio.reference_jobs.calls, 1)
                self.assertEqual(job, before)
                self.assertTrue(studio.queue.empty())
                self.assertEqual(studio.requests, [])

    def test_dead_worker_and_backend_switch_still_block_known_observation(self):
        studio, job = self.fixture()
        studio.worker = Worker(False)
        with self.assertRaisesRegex(server.StudioError, 'worker is unavailable'):
            studio.resume_job(job['id'])
        self.assertEqual(studio.reference_jobs.calls, 0)
        studio.worker = Worker(True)
        studio.backends.busy = True
        with self.assertRaisesRegex(server.StudioError, 'backend switch'):
            studio.resume_job(job['id'])
        self.assertTrue(studio.queue.empty())
        self.assertEqual(job['status'], 'uncertain')

    def test_concurrent_resume_has_one_queue_entry_and_one_refusal(self):
        studio, job = self.fixture()
        outcomes = []
        barrier = threading.Barrier(2)
        def resume():
            barrier.wait(timeout=5)
            try:
                outcomes.append(studio.resume_job(job['id'])['status'])
            except ValueError as exc:
                outcomes.append(str(exc))
        # ServerTests replaces Thread.start for inert workers. Restore it only
        # for these two finite, explicitly joined clients.
        self.start.stop()
        try:
            clients = [threading.Thread(target=resume) for _ in range(2)]
            for client in clients: client.start()
            for client in clients:
                client.join(timeout=5)
                self.assertFalse(client.is_alive())
        finally:
            self.start.start()
        self.assertEqual(outcomes.count('queued'), 1, outcomes)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(studio.queue.qsize(), 1)
        self.assertEqual(studio.requests, [])

    def test_public_stopped_capability_matches_dispatch_eligibility(self):
        for state, pending, eligible in (('uncertain', False, True), ('completed', False, False),
                                         ('queued', False, False), ('uncertain', True, False)):
            with self.subTest(state=state, pending=pending):
                studio, job = self.fixture(state)
                job['tracking_disposition'] = {'status': 'stopped', 'reason': 'operator', 'recorded_at': 1.0}
                if pending: job['pending_submission'] = {}
                self.assertEqual(studio.public(job)['can_resume_tracking'], eligible)
                if eligible:
                    self.assertEqual(studio.resume_job(job['id'])['status'], 'queued')
                else:
                    with self.assertRaises(ValueError): studio.resume_job(job['id'])
                    self.assertTrue(studio.queue.empty())

    def test_new_job_and_prepare_remain_blocked_by_hold(self):
        studio, _ = self.fixture()
        before = copy.deepcopy(studio.jobs)
        for method in (studio.prepare, studio.create_job):
            with self.subTest(method=method.__name__), self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
                method({'preset_id': 'demo', 'controls': {}})
        self.assertEqual(studio.jobs, before)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(studio.requests, [])


if __name__ == '__main__':
    unittest.main()
