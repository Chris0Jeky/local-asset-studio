"""GPU admission before durable workflow intent; real leases, inert backend fakes."""
import copy
import json
import threading
import unittest
from unittest.mock import patch

import test_gpu_lease as lease_fixtures
from test_workflow_document_runs import RunFixture
from studio_workflow import execution
from studio_workflow.core import canonical
from studio_workflow.saved_dispatch import run_saved
from studio_workflow.run_http import PREFIX


def attach_lease(studio):
    manager = lease_fixtures.FakeManager(); manager.active = 'primary'
    manager._local_work = lambda ignore_job_ids=(): any(job.get('status') == 'queued' for job in studio.jobs.values())
    studio.backends = manager
    studio._write_json_atomic = lambda path, value: write_json(path, value)
    now = [10000.0]
    studio.gpu_lease = lease_fixtures.GpuLease(studio, clock=lambda: now[0])
    return now


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


class WorkflowAdmissionTests(RunFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.now = attach_lease(self.runtime)
        self.prepared = self.prepare()
        self.ticket = self.prepared['record']['report']['ticket']
        self.path = self.runtime.runs / 'workflow-requests' / (self.ticket['request_id'] + '.json')

    def hold(self):
        return self.runtime.gpu_lease.acquire({'holder': 'local-qwen', 'ttl_seconds': 600})

    def release(self):
        return self.runtime.gpu_lease.release({'holder': 'local-qwen'})

    def dispatch(self):
        return execution.run_ticket(self.runtime, self.ticket, approved=True)

    def assert_refused(self, call):
        with self.assertRaises(ValueError) as caught: call()
        error = caught.exception
        self.assertEqual(getattr(error, 'code', None), 'gpu_leased')
        self.assertEqual(getattr(error, 'status', None), 409)
        response = error.response()
        self.assertFalse(response['dispatch_attempted'])
        self.assertEqual(response['holder'], 'local-qwen')
        self.assertIn('same ticket', response['recovery'])
        self.assertFalse(self.runtime.jobs); self.assertEqual(self.runtime.submissions, 0)
        self.assertFalse(self.path.exists())

    def test_held_lease_refuses_before_ticket_pins_or_dispatch_intent(self):
        self.hold()
        with patch.object(execution, '_pins', side_effect=AssertionError('No preparation after refusal')):
            self.assert_refused(self.dispatch)

    def test_release_allows_the_original_refused_ticket_once(self):
        self.hold(); self.assert_refused(self.dispatch); self.release()
        first = self.dispatch(); again = self.dispatch()
        self.assertTrue(first['dispatch_attempted']); self.assertTrue(again['replayed'])
        self.assertEqual(self.runtime.submissions, 1)
        self.assertEqual(json.loads(self.path.read_bytes())['ticket'], self.ticket)

    def test_expiry_allows_the_original_refused_ticket(self):
        self.hold(); self.assert_refused(self.dispatch); self.now[0] += 600
        self.assertTrue(self.dispatch()['dispatch_attempted'])
        self.assertEqual(self.runtime.submissions, 1)

    def test_existing_job_recovery_bypasses_lease_admission_and_preserves_intent(self):
        first = self.dispatch(); self.runtime.jobs[first['job']['id']]['status'] = 'completed'
        original = self.path.read_bytes(); self.hold()
        with patch.object(self.runtime.gpu_lease, 'require_available', side_effect=AssertionError('Recovery is not new work')):
            replayed = self.dispatch()
        self.assertTrue(replayed['replayed']); self.assertFalse(replayed['dispatch_attempted'])
        self.assertEqual(self.runtime.submissions, 1); self.assertEqual(self.path.read_bytes(), original)

    def test_orphaned_intent_remains_reconciliation_only_during_lease(self):
        self.dispatch(); self.runtime.jobs.clear(); original = self.path.read_bytes(); self.hold()
        with patch.object(self.runtime.gpu_lease, 'require_available', side_effect=AssertionError('No new admission')):
            replayed = self.dispatch()
        self.assertEqual(replayed['status'], 'reconciliation_required')
        self.assertFalse(replayed['dispatch_attempted']); self.assertEqual(self.runtime.submissions, 1)
        self.assertEqual(self.path.read_bytes(), original)

    def test_corrupt_replay_is_not_misclassified_as_a_fresh_refusal(self):
        self.dispatch(); self.runtime.jobs.clear(); self.hold(); self.path.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'different content'): self.dispatch()
        self.assertEqual(self.runtime.submissions, 1); self.assertEqual(self.path.read_bytes(), b'{}')

    def test_failed_lease_observation_is_not_a_definite_gpu_refusal_or_an_intent(self):
        with patch.object(self.runtime.gpu_lease, 'require_available', side_effect=OSError('state unavailable')):
            with self.assertRaises(OSError): self.dispatch()
        self.assertFalse(self.path.exists()); self.assertEqual(self.runtime.submissions, 0)

    def test_approval_still_precedes_admission(self):
        self.hold()
        with patch.object(self.runtime.gpu_lease, 'require_available', side_effect=AssertionError('No approval')):
            with self.assertRaisesRegex(ValueError, 'Explicit approval'):
                execution.run_ticket(self.runtime, self.ticket, approved=False)
        self.assertFalse(self.path.exists()); self.assertEqual(self.runtime.submissions, 0)

    def test_admission_and_enqueue_hold_the_same_acquisition_lock(self):
        attempts = []; errors = []
        def competing_acquisition():
            entered = self.runtime.lock.acquire(blocking=False)
            try:
                if entered: self.hold()
                attempts.append(entered)
            except BaseException as exc: errors.append(exc)
            finally:
                if entered: self.runtime.lock.release()
        def probe():
            thread = threading.Thread(target=competing_acquisition)
            thread.start(); thread.join(5)
            self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])
        original_check = self.runtime.gpu_lease.require_available
        original_create = self.runtime.create_job
        def check():
            original_check(); probe()
        def create(*args, **kwargs):
            probe(); return original_create(*args, **kwargs)
        with patch.object(self.runtime.gpu_lease, 'require_available', side_effect=check), \
             patch.object(self.runtime, 'create_job', side_effect=create):
            result = self.dispatch()
        self.assertEqual(attempts, [False, False])
        self.assertTrue(result['dispatch_attempted']); self.assertEqual(self.runtime.submissions, 1)
        with self.assertRaises(lease_fixtures.GpuLeaseError) as caught: self.hold()
        self.assertEqual(caught.exception.code, 'studio_work_active')

    def test_saved_dispatch_preserves_definite_admission_refusal(self):
        self.hold()
        approval = {'approved': True, 'record_sha256': self.prepared['record_sha256'],
                    'ticket_sha256': self.prepared['record']['report']['ticket_sha256']}
        self.assert_refused(lambda: run_saved(self.runtime, self.store, self.value['request_id'], approval))
        self.release()
        result = run_saved(self.runtime, self.store, self.value['request_id'], approval)
        self.assertTrue(result['dispatch']['dispatch_attempted'])
        self.assertEqual(self.runtime.submissions, 1)

    def test_post_intent_failure_remains_unknown_and_is_never_retried(self):
        self.runtime.fail_after_job = True
        result = self.dispatch()
        self.assertEqual(result['status'], 'reconciliation_required'); self.assertTrue(result['dispatch_attempted'])
        self.assertTrue(self.path.exists()); self.assertTrue(self.dispatch()['replayed'])
        self.assertEqual(self.runtime.submissions, 1)


class WorkflowAdmissionHttpTests(unittest.TestCase):
    def setUp(self):
        from test_workflow_document_runs_integration import DocumentRunIntegrationTests
        self.fixture = DocumentRunIntegrationTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.studio = self.fixture.studio
        self.now = attach_lease(self.studio)
        status, prepared = self.fixture.request(PREFIX, self.fixture.value)
        self.assertEqual(status, 200, prepared)
        self.prepared = prepared
        self.ticket = prepared['record']['report']['ticket']
        self.intent = self.studio.runs / 'workflow-requests' / (self.ticket['request_id'] + '.json')

    def test_ticket_http_returns_409_without_consuming_the_request(self):
        self.studio.gpu_lease.acquire({'holder': 'local-qwen', 'ttl_seconds': 600})
        body = {'ticket': self.ticket, 'approved': True}
        status, result = self.fixture.request('/api/workflow-studio/run', body)
        self.assertEqual(status, 409, result); self.assertEqual(result['code'], 'gpu_leased')
        self.assertFalse(result['dispatch_attempted']); self.assertEqual(result['holder'], 'local-qwen')
        self.assertFalse(self.intent.exists()); self.assertEqual(self.studio.queue.qsize(), 0)
        self.studio.gpu_lease.release({'holder': 'local-qwen'})
        status, result = self.fixture.request('/api/workflow-studio/run', body)
        self.assertEqual(status, 200, result); self.assertTrue(result['dispatch_attempted'])
        self.assertEqual(self.studio.queue.qsize(), 1)

    def test_saved_http_returns_409_and_reuses_exact_original_record_after_release(self):
        self.studio.gpu_lease.acquire({'holder': 'local-qwen', 'ttl_seconds': 600})
        path = PREFIX + '/prepared-run/run'
        body = {'approved': True, 'record_sha256': self.prepared['record_sha256'],
                'ticket_sha256': self.prepared['record']['report']['ticket_sha256']}
        before = copy.deepcopy(self.prepared['record'])
        status, result = self.fixture.request(path, body)
        self.assertEqual(status, 409, result); self.assertEqual(result['code'], 'gpu_leased')
        self.assertFalse(result['dispatch_attempted']); self.assertFalse(self.intent.exists())
        self.assertEqual(self.studio.queue.qsize(), 0)
        self.assertEqual(self.fixture.request(PREFIX + '/prepared-run')[1]['record'], before)
        self.studio.gpu_lease.release({'holder': 'local-qwen'})
        status, result = self.fixture.request(path, body)
        self.assertEqual(status, 200, result); self.assertTrue(result['dispatch']['dispatch_attempted'])
        self.assertEqual(self.fixture.request(path, body)[1]['dispatch']['replayed'], True)
        self.assertEqual(self.studio.queue.qsize(), 1)
