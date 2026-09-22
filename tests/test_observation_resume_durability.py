"""Observation queue ownership requires proven local state durability (#716)."""
import copy
import os
import unittest
from unittest.mock import patch

import test_server as fixtures
import test_observation_resume_persistence as persistence


FakeStudio = fixtures.FakeStudio


class ObservationResumeDurabilityTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    tearDown = fixtures.ServerTests.tearDown
    fixture = persistence.ObservationResumePersistenceTests.fixture
    state_path = staticmethod(persistence.ObservationResumePersistenceTests.state_path)

    def test_file_sync_failure_never_publishes_memory_or_queue(self):
        studio, job = self.fixture()
        state_path = self.state_path(studio, job)
        before_job = copy.deepcopy(job)
        before_state = state_path.read_bytes()

        with patch('os.fsync', side_effect=OSError('injected file sync failure')):
            with self.assertRaisesRegex(OSError, 'file sync failure'):
                studio.resume_job(job['id'])

        self.assertEqual(job, before_job)
        self.assertEqual(state_path.read_bytes(), before_state)
        self.assertTrue(studio.queue.empty())
        self.assertFalse(any(state_path.parent.glob('state.json.*.tmp')))
        self.assertEqual(studio.requests, [])

        result = studio.resume_job(job['id'])
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))

    def test_parent_sync_failure_after_replace_stays_unpublished_and_retryable(self):
        studio, job = self.fixture()
        state_path = self.state_path(studio, job)
        before_job = copy.deepcopy(job)

        with patch.object(
            studio,
            '_sync_parent_directory',
            side_effect=OSError('injected parent sync failure'),
            create=True,
        ) as sync_parent:
            with self.assertRaisesRegex(OSError, 'parent sync failure'):
                studio.resume_job(job['id'])

        sync_parent.assert_called_once_with(state_path.parent)
        self.assertEqual(job, before_job)
        self.assertTrue(studio.queue.empty())
        self.assertFalse(any(state_path.parent.glob('state.json.*.tmp')))
        self.assertEqual(studio.requests, [])

        # The replacement may be visible after a failed directory barrier, but
        # visibility alone did not earn worker ownership. A fresh explicit call
        # must publish and synchronize the same state before queueing it once.
        result = studio.resume_job(job['id'])
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
        self.assertTrue(studio.queue.empty())

    def test_restart_keeps_known_prompt_ids_but_does_not_replay_queue(self):
        studio, job = self.fixture()
        studio.resume_job(job['id'])
        recovered = FakeStudio(self.root, [])
        retained = recovered.jobs[job['id']]
        self.assertEqual(retained['status'], 'uncertain')
        self.assertEqual(retained['prompt_ids'], ['retained'])
        self.assertEqual(retained['submissions'], job['submissions'])
        self.assertTrue(recovered.queue.empty())
        self.assertEqual(recovered.requests, [])

    def test_global_writer_is_not_silently_given_observation_barriers(self):
        studio, job = self.fixture()
        with patch('os.fsync', side_effect=AssertionError('global writer changed')):
            studio._write_json_atomic(self.state_path(studio, job), {'only': 'visibility'})


if __name__ == '__main__':
    unittest.main()
