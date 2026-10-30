"""GET /api/jobs answers an unchanged read from cached bytes, before any projection or serialization (#1767).

The cache key is (jobs-view revision, privacy scope). Every job mutation bumps the revision; while a job is active, or the worker is busy,
nothing is cached at all, because the worker edits jobs in place."""
import copy
import hashlib
import json
import socket
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http_test_server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_server import GRAPH, PRESET, server
import run_migration
import test_run_migration_apply as apply_tests
import test_run_migration_plan as plan_tests

ORIGIN = 'http://127.0.0.1:8191'


class JobsConditionalReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        for name in ('presets', 'workflows/api', 'config', 'fake-comfy/input'): (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / 'config/local.json').write_text(json.dumps({'comfy_root': str(self.root / 'fake-comfy')}))
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': [PRESET]}))
        (self.root / 'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        with patch.object(threading.Thread, 'start', lambda *_: None): self.studio = server.Studio(self.root)
        self.ids = {name: self.settled(name, status, **extra) for name, status, extra in (
            ('done-a', 'completed', {}), ('done-b', 'completed', {}), ('failed', 'failed', {}),
            ('unsent', 'uncertain', {}), ('tracked', 'uncertain', {}), ('spare-a', 'completed', {}), ('spare-b', 'completed', {}),
            ('private', 'completed', {'privacy': 'private'}))}
        handler = type('JobsConditionalHandler', (server.Handler,), {'studio': self.studio})
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.tmp.cleanup); self.addCleanup(self.close)

    def close(self):
        if self.thread.is_alive(): self.http.shutdown()
        self.http.server_close(); self.thread.join(3)

    def settled(self, name, status, **extra):
        identifier = self.studio.create_job({'preset_id': 'demo', 'controls': {}, **extra}, enqueue=False)['id']
        job = self.studio.jobs[identifier]; job['status'] = status; job['message'] = name; self.studio._save(job)
        return identifier

    def job(self, name): return self.studio.jobs[self.ids[name]]

    def send(self, method, path, headers=None, body=None):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=10)
        try:
            connection.request(method, path, body, {'Host': '127.0.0.1:8191', **(headers or {})})
            if connection.sock:
                try: connection.sock.shutdown(socket.SHUT_WR)
                except OSError: pass
            response = connection.getresponse()
            return response.status, response.read(), {k.lower(): v for k, v in response.getheaders()}
        finally: connection.close()

    def get(self, scope='regular', etag=None):
        return self.send('GET', '/api/jobs', {'X-Studio-Privacy': scope, **({'If-None-Match': etag} if etag else {})})

    def fresh(self, scope='regular'):
        """The uncached answer, projected directly from the live jobs."""
        rows = [j for j in self.studio.jobs.values() if scope == 'all' or j.get('privacy', 'regular') == scope]
        return [self.studio.public(j) for j in sorted(rows, key=lambda j: j['created_at'], reverse=True)]

    def counting(self):
        """Count projections and serializations inside the patches; json.dumps is patched process-wide, so keep the block to one request."""
        calls = {'public': 0}; original = server.Studio.public
        def spy(studio, job): calls['public'] += 1; return original(studio, job)
        return calls, patch.object(server.Studio, 'public', spy), patch.object(server.json, 'dumps', wraps=json.dumps)

    def assert_served_without_work(self, etag, scope='regular', conditional=True):
        calls, public, dumps = self.counting()
        with public, dumps as spy:
            status, body, headers = self.get(scope, etag if conditional else None)
        self.assertEqual((calls['public'], spy.call_count), (0, 0), 'a cached read must not project or serialize')
        self.assertEqual(headers['etag'], etag)
        self.assertEqual(status, 304 if conditional else 200)
        return body

    def test_unchanged_conditional_reads_skip_projection_and_serialization(self):
        status, body, headers = self.get(); etag = headers['etag']
        self.assertEqual((status, json.loads(body)), (200, self.fresh()))
        self.assertEqual(etag, '"' + hashlib.sha256(body).hexdigest() + '"')
        for _ in range(3): self.assertEqual(self.assert_served_without_work(etag), b'')   # 304 carries the first answer's ETag
        self.assertEqual(self.assert_served_without_work(etag, conditional=False), body)   # a plain refetch comes from the same bytes
        calls, public, dumps = self.counting()
        with public, dumps as spy: status, _, _ = self.get(etag='"stale"')
        self.assertEqual((status, calls['public'], spy.call_count), (200, 0, 0))   # a stale validator gets the cached bytes, nothing rebuilt

    def test_first_read_projects_once_per_regular_job(self):
        calls, public, _ = self.counting()
        with public: self.get()
        self.assertEqual(calls['public'], len(self.fresh()))

    def mutate_save(self): self.job('done-a')['message'] = 'edited'; self.studio._save(self.job('done-a'))
    def mutate_insert(self):
        clone = copy.deepcopy(self.job('done-a')); clone.update(id='clone', created_at=clone['created_at'] + 1); self.studio.jobs['clone'] = clone
    def mutate_pop(self): self.studio.jobs.pop(self.ids['spare-a'])
    def mutate_delete(self): del self.studio.jobs[self.ids['spare-b']]
    def mutate_put_away(self): self.studio.put_away_job(self.ids['failed'], True)
    def mutate_abandon(self): self.studio.abandon_job(self.ids['unsent'], 'never sent')
    def mutate_stop_tracking(self):
        job = self.job('tracked'); job.update(prompt_ids=['p1'], submissions=[{'prompt_id': 'p1', 'status': 'running'}]); self.studio._save(job)
        self.get()   # the saved edit already invalidated; warm again so only stop_tracking is under test
        self.studio.stop_tracking(job['id'], 'owner stopped it')
    def mutate_explicit_bump(self): self.job('done-b')['label'] = 'in place'; self.studio.bump_jobs_view()

    def test_every_mutation_kind_invalidates(self):
        for name in ('save', 'insert', 'pop', 'delete', 'put_away', 'abandon', 'stop_tracking', 'explicit_bump'):
            with self.subTest(name):
                _, _, headers = self.get(); stale = headers['etag']
                self.assert_served_without_work(stale)
                getattr(self, 'mutate_' + name)()
                status, body, headers = self.get(etag=stale)
                self.assertEqual(status, 200, name + ' left the cached answer standing')
                self.assertNotEqual(headers['etag'], stale)
                self.assertEqual(json.loads(body), self.fresh())
                self.assertEqual(self.assert_served_without_work(headers['etag']), b'')

    def test_private_and_regular_caches_stay_separate(self):
        tags = {}
        for scope in ('regular', 'private', 'all'):
            status, body, headers = self.get(scope); tags[scope] = headers['etag']
            self.assertEqual((status, json.loads(body)), (200, self.fresh(scope)))
        self.assertEqual(len(set(tags.values())), 3)
        self.assertNotIn(self.ids['private'], {j['id'] for j in json.loads(self.get('regular')[1])})
        self.assertEqual({j['id'] for j in json.loads(self.get('private')[1])}, {self.ids['private']})
        for scope, etag in tags.items(): self.assert_served_without_work(etag, scope)
        status, body, _ = self.get('private', tags['regular'])   # another scope's validator never matches
        self.assertEqual((status, {j['id'] for j in json.loads(body)}), (200, {self.ids['private']}))
        self.job('private')['message'] = 'private edit'; self.studio._save(self.job('private'))
        status, body, _ = self.get('private', tags['private'])
        self.assertEqual((status, 'private edit' in body.decode()), (200, True))
        self.assertNotIn('private edit', self.get('regular')[1].decode())
        self.assertEqual(json.loads(self.get('regular')[1]), self.fresh('regular'))

    def test_active_job_bypasses_the_cache(self):
        self.get()
        queued = self.studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)
        _, _, headers = self.get(); etag = headers['etag']
        self.studio.jobs[queued['id']]['message'] = 'worker edit with no save and no bump'
        status, body, headers = self.get(etag=etag)
        self.assertEqual(status, 200); self.assertIn('worker edit with no save', body.decode())
        calls, public, _ = self.counting()
        with public: self.get(etag=headers['etag'])
        self.assertEqual(calls['public'], len(self.fresh()))   # every row projected again while the job is queued
        self.studio.cancel_job(queued['id'])   # settles the never-submitted job and bumps
        _, _, headers = self.get(); self.assert_served_without_work(headers['etag'])
        self.assertEqual(json.loads(self.get()[1]), self.fresh())

    def test_busy_worker_and_open_cancel_request_bypass_the_cache(self):
        _, _, headers = self.get(); etag = headers['etag']
        for label, patcher in (('busy', patch.object(self.studio, '_worker_busy', True)), ('cancel', patch.dict(self.studio.cancel_requests, {'x': {}}))):
            with self.subTest(label), patcher:
                calls, public, _ = self.counting()
                with public: self.get(etag=etag)
                self.assertEqual(calls['public'], len(self.fresh()))
        self.assert_served_without_work(etag)

    def test_post_answers_bump_for_mutations_no_method_announces(self):
        _, _, headers = self.get(); stale = headers['etag']
        def quiet_put_away(studio, job_id, put_away): studio.jobs[job_id]['message'] = 'changed by a POST'; return {'ok': True}
        with patch.object(server.Studio, 'put_away_job', quiet_put_away):
            status, _, _ = self.send('POST', f"/api/jobs/{self.ids['failed']}/put-away", {'Origin': ORIGIN, 'Content-Type': 'application/json'}, json.dumps({'put_away': True}))
        self.assertEqual(status, 200)
        status, body, _ = self.get(etag=stale)
        self.assertEqual(status, 200); self.assertIn('changed by a POST', body.decode())

    def test_a_mutation_during_the_build_is_never_served_from_the_cache(self):
        original = server.Studio.public; edits = []
        def spy(studio, job):
            row = original(studio, job)
            if not edits: edits.append(job['id']); job['message'] = 'landed mid-build'; studio._save(job)
            return row
        with patch.object(server.Studio, 'public', spy): _, first, _ = self.get()
        self.assertNotIn('landed mid-build', first.decode())   # that row was already projected
        _, second, _ = self.get()
        self.assertIn('landed mid-build', second.decode())
        self.assertEqual(json.loads(second), self.fresh())

    def test_unbumped_edits_heal_when_the_entry_expires(self):
        _, _, headers = self.get(); etag = headers['etag']
        self.job('done-a')['message'] = 'edited with no bump'
        self.assertEqual(self.get(etag=etag)[0], 304)   # the cache cannot see it ...
        with patch.object(server, 'JOBS_VIEW_MAX_AGE', 0.0): status, body, _ = self.get(etag=etag)
        self.assertEqual(status, 200); self.assertIn('edited with no bump', body.decode())   # ... until the entry expires

    def test_cache_stays_bounded(self):
        for _ in range(25):
            self.studio.bump_jobs_view()
            for scope in ('regular', 'private', 'all'): self.get(scope)
        self.assertLessEqual(len(self.studio._jobs_views), 3)
        self.assertEqual({key[0] for key in self.studio._jobs_views}, {self.studio.jobs.rev})


class MigrationInvalidatesJobsViewTests(unittest.TestCase):
    base = plan_tests.RunMigrationPlanTests.__dict__
    applying = apply_tests.RunMigrationApplyTests.__dict__
    setUp, close, tree, project, comparison, scene = base['setUp'], base['close'], base['tree'], base['project'], base['comparison'], base['scene']
    completed, post, get, scenario, plan, body = applying['completed'], applying['post'], applying['get'], applying['scenario'], applying['plan'], applying['body']

    def conditional(self, scope, etag=None):
        conn = HTTPConnection('127.0.0.1', self.http.server_port, timeout=20)
        try:
            conn.request('GET', '/api/jobs', headers={'Host': '127.0.0.1:8191', 'X-Studio-Privacy': scope, **({'If-None-Match': etag} if etag else {})})
            response = conn.getresponse(); return response.status, response.read(), response.getheader('ETag')
        finally: conn.close()

    def test_migration_apply_moves_the_run_between_cached_scopes(self):
        s = self.scenario(); child = self.studio.jobs[s['child']]; child['status'] = 'failed'; self.studio._save(child)   # settled: the cache is live
        plan = self.plan(s)
        warm = {scope: self.conditional(scope) for scope in ('regular', 'private')}
        self.assertEqual(self.conditional('regular', warm['regular'][2])[0], 304)
        self.assertIn(s['jid'], {j['id'] for j in json.loads(warm['regular'][1])})
        status, out = run_migration.apply(self.studio, self.body(s, plan), 'all')   # direct: the POST answer's own bump must not stand in for migration's
        self.assertEqual((status, out['stage']), (200, 'complete'), out)
        status, body, _ = self.conditional('regular', warm['regular'][2])
        self.assertEqual(status, 200); self.assertNotIn(s['jid'], {j['id'] for j in json.loads(body)})
        status, body, _ = self.conditional('private', warm['private'][2])
        self.assertEqual(status, 200); self.assertIn(s['jid'], {j['id'] for j in json.loads(body)})


if __name__ == '__main__':
    unittest.main()
