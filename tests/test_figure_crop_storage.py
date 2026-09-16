"""Real Workspace SQLite integration for one-at-a-time crop publication."""
import copy
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio_workflow import addressable_figures as figures
from test_addressable_figures import register_sheet
from test_server import server


class FigureCropStorageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.store=server.AssetWorkspace(self.root)
        self.parent,_=register_sheet(self.store,self.root)
        self.scope=self.store.snapshot()['workspace_id']
        self.before=self.store.file(self.parent).read_bytes()
        self.payload=dict(workspace_id=self.scope,request_id='bounded-crop-storage-0001',
            asset_id=self.parent,parent_sha256=self.store.get(self.parent)['sha256'],
            rectangles=[dict(x=0,y=0,width=5000,height=10000),dict(x=5000,y=0,width=5000,height=10000)])

    def assert_no_commit(self):
        self.assertEqual(len(self.store.snapshot()['assets']),1)
        with self.store.connection() as db:
            self.assertIsNone(db.execute('SELECT result FROM asset_commands WHERE request_id=?',
                                         (self.payload['request_id'],)).fetchone())
        self.assertEqual(self.store.file(self.parent).read_bytes(),self.before)
        self.assertEqual(list(self.store.media.glob('*.part')),[])

    def test_second_snapshot_failure_keeps_database_atomic_and_exact_retry_safe(self):
        calls=[];original=figures._snapshot_png
        def failing(store,data):
            calls.append(None)
            if len(calls)==2:raise OSError('second snapshot fault')
            return original(store,data)
        with patch.object(figures,'_snapshot_png',failing):
            with self.assertRaisesRegex(OSError,'snapshot fault'):figures.split_figures(self.store,self.payload)
        self.assert_no_commit()
        result=figures.split_figures(self.store,self.payload)
        self.assertEqual(len(result['created']),2)
        self.assertFalse(result['generation_submitted'])
        with patch.object(figures,'_read_parent',side_effect=AssertionError('replay must not decode')):
            self.assertEqual(figures.split_figures(self.store,copy.deepcopy(self.payload)),result)
        self.assertEqual(len(self.store.snapshot()['assets']),3)

    def test_receipt_failure_rolls_back_all_children_but_not_shared_snapshots(self):
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER fail_crop_receipt BEFORE INSERT ON asset_commands "
                       "BEGIN SELECT RAISE(ABORT, 'receipt fault'); END")
        with self.assertRaises((sqlite3.Error, server.WorkspaceError)):figures.split_figures(self.store,self.payload)
        self.assert_no_commit()
        with self.store.connection() as db:db.execute('DROP TRIGGER fail_crop_receipt')
        result=figures.split_figures(self.store,self.payload)
        self.assertEqual(len(result['created']),2)
        for index,identity in enumerate(result['created']):
            child=self.store.get(identity)
            self.assertEqual(child['lineage'],[self.parent])
            self.assertEqual(child['source']['crop_basis_points'],self.payload['rectangles'][index])

    def test_aggregate_refusal_never_publishes_snapshots(self):
        with patch.object(figures,'MAX_AGGREGATE_CROP_PIXELS',4001), \
             patch.object(figures,'_snapshot_png',side_effect=AssertionError('must preflight first')):
            with self.assertRaisesRegex(server.WorkspaceError,'aggregate'):
                figures.split_figures(self.store,self.payload)
        self.assert_no_commit()

    def test_parent_lifecycle_change_before_commit_prevents_child_rows(self):
        original=figures._encode_crops
        def prepare(*args):
            result=original(*args)
            with self.store.connection() as db:
                db.execute('UPDATE assets SET trashed_at=1 WHERE id=?',(self.parent,))
            return result
        with patch.object(figures,'_encode_crops',prepare):
            with self.assertRaisesRegex(server.WorkspaceError,'trashed'):
                figures.split_figures(self.store,self.payload)
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assets').fetchone()[0],1)
            self.assertIsNone(db.execute('SELECT result FROM asset_commands WHERE request_id=?',
                                        (self.payload['request_id'],)).fetchone())


if __name__=='__main__':unittest.main()
