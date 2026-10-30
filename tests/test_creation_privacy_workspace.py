"""Private catalogue boundaries use synthetic bytes and the real SQLite owner."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from test_workspace import workspace


def symlinks_available():
    with tempfile.TemporaryDirectory() as name:
        target = os.path.join(name, 'target'); os.mkdir(target)
        try: os.symlink(target, os.path.join(name, 'link'), target_is_directory=True); return True
        except (OSError, NotImplementedError): return False
SYMLINKS_AVAILABLE = symlinks_available()


class CreationPrivacyWorkspaceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root / 'synthetic.png'; self.source.write_bytes(b'harmless synthetic image bytes')
        self.regular_job = {'id':'ordinary-job', 'created_at':1, 'preset_name':'Ordinary scene',
                            'outputs':[{'filename':'synthetic.png','media_type':'image'}]}
        self.private_job = dict(self.regular_job, id='private-job', created_at=2,
                                preset_name='Quiet canary scene', privacy='private')
        self.regular = self.store.register(self.regular_job, 0, self.source)
        self.private = self.store.register(self.private_job, 0, self.source)
        self.scope = self.store.snapshot()['workspace_id']

    def command(self, ids, **fields):
        return dict(workspace_id=self.scope, request_id=uuid.uuid4().hex, ids=ids,
                    expected_revisions={i:self.store.get(i, privacy='all')['metadata_revision'] for i in ids},
                    **fields)

    def test_private_registration_is_hidden_from_ordinary_snapshot(self):
        self.assertEqual([a['id'] for a in self.store.snapshot()['assets']], [self.regular])
        self.assertEqual([a['id'] for a in self.store.snapshot(privacy='private')['assets']], [self.private])
        self.assertEqual({a['id'] for a in self.store.snapshot(privacy='all')['assets']}, {self.private,self.regular})

    def test_private_bytes_use_a_separate_root_even_when_content_is_identical(self):
        regular = self.store.file(self.regular)
        private = self.store.file(self.private, privacy='private')
        self.assertEqual(regular.parent, self.root/'workspace'/'media')
        self.assertEqual(private.parent, self.root/'private'/'media')
        self.assertNotEqual(regular, private)
        self.assertEqual(regular.read_bytes(), private.read_bytes())
        self.assertEqual(self.store.get(self.private, privacy='private')['url'],
                         '/api/assets/'+self.private+'/file?privacy=private')
        self.assertEqual(workspace.AssetWorkspace(self.root).file(self.private, privacy='private').read_bytes(),
                         b'harmless synthetic image bytes')

    def test_known_private_ids_do_not_bypass_ordinary_reads(self):
        for read in (self.store.get, self.store.file, self.store.file_entry, self.store.metadata):
            with self.subTest(read=read.__name__), self.assertRaisesRegex(workspace.WorkspaceError, 'Asset not found'):
                read(self.private)
        digest = self.store.get(self.private, privacy='private')['sha256']
        self.assertEqual(self.store.asset_by_sha256(digest)['id'], self.regular)
        self.assertEqual(self.store.asset_by_sha256(digest, privacy='private')['id'], self.private)

    def test_private_search_filtering_precedes_pagination_and_binds_cursor_scope(self):
        self.assertEqual(self.store.asset_page(q='canary')['assets'], [])
        self.assertEqual([a['id'] for a in self.store.asset_page(limit=1)['assets']], [self.regular])
        private = self.store.asset_page(filters={'privacy':'private'}, q='canary', details=True)
        self.assertEqual([a['id'] for a in private['assets']], [self.private])
        first = self.store.asset_page(limit=1, filters={'privacy':'all'})
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.asset_page(limit=1, cursor=first['next_cursor'])
        self.assertEqual(caught.exception.code, 'asset_cursor_mismatch')
        self.assertEqual([a['id'] for a in self.store.asset_page(limit=1, filters={'privacy':'all'},
                         cursor=first['next_cursor'])['assets']], [self.regular])

    def test_hidden_selection_matches_a_missing_identity_without_metadata(self):
        result = self.store.asset_selection([self.private,self.regular], workspace_id=self.scope, details=True)
        self.assertEqual(result['items'][0], {'id':self.private,'state':'missing','asset':None})
        self.assertEqual(result['items'][1]['asset']['id'], self.regular)
        private = self.store.asset_selection([self.private,self.regular], workspace_id=self.scope, privacy='private')
        self.assertEqual(private['items'][0]['asset']['privacy'], 'private')
        self.assertEqual(private['items'][1], {'id':self.regular,'state':'missing','asset':None})

    def test_hidden_commands_are_atomic_and_private_receipts_stay_hidden(self):
        command = self.command([self.regular,self.private], action='edit', notes='harmless private canary')
        with self.assertRaises(workspace.WorkspaceError) as caught: self.store.update(command)
        self.assertNotIn('Quiet canary', json.dumps(caught.exception.response()))
        self.assertEqual(self.store.get(self.regular)['notes'], '')
        private = self.command([self.private], action='edit', notes='harmless private canary')
        result = self.store.update(private, privacy='private')
        self.assertEqual(self.store.command_status(private['request_id'], self.scope)['status'], 'unknown')
        self.assertEqual(self.store.update(private, privacy='private')['applied'], result['applied'])
        self.assertEqual(self.store.command_status(private['request_id'], self.scope, privacy='private')['applied'],
                         result['applied'])
        with self.assertRaises(workspace.WorkspaceError): self.store.update(private)

    def test_collections_and_counts_are_scoped_and_mixed_membership_is_refused(self):
        regular = self.store.collection({'name':'Ordinary shelf'})
        private = self.store.collection({'name':'Quiet canary shelf'}, privacy='private')
        self.store.update(self.command([self.private], action='add_collection', collection_id=private['id']), privacy='private')
        self.assertEqual([c['id'] for c in self.store.collection_page()['collections']], [regular['id']])
        private_page = self.store.collection_page(privacy='private')
        self.assertEqual([(c['id'],c['count']) for c in private_page['collections']], [(private['id'],1)])
        with self.assertRaises(workspace.WorkspaceError):
            self.store.update(self.command([self.private], action='add_collection', collection_id=regular['id']), privacy='all')
        self.assertEqual(self.store.get(self.private, privacy='private')['metadata_revision'], 1)

    def test_deleted_private_collection_receipts_remain_private(self):
        command = {'format':'studio.collection-command/v1','workspace_id':self.scope,
                   'request_id':'private-collection-create','action':'create','name':'Canary collection','description':''}
        created = self.store.collection(command, privacy='private')['receipt']['result']
        delete = {'format':command['format'],'workspace_id':self.scope,'request_id':'private-collection-delete',
                  'action':'delete','id':created['id'],'expected_revision':1}
        self.store.collection(delete, privacy='private')
        for request in (command['request_id'],delete['request_id']):
            self.assertEqual(self.store.collection_status(request,self.scope)['status'], 'unknown')
            self.assertEqual(self.store.collection_status(request,self.scope,privacy='private')['status'], 'committed')

    def test_family_and_recovery_do_not_discover_private_relations(self):
        from studio_workflow import asset_family, asset_recovery_observation
        with self.store.connection() as db:
            db.execute('UPDATE assets SET lineage=? WHERE id=?', (json.dumps([self.private]), self.regular))
        studio = SimpleNamespace(assets=self.store, jobs={self.regular_job['id']:self.regular_job,
                                                       self.private_job['id']:self.private_job})
        family = asset_family.observe(studio,self.regular,workspace_id=self.scope,children=True)
        self.assertNotIn(self.private, json.dumps(family))
        recovery = asset_recovery_observation.observe(self.store,[self.private],self.scope)
        self.assertEqual(recovery['targets'], [{'id':self.private,'state':'missing'}])
        private = asset_recovery_observation.observe(self.store,[self.private],self.scope,privacy='private')
        self.assertEqual(private['targets'][0]['title'], 'Quiet canary scene · 1')

    def test_invalid_privacy_and_reclassification_cannot_publish_regular_content(self):
        with self.assertRaises(workspace.WorkspaceError):
            self.store.register(dict(self.private_job, privacy='regular'),0,self.source)
        for value in (None, True, '', 'PRIVATE', 'all'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.register(dict(self.private_job,id='invalid-'+str(value),privacy=value),0,self.source)
        with self.store.connection() as db: db.execute("UPDATE assets SET privacy='broken' WHERE id=?", (self.private,))
        self.assertNotIn(self.private, json.dumps(self.store.snapshot()))
        with self.assertRaises(workspace.WorkspaceError): self.store.file(self.private, privacy='all')

    def test_private_storage_refuses_symlinked_roots_and_media_before_writing(self):
        if not SYMLINKS_AVAILABLE: self.skipTest('symlinks unavailable on this host (needs the Windows symlink privilege)')
        for directory in ('private', 'private/media'):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as name:
                root = Path(name); store = workspace.AssetWorkspace(root)
                target = root / 'workspace' / 'media'
                link = root / directory; link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target, target_is_directory=True)
                before = list(target.iterdir())
                with self.assertRaisesRegex(workspace.WorkspaceError, 'Private storage'):
                    store.snapshot_file(self.source, privacy='private')
                self.assertEqual(list(target.iterdir()), before)
                with self.assertRaises(workspace.WorkspaceError):
                    workspace.AssetWorkspace(root).storage_root('private')

    def test_private_figure_sources_and_command_receipts_are_unavailable(self):
        import sys
        from unittest.mock import patch
        from studio_workflow import addressable_figures
        self.enterContext(patch.dict(sys.modules, {workspace.__name__:workspace}))
        payload = {'workspace_id':self.scope, 'request_id':'private-figure-request', 'asset_id':self.private,
                   'parent_sha256':self.store.get(self.private, privacy='private')['sha256'],
                   'rectangles':[{'x':0,'y':0,'width':10000,'height':10000}]}
        with patch.object(addressable_figures, '_read_parent') as decode:
            with self.assertRaisesRegex(workspace.WorkspaceError, 'Parent asset was not found'):
                addressable_figures.split_figures(self.store, payload)
            decode.assert_not_called()
        with self.store.connection() as db:
            db.execute('INSERT INTO asset_commands (request_id,fingerprint,result,created_at,privacy) VALUES (?,?,?,?,?)',
                       (payload['request_id'],addressable_figures._fingerprint(self.store,payload),
                        json.dumps({'private_canary':'must remain hidden'}),1,'private'))
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Command was not found'):
            addressable_figures.split_figures(self.store,payload)

    def test_regular_cards_refuse_private_or_unknown_source_claims_before_writing(self):
        base={'action':'create','kind':'look','name':'Ordinary card','body':{}}
        for lineage in ([{'asset_id':self.private}], [{'asset_id':'unknown'}],
                        [{'job_id':self.private_job['id']}], [{'nested':{'privacy':'private'}}],
                        [{'privacy':None}], [{'nested':[{'asset_id':self.private}]}]):
            with self.subTest(lineage=lineage), self.assertRaises(workspace.WorkspaceError):
                self.store.card_command(dict(base,lineage=lineage))
        self.assertEqual(self.store.cards('look'),[])
        card=self.store.card_command(dict(base,lineage=[{'asset_id':self.regular,'privacy':'regular'},
                                                       {'job_id':'external-historical-job'}]))
        with self.assertRaises(workspace.WorkspaceError):
            self.store.card_command({'action':'edit','id':card['id'],'expected_revision':0,
                                     'lineage':[{'asset_id':self.private}]})
        self.assertEqual(self.store.card(card['id'])['revision'],0)

    def test_legacy_setups_refuse_private_classification_and_nested_sources(self):
        for extra,recipe in [({'privacy':'private'},{}), ({'privacy':None},{}),
                             ({},{'privacy':'private'}), ({},{'parent_assets':[self.private]}),
                             ({},{'parent_by_input':{'reference':self.private}}),
                             ({},{'continuation':{'source':{'asset_id':self.private}}}),
                             ({},{'source_asset_id':'unknown'}), ({},{'job_id':self.private_job['id']})]:
            with self.subTest(extra=extra,recipe=recipe), self.assertRaises(workspace.WorkspaceError):
                self.store.save_setup({'name':'Canary setup','recipe':recipe,**extra})
        self.assertEqual(self.store.setups(),[])
        self.store.save_setup({'name':'Regular setup','privacy':'regular','recipe':
                              {'parent_assets':[self.regular],'job_id':'external-historical-job'}})
        self.assertEqual(len(self.store.setups()),1)


if __name__ == '__main__': unittest.main()
