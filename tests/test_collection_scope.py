"""Versioned collection scope stays on the same Workspace transaction."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from app.workspace import AssetWorkspace, WorkspaceError

class CollectionScope(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=AssetWorkspace(Path(self.tmp.name)/'a');self.other=AssetWorkspace(Path(self.tmp.name)/'b')
        self.identity=self.store.snapshot()['workspace_id'];self.foreign=self.other.snapshot()['workspace_id']
    def create(self, **extra):
        return {'format':'studio.collection-command/v1','action':'create','request_id':'scoped-request-0001',
                'name':'Scoped','description':'','workspace_id':self.identity,**extra}
    def test_scoped_success_and_legacy_shape(self):
        old=self.store.collection({'name':'Legacy'})
        self.assertEqual(set(old),{'id','name','description'})
        value=self.store.collection(self.create())
        self.assertEqual(value['workspace_id'],self.identity)
        result=self.store.collection({'format':'studio.collection-command/v1','action':'delete','id':value['receipt']['result']['id'],
                                      'workspace_id':self.identity,'request_id':'scoped-delete-0001','expected_revision':1})
        self.assertEqual(result['workspace_id'],self.identity)
    def test_foreign_scope_refuses_all_actions_without_change(self):
        old=self.store.collection({'name':'Keep me'});before=self.store.snapshot()
        for action in ['create','rename','delete']:
            with self.subTest(action=action),self.assertRaises(WorkspaceError) as raised:
                payload=self.create(action=action,workspace_id=self.foreign)
                if action!='create':payload.update(id=old['id'],expected_revision=1)
                if action=='delete':payload.pop('name');payload.pop('description')
                self.store.collection(payload)
            self.assertEqual(raised.exception.code,'collection_workspace_conflict')
            self.assertEqual(self.store.snapshot(),before)
    def test_explicit_invalid_scope_cannot_become_legacy(self):
        for value in [None,'',3,'A'*32,{},'a'*31]:
            with self.subTest(value=value),self.assertRaises(WorkspaceError):
                self.store.collection({'name':'No write','workspace_id':value})
        self.assertEqual(self.store.snapshot()['collections'],[])
    def test_database_path_change_after_scope_uses_original_connection(self):
        original=self.store._workspace_id;target=self.store.database
        def change(db):
            identity=original(db);self.store.database=self.other.database;return identity
        with patch.object(self.store,'_workspace_id',side_effect=change):
            result=self.store.collection(self.create(name='Original only'))
        self.store.database=target
        self.assertEqual(self.store.snapshot()['collections'][0]['id'],result['receipt']['result']['id'])
        self.assertEqual(self.other.snapshot()['collections'],[])
