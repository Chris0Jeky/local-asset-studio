"""Bound the existing queue wait without touching ComfyUI work or replaying POSTs."""
import copy
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

import test_production as fixtures
from test_server import FakeStudio, server
import submission_evidence


IDLE = {'queue_running': [], 'queue_pending': []}
BUSY = {'queue_running': [[1, 'manual-owner-prompt']], 'queue_pending': []}


class Clock:
    def __init__(self): self.now = 0.; self.sleeps = []
    def monotonic(self): return self.now
    def sleep(self, seconds):
        self.sleeps.append(seconds); self.now += seconds
        if self.now > 65: raise AssertionError('Queue wait exceeded its bounded test clock')
    def module(self): return SimpleNamespace(monotonic=self.monotonic, sleep=self.sleep, time=time.time)


class PreSubmitWaitTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ProductionTests(); self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root; self.studio = FakeStudio(self.root, [])
        self.clock = Clock()
        self.enterContext(patch.object(server, 'time', self.clock.module()))

    def job(self):
        return self.studio.jobs[self.studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)['id']]

    def dispatch(self, *items):
        with patch.object(self.studio.queue, 'get', side_effect=[*items, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt): self.studio._work()

    def assert_unsent(self, job):
        self.assertEqual(job['status'], 'not_submitted')
        self.assertTrue(submission_evidence.never_submitted(job))
        self.assertEqual(job['prompt_ids'], []); self.assertEqual(job['submissions'], [])
        self.assertEqual(job['outputs'], []); self.assertNotIn('pending_submission', job)
        self.assertTrue(self.studio.public(job)['can_abandon'])

    def test_busy_queue_expires_without_post_and_releases_next_worker_item(self):
        job = self.job(); seen = []; original = copy.deepcopy(job['graph'])
        def request(path, **kwargs): seen.append((path, self.clock.now, kwargs)); return copy.deepcopy(BUSY)
        with patch.object(self.studio, '_request', side_effect=request), patch.object(self.studio, '_resume') as observe:
            other = self.job()
            self.dispatch(('generate', job['id']), ('observe', other['id']))
        self.assert_unsent(job); observe.assert_called_once_with(other)
        self.assertIn('busy', job['message']); self.assertIn('Nothing was submitted', job['message'])
        self.assertEqual(job['graph'], original); self.assertLessEqual(self.clock.now, 60)
        self.assertTrue(seen); self.assertTrue(all(p == '/queue' and t < 60 for p, t, _ in seen))
        self.assertTrue(all(0 < kw['timeout'] <= min(10, 60-t) for _, t, kw in seen))

    def test_idle_before_deadline_keeps_original_single_submission_path(self):
        job = self.job(); polls = []; posts = []
        def request(path, *args, **kwargs):
            if path == '/queue': polls.append(self.clock.now); return BUSY if len(polls) == 1 else IDLE
            if path == '/prompt': posts.append(copy.deepcopy(args)); return {'prompt_id': 'known'}
            return {'known': {'status': {'status_str': 'success'}, 'outputs': {}}}
        with patch.object(self.studio, '_request', side_effect=request): self.studio._run(job)
        self.assertEqual(job['status'], 'completed'); self.assertEqual(polls, [0, 2]); self.assertEqual(len(posts), 1)
        self.assertEqual(job['prompt_ids'], ['known'])

    def test_missing_or_malformed_queue_fields_never_mean_idle(self):
        for response in ({}, {'queue_running': []}, {'queue_pending': []},
                         {'queue_running': None, 'queue_pending': []},
                         {'queue_running': [], 'queue_pending': False}, [], None):
            with self.subTest(response=response):
                job = self.job(); calls = []
                def request(path, *args, **kwargs): calls.append(path); return response
                with patch.object(self.studio, '_request', side_effect=request): self.dispatch(('generate', job['id']))
                self.assert_unsent(job); self.assertEqual(calls, ['/queue'])
                self.assertIn('inspect', job['message'].lower())

    def test_transport_failures_release_locally_without_false_remote_uncertainty(self):
        for failure in (URLError('offline'), TimeoutError('read timed out'), IncompleteRead(b'{'),
                        json.JSONDecodeError('bad', '{', 0), UnicodeDecodeError('utf8', b'\xff', 0, 1, 'bad')):
            with self.subTest(failure=type(failure).__name__):
                job = self.job()
                with patch.object(self.studio, '_request', side_effect=failure) as request:
                    self.dispatch(('generate', job['id']))
                self.assert_unsent(job); request.assert_called_once()
                self.assertIn('Nothing was submitted', job['message'])

    def test_expired_idle_reply_and_oversleep_cannot_authorize_a_post(self):
        for late_idle in (True, False):
            with self.subTest(late_idle=late_idle):
                self.clock.now = 0; job = self.job(); calls = []
                def request(path, *args, **kwargs):
                    calls.append(path)
                    if len(calls) > 2: raise AssertionError('Original wait began another read after expiry')
                    if late_idle: self.clock.now = 61; return IDLE
                    return BUSY
                def oversleep(_): self.clock.now = 61
                with patch.object(self.studio, '_request', side_effect=request), patch.object(server.time, 'sleep', side_effect=oversleep):
                    self.dispatch(('generate', job['id']))
                self.assert_unsent(job); self.assertEqual(calls, ['/queue'])

    def test_restart_preserves_recipe_and_does_not_automatically_retry(self):
        job = self.job(); folder = self.studio.runs/job['id']
        originals = {p.name: p.read_bytes() for p in folder.iterdir() if p.name != 'state.json'}
        with patch.object(self.studio, '_request', return_value=BUSY): self.dispatch(('generate', job['id']))
        self.assert_unsent(job)
        restored = FakeStudio(self.root, []); saved = restored.jobs[job['id']]
        self.assertTrue(submission_evidence.never_submitted(saved)); self.assertEqual(saved['status'], 'not_submitted')
        self.assertEqual(restored.requests, []); self.assertEqual(restored.queue.qsize(), 0)
        for name, data in originals.items(): self.assertEqual((folder/name).read_bytes(), data)
        result = restored.abandon_job(job['id'], 'Keep this recipe for another time')
        self.assertEqual(result['abandonment']['basis'], 'never_submitted')

    def test_production_timeout_is_interrupted_reuses_identity_and_keeps_reservations(self):
        lab = self.studio.production; project = lab.create(self.fixture.intent()); lab.start(project['id'])
        budget = copy.deepcopy(lab.get(project['id'])['budget'])
        with patch.object(self.studio, '_request', return_value=BUSY): self.dispatch(('production', project['id']))
        state = lab.get(project['id'])['state']; self.assertEqual(state['status'], 'interrupted')
        self.assertEqual(len(self.studio.jobs), 1)
        job = self.studio.jobs[state['attempts']['0']['job_id']]; self.assert_unsent(job)
        self.assertEqual(lab.get(project['id'])['budget'], budget)
        lab.resume(project['id']); self.clock.now = 0
        with patch.object(self.studio, '_request', return_value=BUSY): self.dispatch(('production', project['id']))
        self.assertEqual(lab.get(project['id'])['state']['status'], 'interrupted')
        self.assertEqual(lab.get(project['id'])['budget'], budget); self.assertEqual(list(self.studio.jobs), [job['id']])
        # A separate, explicit Resume after idle may execute the original stages, not allocate new attempts.
        lab.resume(project['id']); self.clock.now = 0
        self.studio.replies = iter([IDLE, {'prompt_id':'one'}, {'one':{'status':{'status_str':'success'},'outputs':{}}},
                                   IDLE, {'prompt_id':'two'}, {'two':{'status':{'status_str':'success'},'outputs':{}}}])
        with patch.object(lab, 'contact_sheet', return_value=[]): lab.run(project['id'])
        self.assertEqual(lab.get(project['id'])['state']['status'], 'awaiting_review')
        self.assertEqual(lab.get(project['id'])['budget'], budget); self.assertEqual(len(self.studio.jobs), 2)
        self.assertEqual(self.fixture.post_count(self.studio), 2)

    def test_expired_wait_does_not_enqueue_an_automatic_retry(self):
        job = self.job(); polls = []
        def request(path, **kwargs): polls.append(path); return BUSY
        with patch.object(self.studio, '_request', side_effect=request):
            self.dispatch(('generate', job['id']))
            self.assert_unsent(job)
            before = len(polls)
            # Direct _run historically accepts not_submitted for explicit Production re-entry;
            # this test only establishes that timeout itself enqueues no retry.
            self.assertEqual(self.studio.queue.qsize(), 0); self.assertEqual(len(polls), before)

    def test_known_or_pending_submissions_do_not_enter_queue_wait(self):
        for evidence in ({'prompt_ids':['retained']}, {'pending_submission':{}}, {'submissions':None}):
            with self.subTest(evidence=evidence):
                job = self.job(); job.update(evidence); original = copy.deepcopy(job)
                with patch.object(self.studio, '_wait_for_queue') as wait:
                    with self.assertRaises(server.StudioError): self.studio._run(job)
                wait.assert_not_called(); self.assertEqual(job, original)

    def test_real_http_busy_queue_is_read_only_on_retained_backend(self):
        self.fixture.patches[0].stop(); seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(('GET', self.path)); body = json.dumps(BUSY).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_POST(self): seen.append(('POST', self.path)); self.send_error(500)
            def log_message(self, *_): pass
        http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=http.serve_forever); thread.start()
        try:
            job = self.job(); job['comfy_url'] = f'http://127.0.0.1:{http.server_port}'
            with patch.object(self.studio, '_request', side_effect=lambda *a, **kw:server.Studio._request(self.studio, *a, **kw)):
                self.dispatch(('generate', job['id']))
            self.assert_unsent(job); self.assertTrue(seen); self.assertTrue(all(x == ('GET','/queue') for x in seen))
        finally:
            http.shutdown(); http.server_close(); thread.join(3)
        self.assertFalse(thread.is_alive())

    def test_real_consumer_thread_reaches_next_item_without_replacement(self):
        job = self.job(); other = self.job(); observed = []; finished = threading.Event()
        self.fixture.patches[0].stop()
        def observe(value):
            observed.append((value['id'], threading.current_thread())); raise SystemExit
        def consume():
            try: self.studio._work()
            except SystemExit: finished.set()
        worker = threading.Thread(target=consume, daemon=True)
        self.studio.worker = worker
        with patch.object(self.studio, '_request', return_value=BUSY), patch.object(self.studio, '_resume', side_effect=observe):
            self.studio.queue.put(('generate', job['id'])); self.studio.queue.put(('observe', other['id']))
            worker.start(); worker.join(3)
        self.assertTrue(finished.is_set()); self.assertFalse(worker.is_alive())
        self.assertEqual(observed, [(other['id'], worker)]); self.assertIs(self.studio.worker, worker)
        self.assert_unsent(job); self.assertTrue(self.studio.queue.empty())

    def test_read_time_reduces_remaining_sleep_and_pending_work_is_not_idle(self):
        job = self.job(); calls = []
        def request(path, **kwargs):
            calls.append((path, kwargs['timeout'])); self.clock.now += 59.5
            return {'queue_running': [], 'queue_pending': [[2, 'manual-queued-prompt']]}
        with patch.object(self.studio, '_request', side_effect=request): self.dispatch(('generate', job['id']))
        self.assert_unsent(job); self.assertEqual(calls, [('/queue', 10)])
        self.assertEqual(self.clock.sleeps, [.5]); self.assertEqual(self.clock.now, 60)

    def test_failed_timeout_recording_keeps_worker_alive_and_disk_evidence_recoverable(self):
        job = self.job(); other = self.job(); save = self.studio._save
        folder = self.studio.runs/job['id']
        before = {name:(folder/name).read_bytes() for name in ('recipe.json', 'workflow.json')}
        def failed_record(value):
            if value['id'] == job['id'] and value['status'] in ('not_submitted', 'failed'):
                raise OSError('fixture: run directory locked')
            return save(value)
        with patch.object(self.studio, '_request', return_value=BUSY), patch.object(self.studio, '_save', side_effect=failed_record), \
             patch.object(self.studio, '_resume') as observe:
            self.dispatch(('generate', job['id']), ('observe', other['id']))
        observe.assert_called_once_with(other)
        self.assertFalse(self.studio.worker_failure['durable'])
        saved = json.loads((folder/'state.json').read_bytes())
        self.assertTrue(submission_evidence.never_submitted(saved)); self.assertEqual(saved['status'], 'waiting')
        self.assertEqual(self.studio.requests, [])
        restored = FakeStudio(self.root, [])
        self.assertTrue(submission_evidence.never_submitted(restored.jobs[job['id']]))
        self.assertEqual(restored.jobs[job['id']]['status'], 'not_submitted')
        self.assertTrue(restored.queue.empty()); self.assertEqual(restored.requests, [])
        for name, data in before.items(): self.assertEqual((folder/name).read_bytes(), data)
