"""Causal regressions for privacy in secondary metadata and diagnostic reads."""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_creation_privacy_review as core_fixture
import test_creation_privacy_workspace as workspace_fixture
import test_asset_family as family_fixture
from studio_workflow import asset_family


class PrivacyCatalogueProjectionTests(unittest.TestCase):
    setUp = workspace_fixture.CreationPrivacyWorkspaceTests.setUp
    command = workspace_fixture.CreationPrivacyWorkspaceTests.command

    def observations(self, privacy='regular'):
        return (self.store.asset_page(limit=1, filters={'privacy':privacy}, include_collections=True),
                self.store.asset_selection([self.regular], workspace_id=self.scope, privacy=privacy),
                self.store.collection_page(limit=1, privacy=privacy))

    def test_private_mutations_leave_every_regular_observation_and_cursor_unchanged(self):
        second = self.store.register(dict(self.regular_job, id='second-ordinary-job', created_at=3), 0, self.source)
        for name in ('Ordinary A', 'Ordinary B'): self.store.collection({'name':name})
        private_collection = self.store.collection({'name':'Private A'}, privacy='private')['id']
        before = self.observations()
        self.assertIsNotNone(before[0]['next_cursor']); self.assertIsNotNone(before[2]['next_cursor'])
        private_ids = []
        def insert(): private_ids.append(self.store.register(dict(self.private_job, id='new-private-job'), 0, self.source))
        def delete_asset():
            with self.store.connection() as db: db.execute('DELETE FROM assets WHERE id=?', (private_ids[0],))
        operations = (
            ('insert', insert),
            ('edit', lambda:self.store.update(self.command([self.private], action='edit', notes='PRIVATE-NOTES'), privacy='private')),
            ('create collection', lambda:self.store.collection({'name':'Private B'}, privacy='private')),
            ('rename collection', lambda:self.store.collection({'action':'rename','id':private_collection,'name':'Private C'}, privacy='private')),
            ('add membership', lambda:self.store.update(self.command([self.private], action='add_collection', collection_id=private_collection), privacy='private')),
            ('remove membership', lambda:self.store.update(self.command([self.private], action='remove_collection', collection_id=private_collection), privacy='private')),
            ('delete collection', lambda:self.store.collection({'action':'delete','id':private_collection}, privacy='private')),
            ('delete asset', delete_asset),
        )
        for name, mutate in operations:
            with self.subTest(operation=name):
                mutate()
                self.assertEqual(self.observations(), before)
                page = self.store.asset_page(limit=1, cursor=before[0]['next_cursor'])
                self.assertEqual([a['id'] for a in page['assets']], [self.regular])
                self.assertNotEqual(page['assets'][0]['id'], second)
                self.assertEqual(len(self.store.collection_page(limit=1, cursor=before[2]['next_cursor'])['collections']), 1)

    def test_regular_mutation_leaves_private_cursor_and_selection_unchanged(self):
        self.store.register(dict(self.private_job, id='second-private-job', created_at=3), 0, self.source)
        for name in ('Private A', 'Private B'): self.store.collection({'name':name}, privacy='private')
        before = self.observations('private')
        self.store.update(self.command([self.regular], action='edit', title='Changed ordinary title'))
        self.store.collection({'name':'New ordinary shelf'})
        self.assertEqual(self.observations('private'), before)
        page = self.store.asset_page(limit=1, filters={'privacy':'private'}, cursor=before[0]['next_cursor'])
        self.assertEqual(page['assets'][0]['id'], self.private)
        self.assertEqual(len(self.store.collection_page(limit=1, privacy='private', cursor=before[2]['next_cursor'])['collections']), 1)

    def test_all_scope_still_observes_changes_to_either_classification(self):
        for privacy, identifier in (('private',self.private), ('regular',self.regular)):
            with self.subTest(privacy=privacy):
                before = self.store.asset_page(limit=1, filters={'privacy':'all'})
                self.store.update(self.command([identifier], action='edit', favorite=True), privacy=privacy)
                after = self.store.asset_page(limit=1, filters={'privacy':'all'})
                self.assertGreater(after['catalogue']['revision'], before['catalogue']['revision'])
                with self.assertRaises(workspace_fixture.workspace.WorkspaceError) as error:
                    self.store.asset_page(limit=1, filters={'privacy':'all'}, cursor=before['next_cursor'])
                self.assertEqual(error.exception.code, 'asset_cursor_stale')

    def test_raw_reclassification_invalidates_both_affected_scope_stamps(self):
        before = {p:self.observations(p)[0]['catalogue'] for p in ('regular','private','all')}
        with self.store.connection() as db: db.execute("UPDATE assets SET privacy='regular' WHERE id=?", (self.private,))
        for privacy, stamp in before.items():
            with self.subTest(privacy=privacy):
                self.assertNotEqual(self.observations(privacy)[0]['catalogue'], stamp)

    def test_private_parent_deletes_cascade_without_changing_regular_stamps(self):
        for parent in ('asset','collection'):
            with self.subTest(parent=parent):
                asset = self.store.register(dict(self.private_job, id='cascade-private-'+parent), 0, self.source)
                collection = self.store.collection({'name':'Private cascade '+parent}, privacy='private')['id']
                self.store.update(self.command([asset], action='add_collection', collection_id=collection), privacy='private')
                before = self.observations(); private_before = self.observations('private')[0]['catalogue']
                with self.store.connection() as db:
                    db.execute('DELETE FROM '+('assets' if parent=='asset' else 'collections')+' WHERE id=?',
                               (asset if parent=='asset' else collection,))
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM collection_assets WHERE collection_id=?', (collection,)).fetchone()[0], 0)
                self.assertEqual(self.observations(), before)
                self.assertNotEqual(self.observations('private')[0]['catalogue'], private_before)

    def test_membership_move_updates_both_visible_scopes_atomically(self):
        regular = self.store.collection({'name':'Ordinary shelf'})['id']
        private = self.store.collection({'name':'Private shelf'}, privacy='private')['id']
        self.store.update(self.command([self.regular], action='add_collection', collection_id=regular))
        before = {p:self.observations(p)[0]['catalogue'] for p in ('regular','private','all')}
        with self.store.connection() as db:
            db.execute('UPDATE collection_assets SET collection_id=?,asset_id=? WHERE collection_id=? AND asset_id=?',
                       (private,self.private,regular,self.regular))
        for privacy, stamp in before.items():
            with self.subTest(privacy=privacy): self.assertNotEqual(self.observations(privacy)[0]['catalogue'], stamp)

    def test_invisible_corrupt_cross_scope_membership_does_not_disclose_hidden_activity(self):
        collection = self.store.collection({'name':'Ordinary shelf'})['id']
        before = {p:self.observations(p) for p in ('regular','private')}
        all_before = self.observations('all')[0]['catalogue']
        with self.store.connection() as db:
            db.execute('INSERT INTO collection_assets (collection_id,asset_id) VALUES (?,?)', (collection,self.private))
        for privacy, result in before.items():
            with self.subTest(privacy=privacy): self.assertEqual(self.observations(privacy), result)
        self.assertNotEqual(self.observations('all')[0]['catalogue'], all_before)

    def test_legacy_stamp_migration_preserves_rows_and_invalidates_old_scope_cursors(self):
        before = self.store.snapshot(privacy='all')
        with self.store.connection() as db:
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'asset_read_%'").fetchall():
                db.execute('DROP TRIGGER '+row[0])
            db.execute('DROP TABLE asset_read_state_v1')
            db.execute('CREATE TABLE asset_read_state_v1 (singleton INTEGER PRIMARY KEY,version INTEGER,epoch TEXT,revision INTEGER)')
            db.execute('INSERT INTO asset_read_state_v1 VALUES (1,1,?,900)', ('a'*32,))
        self.store = workspace_fixture.workspace.AssetWorkspace(self.root)
        self.assertEqual(self.store.snapshot(privacy='all'), before)
        regular = self.store.asset_page()['catalogue']; private = self.store.asset_page(filters={'privacy':'private'})['catalogue']
        self.assertNotEqual(regular['epoch'], 'a'*32); self.assertNotEqual(private['epoch'], regular['epoch'])
        self.assertEqual(regular['revision'], 0); self.assertEqual(private['revision'], 0)
        self.assertEqual(self.store.asset_page(filters={'privacy':'all'})['catalogue'], {'epoch':'a'*32,'revision':900})
        with self.store.connection() as db: db.execute("UPDATE assets SET title='New ordinary title' WHERE id=?", (self.regular,))
        self.assertEqual(self.store.asset_page()['catalogue']['revision'], 1)
        self.assertEqual(self.store.asset_page(filters={'privacy':'private'})['catalogue'], private)

    def test_invalid_scoped_stamp_refuses_mutation_and_is_never_reset(self):
        with self.store.connection() as db: db.execute('UPDATE asset_read_state_v1 SET regular_revision=?', (2**53-1,))
        before = self.store.get(self.regular)
        with self.assertRaises(workspace_fixture.workspace.WorkspaceError) as error:
            self.store.update(self.command([self.regular], action='edit', title='Must not commit'))
        self.assertEqual(error.exception.code, 'asset_read_unavailable')
        self.assertEqual(self.store.get(self.regular), before)
        with self.store.connection() as db: db.execute('PRAGMA ignore_check_constraints=ON'); db.execute("UPDATE asset_read_state_v1 SET regular_revision='invalid'")
        with self.assertRaises(ValueError): workspace_fixture.workspace.AssetWorkspace(self.root)
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT regular_revision FROM asset_read_state_v1').fetchone()[0], 'invalid')


class PrivacyFamilyProjectionTests(unittest.TestCase):
    setUp = family_fixture.AssetFamilyTests.setUp

    def test_regular_family_never_joins_private_job_controls_at_any_depth(self):
        job = self.studio.jobs['family-job-1']; job['privacy']='private'; job['controls']['denoise']='PRIVATE-FAMILY-CANARY'
        for privacy in ('regular','all'):
            with self.subTest(privacy=privacy):
                result = asset_family.observe(self.studio,self.ids[-1],workspace_id=self.scope,privacy=privacy)
                children = asset_family.observe(self.studio,self.ids[0],workspace_id=self.scope,privacy=privacy,children=True)
                self.assertNotIn('PRIVATE-FAMILY-CANARY', json.dumps([result,children]))
                self.assertEqual(result['nodes'][-1]['strength'], '0.3')

    def test_private_family_keeps_matching_job_controls(self):
        self.studio.jobs['family-job-3']['privacy']='private'
        with self.store.connection() as db: db.execute("UPDATE assets SET privacy='private' WHERE id=?", (self.ids[-1],))
        result = asset_family.observe(self.studio,self.ids[-1],workspace_id=self.scope,privacy='private')
        self.assertEqual(result['nodes'][0]['strength'], '0.3')

    def test_all_scope_cannot_recall_a_mismatched_job_recipe(self):
        self.studio.jobs['family-job-3']['privacy']='private'
        with patch.object(self.studio,'export_recipe', wraps=self.studio.export_recipe) as export:
            with self.assertRaises(ValueError):
                asset_family.recall(self.studio,self.ids[-1],workspace_id=self.scope,privacy='all')
            export.assert_not_called()


class PrivacyWorkerProjectionTests(unittest.TestCase):
    setUp = core_fixture.CorePrivacyReviewTests.setUp
    tearDown = core_fixture.CorePrivacyReviewTests.tearDown
    studio = core_fixture.CorePrivacyReviewTests.studio

    def worker_failure(self, privacy):
        studio=self.studio()
        job=studio.create_job({'preset_id':'demo','privacy':privacy,'controls':{'positive':'PRIVATE-HEALTH-CANARY'}},enqueue=False)
        trace=io.StringIO()
        with patch.object(studio.queue,'get',side_effect=[('generate',job['id']),KeyboardInterrupt]), \
             patch.object(studio,'_run',side_effect=RuntimeError('execution failed')), \
             patch.object(studio,'_save',side_effect=OSError('PRIVATE-HEALTH-CANARY '+str(studio._job_directory(job['id'])))), \
             patch('sys.stderr',trace):
            with self.assertRaises(KeyboardInterrupt): studio._work()
        return studio,job,trace.getvalue()

    def test_private_worker_failure_keeps_internal_evidence_but_redacts_health_and_log(self):
        studio,job,trace=self.worker_failure('private')
        self.assertEqual(studio.worker_failure['id'],job['id'])
        self.assertIn('PRIVATE-HEALTH-CANARY',studio.worker_failure['recording_error'])
        internal=copy.deepcopy(studio.worker_failure)
        for online in (True,False):
            with self.subTest(online=online), patch.object(studio,'_request',side_effect=None if online else OSError('offline'),return_value={}):
                result=studio.health()
                self.assertTrue(result['degraded']);self.assertIsNotNone(result['worker_failure'])
                self.assertNotIn(job['id'],json.dumps(result));self.assertNotIn('PRIVATE-HEALTH-CANARY',json.dumps(result))
                self.assertEqual(studio.worker_failure,internal)
        self.assertNotIn(job['id'],trace);self.assertNotIn('PRIVATE-HEALTH-CANARY',trace)

    def test_private_failure_stays_redacted_when_job_is_no_longer_in_memory(self):
        studio,job,_=self.worker_failure('private');del studio.jobs[job['id']]
        with patch.object(studio,'_request',side_effect=OSError('offline')):
            result=studio.health()
        self.assertNotIn(job['id'],json.dumps(result));self.assertNotIn('PRIVATE-HEALTH-CANARY',json.dumps(result))

    def test_regular_worker_failure_retains_the_existing_diagnostic_envelope(self):
        studio,job,trace=self.worker_failure('regular')
        with patch.object(studio,'_request',return_value={}): result=studio.health()
        self.assertEqual(result['worker_failure'],studio.worker_failure)
        self.assertIn(job['id'],trace);self.assertIn('PRIVATE-HEALTH-CANARY',trace)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the health view contract')
    def test_private_worker_alert_renders_without_identity_or_raw_error(self):
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('creation_privacy_health.cjs'))],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__': unittest.main()
