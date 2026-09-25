"""Direct job admission and GPU acquisition share one lock, not an HTTP I/O lock."""
import io
import json
import threading
import unittest
from unittest.mock import patch

import test_gpu_lease as fixtures


class DirectJobAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ServerLeaseTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.studio = self.fixture.studio
        self.payload = {'preset_id': 'demo', 'controls': {}}
        self.now = [10000.0]
        self.studio.gpu_lease = fixtures.GpuLease(self.studio, clock=lambda: self.now[0])

    def hold(self):
        return self.studio.gpu_lease.acquire({'holder': 'local-qwen', 'ttl_seconds': 600})

    def probe_lock(self, acquire_lease=False):
        """Attempt once on another thread, without sleeps or a retained worker."""
        results = []; errors = []
        def probe():
            entered = self.studio.lock.acquire(blocking=False)
            try:
                if entered and acquire_lease: self.hold()
                results.append(entered)
            except BaseException as exc: errors.append(exc)
            finally:
                if entered: self.studio.lock.release()
        thread = threading.Thread(target=probe, name='job-admission-lease-probe')
        thread.start(); thread.join(5)
        self.assertFalse(thread.is_alive(), 'Lock probe did not finish')
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 1)
        return results[0]

    def handler(self, raw=None):
        handler = fixtures.server.Handler.__new__(fixtures.server.Handler)
        handler.studio = self.studio; handler.path = '/api/jobs'
        body = json.dumps(self.payload).encode() if raw is None else raw
        handler.headers = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191',
                           'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.replies = []
        def reply(status, value):
            self.assertTrue(self.probe_lock(), 'HTTP response must not hold Studio.lock')
            handler.replies.append((status, value))
        handler._json = reply
        return handler

    def assert_empty(self):
        self.assertEqual(self.studio.jobs, {})
        self.assertTrue(self.studio.queue.empty())
        self.assertFalse(any(self.studio.runs.glob('*/state.json')))
        self.assertEqual(self.studio.requests, [])

    def test_acquisition_cannot_cross_final_check_or_job_registration(self):
        handler = self.handler(); attempts = []
        original_check = handler._require_gpu
        original_create = self.studio.create_job
        def check():
            original_check(); attempts.append(self.probe_lock(acquire_lease=True))
        def create(*args, **kwargs):
            attempts.append(self.probe_lock(acquire_lease=True))
            return original_create(*args, **kwargs)
        with patch.object(handler, '_require_gpu', side_effect=check), \
             patch.object(self.studio, 'create_job', side_effect=create):
            handler.do_POST()
        self.assertEqual(attempts, [False, False])
        self.assertEqual(len(handler.replies), 1)
        self.assertEqual(handler.replies[0][0], 201)
        job_id = handler.replies[0][1]['id']
        self.assertEqual(self.studio.queue.get_nowait(), ('generate', job_id))
        self.assertTrue(self.studio.queue.empty())
        self.assertIsNone(self.studio.gpu_lease.active())
        self.assertEqual(self.fixture.process.terminated, 0)
        with self.assertRaises(fixtures.GpuLeaseError) as caught: self.hold()
        self.assertEqual(caught.exception.code, 'studio_work_active')
        self.assertEqual(self.fixture.process.terminated, 0)
        self.assertEqual(self.studio.requests, [])

    def test_lease_acquired_while_body_is_read_wins_without_a_job(self):
        handler = self.handler(); original_body = handler._body_json
        def body():
            result = original_body()
            self.assertTrue(self.probe_lock(acquire_lease=True), 'Body read must be outside Studio.lock')
            return result
        with patch.object(handler, '_body_json', side_effect=body): handler.do_POST()
        self.assertEqual(len(handler.replies), 1)
        status, value = handler.replies[0]
        self.assertEqual((status, value['code'], value['holder']), (409, 'gpu_leased', 'local-qwen'))
        self.assert_empty()

    def test_held_lease_refuses_before_preparation_and_release_allows_one_job(self):
        self.hold(); handler = self.handler()
        with patch.object(self.studio, 'prepare', side_effect=AssertionError('A lease must refuse before preparation')):
            handler.do_POST()
        self.assertEqual(handler.replies[0][0], 409)
        self.assertEqual(handler.replies[0][1]['expires_at'], 10600.0)
        self.assert_empty()
        self.studio.gpu_lease.release({'holder': 'local-qwen'})
        handler = self.handler(); handler.do_POST()
        self.assertEqual(handler.replies[0][0], 201)
        self.assertEqual(len(self.studio.jobs), 1); self.assertEqual(self.studio.queue.qsize(), 1)

    def test_expiry_is_observed_before_admission(self):
        self.hold(); self.now[0] += 600
        handler = self.handler(); handler.do_POST()
        self.assertEqual(handler.replies[0][0], 201)
        self.assertEqual(self.studio.gpu_lease.last_release['reason'], 'expired')
        self.assertEqual(len(self.studio.jobs), 1); self.assertEqual(self.studio.queue.qsize(), 1)

    def test_body_errors_refuse_without_entering_admission(self):
        for raw in (b'{', b'\xff'):
            with self.subTest(raw=raw):
                handler = self.handler(raw)
                with patch.object(handler, '_require_gpu', side_effect=AssertionError('Invalid body reached admission')):
                    handler.do_POST()
                self.assertEqual(handler.replies[0][0], 400)
                self.assert_empty()

    def test_foreign_origin_refuses_before_body_or_admission(self):
        handler = self.handler(); handler.headers['Origin'] = 'https://foreign.invalid'
        with patch.object(handler, '_body_json', side_effect=AssertionError('Unsafe body read')), \
             patch.object(handler, '_require_gpu', side_effect=AssertionError('Unsafe admission')):
            handler.do_POST()
        self.assertEqual(handler.replies[0][0], 403); self.assert_empty()

    def test_validation_and_storage_refusals_release_the_lock(self):
        for error, expected in ((fixtures.server.StudioError('invalid recipe'), 400), (OSError('disk full'), 500)):
            with self.subTest(error=type(error).__name__):
                handler = self.handler()
                with patch.object(self.studio, 'create_job', side_effect=error): handler.do_POST()
                self.assertEqual(handler.replies[0][0], expected)
                self.assert_empty()
                self.assertTrue(self.probe_lock(acquire_lease=True))
                self.studio.gpu_lease.release({'holder': 'local-qwen'})

    def test_response_failure_does_not_enqueue_a_second_job(self):
        handler = self.handler(); original_reply = handler._json; calls = []
        def reply(status, value):
            self.assertTrue(self.probe_lock())
            calls.append(status)
            if status == 201: raise BrokenPipeError('lost response')
            return original_reply(status, value)
        handler._json = reply; handler.do_POST()
        self.assertEqual(calls, [201, 500])
        self.assertEqual(len(self.studio.jobs), 1); self.assertEqual(self.studio.queue.qsize(), 1)
        self.assertTrue(next(self.studio.runs.glob('*/state.json')).is_file())
        self.assertEqual(self.studio.requests, [])
