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
import project_storage

APPLY = '/api/assets/migration-apply'
Base = planning.RunMigrationPlanTests.__dict__  # functions only: a TestCase class here would rerun the plan tests


class Crash(BaseException):
    """A process death: it bypasses every `except Exception` rollback, leaving disk state as a real crash would."""


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RunMigrationApplyTests(unittest.TestCase):
    setUp, close, tree = Base['setUp'], Base['close'], Base['tree']
    project, comparison, scene = Base['project'], Base['comparison'], Base['scene']

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
        status, out = self.post(APPLY, self.body(s, plan, destination='regular'))  # Both directions apply; a Regular run is already there
        self.assertEqual((status, out['code']), (409, 'migration_blocked')); self.assertIn('already_in_destination', {b['code'] for b in out['blockers']})
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

    # ---- Review round 1 ----
    def test_an_unfinished_journal_refuses_new_migrations_until_recovery(self):
        s = self.scenario(); body = self.body(s, self.plan(s)); staging = self.studio.experiments/'private/migrations'/body['request_id']
        real_copy, real_rmtree, raised = shutil.copyfile, shutil.rmtree, []
        def corrupt(src, dst, *a, **k):
            result = real_copy(src, dst, *a, **k)
            if Path(src).name == 'recipe.json': Path(dst).write_bytes(Path(dst).read_bytes()+b' ')
            return result
        def locked(path, *a, **k):
            if Path(path) == staging and not raised: raised.append(path); raise PermissionError(13, 'locked by another program')
            return real_rmtree(path, *a, **k)
        with patch.object(run_migration.shutil, 'copyfile', corrupt), patch.object(run_migration.shutil, 'rmtree', locked), self.assertRaises(PermissionError):
            run_migration.apply(self.studio, body, 'all')
        self.assertEqual(self.journal(s)['stage'], 'staging')
        second = self.body(s, self.plan(s), request_id='second-request-identity')
        with self.assertRaises(run_migration.WorkspaceError) as caught: run_migration.apply(self.studio, second, 'all')
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'migration_recovery_pending'))
        self.assertIn('private/migrations/'+body['request_id']+'.json', str(caught.exception)); self.assertIn('move', str(caught.exception))  # Names the file and the way out
        self.assertFalse((self.studio.experiments/'private/runs'/s['jid']).exists())
        self.assertFalse((self.studio.experiments/'private/migrations/second-request-identity.json').exists())
        restarted = self.studio = self.restart()
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'staging', 'stage': 'rolled-back'}])
        second = self.body(s, self.plan(s), request_id='second-request-identity')  # restart settled the queued child, so plan again
        self.assertEqual(run_migration.apply(restarted, second, 'all')[1]['stage'], 'complete')

    def test_recovery_never_deletes_what_another_committed_request_published(self):
        s = self.scenario(); body = self.body(s, self.plan(s))
        with self.crash_at('placed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        targets = [p['target'] for p in self.journal(s)['placements']]
        with self.studio.assets.connection() as db:  # As if a later request had committed the same run onto these files.
            db.execute(run_migration.MARKER_TABLE)
            db.execute('INSERT INTO run_migrations_v1 VALUES (?,?,?,?,?)', ('other-committed-request', '0'*64, json.dumps([s['jid']]), json.dumps(targets), self.journal(s)['created_at']+1))
        self.restart()
        self.assertTrue((self.studio.experiments/'private/runs'/s['jid']/'state.json').is_file())
        self.assertTrue((self.studio.experiments/'private/uploads'/s['upload']).is_file())
        for target in targets: self.assertTrue((self.studio.experiments/target).is_file(), target)

    def test_recovery_keeps_an_upload_that_a_run_created_after_apply_uses(self):
        s = self.scenario(); body = self.body(s, self.plan(s))
        with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        later = self.completed(1); later['references'] = [{'file': s['upload'], 'role': 'subject'}]; self.studio._save(later)
        restarted = self.restart()
        self.assertEqual(restarted.migration_recovery[0]['stage'], 'complete')
        self.assertEqual(sha(restarted._upload_path(s['upload'], 'regular')), sha(self.root/'fake-comfy/input'/s['upload']))
        self.assertEqual(restarted.jobs[s['jid']]['privacy'], 'private')

    def test_a_member_added_to_a_planned_collection_mid_copy_stops_publication(self):
        s = self.scenario(); outsider = self.completed(1)['outputs'][0]['asset_id']; body = self.body(s, self.plan(s))
        def add_member(stage):
            if stage == 'verified':
                with self.studio.assets.connection() as db:
                    db.execute('INSERT INTO collection_assets VALUES (?,?)', ('c-'+s['jid'], outsider))
                    db.execute('UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id=?', (outsider,))
        with patch.object(run_migration, '_checkpoint', add_member): status, out = self.post(APPLY, body)
        self.assertEqual((status, out['code'], out['stage']), (409, 'migration_stale', 'rolled-back'))
        self.assert_regular(s, self.studio)
        with self.studio.assets.connection() as db: self.assertEqual(db.execute('SELECT privacy FROM collections WHERE id=?', ('c-'+s['jid'],)).fetchone()[0], 'regular')

    def test_every_staged_copy_is_flushed_before_verification(self):
        s = self.scenario(); body = self.body(s, self.plan(s)); real, synced, seen = run_migration.os.fsync, [], []
        def fsync(fd): synced.append(fd); return real(fd)
        def checkpoint(stage):
            if stage == 'staging': seen.append((len(synced), sum(1 for p in (self.studio.experiments/'private/migrations'/body['request_id']).rglob('*') if p.is_file())))
        with patch.object(run_migration.os, 'fsync', fsync), patch.object(run_migration, '_checkpoint', checkpoint): status, out = self.post(APPLY, body)
        self.assertEqual(status, 200); flushed, staged = seen[0]
        self.assertGreater(staged, 0); self.assertGreaterEqual(flushed, staged + 1)  # every staged file, after the staging journal write

    def test_recovery_leaves_invalid_or_unmarked_journals_untouched(self):
        s = self.scenario(); body = self.body(s, self.plan(s))
        with self.crash_at('verified'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        folder = self.studio.experiments/'private/migrations'; bogus = folder/'bogus-journal-identity.json'
        bogus.write_text(json.dumps({'format': run_migration.FORMAT, 'request_id': 'someone-else-identity', 'stage': 'staging', 'job_ids': ['x'], 'placements': [], 'copies': []}))
        raw = bogus.read_bytes()
        journal_path = folder/(body['request_id']+'.json'); forged = dict(self.journal(s), stage='published'); journal_path.write_text(json.dumps(forged))
        restarted = self.restart()
        self.assertEqual(sorted(r['request_id'] for r in restarted.migration_recovery if 'error' in r), sorted([body['request_id'], 'bogus-journal-identity']))
        self.assertEqual(bogus.read_bytes(), raw); self.assertEqual(json.loads(journal_path.read_text()), forged)
        self.assertEqual({p.relative_to(self.studio.experiments).as_posix(): sha(p) for p in (self.studio.experiments/'runs'/s['jid']).rglob('*') if p.is_file()}, s['run_files'])
        self.assertEqual(restarted.jobs[s['jid']].get('privacy', 'regular'), 'regular')


    # ---- Follow-ups (#1785) ----
    def test_a_pending_stage_blocks_the_move_and_its_upload_stays_regular_if_one_appears_after_publication(self):
        s = self.scenario(); plan = self.plan(s)
        pid = self.comparison({'references': [{'file': s['upload']}], 'controls': {}})
        status, out = self.post(APPLY, self.body(s, plan))  # the pending stage appeared after this plan was made
        self.assertEqual((status, out['code']), (409, 'migration_blocked'), out)
        self.assertIn('pending_stage_upload', {b['code'] for b in out['blockers']}); self.assert_regular(s, self.studio)
        with self.studio.production.connect() as db: db.execute('DELETE FROM projects WHERE id=?', (pid,))
        body = self.body(s, self.plan(s))
        with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        self.comparison({'references': [{'file': s['upload']}], 'controls': {}})  # created between publication and the start-time cleanup
        restarted = self.restart()
        self.assertEqual(restarted.migration_recovery[0]['stage'], 'complete')
        self.assertEqual(sha(restarted._upload_path(s['upload'], 'regular')), sha(self.root/'fake-comfy/input'/s['upload']))
        self.assertEqual(restarted.jobs[s['jid']]['privacy'], 'private')

    def test_uploads_named_by_pending_stages_are_protected_and_unreadable_plans_protect_everything(self):
        s = self.scenario(); pid = self.comparison({'references': [{'file': s['upload']}], 'controls': {'reference': 'second.png'}}, {'controls': {'last_reference': 'third.png'}})
        self.assertEqual(run_migration._others(self.studio, {s['jid']}), {s['upload'], 'second.png', 'third.png'})
        self.studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'stage'}}, enqueue=False, job_id=project_storage.stage_job_id(pid, 1))
        self.assertEqual(run_migration._others(self.studio, {s['jid']}), {s['upload'], 'second.png'})  # stage B has a run now: its own job names its uploads
        self.project('{ not json')
        self.assertIsNone(run_migration._others(self.studio, {s['jid']})); self.assertIsNone(run_migration._disk_consumers(self.studio, {s['jid']}))

    def test_scene_project_copies_stay_in_place_and_are_part_of_the_receipt(self):
        s = self.scenario(); pid = self.scene(s['ids'][0]); path = self.studio.experiments/'projects'/pid/'inputs/source0.png'
        path.parent.mkdir(parents=True); path.write_bytes(b'scene bytes')
        plan = self.plan(s); self.assertIn(f'projects/{pid}/inputs/source0.png', {i['id'] for i in plan['items'] if i['kind'] == 'scene_copy'})
        status, out = self.post(APPLY, self.body(s, plan))
        self.assertEqual((status, out['stage']), (200, 'complete'), out)
        self.assertIn(f'projects/{pid}/inputs/source0.png', out['external_copies']); self.assertEqual(path.read_bytes(), b'scene bytes')

    def test_an_unreadable_run_record_keeps_every_upload_in_regular(self):
        s = self.scenario(); sharer = self.completed(1); sharer['references'] = [{'file': s['upload'], 'role': 'subject'}]; self.studio._save(sharer)
        (self.studio.experiments/'runs'/sharer['id']/'state.json').write_text('{ not json')  # Its controls cannot load, so it looks like it uses nothing.
        self.studio = self.restart(); self.assertIn('record_error', self.studio.jobs[sharer['id']])
        status, out = self.post(APPLY, self.body(s, self.plan(s)))
        self.assertTrue((self.studio.experiments/'uploads'/s['upload']).is_file())  # Regular keeps it, Private holds its own copy
        self.assertEqual((status, out['published'], out['stage']), (200, True, 'cleanup-needed'), out)
        self.assertIn('uploads/'+s['upload'], out['cleanup_remaining'])
        self.assertEqual(sha(self.studio._upload_path(s['upload'], 'private')), sha(self.studio.experiments/'uploads'/s['upload']))

    def test_recovery_with_unreadable_records_keeps_uploads_listed_then_a_later_start_clears_them(self):
        s = self.scenario(); body = self.body(s, self.plan(s))
        with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        bad = self.studio.experiments/'runs/unrelated-unreadable-run'; bad.mkdir(); (bad/'state.json').write_text('{ not json')
        restarted = self.studio = self.restart()
        self.assertTrue((self.studio.experiments/'uploads'/s['upload']).is_file())
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': 'cleanup-needed'}])
        self.assertIn('uploads/'+s['upload'], self.journal(s)['remaining'])
        shutil.rmtree(bad)  # The owner dealt with the unreadable record.
        again = self.studio = self.restart()
        self.assertEqual(again.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'cleanup-needed', 'stage': 'complete'}])
        self.assertEqual(self.journal(s)['remaining'], []); self.assert_moved(s, again)

    def test_a_forged_journal_path_outside_private_is_rejected_before_anything_is_deleted(self):
        for field in ('placements', 'copies'):
            with self.subTest(field):
                s = self.scenario(); body = self.body(s, self.plan(s))
                with self.crash_at('verified'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
                victim = self.studio.experiments/('uploads/victim-'+field+'.bin'); victim.write_bytes(b'precious')
                journal_path = self.studio.experiments/'private/migrations'/(body['request_id']+'.json')
                forged = self.journal(s); forged[field][0].update(target='uploads/victim-'+field+'.bin', **({'created': True} if field == 'placements' else {}))
                journal_path.write_text(json.dumps(forged))
                restarted = self.studio = self.restart()
                self.assertTrue(victim.is_file()); self.assertEqual(victim.read_bytes(), b'precious')
                self.assertEqual([r['request_id'] for r in restarted.migration_recovery if 'error' in r], [body['request_id']]); self.assertEqual(json.loads(journal_path.read_text()), forged)
                shutil.rmtree(self.studio.experiments/'private/migrations'/body['request_id'], ignore_errors=True); journal_path.unlink()


    # ---- Journal hardening (#1796) ----
    def test_a_forged_cleanup_source_or_thumbnail_is_rejected_before_cleanup_deletes_it(self):
        cases = (('asset source under uploads/', lambda j: j['copies'], 'asset', {'source': 'uploads/victim.bin'}),
                 ('upload source under runs/', lambda j: j['copies'], 'upload', {'source': 'runs/other-run/state.json'}),
                 ('run_file source of another run', lambda j: j['copies'], 'run_file', {'source': 'runs/other-run/state.json'}),
                 ('dot-dot source', lambda j: j['copies'], 'asset', {'source': 'workspace/../uploads/victim.bin'}),
                 ('thumbnail outside thumbs/', None, None, {'thumbnails': ['uploads/victim.bin']}))
        for name, pick, kind, change in cases:
            with self.subTest(name):
                s = self.scenario(); body = self.body(s, self.plan(s))
                with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
                victim = self.studio.experiments/'uploads/victim.bin'; victim.write_bytes(b'precious')
                other = self.studio.experiments/'runs/other-run/state.json'; other.parent.mkdir(parents=True, exist_ok=True); other.write_bytes(b'precious')
                journal_path = self.studio.experiments/'private/migrations'/(body['request_id']+'.json'); forged = self.journal(s)
                if pick: next(c for c in pick(forged) if c['kind'] == kind).update(change)
                else: forged.update(change)
                journal_path.write_text(json.dumps(forged))
                restarted = self.studio = self.restart()  # The journal is committed, so recovery would run cleanup, which unlinks these paths.
                try:
                    self.assertTrue(victim.is_file() and other.is_file(), 'cleanup deleted a path outside the Regular copy roots')
                    self.assertEqual([r['request_id'] for r in restarted.migration_recovery if 'error' in r], [body['request_id']]); self.assertEqual(json.loads(journal_path.read_text()), forged)
                finally:
                    shutil.rmtree(other.parent); victim.unlink(missing_ok=True); shutil.rmtree(self.studio.experiments/'private/migrations'/body['request_id'], ignore_errors=True); journal_path.unlink()

    def test_recovery_reads_a_record_that_fails_loader_validation_as_unreadable(self):
        s = self.scenario(); sharer = self.completed(1); self.assertIsNotNone(run_migration._disk_consumers(self.studio, {s['jid']}))
        state_path = self.studio.experiments/'runs'/sharer['id']/'state.json'; state = json.loads(state_path.read_text())
        body = self.body(s, self.plan(s))
        with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        state['references'] = {'file': s['upload']}; state_path.write_text(json.dumps(state))  # Parses, fails _validate_job_record, and names the upload where no list can show it.
        self.assertIsNone(run_migration._disk_consumers(self.studio, {s['jid']}))
        restarted = self.studio = self.restart()
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': 'cleanup-needed'}])
        self.assertTrue((self.studio.experiments/'uploads'/s['upload']).is_file()); self.assertIn('uploads/'+s['upload'], self.journal(s)['remaining'])

    def keep_all_crash(self, s):
        """Apply with an unreadable record on disk (journals keep_uploads 'all'), crash at the commit, leave the record broken."""
        bad = self.studio.experiments/'runs/unrelated-unreadable-run'; bad.mkdir(); (bad/'state.json').write_text('{ not json')
        self.studio = self.restart(); body = self.body(s, self.plan(s))
        with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        self.assertEqual(self.journal(s)['keep_uploads'], 'all')
        return body, bad

    def test_a_keep_all_is_kept_while_a_start_cannot_read_every_record_then_settles_normally(self):
        s = self.scenario(); body, bad = self.keep_all_crash(s)
        restarted = self.studio = self.restart()  # Still unreadable: fail closed, and the journal stays 'all'.
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': 'cleanup-needed'}])
        self.assertTrue((self.studio.experiments/'uploads'/s['upload']).is_file()); self.assertIn('uploads/'+s['upload'], self.journal(s)['remaining']); self.assertEqual(self.journal(s)['keep_uploads'], 'all')
        shutil.rmtree(bad)  # Every record reads now: the next start settles it as usual.
        again = self.studio = self.restart()
        self.assertEqual(again.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'cleanup-needed', 'stage': 'complete'}])
        self.assertEqual((self.journal(s)['remaining'], self.journal(s)['keep_uploads']), ([], [])); self.assert_moved(s, again)
        self.assertEqual(sha(again._upload_path(s['upload'], 'private')), sha(self.root/'fake-comfy/input'/s['upload']))
        invalid = self.journal(s); invalid.update(stage='cleanup-needed', keep_uploads='some'); (self.studio.experiments/'private/migrations'/(body['request_id']+'.json')).write_text(json.dumps(invalid))
        self.assertEqual([r['request_id'] for r in self.restart().migration_recovery if 'error' in r], [body['request_id']])  # The field is validated, not trusted

    def test_a_settled_keep_all_still_keeps_an_upload_a_retained_run_names(self):
        s = self.scenario(); sharer = self.completed(1); sharer['references'] = [{'file': s['upload'], 'role': 'subject'}]; self.studio._save(sharer)
        body, bad = self.keep_all_crash(s); shutil.rmtree(bad)
        again = self.studio = self.restart()
        self.assertEqual(again.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': 'complete'}])
        self.assertTrue((self.studio.experiments/'uploads'/s['upload']).is_file()); self.assertEqual(self.journal(s)['keep_uploads'], ['uploads/'+s['upload'], 'uploads/'+s['upload']+'.json'])

    def test_a_real_journal_with_a_thumbnail_a_sidecar_and_a_nested_run_file_passes_the_stricter_check_and_recovers(self):
        s = self.scenario(); nested = self.studio.experiments/'runs'/s['jid']/'frames/deep/f0.png'; nested.parent.mkdir(parents=True); nested.write_bytes(b'nested frame')
        s['run_files']['runs/'+s['jid']+'/frames/deep/f0.png'] = sha(nested); body = self.body(s, self.plan(s))
        with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        journal = self.journal(s); sources = {c['source'] for c in journal['copies']}
        self.assertIn('runs/'+s['jid']+'/frames/deep/f0.png', sources); self.assertTrue({'uploads/'+s['upload'], 'uploads/'+s['upload']+'.json'} <= sources); self.assertTrue(journal['thumbnails'])
        run_migration._check_journal(self.studio, journal, self.studio.experiments/'private/migrations'/(body['request_id']+'.json'))  # the real shapes, not hand-built ones
        restarted = self.studio = self.restart()
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': 'complete'}])
        self.assert_moved(s, restarted); self.assertEqual(self.journal(s)['remaining'], [])
        self.assertEqual((restarted.experiments/'private/runs'/s['jid']/'frames/deep/f0.png').read_bytes(), b'nested frame'); self.assertFalse((restarted.experiments/'runs'/s['jid']).exists())

    # ---- Private -> Regular (#1678, last direction) ----
    def private_scenario(self, outputs=3, seed=None):
        """A completed Private run with a Private upload, a Private thumbnail, a whole Private collection and a Private child."""
        job = self.completed(outputs, seed, privacy='private'); jid = job['id']; ids = [o['asset_id'] for o in job['outputs']]
        upload = self.studio.upload('ref.png', 'image/png', fixture.png(), privacy='private')
        job['references'] = [{'file': upload['file'], 'role': 'subject'}]; self.studio._save(job)
        experiments = self.studio.experiments; thumbs = experiments/'private/thumbs'; thumbs.mkdir(exist_ok=True)
        shas = [self.studio.assets.get(i, privacy='private')['sha256'] for i in ids]
        (thumbs/f'{shas[1]}-256-v1.webp').write_bytes(b'private thumb')
        with self.studio.assets.connection() as db:
            db.execute("INSERT INTO collections (id,name,privacy,created_at) VALUES (?,?,'private',1)", ('c-'+jid, 'Whole'))
            db.executemany('INSERT INTO collection_assets VALUES (?,?)', [('c-'+jid, i) for i in ids])
        child = self.studio.jobs[self.studio.create_job({'preset_id': 'demo', 'controls': {'positive': 'child'}, 'privacy': 'private'}, enqueue=False)['id']]
        child['parent_assets'] = [ids[0]]; self.studio._save(child)
        folder = experiments/'private/runs'/jid
        return dict(job=job, jid=jid, ids=ids, shas=shas, upload=upload['file'], child=child['id'], rows={i: self.studio.assets.get(i, privacy='private') for i in ids},
                    run_files={p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()},
                    external={p.name: sha(p) for p in (self.root/'fake-comfy').rglob('*') if p.is_file()},
                    state=json.loads((folder/'state.json').read_text()), recipe=json.loads((folder/'recipe.json').read_text()))

    def back_body(self, s, request_id=None):
        status, plan = self.post('/api/assets/migration-plan', {'workspace_id': self.workspace_id, 'destination': 'regular', 'job_ids': [s['jid']]})
        self.assertEqual((status, plan['blockers'], plan['apply_available']), (200, [], True), plan)
        return {'workspace_id': self.workspace_id, 'destination': 'regular', 'plan_sha256': plan['plan_sha256'], 'request_id': request_id or 'back-'+s['jid'][:16], 'job_ids': [s['jid']]}

    def assert_back(self, s, studio):
        """Everything the Private run owned now lives in the Regular roots, byte-identical except the classification field."""
        experiments, jid = self.studio.experiments, s['jid']
        job = studio.jobs[jid]; self.assertEqual(job.get('privacy', 'regular'), 'regular'); self.assertNotIn('record_error', job)
        self.assertEqual([o['asset_id'] for o in job['outputs']], s['ids'])
        self.assertFalse((experiments/'private/runs'/jid).exists())
        regular = experiments/'runs'/jid
        self.assertEqual({p.relative_to(regular).as_posix() for p in regular.rglob('*') if p.is_file()}, set(s['run_files']))
        for name, digest in s['run_files'].items():
            if name not in ('state.json', 'recipe.json'): self.assertEqual(sha(regular/name), digest, name)
        self.assertEqual(s['recipe'].get('privacy'), 'private'); self.assertEqual(s['state']['privacy'], 'private')
        self.assertEqual(json.loads((regular/'state.json').read_text()), dict(s['state'], privacy='regular'))
        self.assertEqual(json.loads((regular/'recipe.json').read_text()), {k: v for k, v in s['recipe'].items() if k != 'privacy'})  # as _save writes a Regular recipe
        for asset_id, before in s['rows'].items():
            row = studio.assets.get(asset_id)
            for key in ('id', 'job_id', 'output_index', 'sha256', 'bytes', 'path', 'lineage', 'source', 'title', 'tags'): self.assertEqual(row[key], before[key], key)
            self.assertEqual((row['privacy'], row['metadata_revision']), ('regular', before['metadata_revision']+1))
            self.assertEqual(sha(studio.assets.root/row['path']), row['sha256'])
            self.assertFalse((experiments/'private'/row['path']).exists())
        self.assertTrue(set(s['ids']) <= {a['id'] for a in studio.assets.snapshot('regular')['assets']})
        self.assertFalse(set(s['ids']) & {a['id'] for a in studio.assets.snapshot('private')['assets']})
        self.assertFalse(list((experiments/'private/thumbs').glob(s['shas'][1]+'*')))
        self.assertFalse((experiments/'private/uploads'/s['upload']).exists()); self.assertFalse((experiments/'private/uploads'/(s['upload']+'.json')).exists())
        self.assertEqual(sha(studio._upload_path(s['upload'], 'regular')), sha(self.root/'fake-comfy/input'/s['upload']))
        with studio.assets.connection() as db: self.assertEqual(db.execute('SELECT privacy FROM collections WHERE id=?', ('c-'+jid,)).fetchone()[0], 'regular')
        child = studio.jobs[s['child']]; self.assertEqual((child['privacy'], child['parent_assets']), ('private', [s['ids'][0]]))
        self.assertEqual({p.name: sha(p) for p in (self.root/'fake-comfy').rglob('*') if p.is_file()}, s['external'])
        self.assertFalse((experiments/'private/migrations'/('back-'+jid[:16])).exists())

    def assert_still_private(self, s, studio):
        experiments, jid = self.studio.experiments, s['jid']
        self.assertEqual(studio.jobs[jid]['privacy'], 'private'); self.assertNotIn('record_error', studio.jobs[jid])
        folder = experiments/'private/runs'/jid
        self.assertEqual({p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}, s['run_files'])
        self.assertFalse((experiments/'runs'/jid).exists())
        for asset_id, before in s['rows'].items():
            row = studio.assets.get(asset_id, privacy='private'); self.assertEqual((row['privacy'], row['metadata_revision']), ('private', before['metadata_revision']))
            self.assertTrue((experiments/'private'/row['path']).is_file()); self.assertFalse((studio.assets.root/row['path']).exists())
        self.assertTrue((experiments/'private/uploads'/s['upload']).is_file()); self.assertFalse((experiments/'uploads'/s['upload']).exists())
        self.assertTrue(list((experiments/'private/thumbs').glob(s['shas'][1]+'*')))
        self.assertNotIn(jid, self.regular_job_ids())
        self.assertFalse((experiments/'private/migrations'/('back-'+jid[:16])).exists())

    def test_private_to_regular_moves_the_whole_run_into_the_regular_roots_and_survives_restart(self):
        s = self.private_scenario(); body = self.back_body(s)
        self.assertNotIn(s['jid'], self.regular_job_ids()); self.assertEqual(self.get('/api/jobs/'+s['jid'])[0], 404)
        status, out = self.post(APPLY, body)
        self.assertEqual((status, out['stage'], out['published'], out['destination'], out['cleanup_remaining']), (200, 'complete', True, 'regular', []), out)
        self.assertEqual((out['job_ids'], sorted(out['asset_ids']), out['collection_ids']), ([s['jid']], sorted(s['ids']), ['c-'+s['jid']]))
        self.assert_back(s, self.studio)
        self.assertIn(s['jid'], self.regular_job_ids()); self.assertEqual(self.get('/api/jobs/'+s['jid'])[0], 200)
        journal = self.journal(s, body['request_id']); self.assertEqual((journal['source'], journal['destination'], journal['stage']), ('private', 'regular', 'complete'))
        restarted = self.restart(); self.assertEqual(restarted.migration_recovery, []); self.assert_back(s, restarted)
        self.assertIn(s['jid'], self.regular_job_ids())

    def test_private_to_regular_replays_its_receipt_and_never_reexecutes(self):
        s = self.private_scenario(); body = self.back_body(s); first = self.post(APPLY, body)
        self.assertEqual(first[0], 200)
        with patch.object(run_migration, 'plan', side_effect=AssertionError('replayed a mutation')):
            self.assertEqual(self.post(APPLY, body), first)
            self.assertEqual(self.post(APPLY, dict(body, destination='private'))[1]['code'], 'migration_request_conflict')  # the direction is part of the identity
        self.assert_back(s, self.studio)

    def test_a_private_upload_another_private_run_uses_is_copied_and_kept(self):
        s = self.private_scenario(); sharer = self.completed(1, privacy='private')
        sharer['references'] = [{'file': s['upload'], 'role': 'subject'}]; self.studio._save(sharer)
        regular_user = self.completed(1); regular_user['references'] = [{'file': 'unrelated.png', 'role': 'subject'}]; self.studio._save(regular_user)
        status, out = self.post(APPLY, self.back_body(s))
        self.assertEqual((status, out['stage'], out['cleanup_remaining']), (200, 'complete', []), out)
        kept = self.studio.experiments/'private/uploads'/s['upload']
        self.assertTrue(kept.is_file() and (kept.parent/(s['upload']+'.json')).is_file(), 'the other Private run still reads its upload privately')
        self.assertEqual(sha(self.studio._upload_path(s['upload'], 'regular')), sha(kept))
        self.assertEqual(self.journal(s, 'back-'+s['jid'][:16])['keep_uploads'], ['private/uploads/'+s['upload'], 'private/uploads/'+s['upload']+'.json'])
        self.assertEqual(run_migration._others(self.studio, {s['jid']}, 'private'), {s['upload']}, 'only Private runs read a Private upload')
        self.assertEqual(run_migration._disk_consumers(self.studio, {s['jid']}, 'private'), {s['upload']})
        self.assertIn('unrelated.png', run_migration._disk_consumers(self.studio, {s['jid']}, 'regular'))

    def test_private_to_regular_crash_at_every_journal_boundary_recovers_without_leaving_two_copies(self):
        cases = (('staging', 'staging', 'rolled-back'), ('verified', 'verified', 'rolled-back'), ('placed', 'verified', 'rolled-back'),
                 ('committed', 'verified', 'complete'), ('published', 'published', 'complete'), ('cleanup', 'published', 'complete'))
        for crash, from_stage, stage in cases:
            with self.subTest(crash=crash):
                s = self.private_scenario(); body = self.back_body(s)
                with self.crash_at(crash), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
                self.assertEqual(self.journal(s, body['request_id'])['stage'], from_stage)
                restarted = self.studio = self.restart()
                self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': from_stage, 'stage': stage}])
                if stage == 'complete': self.assert_back(s, restarted); self.assertIn(s['jid'], self.regular_job_ids())
                else: self.assert_still_private(s, restarted)
                status, out = run_migration.apply(restarted, body, 'all')
                self.assertEqual((status, out['stage'], out['recovery']['from_stage'], out['published']), (200 if stage == 'complete' else 500, stage, from_stage, stage == 'complete'))
                if stage == 'rolled-back': self.assertIn('stayed private', out['error'])

    def test_a_run_moved_to_private_and_back_rolls_its_own_placement_back(self):
        s = self.scenario(); self.assertEqual(self.post(APPLY, self.body(s, self.plan(s)))[1]['stage'], 'complete')
        body = self.back_body(s)  # The earlier, committed Regular->Private request names this run; it must not shield the placement below.
        with self.crash_at('placed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
        self.assertTrue((self.studio.experiments/'runs'/s['jid']).is_dir())
        restarted = self.studio = self.restart()
        self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': 'rolled-back'}])
        self.assertFalse((self.studio.experiments/'runs'/s['jid']).exists(), 'a regular copy of a Private run was left behind')
        self.assertEqual(restarted.jobs[s['jid']]['privacy'], 'private'); self.assertNotIn(s['jid'], self.regular_job_ids())
        for asset_id in s['ids']: self.assertFalse((restarted.assets.root/s['rows'][asset_id]['path']).exists())
        self.assertEqual(run_migration.apply(restarted, self.back_body(s, 'back-again-identity'), 'all')[1]['stage'], 'complete')
        self.assertEqual(restarted.jobs[s['jid']]['privacy'], 'regular'); self.assertFalse((self.studio.experiments/'private/runs'/s['jid']).exists())

    def test_a_journal_in_the_shape_written_before_private_to_regular_still_recovers(self):
        for crash, stage in (('verified', 'rolled-back'), ('committed', 'complete')):
            with self.subTest(crash=crash):
                s = self.scenario(); body = self.body(s, self.plan(s))
                with self.crash_at(crash), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
                path = self.studio.experiments/'private/migrations'/(body['request_id']+'.json'); old = self.journal(s)
                self.assertEqual(old.pop('source'), 'regular'); path.write_text(json.dumps(old))  # exactly the pre-change shape: no source field
                restarted = self.studio = self.restart()
                self.assertEqual(restarted.migration_recovery, [{'request_id': body['request_id'], 'from_stage': 'verified', 'stage': stage}])
                if stage == 'complete': self.assert_moved(s, restarted)
                else: self.assert_regular(s, restarted)
                self.assertNotIn('source', self.journal(s))

    def test_forged_journal_paths_are_rejected_in_the_private_to_regular_direction(self):
        cases = (('asset source under the regular root', 'asset', {'source': 'workspace/media/victim.bin'}),
                 ('upload source under regular uploads', 'upload', {'source': 'uploads/victim.bin'}),
                 ('run_file source of another private run', 'run_file', {'source': 'private/runs/other-run/state.json'}),
                 ('target that is not the derived destination', 'asset', {'target': 'uploads/victim.bin'}),
                 ('placement that is no copy', None, {'placements': [{'target': 'uploads/victim.bin', 'created': True}]}),
                 ('thumbnail under the regular thumbs', None, {'thumbnails': ['workspace/thumbs/victim.webp']}),
                 ('a direction that moves nowhere', None, {'source': 'private', 'destination': 'private'}))
        for name, kind, change in cases:
            with self.subTest(name):
                s = self.private_scenario(); body = self.back_body(s)
                with self.crash_at('committed'), self.assertRaises(Crash): run_migration.apply(self.studio, body, 'all')
                victims = [self.studio.experiments/p for p in ('uploads/victim.bin', 'workspace/media/victim.bin', 'private/runs/other-run/state.json', 'workspace/thumbs/victim.webp')]
                for victim in victims: victim.parent.mkdir(parents=True, exist_ok=True); victim.write_bytes(b'precious')
                journal_path = self.studio.experiments/'private/migrations'/(body['request_id']+'.json'); forged = self.journal(s, body['request_id'])
                if kind: next(c for c in forged['copies'] if c['kind'] == kind).update(change)
                else: forged.update(change)
                journal_path.write_text(json.dumps(forged))
                restarted = self.studio = self.restart()
                try:
                    for victim in victims: self.assertEqual(victim.read_bytes(), b'precious', victim)
                    self.assertEqual([r['request_id'] for r in restarted.migration_recovery if 'error' in r], [body['request_id']]); self.assertEqual(json.loads(journal_path.read_text()), forged)
                finally:
                    for victim in victims: victim.unlink(missing_ok=True)
                    shutil.rmtree(self.studio.experiments/'private/runs/other-run', ignore_errors=True); shutil.rmtree(self.studio.experiments/'private/migrations'/body['request_id'], ignore_errors=True); journal_path.unlink()

if __name__ == '__main__':
    unittest.main()
