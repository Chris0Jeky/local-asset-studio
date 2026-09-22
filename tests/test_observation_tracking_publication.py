"""Stopped-tracking Resume keeps consent live until observation publication (#716)."""
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import test_server as fixtures
import test_observation_resume_persistence as persistence
import test_reference_hold_observation_admission as holds


class TrackingPublicationTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    tearDown = fixtures.ServerTests.tearDown

    def fixture(self):
        studio, job = persistence.ObservationResumePersistenceTests.fixture(self)
        studio.stop_tracking(job['id'], 'Pause while reviewing retained evidence')
        directory = studio.runs / job['id']
        self.immutable = {name: (directory / name).read_bytes()
                          for name in ('recipe.json', 'workflow.json')}
        self.graph = job['graph']
        return studio, job, directory / 'state.json'

    def assert_retained(self, studio, job, before):
        for key, value in before.items():
            if key not in ('status', 'message', 'tracking_disposition'):
                self.assertEqual(job[key], value, key)
        self.assertIs(job['graph'], self.graph)
        for name, value in self.immutable.items():
            self.assertEqual((studio.runs / job['id'] / name).read_bytes(), value)
        self.assertEqual(studio.reference_jobs.calls, 0)
        self.assertEqual(studio.requests, [])

    def assert_retry(self, studio, job, before):
        history = studio._tracking_history(before)
        self.assertEqual(studio.resume_job(job['id'])['status'], 'queued')
        disposition = job['tracking_disposition']
        self.assertEqual(disposition['status'], 'resumed')
        self.assertEqual(disposition['history'][:-1], history)
        self.assertEqual(disposition['history'][-1]['status'], 'resumed')
        self.assertEqual(disposition['event_id'], before['tracking_disposition']['event_id'])
        self.assertEqual(studio.tracking_stop_tokens(job), studio.tracking_stop_tokens(before))
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
        self.assertTrue(studio.queue.empty())
        self.assert_retained(studio, job, before)

    def test_file_sync_failure_keeps_stop_consent_and_history_retryable(self):
        studio, job, state = self.fixture()
        before, raw = copy.deepcopy(job), state.read_bytes()
        with patch('os.fsync', side_effect=OSError('injected file sync failure')):
            with self.assertRaisesRegex(OSError, 'file sync failure'):
                studio.resume_job(job['id'])
        self.assertEqual(job, before)
        self.assertEqual(state.read_bytes(), raw)
        self.assertFalse(list(state.parent.glob('state.json.*.tmp')))
        self.assertTrue(studio.queue.empty())
        self.assert_retained(studio, job, before)
        self.assert_retry(studio, job, before)

    def test_failed_parent_barrier_does_not_consume_live_consent(self):
        studio, job, state = self.fixture()
        before = copy.deepcopy(job)
        with patch.object(studio, '_sync_parent_directory', side_effect=OSError('injected parent barrier')) as sync:
            with self.assertRaisesRegex(OSError, 'parent barrier'):
                studio.resume_job(job['id'])
        sync.assert_called_once_with(state.parent)
        self.assertEqual(job, before)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(json.loads(state.read_bytes())['tracking_disposition']['status'], 'resumed')
        self.assertFalse(list(state.parent.glob('state.json.*.tmp')))
        self.assert_retained(studio, job, before)
        self.assert_retry(studio, job, before)

    def test_exception_after_successful_publication_still_requires_explicit_retry(self):
        studio, job, state = self.fixture()
        before = copy.deepcopy(job)
        publish = studio._write_observation_state

        def publish_then_fail(path, value):
            publish(path, value)
            raise OSError('injected after publication')

        with patch.object(studio, '_write_observation_state', side_effect=publish_then_fail):
            with self.assertRaisesRegex(OSError, 'after publication'):
                studio.resume_job(job['id'])
        self.assertEqual(job, before)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(json.loads(state.read_bytes())['status'], 'queued')
        self.assert_retry(studio, job, before)

    def test_replacement_failure_keeps_disk_and_live_history(self):
        studio, job, state = self.fixture()
        before, raw = copy.deepcopy(job), state.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('injected replacement failure')):
            with self.assertRaisesRegex(OSError, 'replacement failure'):
                studio.resume_job(job['id'])
        self.assertEqual(job, before)
        self.assertEqual(state.read_bytes(), raw)
        self.assertFalse(list(state.parent.glob('state.json.*.tmp')))
        self.assertTrue(studio.queue.empty())
        self.assert_retry(studio, job, before)

    def test_parent_barrier_precedes_live_disposition_and_queue_publication(self):
        studio, job, state = self.fixture()
        before = copy.deepcopy(job)
        original = studio._sync_parent_directory

        def observe_barrier(parent):
            self.assertEqual(parent, state.parent)
            self.assertEqual(job, before)
            self.assertTrue(studio.queue.empty())
            published = json.loads(state.read_bytes())
            self.assertEqual(published['status'], 'queued')
            self.assertEqual(published['tracking_disposition']['status'], 'resumed')
            return original(parent)

        with patch.object(studio, '_sync_parent_directory', side_effect=observe_barrier) as sync:
            self.assert_retry(studio, job, before)
        sync.assert_called_once_with(state.parent)

    def test_repeated_stop_history_is_preserved_and_duplicate_resume_is_refused(self):
        studio, job, state = self.fixture()
        first_stop = copy.deepcopy(job['tracking_disposition'])
        # Prepare an earlier stop/resume cycle through the real public commands.
        studio.resume_job(job['id'])
        studio.queue.get_nowait()
        job['status'] = 'uncertain'
        studio._save(job)
        studio.stop_tracking(job['id'], 'Pause again without losing the first event')
        before = copy.deepcopy(job)
        self.assertEqual(studio._tracking_history(before)[0], first_stop)
        self.assert_retry(studio, job, before)
        after, raw = copy.deepcopy(job), state.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Reference analysis may still own resources'):
            studio.resume_job(job['id'])
        self.assertEqual(job, after)
        self.assertEqual(state.read_bytes(), raw)
        self.assertTrue(studio.queue.empty())

    def test_concurrent_retry_publishes_one_resume_event_and_one_queue_item(self):
        studio, job, _ = self.fixture()
        before = copy.deepcopy(job)
        entered, release, second_attempting = threading.Event(), threading.Event(), threading.Event()
        outcomes, barrier_calls = [], []
        original = studio._sync_parent_directory

        def barrier(parent):
            barrier_calls.append(parent)
            if len(barrier_calls) == 1:
                entered.set()
                if not release.wait(5):
                    raise AssertionError('First barrier was not released')
                raise OSError('first barrier failed')
            return original(parent)

        def caller(second=False):
            if second:
                second_attempting.set()
            try:
                outcomes.append(studio.resume_job(job['id']))
            except BaseException as exc:
                outcomes.append(exc)

        # The fixture suppresses background Studio workers; only these callers run.
        self.start.stop()
        threads = [threading.Thread(target=caller), threading.Thread(target=caller, args=(True,))]
        with patch.object(studio, '_sync_parent_directory', side_effect=barrier):
            try:
                threads[0].start()
                self.assertTrue(entered.wait(5))
                threads[1].start()
                self.assertTrue(second_attempting.wait(5))
            finally:
                release.set()
                for thread in threads:
                    if thread.ident is not None:
                        thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(barrier_calls), 2)
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(sum(isinstance(row, OSError) for row in outcomes), 1)
        self.assertEqual([row['status'] for row in outcomes if isinstance(row, dict)], ['queued'])
        self.assertEqual(job['tracking_disposition']['history'][:-1], studio._tracking_history(before))
        self.assertEqual(studio.queue.get_nowait(), ('observe', job['id']))
        self.assertTrue(studio.queue.empty())
        self.assert_retained(studio, job, before)

    def test_restart_after_uncertain_publication_keeps_history_without_queue_replay(self):
        studio, job, state = self.fixture()
        with patch.object(studio, '_sync_parent_directory', side_effect=OSError('barrier uncertain')):
            with self.assertRaisesRegex(OSError, 'barrier uncertain'):
                studio.resume_job(job['id'])
        retained = json.loads(state.read_bytes())
        recovered = fixtures.FakeStudio(self.root, [])
        after = recovered.jobs[job['id']]
        self.assertEqual(after['status'], 'uncertain')
        self.assertEqual(after['tracking_disposition'], retained['tracking_disposition'])
        self.assertEqual(after['prompt_ids'], job['prompt_ids'])
        self.assertEqual(after['submissions'], job['submissions'])
        self.assertTrue(recovered.queue.empty())
        with patch.object(recovered, '_write_observation_state', wraps=recovered._write_observation_state) as publish:
            self.assertEqual(recovered.resume_job(job['id'])['status'], 'queued')
        publish.assert_called_once()
        self.assertEqual(after['tracking_disposition'], retained['tracking_disposition'])
        self.assertEqual(recovered.queue.get_nowait(), ('observe', job['id']))
        self.assertTrue(recovered.queue.empty())
        self.assertEqual(recovered.requests, [])

    def test_dead_worker_does_not_consume_stop_consent_or_attempt_publication(self):
        studio, job, state = self.fixture()
        before, raw = copy.deepcopy(job), state.read_bytes()
        studio.worker = holds.Worker(False)
        with patch.object(studio, '_write_observation_state') as publish:
            with self.assertRaisesRegex(fixtures.server.StudioError, 'worker is unavailable'):
                studio.resume_job(job['id'])
        publish.assert_not_called()
        self.assertEqual(job, before)
        self.assertEqual(state.read_bytes(), raw)
        self.assertTrue(studio.queue.empty())
        self.assert_retained(studio, job, before)

    def test_invalid_evidence_does_not_attempt_publication(self):
        for change in ({'pending_submission': {}}, {'prompt_ids': []}, {'status': 'abandoned'}):
            with self.subTest(change=change):
                studio, job, state = self.fixture()
                job.update(change)
                before, raw = copy.deepcopy(job), state.read_bytes()
                with patch.object(studio, '_write_observation_state') as publish:
                    with self.assertRaises((fixtures.server.StudioError, ValueError)):
                        studio.resume_job(job['id'])
                publish.assert_not_called()
                self.assertEqual(job, before)
                self.assertEqual(state.read_bytes(), raw)
                self.assertTrue(studio.queue.empty())
                self.assertEqual(studio.requests, [])

    def test_oversized_state_does_not_fall_back_to_the_global_writer(self):
        studio, job, state = self.fixture()
        before, raw = copy.deepcopy(job), state.read_bytes()
        with patch.object(fixtures.server.observation_state, 'MAX_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'byte budget'):
                studio.resume_job(job['id'])
        self.assertEqual(job, before)
        self.assertEqual(state.read_bytes(), raw)
        self.assertTrue(studio.queue.empty())
        self.assert_retry(studio, job, before)

    def test_success_never_rewrites_recipe_or_uses_the_global_writer(self):
        studio, job, _ = self.fixture()
        before = copy.deepcopy(job)
        with patch.object(studio, '_write_json_atomic', side_effect=AssertionError('wrong writer')):
            self.assert_retry(studio, job, before)


if __name__ == '__main__':
    unittest.main()
