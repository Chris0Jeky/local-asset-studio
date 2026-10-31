"""Saved-scene return links use real disposable stores and never run media tools."""
import json
import unittest
from unittest.mock import patch

import test_workspace_continue as fixture_module
from studio_av import project as av
import av_projects


class ContinueSceneTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.ContinueCardTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.studio=self.fixture.studio;self.workspace=self.fixture.workspace;self.asset=self.fixture.asset
        for mocked in (patch.object(self.studio.production.av,'executables',return_value={}),
                       patch.object(av_projects,'validate_media',side_effect=lambda p,root,tools:(av.validate(p,root),{}))):
            mocked.start();self.addCleanup(mocked.stop)

    def scene(self, ids=None):
        return self.studio.production.av.create({'action':'create','name':'Saved scene',
            'asset_ids':ids or [self.asset['id']],'frames_per_shot':24})

    def request(self, scope='regular', workspace=None):return self.fixture.request(scope,workspace)

    def test_latest_saved_scene_beyond_six_coexists_with_native_without_read_mutations(self):
        native=self.fixture.fixture.prepare();scenes=[self.scene() for _ in range(8)]
        with self.studio.production.connect() as db:
            db.execute('UPDATE projects SET created=1')
            db.execute('UPDATE projects SET created=9 WHERE id=?',(scenes[-1]['id'],))
            before=[tuple(row) for row in db.execute('SELECT * FROM projects ORDER BY id')]
        code,result=self.request();self.assertEqual(code,200,result)
        entry=result.get('scene',{})
        self.assertEqual(entry.get('state'),'ready',result)
        self.assertEqual(entry['plan'],{'id':scenes[-1]['id'],'name':'Saved scene','created_at':9,
            'revision':0,'status':'planned','render':None,'completed_revision':None})
        self.assertEqual(result['native']['plan']['id'],native['id'])
        with self.studio.production.connect() as db:
            self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM projects ORDER BY id')],before)
        self.assertNotIn('source',json.dumps(entry));self.assertFalse(self.studio.requests);self.assertTrue(self.studio.queue.empty())

    def test_empty_private_all_and_exact_workspace(self):
        self.assertEqual(self.request()[1]['scene'],{'state':'empty','scope':'regular'})
        scene=self.scene()
        with patch.object(self.studio.production,'connect',side_effect=AssertionError('Private must not read production')):
            self.assertEqual(self.request('private')[1]['scene'],{'state':'excluded','scope':'regular'})
        self.assertEqual(self.request('all')[1]['scene']['plan']['id'],scene['id'])
        self.assertEqual(self.request('all')[1]['scene']['scope'],'regular')
        self.assertEqual(self.request(workspace='f'*32)[0],409)
        self.assertEqual(self.request(workspace='../bad')[0],400)

    def test_creation_ties_keep_recorded_lifecycle_states(self):
        scenes=[self.scene() for _ in range(2)];newest=max(scene['id'] for scene in scenes)
        with self.studio.production.connect() as db:db.execute('UPDATE projects SET created=12')
        for status in ('planned','completed','failed','interrupted','cancelled'):
            self.studio.production._mutate(newest,status=status)
            entry=self.request()[1]['scene']['plan']
            self.assertEqual((entry['id'],entry['created_at'],entry['status']),(newest,12,status))
            self.assertIsNone(entry['render']);self.assertIsNone(entry['completed_revision'])

    def test_identical_sources_in_another_workspace_do_not_establish_scene_ownership(self):
        from workspace import AssetWorkspace
        scene=self.scene();original=self.studio.assets
        second=AssetWorkspace(self.fixture.fixture.root/'scene-other-workspace')
        with original.connection() as source,second.connection() as target:
            source.backup(target)
            target.execute("UPDATE workspace_identity SET id=? WHERE singleton=1",('f'*32,))
        self.studio.assets=second
        try:
            code,result=self.request(workspace='f'*32)
            self.assertEqual(code,200,result)
            self.assertEqual(result['scene']['state'],'empty',result)
            self.assertNotIn(scene['id'],json.dumps(result))
        finally:self.studio.assets=original

    def test_scene_without_matching_immutable_workspace_evidence_is_unavailable(self):
        scene=self.scene();identifier=scene['id']
        with self.studio.production.connect() as db:
            saved=db.execute('SELECT document FROM av_events WHERE project_id=? AND revision=0',(identifier,)).fetchone()[0]
        for identity in (None,'bad','f'*32):
            document=json.loads(saved)
            if identity is None:document.pop('workspace_id',None)
            else:document['workspace_id']=identity
            with self.studio.production.connect() as db:
                db.execute('UPDATE av_events SET document=? WHERE project_id=? AND revision=0',(json.dumps(document),identifier))
            self.assertEqual(self.request()[1]['scene']['state'],'unavailable')

    def test_workspace_identity_change_during_intake_cannot_commit_a_scene(self):
        from workspace import WorkspaceError
        def change(*args):
            with self.studio.assets.connection() as db:
                db.execute("UPDATE workspace_identity SET id=? WHERE singleton=1",('f'*32,))
        with patch.object(av_projects,'validate_media',side_effect=change):
            with self.assertRaisesRegex(WorkspaceError,'different Workspace'):self.scene()
        with self.studio.production.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM av_documents').fetchone()[0],0)
        self.assertFalse(self.studio.requests);self.assertTrue(self.studio.queue.empty())

    def test_newer_failed_attempt_and_older_completed_revision_remain_distinct(self):
        scene=self.scene();identifier=scene['id']
        self.studio.production.av.command(identifier,{'action':'edit','expected_revision':0,
            'section':'shots','clip_id':'shot0','changes':{'frames':48}})
        with self.studio.production.connect() as db:
            for key,revision,status,created in [('c'*32,0,'completed',1),('f'*32,1,'failed',2)]:
                db.execute('INSERT INTO av_renders VALUES (?,?,?,?,?,?,?)',(key,identifier,revision,'{}',status,'{}',created))
            before={table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
                    for table in ('av_documents','av_events','av_renders','av_exports')}
        self.studio.production._mutate(identifier,status='failed')
        entry=self.request()[1]['scene']['plan']
        self.assertEqual((entry['revision'],entry['status']),(1,'failed'))
        self.assertEqual(entry['render'],{'revision':1,'status':'failed'});self.assertEqual(entry['completed_revision'],0)
        with self.studio.production.connect() as db:
            self.assertEqual({table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in before},before)

    def test_latest_missing_file_marker_or_fingerprint_never_falls_back(self):
        self.scene();latest=self.scene();path=self.studio.production.root/latest['id']/'plan.json';raw=path.read_bytes()
        path.unlink();self.assertEqual(self.request()[1]['scene']['state'],'unavailable');path.write_bytes(raw)
        marker=path.parent/'.incomplete-create';marker.write_text('incomplete')
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable');marker.unlink()
        saved=json.loads(raw);saved['name']='Changed file';path.write_text(json.dumps(saved))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable');path.write_bytes(raw)
        with self.studio.production.connect() as db:
            saved['sha256']='f'*64;db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(saved),latest['id']))
        path.write_text(json.dumps(saved));self.assertEqual(self.request()[1]['scene']['state'],'unavailable')

    def test_malformed_or_missing_scene_records_are_not_empty(self):
        latest=self.scene();identifier=latest['id']
        with self.studio.production.connect() as db:
            saved={table:dict(db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identifier,)).fetchone())
                   for table,key in [('projects','id'),('av_documents','project_id'),('av_events','project_id')]}
        typo=json.loads(saved['projects']['plan']);typo['kind']='av-typo'
        cases=[('projects','plan','not json'),('projects','plan',json.dumps(typo)),('projects','state','[]'),
               ('projects','created','not a date'),('av_documents','document','null'),('av_documents','revision',1),
               ('av_events','document','{}')]
        for table,column,value in cases:
            key='id' if table=='projects' else 'project_id'
            with self.subTest(table=table,column=column):
                with self.studio.production.connect() as db:db.execute('UPDATE '+table+' SET '+column+'=? WHERE '+key+'=?',(value,identifier))
                self.assertEqual(self.request()[1]['scene']['state'],'unavailable')
                with self.studio.production.connect() as db:db.execute('UPDATE '+table+' SET '+column+'=? WHERE '+key+'=?',(saved[table][column],identifier))
        with self.studio.production.connect() as db:db.execute('DELETE FROM av_events WHERE project_id=?',(identifier,))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable')
        with self.studio.production.connect() as db:
            row=saved['av_events'];db.execute('INSERT INTO av_events VALUES (?,?,?,?)',(row['project_id'],row['revision'],row['event'],row['document']))
        with self.studio.production.connect() as db:
            db.execute('PRAGMA foreign_keys=OFF')  # Simulate damaged persisted data, not an application deletion.
            db.execute('DELETE FROM projects WHERE id=?',(identifier,))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable')

    def test_unsafe_project_identity_and_future_render_revision_are_unavailable(self):
        scene=self.scene();identifier=scene['id']
        with self.studio.production.connect() as db:
            db.execute('INSERT INTO av_renders VALUES (?,?,?,?,?,?,?)',('f'*32,identifier,1,'{}','failed','{}',1))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable')
        with self.studio.production.connect() as db:
            db.execute('PRAGMA foreign_keys=OFF');db.execute('DELETE FROM av_renders WHERE project_id=?',(identifier,))
            db.execute('UPDATE projects SET id=? WHERE id=?',('../escape',identifier))
            for table in ('av_documents','av_events'):db.execute('UPDATE '+table+' SET project_id=? WHERE project_id=?',('../escape',identifier))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable')

    def test_linked_plan_file_is_unavailable(self):
        scene=self.scene();path=self.studio.production.root/scene['id']/'plan.json';saved=path.with_name('retained-plan.json')
        path.rename(saved)
        try:path.symlink_to(saved)
        except OSError:
            saved.rename(path);self.skipTest('File symlinks unavailable on this host')
        try:self.assertEqual(self.request()[1]['scene']['state'],'unavailable')
        finally:path.unlink();saved.rename(path)

    def test_private_shared_sources_are_hidden_and_bounded_search_is_honest(self):
        from test_production import png
        own=self.scene();other=self.studio.import_image('other.png','image/png',png())['asset']
        mixed=self.scene([self.asset['id'],other['id']])
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(other['id'],))
        result=self.request('all')[1]
        self.assertEqual(result['scene']['plan']['id'],own['id']);self.assertNotIn(mixed['id'],json.dumps(result))
        with patch.object(av_projects,'CONTINUE_WINDOW',1):self.assertEqual(self.request()[1]['scene']['state'],'incomplete')

    def test_source_hash_intake_membership_and_job_privacy_are_required(self):
        scene=self.scene();identifier=scene['id'];original=self.asset['sha256']
        with self.studio.assets.connection() as db:db.execute('UPDATE assets SET sha256=? WHERE id=?',('f'*64,self.asset['id']))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable')
        with self.studio.assets.connection() as db:db.execute('UPDATE assets SET sha256=? WHERE id=?',(original,self.asset['id']))
        with self.studio.production.connect() as db:
            document=json.loads(db.execute('SELECT document FROM av_documents WHERE project_id=?',(identifier,)).fetchone()[0])
            document['sources'][0]['asset_id']='foreign-source'
            db.execute('UPDATE av_documents SET document=? WHERE project_id=?',(json.dumps(document),identifier))
        self.assertEqual(self.request()[1]['scene']['state'],'unavailable')
        with self.studio.production.connect() as db:
            db.execute('UPDATE av_documents SET document=(SELECT document FROM av_events WHERE project_id=? AND revision=0) WHERE project_id=?',(identifier,identifier))
        self.studio.jobs[self.asset['job_id']]['privacy']='private'
        self.assertEqual(self.request()[1]['scene']['state'],'empty')

    def test_scene_failure_preserves_other_sections_and_changed_workspace_is_refused(self):
        native=self.fixture.fixture.prepare();self.scene()
        with patch.object(self.studio.production.av,'continue_observation',side_effect=ValueError('unavailable')):
            result=self.request()[1]
            self.assertEqual(result['scene']['state'],'unavailable');self.assertEqual(result['native']['plan']['id'],native['id'])
        original=self.studio.production.av.continue_observation
        def change(workspace):
            result=original(workspace)
            with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(self.asset['id'],))
            return result
        with patch.object(self.studio.production.av,'continue_observation',side_effect=change):self.assertEqual(self.request()[0],409)

    def test_continue_never_reads_unbounded_lists_or_executes_media(self):
        self.scene()
        with patch.object(self.studio.production,'list',side_effect=AssertionError('Unbounded production read')), \
             patch.object(self.studio.production.av,'list',side_effect=AssertionError('Unbounded scene read')), \
             patch.object(self.studio.production.av,'inspect',side_effect=AssertionError('Full scene read')), \
             patch.object(self.studio.production.av,'executables',side_effect=AssertionError('Native preflight')), \
             patch.object(av_projects,'render',side_effect=AssertionError('Render')):
            self.assertEqual(self.request()[1]['scene']['state'],'ready')
