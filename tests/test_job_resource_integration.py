"""Resource observation must not become generation or persistence authority."""
import copy
import hashlib
import json
import threading
from types import SimpleNamespace as NS
import unittest
from urllib.error import URLError
from unittest.mock import patch

import test_server as fixtures
import test_job_resources as resource_fixtures

START_THREAD = threading.Thread.start


class Recorder:
    def __init__(self, studio, failing=None):
        self.studio = studio; self.failing = failing; self.events = []

    def record(self, kind, value):
        # Retain a copy before deliberately corrupting the collaborator's input.
        self.events.append((kind, copy.deepcopy(value)))
        if kind == 'intent':
            state = json.loads((self.studio.runs / value['job_id'] / 'state.json').read_text())
            assert state['pending_submission']['index'] == value['index']
            assert len([args for args, _ in self.studio.requests if args[0] == '/prompt']) == value['index']
        value.clear()
        if self.failing == kind: raise OSError('synthetic telemetry persistence failure')

    def intent(self, value): self.record('intent', value)
    def accepted(self, value): self.record('accepted', value)
    def finish(self, value): self.record('finish', value)


class JobResourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ServerTests(); self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)

    def run_job(self, observer=True, failing=None, reply=None):
        replies = [{'queue_running': [], 'queue_pending': []},
                   reply if reply is not None else {'prompt_id': 'accepted-once'},
                   {'accepted-once': {'status': {'status_str': 'success'}, 'outputs': {}}}]
        studio = fixtures.FakeStudio(self.fixture.root, replies)
        recorder = Recorder(studio, failing) if observer else None
        studio.resource_observations = recorder
        job = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)['id']]
        studio._run(job)
        saved = json.loads((studio.runs / job['id'] / 'state.json').read_text())
        self.assertEqual(saved['status'], job['status'])
        self.assertEqual(saved['prompt_ids'], job['prompt_ids'])
        return studio, job, recorder, saved

    def test_existing_coordinator_records_durable_intent_response_and_exit(self):
        studio, job, recorder, saved = self.run_job()
        self.assertEqual(job['status'], 'completed')
        self.assertEqual([args[0] for args, _ in studio.requests], ['/queue', '/prompt', '/history/accepted-once'])
        self.assertEqual([kind for kind, _ in recorder.events], ['intent', 'accepted', 'finish'])
        intent, accepted, finished = [value for _, value in recorder.events]
        submitted = studio.requests[1][0][2]['prompt']
        expected = hashlib.sha256(json.dumps(submitted, sort_keys=True, separators=(',', ':'),
                                            ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        self.assertEqual(intent['graph_sha256'], expected)
        self.assertEqual(intent['job_id'], job['id']); self.assertEqual(intent['index'], 0)
        self.assertEqual(accepted['prompt_id'], 'accepted-once')
        self.assertEqual(finished['coordinator_exit_status'], 'completed')
        self.assertNotIn('graph', intent); self.assertNotIn('controls', intent)
        self.assertNotIn('resource_observations', saved)

    def test_observer_failures_and_input_mutation_leave_job_evidence_intact(self):
        for failing in ('intent', 'accepted', 'finish'):
            with self.subTest(failing=failing):
                studio, job, recorder, saved = self.run_job(failing=failing)
                self.assertEqual(job['status'], 'completed')
                self.assertEqual(job['prompt_ids'], ['accepted-once'])
                self.assertEqual(len([args for args, _ in studio.requests if args[0] == '/prompt']), 1)
                self.assertEqual(len(recorder.events), 3)
                self.assertEqual(saved['submissions'][0]['prompt_id'], 'accepted-once')
                self.assertNotIn('pending_submission', saved)

    def test_dropped_reply_preserves_intent_and_does_not_fabricate_acceptance(self):
        studio, job, recorder, saved = self.run_job(reply=URLError('synthetic lost reply'))
        self.assertEqual(job['status'], 'uncertain')
        self.assertEqual(saved['prompt_ids'], [])
        self.assertIn('pending_submission', saved)
        self.assertEqual([kind for kind, _ in recorder.events], ['intent', 'finish'])
        self.assertEqual(recorder.events[-1][1]['coordinator_exit_status'], 'uncertain')
        self.assertEqual([args[0] for args, _ in studio.requests], ['/queue', '/prompt'])

    def test_disabled_observer_keeps_existing_submission_contract(self):
        with patch.object(fixtures.server.job_resources, 'event_snapshot') as snapshot:
            studio, job, recorder, saved = self.run_job(observer=False)
            snapshot.assert_not_called()
        self.assertIsNone(recorder); self.assertEqual(saved['status'], 'completed')
        self.assertEqual(job['prompt_ids'], ['accepted-once'])
        self.assertEqual([args[0] for args, _ in studio.requests], ['/queue', '/prompt', '/history/accepted-once'])

    def test_each_batch_member_binds_the_actual_expanded_graph(self):
        replies = [{'queue_running': [], 'queue_pending': []}]
        for index in range(4):
            replies.extend([{'prompt_id': str(index)}, {str(index): {'status': {'status_str': 'success'}, 'outputs': {}}}])
        studio = fixtures.FakeStudio(self.fixture.root, replies)
        recorder = Recorder(studio); studio.resource_observations = recorder
        job = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {'seed': 12}, 'batch_count': 4}, enqueue=False)['id']]
        studio._run(job)
        posts = [args[2]['prompt'] for args, _ in studio.requests if args[0] == '/prompt']
        intents = [value for kind, value in recorder.events if kind == 'intent']
        self.assertEqual(len(recorder.events), 9)
        self.assertEqual([value['graph_sha256'] for value in intents], [fixtures.server.job_resources.digest(graph) for graph in posts])
        self.assertEqual(len({value['graph_sha256'] for value in intents}), 4)
        self.assertEqual(job['prompt_ids'], ['0', '1', '2', '3'])

    def test_known_response_is_observed_before_core_save_failure_without_replay(self):
        studio = fixtures.FakeStudio(self.fixture.root, [{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'known-before-save'}])
        recorder = Recorder(studio); studio.resource_observations = recorder
        job = studio.jobs[studio.create_job({'preset_id': 'demo'}, enqueue=False)['id']]
        original = studio._save
        def save(value):
            if value['status'] == 'running': raise OSError('synthetic core state write failure')
            return original(value)
        with patch.object(studio, '_save', side_effect=save):
            with self.assertRaises(OSError): studio._run(job)
        saved = json.loads((studio.runs / job['id'] / 'state.json').read_text())
        self.assertIn('pending_submission', saved); self.assertEqual(saved['prompt_ids'], [])
        self.assertEqual(recorder.events[1][1]['prompt_id'], 'known-before-save')
        self.assertEqual(recorder.events[-1][1]['coordinator_exit_status'], 'running')
        studio.record_job_failure(job, OSError('synthetic core state write failure'))
        self.assertEqual(job['status'], 'uncertain'); self.assertEqual(job['prompt_ids'], ['known-before-save'])
        before = copy.deepcopy(recorder.events)
        with self.assertRaises(fixtures.server.StudioError): studio._run(job)
        self.assertEqual(recorder.events, before)
        self.assertEqual([args[0] for args, _ in studio.requests], ['/queue', '/prompt'])

    def test_pending_intent_save_failure_prevents_observer_and_post(self):
        studio = fixtures.FakeStudio(self.fixture.root, [{'queue_running': [], 'queue_pending': []}])
        recorder = Recorder(studio); studio.resource_observations = recorder
        job = studio.jobs[studio.create_job({'preset_id': 'demo'}, enqueue=False)['id']]
        original = studio._save
        def save(value):
            if value.get('pending_submission'): raise OSError('synthetic pending write failure')
            return original(value)
        with patch.object(studio, '_save', side_effect=save):
            with self.assertRaises(OSError): studio._run(job)
        self.assertEqual([kind for kind, _ in recorder.events], ['finish'])
        self.assertEqual([args[0] for args, _ in studio.requests], ['/queue'])

    def test_real_observer_blocked_sample_cannot_block_completed_job(self):
        entered, release = threading.Event(), threading.Event()
        def sampler(*_):
            def sample(): entered.set(); release.wait(5); return resource_fixtures.sample()
            return NS(sample=sample, binding={'fixture': True})
        def thread_factory(**kwargs):
            thread = threading.Thread(**kwargs); thread.start = lambda: START_THREAD(thread)
            return thread
        studio = fixtures.FakeStudio(self.fixture.root, [{'queue_running': [], 'queue_pending': []},
                    {'prompt_id': 'once'}, {'once': {'status': {'status_str': 'success'}, 'outputs': {}}}])
        manager = fixtures.server.job_resources.JobResourceObservations(studio.root, studio.backends,
                    samples=3, sampler_factory=sampler, source_reader=lambda _: {'fixture': True}, thread_factory=thread_factory)
        studio.resource_observations = manager
        job = studio.jobs[studio.create_job({'preset_id': 'demo'}, enqueue=False)['id']]
        request = studio._request
        def dispatch(*args, **kwargs):
            if args[0] == '/prompt': self.assertTrue(entered.wait(5))
            return request(*args, **kwargs)
        try:
            with patch.object(studio, '_request', side_effect=dispatch): studio._run(job)
            self.assertEqual(job['status'], 'completed'); self.assertFalse(manager.last.done.is_set())
            saved = json.loads((studio.runs / job['id'] / 'state.json').read_text())
            self.assertEqual(saved['prompt_ids'], ['once']); self.assertEqual(saved['status'], 'completed')
            self.assertEqual([args[0] for args, _ in studio.requests], ['/queue', '/prompt', '/history/once'])
        finally:
            release.set()
            if manager.thread: manager.thread.join(timeout=5)
        self.assertTrue(manager.last.done.is_set())
        self.assertEqual(json.loads((manager.last.path / 'summary.json').read_text())['sampling']['observed'], 0)


if __name__ == '__main__': unittest.main()
