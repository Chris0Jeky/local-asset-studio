"""Returning-owner observations use disposable SQLite, never an exporter."""
import json
import shutil
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch

import test_native_export_history as history_fixture
from test_production import server


class ContinueCardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = history_fixture.NativeExportHistoryTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.studio = self.fixture.studio
        self.workspace = self.fixture.workspace
        self.asset = self.fixture.asset

    def request(self, scope='regular', workspace=None):
        handler = server.Handler.__new__(server.Handler); handler.studio = self.studio
        handler.path = '/api/workspace/continue?workspace_id='+(workspace or self.workspace)
        handler.headers = {'X-Studio-Privacy':scope}; handler._safe_host = lambda:True
        sent=[]; handler._json=lambda status,body:sent.append((status,body))
        handler.do_GET(); return sent[0]

    def test_old_kept_picture_survives_recent_six_and_queries_are_read_only(self):
        from test_asset_reads import AssetReadTests
        seed = AssetReadTests(); seed.store = self.studio.assets; seed.seed(12)
        with self.studio.assets.connection() as db:
            db.execute("UPDATE assets SET review='selected',created_at=0 WHERE id=?", (self.asset['id'],))
            before = [tuple(row) for row in db.execute('SELECT * FROM assets ORDER BY id')]
        status,result = self.request()
        self.assertEqual(status,200,result)
        self.assertEqual(result['kept']['asset']['id'],self.asset['id'])
        self.assertEqual(result['kept']['asset']['created_at'],0)
        self.assertEqual(result['native']['state'],'empty')
        with self.studio.assets.connection() as db:
            self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM assets ORDER BY id')],before)
        self.assertFalse(self.studio.requests); self.assertTrue(self.studio.queue.empty())

    def test_scope_ties_and_noneligible_pictures(self):
        from test_asset_reads import AssetReadTests
        seed=AssetReadTests();seed.store=self.studio.assets;seed.seed(10)
        with self.studio.assets.connection() as db:
            db.execute("UPDATE assets SET review='selected',created_at=1")
            db.execute("UPDATE assets SET privacy='private' WHERE id='asset-000009'")
            db.execute("UPDATE assets SET run_label='Agent lab' WHERE id='asset-000008'")
            db.execute("UPDATE assets SET review='needs_work' WHERE id='asset-000007'")
            db.execute("UPDATE assets SET trashed_at=2 WHERE id='asset-000006'")
            db.execute("UPDATE assets SET archived_at=2 WHERE id='asset-000005'")
            db.execute('UPDATE assets SET created_at=0 WHERE id=?',(self.asset['id'],))
        self.assertEqual(self.request()[1]['kept']['asset']['id'],'asset-000004')
        with patch.object(self.studio.production,'connect',side_effect=AssertionError('Private must not read exports')):
            result=self.request('private')[1]
            self.assertEqual(result['kept']['asset']['id'],'asset-000009')
            self.assertEqual(result['native']['state'],'excluded')
        result=self.request('all')[1]
        self.assertEqual(result['kept']['asset']['id'],'asset-000009')
        self.assertEqual(result['native']['scope'],'regular')

    def test_native_created_order_retains_every_recorded_status_without_file_claims(self):
        plans=[self.fixture.prepare() for _ in range(8)]
        for status in ('planned','completed','failed'):
            newest=max(plans,key=lambda p:p['id'])
            with self.studio.production.connect() as db:db.execute('UPDATE projects SET created=10')
            self.studio.production._mutate(newest['id'],status=status)
            result=self.request()[1]['native']
            self.assertEqual(result['state'],'ready');self.assertEqual(result['plan']['id'],newest['id'])
            self.assertEqual(result['plan']['status'],status);self.assertEqual(result['plan']['created_at'],10)
            self.assertNotIn('artifacts',result['plan'])
        self.assertFalse(self.studio.requests);self.assertTrue(self.studio.queue.empty())

    def test_missing_or_malformed_latest_is_unavailable_not_empty_or_older(self):
        self.fixture.prepare(); newest=self.fixture.prepare()
        plan_path=self.studio.production.root/newest['id']/'plan.json'
        plan_path.unlink()
        self.assertEqual(self.request()[1]['native']['state'],'unavailable')
        with self.studio.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',('not json',newest['id']))
        self.assertEqual(self.request()[1]['native']['state'],'unavailable')

    def test_private_shared_source_is_hidden_and_capped_search_is_honest(self):
        import workspace_continue
        own=self.fixture.prepare()
        other=self.studio.import_image('private.png','image/png',__import__('test_production').png())['asset']
        mixed=self.fixture.prepare(ids=[self.asset['id'],other['id']])
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(other['id'],))
        result=self.request()[1]
        self.assertEqual(result['native']['plan']['id'],own['id'])
        self.assertNotIn(mixed['id'],json.dumps(result))
        with patch.object(workspace_continue,'PLAN_WINDOW',1):
            self.assertEqual(self.request()[1]['native']['state'],'incomplete')

    def test_workspace_and_source_identity_are_required(self):
        self.assertEqual(self.request(workspace='f'*32)[0],409)
        self.assertEqual(self.request(workspace='../bad')[0],400)
        self.fixture.prepare()
        with self.studio.assets.connection() as db:db.execute("UPDATE assets SET job_id='foreign-job' WHERE id=?",(self.asset['id'],))
        self.assertEqual(self.request()[1]['native']['state'],'unavailable')

    def test_partial_asset_failure_preserves_native_observation(self):
        from workspace import WorkspaceError
        self.fixture.prepare()
        with patch.object(self.studio.assets,'asset_page',side_effect=WorkspaceError('broken catalogue')):
            status,result=self.request()
        self.assertEqual(status,200);self.assertEqual(result['kept']['state'],'unavailable')
        self.assertEqual(result['native']['state'],'ready')

    def test_malformed_identity_state_and_missing_kind_fail_closed(self):
        newest=self.fixture.prepare()
        with self.studio.production.connect() as db:
            saved=dict(db.execute('SELECT plan,state FROM projects WHERE id=?',(newest['id'],)).fetchone())
        typo=json.loads(saved['plan']);typo['kind']='nativ'
        for field,value in (('id','../escape'),('state','[]'),('plan','null'),('plan','{}'),('plan',json.dumps(typo)),('created','invalid')):
            with self.subTest(field=field,value=value):
                with self.studio.production.connect() as db:db.execute('UPDATE projects SET '+field+'=? WHERE id=?',(value,newest['id']))
                self.assertEqual(self.request()[1]['native']['state'],'unavailable')
                with self.studio.production.connect() as db:
                    if field=='id':db.execute('UPDATE projects SET id=? WHERE id=?',(newest['id'],value))
                    else:db.execute('UPDATE projects SET '+field+'=? WHERE id=?',(saved.get(field,1),newest['id']))

    def test_read_overlap_with_workspace_metadata_change_is_refused(self):
        import workspace_continue
        original=workspace_continue.latest_native
        def change(*args):
            with self.studio.assets.connection() as db:db.execute("UPDATE assets SET privacy='private' WHERE id=?",(self.asset['id'],))
            return original(*args)
        with patch.object(workspace_continue,'latest_native',side_effect=change):
            status,result=self.request()
        self.assertEqual(status,409);self.assertEqual(result['code'],'asset_continue_stale')

class ContinueControllerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node is required for controller contracts')
    def test_continue_controller(self):
        result=subprocess.run([shutil.which('node'),'--test',str(Path(__file__).with_name('continue_card.cjs'))],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
