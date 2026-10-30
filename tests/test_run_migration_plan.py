"""Read-only completed-run privacy migration planning (#1678, first slice): closure, blockers, hash, zero writes."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from http_test_server import ThreadingHTTPServer
import test_server as fixture

ROUTE = '/api/assets/migration-plan'


class RunMigrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); root = self.root = Path(self.tmp.name)
        for name in ('presets', 'workflows/api', 'config', 'fake-comfy/input', 'fake-comfy/output'): (root/name).mkdir(parents=True, exist_ok=True)
        (root/'config/local.json').write_text(json.dumps({'comfy_root': str(root/'fake-comfy')}))
        (root/'presets/catalog.json').write_text(json.dumps({'presets': [fixture.PRESET]}))
        (root/'workflows/api/demo-api.json').write_text(json.dumps(fixture.GRAPH))
        with patch.object(threading.Thread, 'start', lambda *_: None): self.studio = fixture.server.Studio(root)
        handler = type('MigrationPlanHandler', (fixture.server.extend_handler(fixture.server.Handler),), {'studio': self.studio})
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval': .01}, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        with self.studio.assets.connection() as db: self.workspace_id = db.execute('SELECT id FROM workspace_identity').fetchone()[0]

    def close(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(3)

    def completed(self, outputs=3, privacy='regular', text='regular canary'):
        payload = {'preset_id': 'demo', 'controls': {'positive': text}}
        if privacy == 'private': payload['privacy'] = 'private'
        identifier = self.studio.create_job(payload, enqueue=False)['id']; job = self.studio.jobs[identifier]
        job.update(status='completed', prompt_ids=['p-'+identifier], submissions=[{'prompt_id': 'p-'+identifier, 'status': 'completed', 'graph': copy.deepcopy(job['graph'])}],
                   outputs=[{'filename': f'{identifier}-{i}.png', 'media_type': 'image', 'type': 'output', 'prompt_id': 'p-'+identifier} for i in range(outputs)])
        for index, output in enumerate(job['outputs']):
            source = self.root/'fake-comfy/output'/output['filename']
            from PIL import Image
            Image.new('RGB', (8, 8), (index*40 % 256, len(identifier), 9)).save(source)
            output['asset_id'] = self.studio.assets.register(job, index, source)
        self.studio._save(job)
        return job

    def request(self, body, *, headers=None, raw=None):
        conn = HTTPConnection('127.0.0.1', self.http.server_port, timeout=10)
        try:
            fields = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191', 'Content-Type': 'application/json', **(headers or {})}
            conn.request('POST', ROUTE, raw if raw is not None else json.dumps(body), fields); response = conn.getresponse()
            return response.status, response.read()
        finally: conn.close()

    def plan(self, headers=None, **body):
        status, raw = self.request(dict({'workspace_id': self.workspace_id, 'destination': 'private'}, **body), headers=headers)
        self.assertEqual(status, 200, raw); return json.loads(raw)

    def kinds(self, plan, kind):
        return [item for item in plan['items'] if item['kind'] == kind]

    def codes(self, plan):
        return {blocker['code'] for blocker in plan['blockers']}

    def test_multi_output_closure_covers_run_siblings_thumbs_uploads_collections_children_and_external_copies(self):
        job = self.completed(3)
        upload = self.studio.upload('ref.png', 'image/png', fixture.png())
        job['references'] = [{'file': upload['file'], 'role': 'subject'}]; self.studio._save(job)
        ids = [o['asset_id'] for o in job['outputs']]
        thumbs = self.studio.assets.root/'thumbs'; thumbs.mkdir()
        sha = self.studio.assets.get(ids[1])['sha256']; (thumbs/f'{sha}-256-v1.webp').write_bytes(b'thumb')
        with self.studio.assets.connection() as db:
            db.execute("INSERT INTO collections (id,name,created_at) VALUES ('c-whole','Whole',1)")
            db.executemany("INSERT INTO collection_assets VALUES ('c-whole',?)", [(i,) for i in ids])
        child = self.studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'child'}}, enqueue=False)
        self.studio.jobs[child['id']]['parent_assets'] = [ids[0]]
        plan = self.plan(asset_ids=[ids[2]])  # one sibling resolves the whole run
        self.assertEqual({i['id'] for i in self.kinds(plan, 'asset')}, set(ids))
        self.assertEqual([i['id'] for i in self.kinds(plan, 'run')], [job['id']])
        run_files = {i['id'] for i in self.kinds(plan, 'run_file')}
        for name in ('recipe.json', 'state.json', 'workflow.json'): self.assertIn('runs/'+job['id']+'/'+name, run_files)
        self.assertEqual([i['id'] for i in self.kinds(plan, 'thumbnail')], ['workspace/thumbs/'+sha+'-256-v1.webp'])
        self.assertEqual({i['id'] for i in self.kinds(plan, 'upload')}, {'uploads/'+upload['file'], 'uploads/'+upload['file']+'.json'})
        self.assertEqual([i['id'] for i in self.kinds(plan, 'collection')], ['c-whole'])
        self.assertEqual([i['id'] for i in self.kinds(plan, 'lineage_child')], [child['id']])
        external = {i['id'] for i in self.kinds(plan, 'external_copy')}
        self.assertIn('comfyui/input/'+upload['file'], external)
        for output in job['outputs']: self.assertIn('comfyui/output/'+output['filename'], external)
        for item in self.kinds(plan, 'asset'):
            self.assertEqual(item['classification'], 'regular'); self.assertRegex(item['sha256'], '^[0-9a-f]{64}$'); self.assertEqual(item['revision'], 0)
        self.assertEqual(plan['blockers'], [{'code': 'scope_partial', 'message': plan['blockers'][0]['message']}])
        copied = sum(i['bytes'] for i in plan['items'] if i['kind'] in ('run_file', 'asset', 'upload', 'thumbnail'))
        self.assertEqual(plan['byte_estimate'], copied); self.assertGreater(copied, 0)
        self.assertFalse(plan['apply_available']); self.assertRegex(plan['plan_sha256'], '^[0-9a-f]{64}$')

    def test_running_uncertain_partial_and_pending_submission_runs_are_blocked_and_left_unchanged(self):
        for status, extra in (('running', {}), ('uncertain', {}), ('partial', {}), ('queued', {}), ('completed', {'pending_submission': {'index': 0}})):
            with self.subTest(status=status, extra=extra):
                job = self.completed(1); job.update(status=status, **extra); before = copy.deepcopy(job)
                plan = self.plan(job_ids=[job['id']])
                self.assertIn('run_not_settled', self.codes(plan)); self.assertFalse(plan['applicable'])
                self.assertEqual(self.studio.jobs[job['id']], before)

    def test_destination_already_satisfied_is_a_blocker(self):
        job = self.completed(2, privacy='private', text='private canary')
        plan = self.plan(headers={'X-Studio-Privacy': 'private'}, job_ids=[job['id']])
        self.assertIn('already_in_destination', self.codes(plan))
        self.assertEqual({i['classification'] for i in self.kinds(plan, 'asset')}, {'private'})
        regular = self.plan(headers={'X-Studio-Privacy': 'private'}, job_ids=[job['id']], destination='regular')
        self.assertNotIn('already_in_destination', self.codes(regular))

    def test_missing_sibling_and_missing_snapshot_are_blockers(self):
        job = self.completed(3); ids = [o['asset_id'] for o in job['outputs']]
        with self.studio.assets.connection() as db: db.execute('DELETE FROM assets WHERE id=?', (ids[1],))
        media = self.studio.assets.root/self.studio.assets.get(ids[2])['path']; media.unlink()
        plan = self.plan(asset_ids=[ids[0]])
        missing = [b for b in plan['blockers'] if b['code'] == 'missing_sibling']
        self.assertEqual([(b['run_id'], b['output_index']) for b in missing], [(job['id'], 1)])
        self.assertIn('missing_snapshot', self.codes(plan))

    def test_mixed_collection_is_a_blocker(self):
        job, other = self.completed(1), self.completed(1)
        with self.studio.assets.connection() as db:
            db.execute("INSERT INTO collections (id,name,created_at) VALUES ('c-mixed','Mixed',1)")
            db.executemany("INSERT INTO collection_assets VALUES ('c-mixed',?)", [(job['outputs'][0]['asset_id'],), (other['outputs'][0]['asset_id'],)])
        self.assertIn('collection_mixed', self.codes(self.plan(job_ids=[job['id']])))

    def test_plan_hash_is_stable_and_binds_revisions(self):
        job = self.completed(2); ids = [o['asset_id'] for o in job['outputs']]
        first, second = self.plan(asset_ids=ids), self.plan(asset_ids=list(reversed(ids)))
        self.assertEqual(first['plan_sha256'], second['plan_sha256']); self.assertEqual(first['items'], second['items'])
        self.assertNotEqual(first['plan_sha256'], self.plan(asset_ids=ids, destination='regular')['plan_sha256'])
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id=?', (ids[0],))
        self.assertNotEqual(first['plan_sha256'], self.plan(asset_ids=ids)['plan_sha256'])

    def tree(self):
        experiments = self.studio.experiments
        files = {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob('*') if p.is_file() and not p.name.endswith(('-wal', '-shm', '.sqlite3'))}
        db = sqlite3.connect(experiments/'workspace/assets.sqlite3')
        try: dump = list(db.iterdump())
        finally: db.close()
        return files, dump

    def test_planning_writes_nothing(self):
        job = self.completed(3); private = self.completed(1, privacy='private', text='private canary')
        job_state = json.dumps(self.studio.jobs[job['id']], sort_keys=True, default=str)
        before = self.tree()
        self.plan(job_ids=[job['id']]); self.plan(headers={'X-Studio-Privacy': 'all'}, job_ids=[job['id'], private['id']])
        self.request({'workspace_id': self.workspace_id, 'destination': 'private', 'job_ids': ['missing-job']})
        self.assertEqual(self.tree(), before)
        self.assertEqual(json.dumps(self.studio.jobs[job['id']], sort_keys=True, default=str), job_state)

    def test_regular_scope_never_discloses_private_ids(self):
        private = self.completed(2, privacy='private', text='PRIVATE-PLAN-CANARY'); asset = private['outputs'][0]['asset_id']
        regular = self.completed(1)
        # The private run reuses a regular output as its parent: a regular plan must not list that child.
        self.studio.jobs[private['id']]['parent_assets'] = [regular['outputs'][0]['asset_id']]
        for field, hidden, unknown in (('asset_ids', asset, 'f'*32), ('job_ids', private['id'], 'f'*32)):
            with self.subTest(field=field):
                status, raw = self.request({'workspace_id': self.workspace_id, 'destination': 'regular', field: [hidden]})
                status2, raw2 = self.request({'workspace_id': self.workspace_id, 'destination': 'regular', field: [unknown]})
                self.assertEqual((status, raw.replace(hidden.encode(), b'X')), (status2, raw2.replace(unknown.encode(), b'X')))
                self.assertGreaterEqual(status, 400); self.assertNotIn(b'PRIVATE-PLAN-CANARY', raw)
        plan = self.request({'workspace_id': self.workspace_id, 'destination': 'private', 'job_ids': [regular['id']]})[1]
        self.assertNotIn(private['id'].encode(), plan); self.assertNotIn(asset.encode(), plan)
        visible = self.plan(headers={'X-Studio-Privacy': 'all'}, job_ids=[regular['id']])
        self.assertIn(private['id'], [i['id'] for i in self.kinds(visible, 'lineage_child')])
        self.assertNotIn('scope_partial', self.codes(visible))

    def test_control_bound_reference_uploads_join_the_closure(self):
        upload = self.studio.upload('pose.png', 'image/png', fixture.png())
        identifier = self.studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'ref run', 'reference': upload['file']}}, enqueue=False)['id']
        job = self.studio.jobs[identifier]; job.update(status='completed'); self.assertEqual(job.get('references') or [], [])
        plan = self.plan(job_ids=[identifier])
        self.assertEqual({i['id'] for i in self.kinds(plan, 'upload')}, {'uploads/'+upload['file'], 'uploads/'+upload['file']+'.json'})
        self.assertIn('comfyui/input/'+upload['file'], {i['id'] for i in self.kinds(plan, 'external_copy')})

    def insert_receipts(self, asset_id, count, prefix='receipt'):
        with self.studio.assets.connection() as db:
            db.executemany("INSERT INTO asset_commands (request_id,fingerprint,result,created_at) VALUES (?,?,?,1)",
                           [(f'{prefix}-{i:04d}-aaaaaaaa', 'f', json.dumps({'updated': [asset_id]})) for i in range(count)])

    def test_receipt_overflow_blocks_and_shared_request_ids_do_not_collide(self):
        job = self.completed(1); asset_id = job['outputs'][0]['asset_id']
        self.insert_receipts(asset_id, 1)
        with self.studio.assets.connection() as db:
            db.execute("INSERT INTO collection_commands_v1 VALUES ('receipt-0000-aaaaaaaa',1,?,'c','{}','x',?,'y',2,'regular')", (self.workspace_id, json.dumps({'ids': [asset_id]})))
        plan = self.plan(job_ids=[job['id']])
        self.assertEqual(sorted(i['table'] for i in self.kinds(plan, 'receipt')), ['asset_commands', 'collection_commands_v1'])
        self.assertNotIn('receipts_overflow', self.codes(plan))
        self.insert_receipts(asset_id, 50, 'more')  # 51 receipts in asset_commands exceed the bound of 50
        overflow = self.plan(job_ids=[job['id']])
        self.assertIn('receipts_overflow', self.codes(overflow)); self.assertFalse(overflow['applicable'])

    def test_native_operation_runs_are_unsupported(self):
        job = self.completed(1); job['operation'] = 'native.articulated-prop.v1'
        self.assertIn('unsupported_operation', self.codes(self.plan(job_ids=[job['id']])))

    def test_item_bound_refuses_before_hashing_everything(self):
        import run_migration
        job = self.completed(5); calls = []
        real = run_migration.digest_file
        def counted(path): calls.append(path); return real(path)
        with patch.object(run_migration, 'MAX_ITEMS', 3), patch.object(run_migration, 'digest_file', counted):
            status, raw = self.request({'workspace_id': self.workspace_id, 'destination': 'private', 'job_ids': [job['id']]})
        self.assertEqual(status, 413, raw); self.assertLessEqual(len(calls), 3)

    def test_directory_alias_inside_run_folder_is_a_blocker_not_followed(self):
        import os, subprocess
        job = self.completed(1); outside = self.root/'outside'; outside.mkdir(); (outside/'secret.txt').write_text('x')
        link = self.studio._job_directory(job['id'])/'linked'
        try: os.symlink(outside, link, target_is_directory=True)
        except OSError:
            if os.name != 'nt' or subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True).returncode: self.skipTest('no directory links here')
        plan = self.plan(job_ids=[job['id']])
        self.assertIn('run_storage_alias', self.codes(plan))
        self.assertFalse(any('secret.txt' in i['id'] for i in plan['items']))

    def test_input_bounds_and_validation(self):
        job = self.completed(1); good = {'workspace_id': self.workspace_id, 'destination': 'private', 'job_ids': [job['id']]}
        cases = [dict(good, destination='all'), dict(good, destination=None), {k: v for k, v in good.items() if k != 'workspace_id'},
                 dict(good, job_ids=[]), dict(good, job_ids=[job['id'], job['id']]), dict(good, job_ids=['../x']),
                 dict(good, job_ids=[str(i) for i in range(51)]), dict(good, extra=True), dict(good, asset_ids='abc'),
                 dict(good, workspace_id='nothex'), dict(good, workspace_id=None)]
        for body in cases:
            with self.subTest(body=body): self.assertEqual(self.request(body)[0], 400)
        self.assertEqual(self.request(None, raw='[]')[0], 400)
        self.assertEqual(self.request(dict(good, workspace_id='0'*32))[0], 409)


if __name__ == '__main__':
    unittest.main()
