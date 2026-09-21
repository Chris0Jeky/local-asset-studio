"""Collection-count correctness and deterministic assembly-work bounds."""
import tempfile
import unittest
from pathlib import Path

from test_workspace import workspace
from workspace_snapshot_benchmark import populate


class WorkspaceSnapshotCountsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = workspace.AssetWorkspace(Path(self.temp.name))

    def assert_counts(self, snapshot):
        # Independent oracle, intentionally slow but confined to test fixtures.
        expected = {c['id']: sum(c['id'] in a['collections'] and not a['trashed_at'] for a in snapshot['assets'])
                    for c in snapshot['collections']}
        self.assertEqual({c['id']: c['count'] for c in snapshot['collections']}, expected)

    def test_sparse_dense_empty_and_trashed_memberships(self):
        populate(self.store, 23, 7, 4)
        with self.store.connection() as db:
            db.execute("INSERT INTO collections (id,name,description,created_at) VALUES ('empty','Empty', '',0)")
            db.execute("UPDATE assets SET trashed_at=0 WHERE id='a0'")  # Preserve legacy truthiness.
        before = self.store.snapshot()
        self.assert_counts(before)
        self.assertEqual(next(c['count'] for c in before['collections'] if c['id'] == 'empty'), 0)
        with self.store.connection() as db:
            db.execute('UPDATE assets SET trashed_at=123')
        after = self.store.snapshot()
        self.assertTrue(all(c['count'] == 0 for c in after['collections']))
        self.assertEqual([a['collections'] for a in before['assets']], [a['collections'] for a in after['assets']])
        with self.store.connection() as db:
            db.execute('UPDATE assets SET trashed_at=NULL')
        self.assert_counts(self.store.snapshot())

    def test_deleted_collection_preserves_asset_order_and_other_membership(self):
        populate(self.store, 30, 10, 3)
        before = self.store.snapshot()
        self.store.collection({'id': 'c4', 'action': 'delete'})
        after = self.store.snapshot()
        self.assertEqual([a['id'] for a in after['assets']], [a['id'] for a in before['assets']])
        for a, b in zip(before['assets'], after['assets']):
            self.assertEqual(b, dict(a, collections=[c for c in a['collections'] if c != 'c4'],
                                     metadata_revision=a['metadata_revision'] + int('c4' in a['collections'])))
        self.assert_counts(after)

    def test_collection_assembly_does_not_rescan_all_assets_per_collection(self):
        assets, collections, per_asset = 1000, 100, 3
        populate(self.store, assets, collections, per_asset)
        reads = [0]
        class MeasuredAsset(dict):
            def __getitem__(self, key):
                if key in ('collections', 'trashed_at'):
                    reads[0] += 1
                return super().__getitem__(key)
        original = self.store._asset
        self.store._asset = lambda row: MeasuredAsset(original(row))
        snapshot = self.store.snapshot()
        self.assertLessEqual(reads[0], 2*assets*per_asset + assets + collections,
                             'Collection projection regressed to rescanning each asset per collection')
        self.assert_counts(snapshot)

    def test_snapshot_is_read_only_and_empty_store_is_still_supported(self):
        empty = self.store.snapshot()
        self.assertEqual(empty['assets'], [])
        self.assertEqual(empty['collections'], [])
        self.assertRegex(empty['workspace_id'], r'^[0-9a-f]{32}$')
        populate(self.store, 8, 4, 2)
        with self.store.connection() as db:
            before = '\n'.join(db.iterdump())
        first = self.store.snapshot()
        self.assertEqual(first['workspace_id'], empty['workspace_id'])
        self.assertEqual(first, self.store.snapshot())
        with self.store.connection() as db:
            self.assertEqual(before, '\n'.join(db.iterdump()))
        self.assert_counts(first)


if __name__ == '__main__':
    unittest.main()
