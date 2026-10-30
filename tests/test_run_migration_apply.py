"""Regular->Private apply of a completed run: durable journal, verified publication, start-time recovery (#1678, third slice)."""
import errno
import hashlib
import json
import shutil
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

import test_server as fixture  # puts app/ on sys.path first
import run_migration
import test_run_migration_plan as planning

APPLY = '/api/assets/migration-apply'
Base = planning.RunMigrationPlanTests.__dict__  # functions only: a TestCase class here would rerun the plan tests


class Crash(BaseException):
    """A process death: it bypasses every `except Exception` rollback, leaving disk state as a real crash would."""


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RunMigrationApplyTests(unittest.TestCase):
    setUp, close, tree = Base['setUp'], Base['close'], Base['tree']

    def completed(self, outputs=3, seed=None, privacy='regular'):
        """Base.completed, but each run's pictures are distinct unless a seed asks for identical bytes."""
        from PIL import Image
        payload = {'preset_id': 'demo', 'controls': {'positive': privacy+' canary'}, **({'privacy': 'private'} if privacy == 'private' else {})}
        identifier = self.studio.create_job(payload, enqueue=False)['id']; job = self.studio.jobs[identifier]
        job.update(status='completed', prompt_ids=['p-'+identifier], submissions=[{'prompt_id': 'p-'+identifier, 'status': 'completed', 'graph': json.loads(json.dumps(job['graph']))}],
                   outputs=[{'filename': f'{identifier}-{i}.png', 'media_type': 'image', 'type': 'output', 'prompt_id': 'p-'+identifier} for i in range(outputs)])
        colour = hashlib.sha256((seed or identifier).encode()).digest()
        for index, output in enumerate(job['outputs']):
            source = self.root/'fake-comfy/output'/output['filename']
            Image.new('RGB', (8, 8), (colour[0], colour[1], (colour[2]+index*40) % 256)).save(source)
            output['asset_id'] = self.studio.assets.register(job, index, source)
        self.studio._save(job)
        return job

    def post(self, route, body, scope='all'):
        conn = HTTPConnection('127.0.0.1', self.http.server_port, timeout=20)
        try:
            conn.request('POST', route, json.dumps(body), {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191',
                                                         'Content-Type': 'application/json', 'X-Studio-Privacy': scope})
            response = conn.getresponse(); return response.status, json.loads(response.read())
        finally: conn.close()

    def get(self, path, scope='regular'):
        conn = HTTPConnection('127.0.0.1', self.http.server_port, timeout=20)
        try:
            conn.request('GET', path, headers={'Host': '127.0.0.1:8191', 'X-Studio-Privacy': scope}); response = conn.getresponse()
            return response.status, response.read()
        finally: conn.close()

    def restart(self):
        with patch.object(threading.Thread, 'start', lambda *_: None): studio = fixture.server.Studio(self.root)
        self.http.RequestHandlerClass.studio = studio
        return studio

    def scenario(self, outputs=3, seed=None):
        job = self.completed(outputs, seed); jid = job['id']; ids = [o['asset_id'] for o in job['outputs']]
        upload = self.studio.upload('ref.png', 'image/png', fixture.png())
        job['references'] = [{'file': upload['file'], 'role': 'subject'}]; self.studio._save(job)
        thumbs = self.studio.assets.root/'thumbs'; thumbs.mkdir(exist_ok=True)
        shas = [self.studio.assets.get(i)['sha256'] for i in ids]
        (thumbs/f'{shas[1]}-256-v1.webp').write_bytes(b'thumb')
        with self.studio.assets.connection() as db:
            db.execute('INSERT INTO collections (id,name,created_at) VALUES (?,?,1)', ('c-'+jid, 'Whole'))
            db.executemany('INSERT INTO collection_assets VALUES (?,?)', [('c-'+jid, i) for i in ids])
        child = self.studio.jobs[self.studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'child'}}, enqueue=False)['id']]
        child['parent_assets'] = [ids[0]]; self.studio._save(child)
        experiments = self.studio.experiments
        rows = {i: self.studio.assets.get(i) for i in ids}
        return dict(job=job, jid=jid, ids=ids, shas=shas, upload=upload['file'], child=child['id'], rows=rows,
                    run_files={p.relative_to(experiments).as_posix(): sha(p) for p in (experiments/'runs'/jid).rglob('*') if p.is_file()},
                    external={p.name: sha(p) for p in (self.root/'fake-comfy').rglob('*') if p.is_file()},
                    state=json.loads((experiments/'runs'/jid/'state.json').read_text()), recipe=json.loads((experiments/'runs'/jid/'recipe.json').read_text()))

    def plan(self, s):
        status, data = self.post('/api/assets/migration-plan', {'workspace_id': self.workspace_id, 'destination': 'private', 'job_ids': [s['jid']]})
        self.assertEqual(status, 200, data); self.assertEqual(data['blockers'], []); return data

    def body(self, s, plan, request_id=None, **extra):
        return dict({'workspace_id': self.workspace_id, 'destination': 'private', 'plan_sha256': plan['plan_sha256'],
                     'request_id': request_id or 'migrate-'+s['jid'][:16], 'job_ids': [s['jid']]}, **extra)

    def journal(self, s, request_id=None):
        return json.loads((self.studio.experiments/'private/migrations'/((request_id or 'migrate-'+s['jid'][:16])+'.json')).read_text())

    def assert_moved(self, s, studio):
        experiments, jid = self.studio.experiments, s['jid']
        job = studio.jobs[jid]
        self.assertEqual(job['privacy'], 'private'); self.assertNotIn('record_error', job)
        self.assertEqual([o['asset_id'] for o in job['outputs']], s['ids'])
        self.assertFalse((experiments/'runs'/jid).exists())
        private = experiments/'private/runs'/jid
        for rel, digest in s['run_files'].items():
            name = rel.split('/', 2)[2]
            if name not in ('state.json', 'recipe.json'): self.assertEqual(sha(private/name), digest, name)  # byte-identical, incl. the submitted graph
        self.assertEqual(json.loads((private/'state.json').read_text()), dict(s['state'], privacy='private'))
        self.assertEqual(json.loads((private/'recipe.json').read_text()), dict(s['recipe'], privacy='private'))
        for asset_id, before in s['rows'].items():
            row = studio.assets.get(asset_id, privacy='private')
            for key in ('id', 'job_id', 'output_index', 'sha256', 'bytes', 'path', 'lineage', 'source', 'title', 'tags'): self.assertEqual(row[key], before[key], key)
            self.assertEqual(row['metadata_revision'], before['metadata_revision']+1)
            with self.assertRaises(ValueError): studio.assets.get(asset_id)  # Regular cannot read it
            self.assertEqual(sha(experiments/'private'/row['path']), row['sha256'])
            self.assertFalse((studio.assets.root/row['path']).exists())
        self.assertFalse(set(s['ids']) & {a['id'] for a in studio.assets.snapshot('regular')['assets']})
        self.assertTrue(set(s['ids']) <= {a['id'] for a in studio.assets.snapshot('private')['assets']})
        self.assertFalse(list((studio.assets.root/'thumbs').glob(s['shas'][1]+'*')))
        self.assertFalse((experiments/'uploads'/s['upload']).exists()); self.assertFalse((experiments/'uploads'/(s['upload']+'.json')).exists())
        self.assertEqual(sha(studio._upload_path(s['upload'], 'private')), sha(self.root/'fake-comfy/input'/s['upload']))
        with self.assertRaises(ValueError): studio._upload_path(s['upload'], 'regular')
        with studio.assets.connection() as db:
            self.assertEqual(db.execute('SELECT privacy FROM collections WHERE id=?', ('c-'+jid,)).fetchone()[0], 'private')
            self.assertEqual({r[0] for r in db.execute('SELECT asset_id FROM collection_assets WHERE collection_id=?', ('c-'+jid,))}, set(s['ids']))
        child = studio.jobs[s['child']]; self.assertEqual((child.get('privacy', 'regular'), child['parent_assets']), ('regular', [s['ids'][0]]))
        self.assertEqual({p.name: sha(p) for p in (self.root/'fake-comfy').rglob('*') if p.is_file()}, s['external'])  # ComfyUI copies untouched
        self.assertFalse((experiments/'private/migrations'/('migrate-'+jid[:16])).exists())

    def assert_regular(self, s, studio):
        experiments, jid = self.studio.experiments, s['jid']
        job = studio.jobs[jid]
        self.assertEqual(job.get('privacy', 'regular'), 'regular'); self.assertNotIn('record_error', job)
        self.assertEqual({p.relative_to(experiments).as_posix(): sha(p) for p in (experiments/'runs'/jid).rglob('*') if p.is_file()}, s['run_files'])
        self.assertFalse((experiments/'private/runs'/jid).exists())
        for asset_id, before in s['rows'].items():
            row = studio.assets.get(asset_id); self.assertEqual((row['privacy'], row['metadata_revision']), ('regular', before['metadata_revision']))
            self.assertTrue((studio.assets.root/row['path']).is_file()); self.assertFalse((experiments/'private'/row['path']).exists())
        self.assertTrue((experiments/'uploads'/s['upload']).is_file()); self.assertFalse((experiments/'private/uploads'/s['upload']).exists())
        self.assertTrue(list((studio.assets.root/'thumbs').glob(s['shas'][1]+'*')))
        self.assertFalse((experiments/'private/migrations'/('migrate-'+jid[:16])).exists())

    def regular_job_ids(self, scope='regular'):
        status, raw = self.get('/api/jobs', scope); self.assertEqual(status, 200); return {j['id'] for j in json.loads(raw)}

    def test_happy_path_moves_the_whole_run_and_survives_restart(self):
        s = self.scenario(); plan = self.plan(s)
        self.assertIn(s['jid'], self.regular_job_ids())
        status, out = self.post(APPLY, self.body(s, plan))
        self.assertEqual((status, out['stage'], out['published'], out['cleanup_remaining']), (200, 'complete', True, []), out)
        self.assertEqual((out['job_ids'], sorted(out['asset_ids']), out['collection_ids']), ([s['jid']], sorted(s['ids']), ['c-'+s['jid']]))
        self.assertIn('comfyui/input/'+s['upload'], out['external_copies'])
        self.assert_moved(s, self.studio)
        self.assertNotIn(s['jid'], self.regular_job_ids()); self.assertIn(s['jid'], self.regular_job_ids('private'))
        self.assertNotEqual(self.get('/api/uploads/'+s['upload'])[0], 200)
        self.assertEqual(self.get('/api/jobs/'+s['jid'])[0], 404)
        restarted = self.restart()
        self.assertEqual(restarted.migration_recovery, [])
        self.assert_moved(s, restarted)
        self.assertNotIn(s['jid'], self.regular_job_ids()); self.assertIn(s['jid'], self.regular_job_ids('all'))
        self.assertEqual(self.journal(s)['stage'], 'complete')

    def test_stale_plan_is_refused_with_zero_changes(self):
        s = self.scenario(); plan = self.plan(s)
        with self.studio.assets.connection() as db: db.execute('UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id=?', (s['ids'][0],))
        before = self.tree()
        status, out = self.post(APPLY, self.body(s, plan))
        self.assertEqual((status, out['code']), (409, 'migration_stale'), out); self.assertNotIn('plan_sha256', out)
        self.assertEqual(self.tree(), before); self.assertEqual(self.studio.jobs[s['jid']].get('privacy', 'regular'), 'regular')

    def test_blockers_direction_and_scope_are_refused_without_changes(self):
        s = self.scenario(); plan = self.plan(s)
        before = self.tree()
        status, out = self.post(APPLY, self.body(s, plan, destination='regular'))
        self.assertEqual((status, out['code']), (400, 'migration_direction_unsupported'))
        status, out = self.post(APPLY, self.body(s, plan), scope='regular')
        self.assertEqual((status, out['code']), (400, 'migration_scope_required'))
        self.studio.jobs[s['jid']]['status'] = 'uncertain'
        status, out = self.post(APPLY, self.body(s, plan))
        self.assertEqual((status, out['code']), (409, 'migration_blocked')); self.assertIn('run_not_settled', {b['code'] for b in out['blockers']})
        self.assertEqual(self.tree(), before); self.assertEqual(self.studio.jobs[s['jid']]['status'], 'uncertain')

    def test_duplicate_request_id_replays_the_receipt_and_never_reexecutes(self):
        s = self.scenario(); plan = self.plan(s); body = self.body(s, plan)
        first = self.post(APPLY, body)
        self.assertEqual(first[0], 200)
        with patch.object(run_migration, 'plan', side_effect=AssertionError('replayed a mutation')):
            self.assertEqual(self.post(APPLY, body), first)
            status, out = self.post(APPLY, dict(body, plan_sha256='0'*64))
            self.assertEqual((status, out['code']), (409, 'migration_request_conflict'))
        status, out = self.post(APPLY, dict(body, request_id='another-request-identity'))
        self.assertEqual((status, out['code']), (409, 'migration_blocked'))
        self.assertIn('already_in_destination', {b['code'] for b in out['blockers']})
        self.assertFalse((self.studio.experiments/'private/migrations/another-request-identity.json').exists())

    def crash_at(self, stage):
        def checkpoint(reached):
            if reached == stage: raise Crash(stage)
        return patch.object(run_migration, '_checkpoint', checkpoint)

    def test_crash_at_every_journal_boundary_recovers_at_start_without_regular_disclosure(self):
        cases = (('staging', 'staging', 'rolled-back'), ('verified', 'verified', 'rolled-back'), ('placed', 'verified', 'rolled-back'),
                 ('committed', 'verified', 'complete'), ('published', 'published', 'complete'), ('cleanup', 'published', 'complete'))
        for crash, from_stage, stage in cases:
            with self.subTest(crash=crash):
                s = self.scenario(); body = self.body(s, self.plan(s))
                with self.crash_at(crash), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
                self.assertEqual(self.journal(s)['stage'], from_stage)
                restarted = self.studio = self.restart()
                self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': from_stage, 'stage': stage}])
                if stage == 'complete': self.assert_moved(s, restarted); self.assertNotIn(s['jid'], self.regular_job_ids())
                else: self.assert_regular(s, restarted); self.assertIn(s['jid'], self.regular_job_ids())
                status, out = run_migration.apply(restarted, body, 'all')  # the original identity reports the actual recovered stage
                self.assertEqual((out['stage'], out['recovery']['from_stage'], out['published']), (stage, from_stage, stage == 'complete'))
                self.assertEqual(status, 200 if stage == 'complete' else 500)

    def test_failed_cleanup_stays_visible_and_is_finished_at_restart(self):
        s = self.scenario(); body = self.body(s, self.plan(s))
        locked = self.studio.assets.root/s['rows'][s['ids'][0]]['path']; real = Path.unlink
        def unlink(path, *a, **k):
            if Path(path) == locked: raise PermissionError(13, 'locked by another program')
            return real(path, *a, **k)
        with patch.object(Path, 'unlink', unlink): status, out = self.post(APPLY, body)
        self.assertEqual((status, out['stage'], out['published']), (200, 'cleanup-needed', True))
        self.assertEqual(out['cleanup_remaining'], [locked.relative_to(self.studio.experiments).as_posix()])
        self.assertTrue(locked.exists()); self.assertEqual(self.post(APPLY, body)[1]['stage'], 'cleanup-needed')
        restarted = self.restart()
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'cleanup-needed', 'stage': 'complete'}])
        self.assert_moved(s, restarted)

    def test_disk_full_failed_copy_and_hash_mismatch_never_publish(self):
        real = shutil.copyfile
        def full(src, dst, *a, **k):
            if Path(src).name == 'workflow.json': raise OSError(errno.ENOSPC, 'No space left on device')
            return real(src, dst, *a, **k)
        def refused(src, dst, *a, **k):
            if Path(src).suffix == '.png' and 'media' in Path(src).parts: raise PermissionError(13, 'locked')
            return real(src, dst, *a, **k)
        def corrupt(src, dst, *a, **k):
            result = real(src, dst, *a, **k)
            if Path(src).name == 'recipe.json': Path(dst).write_bytes(Path(dst).read_bytes()+b' ')
            return result
        for name, copier, expected in (('disk full', full, (507, 'migration_storage_full')), ('failed copy', refused, (500, 'migration_failed')),
                                       ('hash mismatch', corrupt, (409, 'migration_verify_failed'))):
            with self.subTest(name):
                s = self.scenario(); body = self.body(s, self.plan(s))
                with patch.object(run_migration.shutil, 'copyfile', copier): status, out = self.post(APPLY, body)
                self.assertEqual((status, out['code'], out['stage'], out['published']), (*expected, 'rolled-back', False), out)
                self.assert_regular(s, self.studio); self.assertIn(s['jid'], self.regular_job_ids())
                self.assertEqual(self.post(APPLY, body), (status, out))  # the failure is the receipt; no silent re-run
                restarted = self.restart(); self.assertEqual(restarted.migration_recovery, []); self.assert_regular(s, restarted); self.studio = restarted

    def test_concurrent_job_write_is_refused_and_concurrent_asset_write_stops_publication(self):
        s = self.scenario(); body = self.body(s, self.plan(s)); seen = []
        def write_job(stage):
            if stage == 'verified':
                with self.assertRaises(fixture.server.StudioError) as caught: self.studio._save(self.studio.jobs[s['jid']])
                seen.append(caught.exception.code)
        with patch.object(run_migration, '_checkpoint', write_job): status, out = self.post(APPLY, body)
        self.assertEqual((status, out['stage'], seen), (200, 'complete', ['migration_in_progress']))
        self.studio._save(self.studio.jobs[s['jid']])  # the guard ends with the migration
        other = self.scenario(); body = self.body(other, self.plan(other))
        def write_asset(stage):
            if stage == 'verified':
                with self.studio.assets.connection() as db: db.execute('UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id=?', (other['ids'][1],))
        with patch.object(run_migration, '_checkpoint', write_asset): status, out = self.post(APPLY, body)
        self.assertEqual((status, out['code'], out['stage'], out['failed_stage']), (409, 'migration_stale', 'rolled-back', 'verified'))
        other['rows'][other['ids'][1]]['metadata_revision'] += 1
        self.assert_regular(other, self.studio)

    def test_upload_and_snapshot_shared_with_another_regular_run_stay_regular_and_are_also_copied(self):
        s = self.scenario(seed='same-bytes'); sharer = self.completed(1, seed='same-bytes')
        shared = self.studio.assets.get(sharer['outputs'][0]['asset_id']); self.assertEqual(shared['sha256'], s['shas'][0])
        sharer['references'] = [{'file': s['upload'], 'role': 'subject'}]; self.studio._save(sharer)
        status, out = self.post(APPLY, self.body(s, self.plan(s)))
        self.assertEqual((status, out['stage']), (200, 'complete'))
        self.assertTrue((self.studio.experiments/'uploads'/s['upload']).is_file())
        self.assertEqual(sha(self.studio._upload_path(s['upload'], 'private')), sha(self.studio.experiments/'uploads'/s['upload']))
        self.assertEqual(sha(self.studio.assets.file(shared['id'])), shared['sha256'])  # the regular sibling's blob stays
        self.assertEqual(sha(self.studio.assets.file(s['ids'][0], privacy='private')), shared['sha256'])  # and Private holds its own copy
        self.assertNotEqual(self.studio.assets.file(shared['id']), self.studio.assets.file(s['ids'][0], privacy='private'))

    def test_rollback_and_publication_keep_a_private_blob_they_did_not_create(self):
        private = self.completed(1, seed='shared', privacy='private'); kept = self.studio.assets.file(private['outputs'][0]['asset_id'], privacy='private')
        s = self.scenario(seed='shared'); body = self.body(s, self.plan(s)); self.assertEqual(sha(kept), s['shas'][0])
        with self.crash_at('placed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        restarted = self.studio = self.restart()
        self.assertEqual(restarted.migration_recovery[0]['stage'], 'rolled-back')
        self.assertEqual(sha(kept), s['shas'][0])  # rollback removed only what it placed
        status, out = run_migration.apply(restarted, self.body(s, self.plan(s), request_id='second-attempt-identity'), 'all')
        self.assertEqual((status, out['stage']), (200, 'complete'))
        self.assertEqual(restarted.assets.file(s['ids'][0], privacy='private'), kept); self.assertEqual(sha(kept), s['shas'][0])


if __name__ == '__main__':
    unittest.main()
