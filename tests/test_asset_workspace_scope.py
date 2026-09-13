"""Same asset IDs are not evidence of the same Workspace. Real SQLite only."""
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test_workspace import workspace


class AssetWorkspaceScope(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.a = workspace.AssetWorkspace(self.root / 'a')
        self.b = workspace.AssetWorkspace(self.root / 'b')
        source = self.root / 'input.png'
        source.write_bytes(b'unchanged original media')
        job = {'id': 'same-job', 'outputs': [{'filename': 'input.png', 'media_type': 'image'}]}
        self.asset = self.a.register(job, 0, source)
        self.assertEqual(self.asset, self.b.register(job, 0, source))

    def tearDown(self):
        self.temp.cleanup()

    def scope(self, store):
        return store.snapshot()['workspace_id']

    def command(self, **changes):
        return dict(ids=[self.asset], action='edit', notes='confirmed in A',
                    expected_revisions={self.asset: self.a.get(self.asset)['metadata_revision']},
                    request_id=uuid.uuid4().hex, workspace_id=self.scope(self.a), **changes)

    def test_identity_is_stable_different_and_not_a_path(self):
        identity = self.scope(self.a)
        self.assertRegex(identity, r'^[0-9a-f]{32}$')
        self.assertEqual(identity, self.scope(workspace.AssetWorkspace(self.root / 'a')))
        self.assertNotEqual(identity, self.scope(self.b))
        self.assertEqual(identity, self.a.metadata(self.asset)['workspace_id'])
        self.assertEqual(identity, self.a.snapshot()['assets'][0]['workspace_id'])

    def test_wrong_workspace_rejected_before_receipt_or_metadata(self):
        command = self.command()
        self.a.update(command)
        for operation in [lambda: self.b.update(command),
                          lambda: self.b.command_status(command['request_id'], self.scope(self.a)),
                          lambda: self.b.metadata(self.asset, self.scope(self.a))]:
            with self.subTest(operation=operation), self.assertRaises(workspace.WorkspaceError) as error:
                operation()
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(error.exception.code, 'asset_workspace_conflict')
            self.assertNotIn('current', error.exception.details)
        self.assertEqual(self.b.get(self.asset)['metadata_revision'], 0)
        self.assertEqual(self.b.command_status(command['request_id'])['status'], 'unknown')

    def test_historical_receipt_and_current_metadata_are_distinct_after_restart(self):
        command = self.command()
        first = self.a.update(command)
        second = self.command()
        second['notes'] = 'newer saved by B tab'
        self.a.update(second)
        reopened = workspace.AssetWorkspace(self.root / 'a')
        for result in [reopened.command_status(command['request_id'], self.scope(self.a)), reopened.update(command)]:
            self.assertEqual(result['applied'], first['applied'])
            self.assertEqual(result['revisions'], first['revisions'])
            self.assertEqual(result['current'][0]['metadata_revision'], 2)
            self.assertEqual(result['current'][0]['notes'], 'newer saved by B tab')
            self.assertEqual(result['current'][0]['workspace_id'], self.scope(self.a))
            self.assertNotIn('path', result['current'][0])
        self.assertEqual(reopened.get(self.asset)['metadata_revision'], 2)
        # The immutable receipt is not rewritten to the latest metadata.
        self.assertNotIn('current', reopened.command_status(command['request_id']))

    def test_scoped_unknown_receipt_stays_read_only(self):
        result = self.a.command_status('a' * 32, self.scope(self.a))
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['workspace_id'], self.scope(self.a))
        self.assertEqual(self.a.get(self.asset)['metadata_revision'], 0)

    def test_scope_discovery_is_not_cached_across_database_replacement(self):
        identity = self.scope(self.a)
        # Substitute another actual database at the same service object boundary.
        self.a.database = self.b.database
        self.assertEqual(self.scope(self.a), self.scope(self.b))
        with self.assertRaises(workspace.WorkspaceError): self.a.metadata(self.asset, identity)

    def test_invalid_scope_and_legacy_protocol(self):
        for value in ['', '../workspace', True, None, 'g'*32]:
            c = self.command(); c['workspace_id'] = value
            with self.subTest(value=value), self.assertRaises(workspace.WorkspaceError): self.a.update(c)
        c = self.command(); del c['workspace_id']
        first = self.a.update(c)
        self.assertEqual(first, self.a.update(c))
        self.assertEqual(first, self.a.command_status(c['request_id']))

    def test_existing_database_identity_migration_is_serialized(self):
        with self.a.connection() as db: db.execute('DROP TABLE workspace_identity')
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: self.scope(workspace.AssetWorkspace(self.root / 'a')), range(8)))
        self.assertEqual(len(set(ids)), 1)

    def test_deleted_asset_does_not_erase_receipt(self):
        c = self.command(); self.a.update(c)
        with self.a.connection() as db: db.execute('DELETE FROM assets WHERE id=?', (self.asset,))
        result = self.a.command_status(c['request_id'], self.scope(self.a))
        self.assertEqual(result['status'], 'applied'); self.assertEqual(result['current'], [])

    def test_identity_and_metadata_are_read_on_the_same_database_connection(self):
        c = self.command(); self.a.update(c)
        identity = self.scope(self.a)
        original = self.a._check_scope
        def switch_after_observing(db, expected):
            found = original(db, expected)
            self.a.database = self.b.database
            return found
        self.a._check_scope = switch_after_observing
        metadata = self.a.metadata(self.asset, identity)
        self.assertEqual(metadata['workspace_id'], identity)
        self.assertEqual(metadata['notes'], 'confirmed in A')
        self.assertEqual(self.scope(self.a), self.scope(self.b))
