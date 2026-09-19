"""Collection receipts use real Workspace SQLite, independently of asset receipts."""
import copy
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from workspace import AssetWorkspace, WorkspaceError, MAX_REVISION
from studio_workflow.core import canonical

FORMAT = 'studio.collection-command/v1'


def service():
    from importlib.util import find_spec
    if find_spec('studio_workflow.collection_commands') is None:
        raise AssertionError('Transactional collection commands are missing')
    from studio_workflow import collection_commands
    return collection_commands


class CollectionCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = AssetWorkspace(self.temp.name)
        self.scope = self.workspace.snapshot()['workspace_id']

    def create(self, request='create-request-0001', **extra):
        return {'format': FORMAT, 'workspace_id': self.scope, 'request_id': request,
                'action': 'create', 'name': 'Original', 'description': 'Retained description', **extra}

    def command(self, value):
        return self.workspace.collection(value)

    def created(self):
        result = self.command(self.create())
        self.assertEqual(result.get('format'), 'studio.collection-result/v1', 'Versioned receipt response missing')
        return result['receipt']['result']

    def edit(self, current, action='rename', request='rename-request-0001', **extra):
        return {'format': FORMAT, 'workspace_id': self.scope, 'request_id': request,
                'action': action, 'id': current['id'], 'expected_revision': current['revision'],
                **({'name': 'Renamed', 'description': 'New description'} if action == 'rename' else {}), **extra}

    def status(self, request):
        self.assertTrue(hasattr(self.workspace, 'collection_status'))
        return self.workspace.collection_status(request, self.scope)

    def evidence(self):
        with self.workspace.connection() as db:
            tables = ['collections', 'collection_assets', 'assets', 'collection_commands_v1', 'asset_commands']
            return {name: sorted((tuple(row) for row in db.execute('SELECT * FROM ' + name)), key=repr) for name in tables}

    def test_status_is_read_only_even_when_sqlite_refuses_every_write(self):
        self.created(); original = self.workspace.connection
        @contextmanager
        def readonly():
            with original() as db:
                db.execute('PRAGMA query_only=ON')
                yield db
        with patch.object(self.workspace, 'connection', readonly):
            self.assertEqual(self.status('create-request-0001')['status'], 'committed')
            self.assertEqual(self.status('unknown-request-0001')['status'], 'unknown')

    def test_valid_historical_receipt_survives_corrupt_current_state(self):
        first = self.command(self.create())
        with self.workspace.connection() as db:
            db.execute('UPDATE collections SET revision=0')
        before = self.evidence()
        for response in (self.status('create-request-0001'), self.command(self.create())):
            self.assertEqual(response['receipt_json'], first['receipt_json'])
            self.assertEqual(response['status'], 'committed')
            self.assertIsNone(response['current'])
            self.assertEqual(response['current_error']['code'], 'collection_storage_corrupt')
        self.assertEqual(self.evidence(), before)

    def test_rehashed_invalid_json_still_fails_closed_and_is_not_repaired(self):
        self.created()
        with self.workspace.connection() as db:
            original = dict(db.execute('SELECT * FROM collection_commands_v1').fetchone())
        for field in ('command', 'receipt'):
            for raw in ('{"x":1,"x":2}', '{"__proto__":1}', 'NaN', '1e999', 'null'):
                with self.subTest(field=field, raw=raw):
                    size = len(raw.encode()) + len(original['receipt' if field == 'command' else 'command'].encode())
                    with self.workspace.connection() as db:
                        db.execute('UPDATE collection_commands_v1 SET command=?,command_sha256=?,receipt=?,receipt_sha256=?,bytes=?',
                                   (original['command'], original['command_sha256'], original['receipt'], original['receipt_sha256'], original['bytes']))
                        db.execute('UPDATE collection_commands_v1 SET ' + field + '=?,' + field + '_sha256=?,bytes=?',
                                   (raw, hashlib.sha256(raw.encode()).hexdigest(), size))
                    before = self.evidence()
                    with self.assertRaises(WorkspaceError) as caught: self.status('create-request-0001')
                    self.assertEqual(caught.exception.code, 'collection_storage_corrupt')
                    self.assertEqual(self.evidence(), before)

    def test_oversize_is_refused_before_loading_stored_text(self):
        self.created()
        with self.workspace.connection() as db:
            db.execute('UPDATE collection_commands_v1 SET receipt=?', ('x' * 16385,))
        original = self.workspace.connection; queries = []
        @contextmanager
        def traced():
            with original() as db:
                db.set_trace_callback(queries.append); yield db
        with patch.object(self.workspace, 'connection', traced), self.assertRaises(WorkspaceError):
            self.status('create-request-0001')
        self.assertFalse(any('SELECT command,receipt FROM' in query for query in queries))
        self.assertTrue(any('length(CAST(receipt AS BLOB))' in query for query in queries))

    def test_journal_exact_byte_boundary_commits_but_one_byte_under_refuses(self):
        from types import SimpleNamespace
        api = service(); command = self.create(); bound = api.bind_command(command)
        identifier = 'd' * 32
        receipt = canonical({'format':api.RECEIPT_FORMAT,'workspace_id':self.scope,'request_id':command['request_id'],
            'request_sha256':bound.sha256,'action':'create','status':'committed','affected_asset_count':0,
            'result':{'id':identifier,'name':command['name'],'description':command['description'],'revision':1,'deleted':False}})
        limit = bound.bytes + len(receipt)
        with patch.object(api.uuid, 'uuid4', return_value=SimpleNamespace(hex=identifier)):
            with patch.object(api, 'MAX_JOURNAL_BYTES', limit - 1), self.assertRaises(WorkspaceError) as caught:
                self.command(command)
            self.assertEqual(caught.exception.code, 'collection_journal_full')
            self.assertEqual(self.workspace.snapshot()['collections'], [])
            with patch.object(api, 'MAX_JOURNAL_BYTES', limit):
                self.assertEqual(self.command(command)['receipt_json'].encode(), receipt)
        with self.workspace.connection() as db:
            self.assertEqual(db.execute('SELECT SUM(bytes) FROM collection_commands_v1').fetchone()[0], limit)

    def test_create_replay_precedes_id_allocation_and_uses_canonical_input(self):
        payload = self.create(name='  α original  ', description=' spaced ')
        first = self.command(payload)
        self.assertEqual(first.get('format'), 'studio.collection-result/v1')
        with patch.object(service().uuid, 'uuid4', side_effect=AssertionError('Replay allocated a new ID')):
            replay = self.command(dict(reversed(list(payload.items()))))
        self.assertFalse(first['replayed']); self.assertTrue(replay['replayed'])
        for field in ('receipt', 'receipt_json', 'receipt_sha256'): self.assertEqual(first[field], replay[field])
        self.assertEqual(first['receipt']['result']['name'], 'α original')
        self.assertEqual(first['receipt']['result']['revision'], 1)
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)
        self.assertEqual(first['receipt']['request_sha256'], hashlib.sha256(canonical(payload)).hexdigest())
        self.assertEqual(first['receipt_sha256'], hashlib.sha256(first['receipt_json'].encode()).hexdigest())
        self.assertEqual(first['receipt_json'].encode(), canonical(first['receipt']))

    def test_changed_bytes_under_same_id_refuse_without_mutation(self):
        current = self.created(); before = self.evidence()
        for payload in (self.create(description='Changed'), self.create(name=' Original '),
                        self.edit(current, request='create-request-0001')):
            with self.subTest(payload=payload), self.assertRaises(WorkspaceError) as caught:
                self.command(payload)
            self.assertEqual(caught.exception.code, 'collection_request_conflict')
            self.assertEqual(self.evidence(), before)

    def test_stale_rename_and_delete_refuse(self):
        original = self.created(); self.command(self.edit(original)); before = self.evidence()
        for action in ('rename', 'delete'):
            with self.subTest(action=action), self.assertRaises(WorkspaceError) as caught:
                self.command(self.edit(original, action=action, request='stale-' + action + '-request'))
            self.assertEqual(caught.exception.code, 'collection_revision_conflict')
            self.assertEqual(caught.exception.status, 409)
            self.assertEqual(self.evidence(), before)

    def test_two_interleaved_writers_have_one_winner(self):
        original = self.created(); stores = [AssetWorkspace(self.temp.name) for _ in range(2)]
        barrier = threading.Barrier(2)
        def attempt(i):
            barrier.wait(timeout=5)
            try: return stores[i].collection(self.edit(original, request='parallel-edit-000' + str(i)))['receipt']['result']['revision']
            except WorkspaceError as exc: return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, (0, 1)))
        self.assertCountEqual(results, [2, 'collection_revision_conflict'])

    def test_two_identical_create_writers_share_one_receipt(self):
        self.assertTrue(hasattr(self.workspace, 'collection_status'))
        stores = [AssetWorkspace(self.temp.name) for _ in range(2)]
        barrier = threading.Barrier(2)
        def attempt(i):
            barrier.wait(timeout=5); return stores[i].collection(self.create())
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, (0, 1)))
        self.assertEqual(results[0]['receipt_json'], results[1]['receipt_json'])
        self.assertCountEqual([x['replayed'] for x in results], [False, True])
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)

    def test_response_loss_reopen_and_later_state_divergence(self):
        first = self.command(self.create()); self.assertIn('receipt', first)
        original = first['receipt']['result']
        self.command(self.edit(original))
        self.workspace = AssetWorkspace(self.temp.name)
        status = self.status('create-request-0001')
        self.assertEqual(status['receipt_json'], first['receipt_json'])
        self.assertEqual(status['receipt']['result']['name'], 'Original')
        self.assertEqual(status['current']['name'], 'Renamed')
        self.assertEqual(status['current']['revision'], 2)
        self.assertEqual(self.command(self.create())['receipt_json'], first['receipt_json'])
        self.command(self.edit(status['current'], 'delete', request='delete-request-0001'))
        status = self.status('create-request-0001')
        self.assertIsNone(status['current'])
        self.assertEqual(status['receipt_json'], first['receipt_json'])
        self.assertFalse(status['receipt']['result']['deleted'])

    def test_unknown_status_is_read_only_and_does_not_reserve_an_id(self):
        self.assertTrue(hasattr(self.workspace, 'collection_status'))
        before = self.evidence()
        result = self.status('unknown-request-0001')
        self.assertEqual(result['status'], 'unknown'); self.assertIsNone(result['receipt'])
        self.assertIn('in-flight', result['recovery'])
        self.assertEqual(self.evidence(), before)
        created = self.command(self.create(request='unknown-request-0001'))
        self.assertEqual(created['status'], 'committed')

    def test_unknown_status_can_precede_commit_of_an_in_flight_writer(self):
        original_connection = self.workspace.connection
        entered, release = threading.Event(), threading.Event()
        @contextmanager
        def paused():
            with original_connection() as db:
                yield db
                entered.set()
                if not release.wait(timeout=5): raise AssertionError('Test writer was not released')
        service()  # Fail meaningfully on the baseline before starting a thread.
        with patch.object(self.workspace, 'connection', paused):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.command, self.create())
                try:
                    self.assertTrue(entered.wait(timeout=5))
                    # Reuse the existing migrated store; constructing one here
                    # takes its own migration write lock, obscuring WAL reads.
                    observer = object.__new__(AssetWorkspace); observer.__dict__ = dict(self.workspace.__dict__)
                    observer.connection = original_connection
                    result = observer.collection_status('create-request-0001', self.scope)
                    self.assertEqual(result['status'], 'unknown')
                finally: release.set()
                self.assertEqual(future.result(timeout=5)['status'], 'committed')
        self.assertEqual(self.status('create-request-0001')['status'], 'committed')

    def test_scope_is_read_inside_transaction_even_on_replay(self):
        self.created()
        with self.workspace.connection() as db: db.execute('UPDATE workspace_identity SET id=?', ('b' * 32,))
        before = self.evidence()
        for operation in (lambda: self.command(self.create()), lambda: self.status('create-request-0001')):
            with self.assertRaises(WorkspaceError) as caught: operation()
            self.assertEqual(caught.exception.code, 'collection_workspace_conflict')
            self.assertEqual(self.evidence(), before)
        with self.assertRaises(WorkspaceError) as caught:
            self.workspace.collection_status('create-request-0001', 'b' * 32)
        self.assertEqual(caught.exception.code, 'collection_storage_corrupt')

    def test_receipt_insert_failure_rolls_back_mutation_and_allocation(self):
        self.created(); before = self.evidence()
        with self.workspace.connection() as db:
            db.execute("CREATE TRIGGER fail_collection_receipt BEFORE INSERT ON collection_commands_v1 BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.command(self.create('failed-request-0001'))
        self.assertEqual(self.evidence(), before)
        self.assertEqual(self.status('failed-request-0001')['status'], 'unknown')

    def test_request_validation_is_strict_and_scoped_calls_never_downgrade(self):
        service(); before = self.evidence()
        invalid = [self.create(format='unknown'), self.create(extra=True), self.create(request_id='short'),
                   self.create(workspace_id='BAD'), self.create(id=None), self.create(name=''),
                   self.create(name='x' * 101), self.create(description='x' * 1001), self.create(action='unknown')]
        for value in invalid:
            with self.subTest(value=str(value)[:120]), self.assertRaises(WorkspaceError): self.command(value)
            self.assertEqual(self.evidence(), before)
        for value in ({'workspace_id': self.scope, 'name': 'Old scoped'}, {'request_id': 'request-only-0001', 'name': 'Not legacy'},
                      {'format': None, 'name': 'Not legacy'}, {'expected_revision': 1, 'name': 'Not legacy'}):
            with self.subTest(value=value), self.assertRaises(WorkspaceError) as caught: self.command(value)
            self.assertEqual(caught.exception.status, 428)
        self.assertEqual(self.evidence(), before)

    def test_invalid_expected_revisions_do_not_coerce_or_consume_ids(self):
        original = self.created(); before = self.evidence()
        for expected in (True, False, 0, -1, 1.0, '1', None, MAX_REVISION + 1):
            with self.subTest(expected=expected), self.assertRaises(WorkspaceError):
                self.command(self.edit(original, expected_revision=expected))
            self.assertEqual(self.evidence(), before)
        missing = self.edit(original); del missing['expected_revision']
        with self.assertRaises(WorkspaceError) as caught: self.command(missing)
        self.assertEqual(caught.exception.status, 428)

    def test_unscoped_legacy_success_shape_is_preserved_and_revision_advances(self):
        legacy = self.workspace.collection({'name': 'Legacy'})
        self.assertEqual(set(legacy), {'id', 'name', 'description'})
        rows = self.workspace.snapshot()['collections']; self.assertIn('revision', rows[0])
        self.assertEqual(rows[0]['revision'], 1)
        scoped = self.command(self.edit(rows[0]))
        self.workspace.collection({'action': 'rename', 'id': legacy['id'], 'name': 'Legacy later'})
        self.assertEqual(self.status('rename-request-0001')['current']['revision'], 3)
        self.assertEqual(self.status('rename-request-0001')['receipt_json'], scoped['receipt_json'])
        self.assertEqual(self.workspace.collection({'action': 'delete', 'id': legacy['id']}), {'id': legacy['id'], 'deleted': True})

    def test_asset_and_collection_receipts_are_independently_typed(self):
        service()
        with self.workspace.connection() as db:
            db.execute('INSERT INTO asset_commands VALUES (?,?,?,?)', ('create-request-0001', 'legacy-digest', '{"status":"legacy"}', 1))
        original = self.created()
        self.assertEqual(self.status('create-request-0001')['receipt']['result']['id'], original['id'])
        with self.workspace.connection() as db:
            self.assertEqual(db.execute('SELECT result FROM asset_commands').fetchone()[0], '{"status":"legacy"}')

    def test_journal_capacity_refuses_new_writes_without_pruning_or_blocking_replay(self):
        first = self.command(self.create()); self.assertIn('receipt', first)
        before = self.evidence(); module = service()
        for patched in ({'MAX_RECEIPTS': 1}, {'MAX_JOURNAL_BYTES': 1}):
            with self.subTest(patched=patched), patch.multiple(module, **patched):
                with self.assertRaises(WorkspaceError) as caught: self.command(self.create('over-budget-0001'))
                self.assertEqual(caught.exception.code, 'collection_journal_full')
                self.assertEqual(self.command(self.create())['receipt_json'], first['receipt_json'])
                self.assertEqual(self.evidence(), before)

    def test_exact_journal_budget_boundary_is_enforced_from_actual_bytes(self):
        self.created(); module = service()
        with self.workspace.connection() as db: used = db.execute('SELECT SUM(bytes) FROM collection_commands_v1').fetchone()[0]
        with patch.object(module, 'MAX_JOURNAL_BYTES', used):
            with self.assertRaises(WorkspaceError): self.command(self.create('full-boundary-0001'))
        with self.workspace.connection() as db: db.execute('UPDATE collection_commands_v1 SET bytes=0')
        before = self.evidence()
        with self.assertRaises(WorkspaceError) as caught: self.command(self.create('bad-accounting-0001'))
        self.assertEqual(caught.exception.code, 'collection_storage_corrupt')
        self.assertEqual(self.evidence(), before)

    def test_corrupt_or_oversized_stored_evidence_refuses_replay_without_repair(self):
        self.created(); module = service()
        with self.workspace.connection() as db: original = dict(db.execute('SELECT * FROM collection_commands_v1').fetchone())
        variants = [
            ('command', '{'), ('receipt', '{'), ('command', 'x' * (module.MAX_COMMAND_BYTES + 1)),
            ('receipt', 'x' * (module.MAX_RECEIPT_BYTES + 1)), ('command_sha256', '0' * 64),
            ('receipt_sha256', '0' * 64), ('version', 2), ('bytes', -1), ('collection_id', 'other'),
            ('workspace_id', 'b' * 32), ('receipt', original['receipt'] + ' '),
        ]
        for column, value in variants:
            with self.subTest(column=column, size=len(str(value))):
                with self.workspace.connection() as db: db.execute(f'UPDATE collection_commands_v1 SET {column}=?', (value,))
                before = self.evidence()
                for operation in (lambda: self.command(self.create()), lambda: self.status('create-request-0001')):
                    with self.assertRaises(WorkspaceError) as caught: operation()
                    self.assertEqual(caught.exception.code, 'collection_storage_corrupt')
                    self.assertEqual(self.evidence(), before)
                with self.workspace.connection() as db: db.execute(f'UPDATE collection_commands_v1 SET {column}=?', (original[column],))

    def test_rehashed_but_wrong_typed_receipt_is_still_refused(self):
        self.created(); module = service()
        with self.workspace.connection() as db: row = dict(db.execute('SELECT * FROM collection_commands_v1').fetchone())
        old = json.loads(row['receipt'])
        variants = []
        for field, value in [('status', 'pending'), ('format', 'studio.asset-receipt/v1'), ('action', 'delete'), ('request_id', 'other-request-0001')]:
            variants.append(old | {field: value})
        for change in ({'revision': True}, {'revision': 2}, {'deleted': True}, {'name': 'Unrequested'}):
            changed = copy.deepcopy(old); changed['result'].update(change); variants.append(changed)
        for receipt in variants:
            raw = canonical(receipt).decode()
            with self.workspace.connection() as db:
                db.execute('UPDATE collection_commands_v1 SET receipt=?,receipt_sha256=?,bytes=?',
                           (raw, hashlib.sha256(raw.encode()).hexdigest(), len(row['command'].encode()) + len(raw.encode())))
            before = self.evidence()
            with self.assertRaises(WorkspaceError) as caught: self.status('create-request-0001')
            self.assertEqual(caught.exception.code, 'collection_storage_corrupt')
            self.assertEqual(self.evidence(), before)

    def test_unknown_schema_version_refuses_status_and_commands_without_repair(self):
        self.created()
        with self.workspace.connection() as db: db.execute('UPDATE collection_command_schema SET version=2')
        before = self.evidence()
        for operation in (lambda: self.command(self.create()), lambda: self.status('create-request-0001'),
                          lambda: AssetWorkspace(self.temp.name)):
            with self.assertRaises(ValueError): operation()
        self.assertEqual(self.evidence(), before)

    def test_collection_revision_overflow_and_corruption_refuse_every_mutation(self):
        original = self.created()
        for revision in (MAX_REVISION, MAX_REVISION + 1, 0, -1, 1.5, 'bad'):
            with self.workspace.connection() as db: db.execute('UPDATE collections SET revision=?', (revision,))
            before = self.evidence()
            for action in ('rename', 'delete'):
                with self.subTest(revision=revision, action=action), self.assertRaises(WorkspaceError):
                    self.command(self.edit(original, action, expected_revision=MAX_REVISION if revision == MAX_REVISION else 1))
                self.assertEqual(self.evidence(), before)
            with self.assertRaises(WorkspaceError): self.workspace.collection({'action': 'delete', 'id': original['id']})
            self.assertEqual(self.evidence(), before)

    def add_asset(self, collection_id, name='a'):
        source = Path(self.temp.name) / (name + '.bin'); source.write_bytes(('original ' + name).encode())
        key = self.workspace.register({'id': name, 'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source)
        with self.workspace.connection() as db: db.execute('INSERT INTO collection_assets VALUES (?,?)', (collection_id, key))
        return key, source, self.workspace.file(key)

    def test_delete_preserves_media_removes_membership_and_increments_once(self):
        current = self.created(); assets = [self.add_asset(current['id'], name) for name in ('a', 'b')]
        other = self.workspace.collection({'name': 'Other'})
        with self.workspace.connection() as db:
            db.execute('INSERT INTO collection_assets VALUES (?,?)', (other['id'], assets[0][0]))
            db.execute('UPDATE assets SET trashed_at=1 WHERE id=?', (assets[1][0],))
        payload = self.edit(current, 'delete', request='delete-request-0001')
        result = self.command(payload)
        self.assertTrue(result['receipt']['result']['deleted']); self.assertEqual(result['receipt']['result']['revision'], 2)
        self.assertEqual(result['receipt']['affected_asset_count'], 2)
        before = self.evidence()
        self.assertEqual(self.command(payload)['receipt_json'], result['receipt_json'])
        self.assertEqual(self.evidence(), before)
        for key, original, snapshot in assets:
            self.assertTrue(original.is_file()); self.assertEqual(original.read_bytes(), snapshot.read_bytes())
            self.assertEqual(self.workspace.get(key)['metadata_revision'], 1)
        with self.workspace.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM collection_assets WHERE collection_id=?', (current['id'],)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM collection_assets WHERE collection_id=?', (other['id'],)).fetchone()[0], 1)

    def test_member_asset_overflow_corruption_or_receipt_fault_rolls_back_delete(self):
        current = self.created(); key, original, snapshot = self.add_asset(current['id'])
        second, _, _ = self.add_asset(current['id'], 'second')
        for revision in (MAX_REVISION, MAX_REVISION + 1, -1, 1.5, 'bad'):
            with self.workspace.connection() as db: db.execute('UPDATE assets SET metadata_revision=? WHERE id=?', (revision, key))
            before = self.evidence()
            with self.subTest(revision=revision), self.assertRaises(WorkspaceError):
                self.command(self.edit(current, 'delete', request='delete-request-0001'))
            self.assertEqual(self.evidence(), before)
            self.assertEqual(self.workspace.get(second)['metadata_revision'], 0)
            self.assertEqual(original.read_bytes(), snapshot.read_bytes())
        with self.workspace.connection() as db:
            db.execute('UPDATE assets SET metadata_revision=0')
            db.execute("CREATE TRIGGER fail_delete_receipt BEFORE INSERT ON collection_commands_v1 BEGIN SELECT RAISE(ABORT,'fault'); END")
        before = self.evidence()
        with self.assertRaises(sqlite3.IntegrityError): self.command(self.edit(current, 'delete', request='delete-request-0001'))
        self.assertEqual(self.evidence(), before)


class CollectionMigrationTests(unittest.TestCase):
    def legacy(self, root):
        folder = Path(root) / 'workspace'; folder.mkdir()
        media = folder / 'media'; media.mkdir(); (media / 'original.bin').write_bytes(b'keep original')
        database = folder / 'assets.sqlite3'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE collections(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT "",created_at REAL NOT NULL)')
            db.execute('INSERT INTO collections VALUES (?,?,?,?)', ('old-id', 'Old name', 'Old description', 123.5))
            db.execute('CREATE TABLE workspace_identity(singleton INTEGER PRIMARY KEY CHECK(singleton=1),id TEXT NOT NULL)')
            db.execute('INSERT INTO workspace_identity VALUES (1,?)', ('a' * 32,))
        return database

    def test_existing_rows_and_media_migrate_deterministically_and_reopen(self):
        with tempfile.TemporaryDirectory() as root:
            self.legacy(root); first = AssetWorkspace(root)
            row = first.snapshot()['collections'][0]
            self.assertIn('revision', row)
            self.assertEqual(row, {'id': 'old-id', 'name': 'Old name', 'description': 'Old description', 'created_at': 123.5, 'revision': 1, 'count': 0})
            reopened = AssetWorkspace(root)
            self.assertEqual(reopened.snapshot(), first.snapshot())
            self.assertEqual((reopened.media / 'original.bin').read_bytes(), b'keep original')
            result = reopened.collection({'format': FORMAT, 'request_id': 'migrated-edit-0001', 'workspace_id': 'a' * 32,
                                          'action': 'rename', 'id': 'old-id', 'expected_revision': 1, 'name': 'New', 'description': ''})
            self.assertEqual(result['receipt']['result']['revision'], 2)

    def test_migration_failure_rolls_back_column_and_journal(self):
        module = service()
        with tempfile.TemporaryDirectory() as root:
            database = self.legacy(root)
            db = sqlite3.connect(database); db.row_factory = sqlite3.Row
            def authorize(action, first, second, database, source):
                return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE and first == 'collection_commands_v1' else sqlite3.SQLITE_OK
            db.set_authorizer(authorize)
            try:
                with self.assertRaises(sqlite3.DatabaseError), db:
                    db.execute('BEGIN IMMEDIATE'); module.migrate(db)
            finally: db.close()
            with sqlite3.connect(database) as check:
                self.assertNotIn('revision', [row[1] for row in check.execute('PRAGMA table_info(collections)')])
                self.assertIsNone(check.execute("SELECT 1 FROM sqlite_master WHERE name='collection_command_schema'").fetchone())
                self.assertEqual(check.execute('SELECT name FROM collections').fetchone()[0], 'Old name')

    def test_simultaneous_migration_keeps_one_identity_and_initial_revision(self):
        service()
        with tempfile.TemporaryDirectory() as root:
            self.legacy(root)
            with ThreadPoolExecutor(max_workers=2) as pool: stores = list(pool.map(lambda _: AssetWorkspace(root), (0, 1)))
            self.assertEqual(stores[0].snapshot(), stores[1].snapshot())
            self.assertEqual(stores[0].snapshot()['workspace_id'], 'a' * 32)
            self.assertEqual(stores[0].snapshot()['collections'][0]['revision'], 1)


if __name__ == '__main__':
    unittest.main()
