"""Operator dispositions publish before acknowledgment and retain retry identity (#716)."""
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import test_server as fixtures
from test_reference_hold_observation_admission import HeldReferenceJobs


class OperatorDispositionPublicationTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    tearDown = fixtures.ServerTests.tearDown

    def fixture(self, kind):
        studio = fixtures.FakeStudio(self.root, [])
        job = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)['id']]
        job.update(status='uncertain', message='Retain original evidence')
        if kind == 'stop':
            job.update(prompt_ids=['known'], submissions=[{'index': 0, 'prompt_id': 'known',
                       'status': 'observing', 'seed': 1, 'graph': job['graph']}])
        elif kind == 'unknown':
            job['pending_submission'] = {'index': 0, 'attempt': 'retained'}
        else:
            job['status'] = 'not_submitted'
        studio._save(job)
        studio.reference_jobs = HeldReferenceJobs()
        directory = studio.runs / job['id']
        self.immutable = {name: (directory / name).read_bytes() for name in ('recipe.json', 'workflow.json')}
        self.graph = job['graph']
        return studio, job, directory / 'state.json'

    @staticmethod
    def invoke(studio, job, kind, reason='Retain this local disposition'):
        if kind == 'stop':
            return studio.stop_tracking(job['id'], reason)
        return studio.abandon_job(job['id'], reason, acknowledge_unknown=kind == 'unknown')

    @staticmethod
    def field(kind):
        return 'tracking_disposition' if kind == 'stop' else 'abandonment'

    def retained(self, studio, job, before):
        for key, value in before.items():
            if key not in ('tracking_disposition', 'status', 'message', 'abandonment'):
                self.assertEqual(job[key], value, key)
        self.assertIs(job['graph'], self.graph)
        for name, value in self.immutable.items():
            self.assertEqual((studio.runs / job['id'] / name).read_bytes(), value)
        self.assertTrue(studio.queue.empty())
        self.assertEqual(studio.requests, [])
        self.assertEqual(studio.reference_jobs.calls, 0)

    def test_prepublication_failures_preserve_live_and_previous_disk_state(self):
        for kind in ('stop', 'never', 'unknown'):
            for seam in ('write', 'fsync', 'replace'):
                with self.subTest(kind=kind, seam=seam):
                    studio, job, state = self.fixture(kind)
                    before, raw = copy.deepcopy(job), state.read_bytes()
                    fault = (patch.object(studio, '_write_observation_state', side_effect=OSError('write failed'))
                             if seam == 'write' else patch('os.fsync', side_effect=OSError('fsync failed'))
                             if seam == 'fsync' else patch.object(Path, 'replace', side_effect=OSError('replace failed')))
                    with fault, self.assertRaisesRegex(OSError, seam):
                        self.invoke(studio, job, kind)
                    self.assertEqual(job, before)
                    self.assertEqual(state.read_bytes(), raw)
                    self.assertFalse(list(state.parent.glob('state.json.*.tmp')))
                    self.retained(studio, job, before)
                    self.invoke(studio, job, kind)
                    self.assertEqual(json.loads(state.read_bytes())[self.field(kind)], job[self.field(kind)])

    def test_visible_replacement_is_not_acknowledged_and_retry_preserves_identity(self):
        for kind in ('stop', 'never', 'unknown'):
            for seam in ('parent', 'after_publish'):
                with self.subTest(kind=kind, seam=seam):
                    studio, job, state = self.fixture(kind)
                    before = copy.deepcopy(job)
                    publish = studio._write_observation_state

                    def publish_then_fail(path, value):
                        publish(path, value)
                        raise OSError('after publish')

                    fault = (patch.object(studio, '_sync_parent_directory', side_effect=OSError('parent failed'))
                             if seam == 'parent' else patch.object(studio, '_write_observation_state', side_effect=publish_then_fail))
                    with fault, self.assertRaises(OSError):
                        self.invoke(studio, job, kind)
                    attempted = json.loads(state.read_bytes())[self.field(kind)]
                    self.assertEqual(job, before)
                    self.retained(studio, job, before)
                    # Readable bytes cannot bypass a still-failing publication barrier.
                    with patch.object(studio, '_sync_parent_directory', side_effect=OSError('still failed')):
                        with self.assertRaisesRegex(OSError, 'still failed'):
                            self.invoke(studio, job, kind)
                    self.assertEqual(job, before)
                    self.assertEqual(json.loads(state.read_bytes())[self.field(kind)], attempted)
                    result = self.invoke(studio, job, kind)
                    self.assertEqual(result[self.field(kind)], attempted)
                    self.assertEqual(self.invoke(studio, job, kind)[self.field(kind)], attempted)
                    self.retained(studio, job, before)

    def test_changed_reason_after_uncertain_publication_cannot_overwrite_event(self):
        for kind in ('stop', 'never', 'unknown'):
            with self.subTest(kind=kind):
                studio, job, state = self.fixture(kind)
                before = copy.deepcopy(job)
                with patch.object(studio, '_sync_parent_directory', side_effect=OSError('uncertain')):
                    with self.assertRaises(OSError): self.invoke(studio, job, kind)
                raw = state.read_bytes()
                with self.assertRaisesRegex(fixtures.server.StudioError, 'reason'):
                    self.invoke(studio, job, kind, 'Different decision')
                self.assertEqual(state.read_bytes(), raw)
                self.assertEqual(job, before)
                self.retained(studio, job, before)

    def test_restart_keeps_attempted_identity_without_queue_or_remote_replay(self):
        for kind in ('stop', 'never', 'unknown'):
            with self.subTest(kind=kind):
                studio, job, state = self.fixture(kind)
                with patch.object(studio, '_sync_parent_directory', side_effect=OSError('uncertain')):
                    with self.assertRaises(OSError): self.invoke(studio, job, kind)
                attempted = json.loads(state.read_bytes())[self.field(kind)]
                restarted = fixtures.FakeStudio(self.root, [])
                restored = restarted.jobs[job['id']]
                self.assertEqual(restored[self.field(kind)], attempted)
                self.assertEqual(self.invoke(restarted, restored, kind)[self.field(kind)], attempted)
                with self.assertRaises(fixtures.server.StudioError):
                    self.invoke(restarted, restored, kind, 'Different decision')
                self.assertTrue(restarted.queue.empty())
                self.assertEqual(restarted.requests, [])

    def test_stop_retry_preserves_all_prior_stop_resume_history(self):
        studio, job, state = self.fixture('stop')
        studio.stop_tracking(job['id'], 'First stop')
        studio.resume_job(job['id'])
        studio.queue.get_nowait()
        job['status'] = 'uncertain'
        studio._save(job)
        history = studio._tracking_history(job)
        with patch.object(studio, '_sync_parent_directory', side_effect=OSError('uncertain')):
            with self.assertRaises(OSError): self.invoke(studio, job, 'stop')
        attempted = json.loads(state.read_bytes())['tracking_disposition']
        self.assertEqual(attempted['history'][:-1], history)
        self.assertEqual(self.invoke(studio, job, 'stop')['tracking_disposition'], attempted)

    def test_concurrent_retry_has_one_event_and_one_acknowledged_disposition(self):
        self.start.stop()  # The Studio worker remains suppressed; permit only explicit callers.
        for kind in ('stop', 'never', 'unknown'):
            with self.subTest(kind=kind):
                # Suppress workers while constructing each fixture.
                with patch.object(threading.Thread, 'start'):
                    studio, job, state = self.fixture(kind)
                entered, release = threading.Event(), threading.Event()
                outcomes, attempted = [], []
                original = studio._sync_parent_directory

                def barrier(parent):
                    if not attempted:
                        attempted.append(json.loads(state.read_bytes())[self.field(kind)])
                        entered.set()
                        if not release.wait(5): raise AssertionError('barrier not released')
                        raise OSError('first attempt uncertain')
                    return original(parent)

                def caller():
                    try: outcomes.append(self.invoke(studio, job, kind))
                    except BaseException as exc: outcomes.append(exc)

                threads = [threading.Thread(target=caller), threading.Thread(target=caller)]
                with patch.object(studio, '_sync_parent_directory', side_effect=barrier):
                    try:
                        threads[0].start()
                        self.assertTrue(entered.wait(5))
                        threads[1].start()
                    finally:
                        release.set()
                        for thread in threads:
                            if thread.ident is not None: thread.join(5)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
                self.assertEqual(len(outcomes), 2)
                self.assertEqual(sum(isinstance(row, OSError) for row in outcomes), 1)
                self.assertEqual([row[self.field(kind)] for row in outcomes if isinstance(row, dict)], attempted)
                self.assertEqual(job[self.field(kind)], attempted[0])
                self.assertTrue(studio.queue.empty())
                self.assertEqual(studio.requests, [])

    def test_retry_refuses_changed_state_instead_of_adopting_foreign_fields(self):
        for kind in ('stop', 'never', 'unknown'):
            with self.subTest(kind=kind):
                studio, job, state = self.fixture(kind)
                before = copy.deepcopy(job)
                with patch.object(studio, '_sync_parent_directory', side_effect=OSError('uncertain')):
                    with self.assertRaises(OSError): self.invoke(studio, job, kind)
                changed = json.loads(state.read_bytes())
                changed['controls']['seed'] = 98765
                state.write_text(json.dumps(changed), encoding='utf-8')
                raw = state.read_bytes()
                with self.assertRaisesRegex(fixtures.server.StudioError, 'changed'):
                    self.invoke(studio, job, kind)
                self.assertEqual(job, before)
                self.assertEqual(state.read_bytes(), raw)

    def test_success_uses_scoped_publication_before_live_change(self):
        for kind in ('stop', 'never', 'unknown'):
            with self.subTest(kind=kind):
                studio, job, state = self.fixture(kind)
                before = copy.deepcopy(job)

                def barrier(parent):
                    self.assertEqual(job, before)
                    self.assertEqual(parent, state.parent)
                    self.assertIn(self.field(kind), json.loads(state.read_bytes()))
                    self.retained(studio, job, before)
                    return False  # Windows explicitly has no parent-directory barrier.

                with patch.object(studio, '_write_json_atomic', side_effect=AssertionError('global writer')), \
                     patch.object(studio, '_sync_parent_directory', side_effect=barrier) as sync:
                    self.invoke(studio, job, kind)
                sync.assert_called_once()
                self.retained(studio, job, before)

    def test_invalid_or_oversized_retained_state_refuses_without_publication(self):
        for kind in ('stop', 'never', 'unknown'):
            for defect in ('duplicate', 'wrong_id', 'overflow', 'oversize'):
                with self.subTest(kind=kind, defect=defect):
                    studio, job, state = self.fixture(kind)
                    before = copy.deepcopy(job)
                    if defect == 'duplicate':
                        state.write_text('{"id":"' + job['id'] + '","id":"' + job['id'] + '"}', encoding='utf-8')
                    elif defect == 'wrong_id': state.write_text('{"id":"another-job"}', encoding='utf-8')
                    elif defect == 'overflow': state.write_text('{"id":"' + job['id'] + '","value":1e999}', encoding='utf-8')
                    raw = state.read_bytes()
                    budget = 1 if defect == 'oversize' else fixtures.server.observation_state.MAX_BYTES
                    with patch.object(fixtures.server.observation_state, 'MAX_BYTES', budget), \
                         patch.object(studio, '_write_observation_state') as publish:
                        with self.assertRaises(fixtures.server.StudioError): self.invoke(studio, job, kind)
                    publish.assert_not_called()
                    self.assertEqual(job, before)
                    self.assertEqual(state.read_bytes(), raw)

    def test_invalid_attempt_identity_cannot_be_reused(self):
        for kind in ('stop', 'never', 'unknown'):
            for defect, value in (('event_id', 'not-an-event'), ('recorded_at', True)):
                with self.subTest(kind=kind, defect=defect):
                    studio, job, state = self.fixture(kind)
                    before = copy.deepcopy(job)
                    with patch.object(studio, '_sync_parent_directory', side_effect=OSError('uncertain')):
                        with self.assertRaises(OSError): self.invoke(studio, job, kind)
                    changed = json.loads(state.read_bytes())
                    changed[self.field(kind)][defect] = value
                    state.write_text(json.dumps(changed), encoding='utf-8')
                    raw = state.read_bytes()
                    with self.assertRaises(fixtures.server.StudioError): self.invoke(studio, job, kind)
                    self.assertEqual(job, before)
                    self.assertEqual(state.read_bytes(), raw)

    def test_concurrent_same_or_different_reasons_do_not_create_a_second_event(self):
        self.start.stop()
        for kind in ('stop', 'never', 'unknown'):
            for different in (False, True):
                with self.subTest(kind=kind, different=different):
                    with patch.object(threading.Thread, 'start'):
                        studio, job, state = self.fixture(kind)
                    entered, release = threading.Event(), threading.Event()
                    outcomes = []
                    original = studio._sync_parent_directory

                    def barrier(parent):
                        entered.set()
                        if not release.wait(5): raise AssertionError('barrier not released')
                        return original(parent)

                    def caller(reason):
                        try: outcomes.append(self.invoke(studio, job, kind, reason))
                        except BaseException as exc: outcomes.append(exc)

                    threads = [threading.Thread(target=caller, args=('First reason',)),
                               threading.Thread(target=caller, args=('Other reason' if different else 'First reason',))]
                    with patch.object(studio, '_sync_parent_directory', side_effect=barrier) as sync:
                        try:
                            threads[0].start()
                            self.assertTrue(entered.wait(5))
                            threads[1].start()
                        finally:
                            release.set()
                            for thread in threads:
                                if thread.ident is not None: thread.join(5)
                    self.assertTrue(all(not thread.is_alive() for thread in threads))
                    self.assertEqual(len(outcomes), 2)
                    sync.assert_called_once()
                    successes = [row[self.field(kind)] for row in outcomes if isinstance(row, dict)]
                    self.assertEqual(len(successes), 1 if different else 2)
                    self.assertTrue(all(row == successes[0] for row in successes))
                    self.assertEqual(sum(isinstance(row, fixtures.server.StudioError) for row in outcomes), int(different))
                    self.assertEqual(json.loads(state.read_bytes())[self.field(kind)], successes[0])


if __name__ == '__main__': unittest.main()
