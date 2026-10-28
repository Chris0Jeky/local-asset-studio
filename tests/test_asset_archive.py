"""Reversible Archive shares the real Workspace's transaction and privacy owners."""
import hashlib
import tempfile
import unittest
import uuid
from pathlib import Path

from test_workspace import workspace


class AssetArchiveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root/'synthetic.png'; self.source.write_bytes(b'synthetic original bytes')
        self.ids = []
        for index in range(3):
            job = {'id':'regular-run', 'created_at':index+1, 'preset_name':'Archive study',
                   'outputs':[{'filename':'synthetic.png','media_type':'image'}]*3,
                   'parent_assets':['retained-parent']}
            self.ids.append(self.store.register(job,index,self.source))
        job = dict(job,id='private-run',privacy='private',preset_name='Private canary')
        self.private = self.store.register(job,0,self.source)
        self.scope = self.store.snapshot()['workspace_id']

    def command(self, action, ids=None, **fields):
        ids = self.ids[:1] if ids is None else ids
        return dict(action=action,ids=ids,workspace_id=self.scope,request_id=uuid.uuid4().hex,
                    expected_revisions={key:self.store.get(key,privacy='all')['metadata_revision'] for key in ids},**fields)

    def apply(self, action, ids=None, privacy='regular', **fields):
        return self.store.update(self.command(action,ids,**fields),privacy=privacy)

    def archive(self, ids=None, privacy='regular'):
        try: return self.apply('archive',ids,privacy=privacy)
        except workspace.WorkspaceError as exc: self.fail('Archive must use the existing command owner: '+str(exc))

    def page_ids(self, **filters):
        return [a['id'] for a in self.store.asset_page(filters=filters)['assets']]

    def test_archive_preserves_bytes_identity_review_lineage_and_membership(self):
        col=self.store.collection({'name':'Retained collection'})['id']
        self.apply('edit',title='Kept title',notes='Kept notes',tags=['keep'],favorite=True,review='selected')
        self.apply('add_collection',collection_id=col)
        before=self.store.get(self.ids[0]);path=self.store.file(self.ids[0]);raw=path.read_bytes()
        result=self.archive()
        after=self.store.get(self.ids[0])
        self.assertIsInstance(after['archived_at'],float)
        self.assertEqual(result['applied'],{'archived_at':after['archived_at']})
        self.assertEqual(after['metadata_revision'],before['metadata_revision']+1)
        for key,value in before.items():
            if key not in ('archived_at','metadata_revision'):self.assertEqual(after[key],value,key)
        self.assertEqual(self.store.file(self.ids[0]),path);self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(self.source.read_bytes(),raw)
        self.assertEqual(self.store.snapshot()['assets'][-1]['collections'],[col])
        self.assertEqual(self.store.collection_page()['collections'][0]['count'],1)
        self.assertNotIn(self.ids[0],self.page_ids())
        self.assertEqual(self.page_ids(archive='archived'),[self.ids[0]])
        self.assertEqual(set(self.page_ids(archive='all')),set(self.ids))

    def test_unarchive_is_reversible_and_survives_restart(self):
        self.archive();self.store=workspace.AssetWorkspace(self.root)
        self.assertIsNotNone(self.store.get(self.ids[0])['archived_at'])
        result=self.apply('unarchive')
        self.assertEqual(result['applied'],{'archived_at':None})
        self.assertIsNone(self.store.get(self.ids[0])['archived_at'])
        self.assertEqual(set(self.page_ids()),set(self.ids))
        self.assertEqual(self.page_ids(archive='archived'),[])

    def test_archive_and_trash_are_independent_in_both_directions(self):
        self.apply('trash');before=self.store.get(self.ids[0])['trashed_at'];self.archive()
        self.assertEqual(self.store.get(self.ids[0])['trashed_at'],before)
        self.assertEqual(self.page_ids(visibility='trash',archive='archived'),[self.ids[0]])
        self.apply('restore');self.assertIsNotNone(self.store.get(self.ids[0])['archived_at'])
        self.assertNotIn(self.ids[0],self.page_ids())
        self.apply('trash');self.apply('unarchive')
        self.assertIsNotNone(self.store.get(self.ids[0])['trashed_at'])
        self.assertEqual(self.page_ids(visibility='trash'),[self.ids[0]])

    def test_noop_mixed_batch_and_zero_timestamp_do_not_burn_revisions(self):
        self.archive()
        with self.store.connection() as db:db.execute('UPDATE assets SET archived_at=0 WHERE id=?',(self.ids[0],))
        result=self.archive(self.ids)
        self.assertEqual(result['unchanged'],self.ids[:1])
        self.assertEqual(result['revisions'],dict.fromkeys(self.ids,1))
        self.assertEqual(self.store.get(self.ids[0])['archived_at'],0)
        result=self.archive(self.ids)
        self.assertEqual(result['unchanged'],self.ids);self.assertEqual(result['applied'],{})
        self.assertEqual(result['revisions'],dict.fromkeys(self.ids,1))
        self.apply('unarchive',self.ids)
        result=self.apply('unarchive',self.ids)
        self.assertEqual(result['unchanged'],self.ids);self.assertEqual(result['applied'],{})

    def test_noop_at_revision_ceiling_but_real_change_is_refused(self):
        self.archive()
        with self.store.connection() as db:db.execute('UPDATE assets SET metadata_revision=? WHERE id=?',(workspace.MAX_REVISION,self.ids[0]))
        self.assertEqual(self.archive()['unchanged'],self.ids[:1])
        with self.assertRaises(workspace.WorkspaceError):self.apply('unarchive')
        self.assertIsNotNone(self.store.get(self.ids[0])['archived_at'])

    def test_stale_batch_is_atomic_and_request_identity_cannot_be_reused(self):
        self.archive()
        stale=self.command('unarchive',self.ids);self.apply('edit',[self.ids[1]],notes='newer')
        before=self.store.snapshot(privacy='all')
        with self.assertRaises(workspace.WorkspaceError) as caught:self.store.update(stale)
        self.assertEqual(caught.exception.code,'asset_revision_conflict')
        self.assertEqual(self.store.snapshot(privacy='all'),before)
        command=self.command('unarchive');self.store.update(command)
        with self.assertRaises(workspace.WorkspaceError) as caught:self.store.update(dict(command,action='archive'))
        self.assertEqual(caught.exception.code,'asset_request_reused')

    def test_lost_acknowledgment_recovers_original_receipt_without_reapplying(self):
        self.archive();command=self.command('unarchive');receipt=self.store.update(command)
        self.archive();before=self.store.snapshot(privacy='all')
        self.store=workspace.AssetWorkspace(self.root)
        recovered=self.store.command_status(command['request_id'],self.scope)
        self.assertEqual(recovered['applied'],receipt['applied'])
        self.assertEqual(recovered['revisions'],receipt['revisions'])
        self.assertGreater(recovered['current'][0]['metadata_revision'],receipt['revisions'][self.ids[0]])
        self.assertEqual(recovered['current'][0].get('archived_at'),self.store.get(self.ids[0])['archived_at'])
        replay=self.store.update(command)
        self.assertEqual(replay,recovered);self.assertEqual(self.store.snapshot(privacy='all'),before)
        self.assertIsNotNone(self.store.get(self.ids[0])['archived_at'])

    def test_private_archives_receipts_and_cursors_remain_in_their_scope(self):
        self.archive()
        first=self.store.asset_page(limit=1)
        command=self.command('archive',[self.private]);receipt=self.store.update(command,privacy='private')
        self.assertEqual(self.store.command_status(command['request_id'],self.scope)['status'],'unknown')
        self.assertEqual(self.store.command_status(command['request_id'],self.scope,privacy='private')['applied'],receipt['applied'])
        self.assertEqual(self.page_ids(archive='archived'),[self.ids[0]])
        self.assertEqual(self.page_ids(archive='archived',privacy='private'),[self.private])
        second=self.store.asset_page(limit=1,cursor=first['next_cursor'])
        self.assertEqual(second['catalogue'],first['catalogue'])
        self.assertEqual(second['assets'][0]['id'],self.ids[1])
        before=self.store.snapshot(privacy='all')
        with self.assertRaises(workspace.WorkspaceError):self.store.update(self.command('unarchive',[self.ids[0],self.private]))
        self.assertEqual(self.store.snapshot(privacy='all'),before)

    def test_archive_query_search_sort_cursor_and_selection_are_bounded(self):
        self.archive(self.ids)
        first=self.store.asset_page(limit=1,filters={'archive':'archived'},q='Archive',sort='oldest')
        self.assertEqual(first['assets'][0]['id'],self.ids[0])
        second=self.store.asset_page(limit=1,cursor=first['next_cursor'],filters={'archive':'archived'},q='Archive',sort='oldest')
        self.assertEqual(second['assets'][0]['id'],self.ids[1])
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.asset_page(limit=1,cursor=first['next_cursor'],filters={'archive':'all'},q='Archive',sort='oldest')
        self.assertEqual(caught.exception.code,'asset_cursor_mismatch')
        selected=self.store.asset_selection([self.ids[2],self.private,'missing'],workspace_id=self.scope)
        self.assertIsNotNone(selected['items'][0]['asset']['archived_at'])
        self.assertEqual([r['state'] for r in selected['items']],['active','missing','missing'])
        self.apply('unarchive',[self.ids[2]])
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.asset_page(limit=1,cursor=first['next_cursor'],filters={'archive':'archived'},q='Archive',sort='oldest')
        self.assertEqual(caught.exception.code,'asset_cursor_stale')

    def test_legacy_unarchived_summary_shape_is_retained(self):
        row=self.store.get(self.ids[0]);self.assertIn('archived_at',row);self.assertIsNone(row['archived_at'])
        page=self.store.asset_page()
        self.assertNotIn('archive',page['filters'])
        self.assertTrue(all('archived_at' not in a for a in page['assets']))
        self.assertEqual(self.store.asset_page(filters={'archive':'active'}),page)

    def test_invalid_archive_filters_and_corrupt_metadata_are_refused(self):
        self.archive()
        for value in (None,True,1,[],{},'trash','ARCHIVED',''):
            with self.subTest(filter=value),self.assertRaises((workspace.WorkspaceError,ValueError)):
                self.store.asset_page(filters={'archive':value})
        for value in ('not a timestamp',float('inf'),b'bad'):
            with self.subTest(stored=value):
                with self.store.connection() as db:db.execute('UPDATE assets SET archived_at=? WHERE id=?',(value,self.ids[0]))
                with self.assertRaises(workspace.WorkspaceError) as caught:self.store.asset_page(filters={'archive':'all'})
                self.assertEqual(caught.exception.code,'asset_read_unavailable')

    def test_existing_database_migration_does_not_rewrite_media_or_receipts(self):
        # Remove only the new nullable column to represent the previous schema.
        self.assertIn('archived_at',self.store.get(self.ids[0]))
        self.apply('edit',notes='retained before migration')
        with self.store.connection() as db:
            receipts=[tuple(r) for r in db.execute('SELECT * FROM asset_commands')]
            db.execute('ALTER TABLE assets DROP COLUMN archived_at')
        path=self.store.media;before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}
        self.store=workspace.AssetWorkspace(self.root)
        self.assertIsNone(self.store.get(self.ids[0])['archived_at'])
        self.assertEqual(self.store.get(self.ids[0])['notes'],'retained before migration')
        with self.store.connection() as db:self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM asset_commands')],receipts)
        self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()},before)


if __name__=='__main__':unittest.main()
