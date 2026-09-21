"""Ordinary observation publishes durable state before queue ownership (#703)."""
import copy
import json
import threading
import unittest
from unittest.mock import patch

import test_server as fixtures
from test_reference_hold_observation_admission import HeldReferenceJobs


FakeStudio = fixtures.FakeStudio


class ObservationResumePersistenceTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    tearDown = fixtures.ServerTests.tearDown

    def fixture(self, status='uncertain', submission_status='observing', batch=1):
        studio = FakeStudio(self.root, [])
        job = studio.jobs[studio.create_job(
            {'preset_id': 'demo', 'controls': {}, 'batch_count': batch},
            enqueue=False,
        )['id']]
        job.update(
            status=status,
            message='Retained original outcome',
            prompt_ids=['retained'],
            submissions=[{
                'index': 0,
                'prompt_id': 'retained',
                'seed': 1,
                'graph': job['graph'],
                'status': submission_status,
            }],
        )
        studio._save(job)
        studio.reference_jobs = HeldReferenceJobs()
        return studio, job

    @staticmethod
    def state_path(studio, job):
        return studio.runs / job['id'] / 'state.json'

    def test_failure_before_state_replace_keeps_live_and_durable_state_retryable(self):
        studio, job = self.fixture()
        state_path = self.state_path(studio, job)
        before_job = copy.deepcopy(job)
        before_state = state_path.read_bytes()
        original = studio._write_json_atomic

        def fail_before_state(path, value):
            if path.name == 'state.json':
                raise OSError('injected before state replace')
            return original(path, value)

        with patch.object(studio, '_write_json_atomic', side_effect=fail_before_state):
            with self.assertRaisesRegex(OSError, 'before state replace'):
                studio.resume_job(job['id'])

        self.assertEqual(job, before_job)
        self.assertEqual(state_path.read_bytes(), before_state)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(studio.requests, [])

        result = studio.resume_job(job['id'])
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
        self.assertEqual(job['prompt_ids'], ['retained'])
        self.assertEqual(studio.requests, [])

    def test_exception_after_state_replace_is_reconciled_and_queued_once(self):
        studio, job = self.fixture()
        state_path = self.state_path(studio, job)
        recipe_path = state_path.with_name('recipe.json')
        workflow_path = state_path.with_name('workflow.json')
        recipe_before = recipe_path.read_bytes()
        workflow_before = workflow_path.read_bytes()
        graph = job['graph']
        original = studio._write_json_atomic
        injected = []

        def fail_after_state(path, value):
            result = original(path, value)
            if path.name == 'state.json' and not injected:
                injected.append(True)
                raise OSError('injected after state replace')
            return result

        with patch.object(studio, '_write_json_atomic', side_effect=fail_after_state):
            result = studio.resume_job(job['id'])

        self.assertEqual(result['status'], 'queued')
        self.assertEqual(job['status'], 'queued')
        self.assertIs(job['graph'], graph)
        self.assertEqual(job['prompt_ids'], ['retained'])
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
        self.assertTrue(studio.queue.empty())
        self.assertEqual(json.loads(state_path.read_text())['status'], 'queued')
        self.assertEqual(recipe_path.read_bytes(), recipe_before)
        self.assertEqual(workflow_path.read_bytes(), workflow_before)
        self.assertEqual(studio.requests, [])

    def test_terminal_reconciliation_remains_retryable_after_prepublication_failure(self):
        studio, job = self.fixture('partial', 'completed', batch=3)
        state_path = self.state_path(studio, job)
        before_job = copy.deepcopy(job)
        before_state = state_path.read_bytes()
        original = studio._write_json_atomic

        def fail_before_state(path, value):
            if path.name == 'state.json':
                raise OSError('terminal state not published')
            return original(path, value)

        with patch.object(studio, '_write_json_atomic', side_effect=fail_before_state):
            with self.assertRaisesRegex(OSError, 'terminal state not published'):
                studio.resume_job(job['id'])

        self.assertEqual(job, before_job)
        self.assertEqual(state_path.read_bytes(), before_state)
        self.assertTrue(studio.queue.empty())

        studio.resume_job(job['id'])
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
        studio._resume(job)
        self.assertEqual(job['status'], 'partial')
        self.assertEqual(job['message'], 'Retained original outcome')
        self.assertEqual(studio.requests, [])

    def test_two_callers_after_commit_side_failure_still_queue_at_most_once(self):
        studio, job = self.fixture()
        original = studio._write_json_atomic
        injected = []
        injection_lock = threading.Lock()
        outcomes = []
        barrier = threading.Barrier(2)

        def fail_once_after_state(path, value):
            result = original(path, value)
            if path.name == 'state.json':
                with injection_lock:
                    if not injected:
                        injected.append(True)
                        raise OSError('injected after committed state')
            return result

        def resume():
            barrier.wait(timeout=5)
            try:
                outcomes.append(studio.resume_job(job['id'])['status'])
            except Exception as exc:  # bounded clients record the refusal for assertion
                outcomes.append(type(exc).__name__ + ': ' + str(exc))

        self.start.stop()
        try:
            with patch.object(studio, '_write_json_atomic', side_effect=fail_once_after_state):
                clients = [threading.Thread(target=resume) for _ in range(2)]
                for client in clients:
                    client.start()
                for client in clients:
                    client.join(timeout=5)
                    self.assertFalse(client.is_alive())
        finally:
            self.start.start()

        self.assertEqual(outcomes.count('queued'), 1, outcomes)
        self.assertEqual(len(outcomes), 2, outcomes)
        self.assertEqual(studio.queue.qsize(), 1)
        self.assertEqual(job['status'], 'queued')
        self.assertEqual(studio.requests, [])


if __name__ == '__main__':
    unittest.main()
