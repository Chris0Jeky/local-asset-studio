"""Real SQLite two-client and response-loss contracts; no Studio/model process."""
import copy
import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
import unittest
import test_workspace as fixture
workspace = fixture.workspace


class AssetMetadataCommands(unittest.TestCase):
    setUp = fixture.WorkspaceTests.setUp
    tearDown = fixture.WorkspaceTests.tearDown
    def command(self, **fields):
        ids = fields.pop('ids', [self.asset])
        return dict(ids=ids, action='edit', request_id=uuid.uuid4().hex,
                    expected_revisions={i: self.store.get(i).get('metadata_revision', 0) for i in ids}, **fields)

    def test_stale_form_cannot_erase_another_clients_confirmed_notes(self):
        older = self.command(title='New title', notes='')
        self.store.update(self.command(notes='A confirmed correction'))
        with self.assertRaisesRegex(workspace.WorkspaceError, 'changed'):
            workspace.AssetWorkspace(self.root).update(older)
        self.assertEqual(self.store.get(self.asset)['notes'], 'A confirmed correction')

    def test_same_request_returns_original_receipt_after_restart_and_later_edit(self):
        command = self.command(notes='first snapshot')
        first = self.store.update(command)
        self.store.update(self.command(notes='newer'))
        recovered = workspace.AssetWorkspace(self.root)
        self.assertEqual(recovered.update(command), first)
        self.assertEqual(recovered.get(self.asset)['notes'], 'newer')
        self.assertEqual(recovered.command_status(command['request_id']), first)

    def test_request_id_reuse_with_other_content_is_rejected(self):
        command = self.command(notes='original'); self.store.update(command)
        with self.assertRaisesRegex(workspace.WorkspaceError, 'request ID'):
            self.store.update(dict(command, notes='changed intent'))
        self.assertEqual(self.store.get(self.asset)['notes'], 'original')

    def test_missing_precondition_is_not_silently_filled_from_current_state(self):
        with self.assertRaises(workspace.WorkspaceError):
            self.store.update({'ids':[self.asset], 'action':'edit', 'notes':'blind overwrite'})
        self.assertEqual(self.store.get(self.asset)['notes'], '')

    def test_missing_receipt_is_unknown_and_does_not_create_a_command(self):
        status = self.store.command_status('1'*32)
        self.assertEqual(status, {'request_id':'1'*32, 'status':'unknown'})
        self.assertEqual(self.store.get(self.asset)['metadata_revision'], 0)

    def test_bulk_conflict_is_atomic_and_returns_bounded_current_metadata(self):
        second = self.store.register(dict(self.job,id='second'), 0, self.source)
        command = self.command(ids=[self.asset,second], notes='bulk')
        self.store.update(self.command(notes='changed elsewhere'))
        with self.assertRaises(workspace.WorkspaceError) as raised:
            self.store.update(command)
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.store.get(second)['notes'], '')
        self.assertEqual(self.store.get(second)['metadata_revision'], 0)
        self.assertNotIn('path', raised.exception.details['current'][0])
        self.assertEqual(self.store.command_status(command['request_id'])['status'], 'unknown')

    def test_parallel_clients_have_one_winner(self):
        gate=threading.Barrier(2)
        commands=[self.command(notes='a'),self.command(notes='b')]
        def write(command):
            store=workspace.AssetWorkspace(self.root);gate.wait()
            try: store.update(command); return 'applied'
            except workspace.WorkspaceError: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(write, commands))
        self.assertCountEqual(results, ['applied','conflict'])
        self.assertEqual(self.store.get(self.asset)['metadata_revision'], 1)

    def test_parallel_identical_request_applies_once(self):
        gate=threading.Barrier(2);command=self.command(notes='once')
        def write(_):
            store=workspace.AssetWorkspace(self.root);gate.wait();return store.update(command)
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(write,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.store.get(self.asset)['metadata_revision'],1)

    def test_trash_and_restore_invalidate_stale_review_but_preserve_original(self):
        stale=self.command(review='selected')
        command=self.command();command['action']='trash';self.store.update(command)
        with self.assertRaises(workspace.WorkspaceError):self.store.update(stale)
        command=self.command();command['action']='restore';self.store.update(command)
        self.assertEqual(self.store.get(self.asset)['review'],'unreviewed')
        self.assertEqual(self.store.file(self.asset).read_bytes(),b'original rendered bytes')
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],2)

    def test_disjoint_fields_require_explicit_rebase_too(self):
        stale=self.command(title='my title')
        self.store.update(self.command(favorite=True))
        with self.assertRaises(workspace.WorkspaceError):self.store.update(stale)
        result=self.store.update(self.command(title='my title'))
        self.assertEqual(result['revisions'][self.asset],2);self.assertTrue(self.store.get(self.asset)['favorite'])

    def test_invalid_revisions_and_ids_do_not_mutate(self):
        for value in [True,False,-1,1.5,'0',None,2**53]:
            command=self.command(notes='invalid');command['expected_revisions'][self.asset]=value
            with self.subTest(value=value),self.assertRaises(workspace.WorkspaceError):self.store.update(command)
        for value in ['', 'x'*129, '../path', None]:
            command=self.command(notes='invalid');command['request_id']=value
            with self.subTest(value=value),self.assertRaises(workspace.WorkspaceError):self.store.update(command)
        for revisions in [{},{self.asset:0,'extra':0}]:
            with self.assertRaises(workspace.WorkspaceError):self.store.update(dict(self.command(notes='invalid'),expected_revisions=revisions))
        self.assertEqual(self.store.get(self.asset)['notes'],'')

    def test_validation_failure_rolls_back_and_does_not_make_a_receipt(self):
        command=self.command(review='commercially_approved')
        with self.assertRaises(workspace.WorkspaceError):self.store.update(command)
        self.assertEqual(self.store.command_status(command['request_id'])['status'],'unknown')
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)

    def test_receipt_and_mutation_commit_together(self):
        command=self.command(notes='must roll back')
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON asset_commands BEGIN SELECT RAISE(ABORT, 'receipt fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.store.update(command)
        self.assertEqual(self.store.get(self.asset)['notes'],'')
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)

    def test_collection_membership_changes_invalidate_snapshot(self):
        collection=self.store.collection({'name':'Test'})
        command=self.command();command.update(action='add_collection',collection_id=collection['id']);self.store.update(command)
        stale=self.command(notes='old membership');self.store.collection({'id':collection['id'],'action':'delete'})
        with self.assertRaises(workspace.WorkspaceError):self.store.update(stale)
        self.assertEqual(self.store.snapshot()['assets'][0]['collections'],[])

    def test_deleted_asset_fails_the_entire_command(self):
        command=self.command(notes='gone')
        with self.store.connection() as db:db.execute('DELETE FROM assets WHERE id=?',(self.asset,))
        with self.assertRaises(workspace.WorkspaceError) as raised:self.store.update(command)
        self.assertEqual(raised.exception.status,409)
        self.assertEqual(raised.exception.details['missing_ids'],[self.asset])

    def test_old_database_migrates_idempotently_without_losing_data(self):
        with self.store.connection() as db:
            db.execute('DROP TABLE IF EXISTS asset_commands')
            columns={row['name'] for row in db.execute('PRAGMA table_info(assets)')}
            if 'metadata_revision' in columns:db.execute('ALTER TABLE assets DROP COLUMN metadata_revision')
        for _ in range(2):recovered=workspace.AssetWorkspace(self.root)
        self.assertEqual(recovered.get(self.asset)['metadata_revision'],0)
        self.assertEqual(recovered.get(self.asset)['sha256'],self.store.get(self.asset)['sha256'])

    def test_collection_payload_type_is_rejected_without_a_sqlite_exception(self):
        for invalid in [[], {}, 1, None]:
            command=self.command();command.update(action='add_collection',collection_id=invalid)
            with self.subTest(value=invalid),self.assertRaises(workspace.WorkspaceError):self.store.update(command)
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)

    def test_collection_deletion_cannot_overflow_revision(self):
        collection=self.store.collection({'name':'At limit'})
        command=self.command();command.update(action='add_collection',collection_id=collection['id']);self.store.update(command)
        with self.store.connection() as db:db.execute('UPDATE assets SET metadata_revision=? WHERE id=?',(2**53-1,self.asset))
        with self.assertRaises(workspace.WorkspaceError):self.store.collection({'id':collection['id'],'action':'delete'})
        self.assertEqual(self.store.snapshot()['assets'][0]['collections'],[collection['id']])
        self.assertEqual(self.store.get(self.asset)['metadata_revision'],2**53-1)
