import importlib.util
import tempfile
import unittest
import uuid
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)


class WorkspaceUpdateGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root / 'render.png'; self.source.write_bytes(b'original rendered bytes')
        self.job = {'id': 'job-1', 'preset_name': 'Study', 'outputs': [{'filename': 'render.png', 'media_type': 'image'}]}
        self.asset = self.store.register(self.job, 0, self.source)

    def tearDown(self):
        self.temp.cleanup()

    def snapshot_asset(self):
        current = self.store.get(self.asset)
        return current['metadata_revision'], current['title']

    def assertAssetUnchanged(self, revision, title):
        current = self.store.get(self.asset)
        self.assertEqual(current['metadata_revision'], revision)
        self.assertEqual(current['title'], title)

    def valid_payload(self, **overrides):
        payload = {
            'ids': [self.asset],
            'action': 'edit',
            'title': 'Guard control title',
            'request_id': uuid.uuid4().hex,
            'expected_revisions': {self.asset: self.store.get(self.asset)['metadata_revision']},
        }
        payload.update(overrides)
        return payload

    def test_non_object_payload_refused(self):
        for body in ([], 'asset', 123, None, True):
            with self.subTest(body=repr(body)):
                revision, title = self.snapshot_asset()
                with self.assertRaisesRegex(workspace.WorkspaceError, 'Asset command must be an object'):
                    self.store.update(body)
                self.assertAssetUnchanged(revision, title)

    def test_ids_shape_refused(self):
        bad_ids_list = [
            'not-a-list',
            None,
            123,
            {},
            [],
            [f'guard-{i}' for i in range(201)],
            [123],
            [None],
            [''],
            ['x' * 129],
        ]
        for bad_ids in bad_ids_list:
            with self.subTest(bad_ids=repr(bad_ids)[:80]):
                revision, title = self.snapshot_asset()
                payload = {
                    'ids': bad_ids,
                    'action': 'edit',
                    'title': 'Should not apply',
                    'request_id': uuid.uuid4().hex,
                    'expected_revisions': {self.asset: self.store.get(self.asset)['metadata_revision']},
                }
                with self.assertRaisesRegex(workspace.WorkspaceError, 'Select between 1 and 200 assets'):
                    self.store.update(payload)
                self.assertAssetUnchanged(revision, title)

    def test_missing_precondition_refused(self):
        revision, title = self.snapshot_asset()
        payload = self.valid_payload()
        del payload['request_id']
        with self.assertRaisesRegex(
            workspace.WorkspaceError,
            'Reload the asset metadata and supply expected_revisions and a new request_id; nothing changed',
        ) as ctx:
            self.store.update(payload)
        self.assertEqual(ctx.exception.status, 428)
        self.assertEqual(ctx.exception.code, 'asset_precondition_required')
        self.assertAssetUnchanged(revision, title)

        revision, title = self.snapshot_asset()
        payload = self.valid_payload()
        del payload['expected_revisions']
        with self.assertRaisesRegex(
            workspace.WorkspaceError,
            'Reload the asset metadata and supply expected_revisions and a new request_id; nothing changed',
        ) as ctx:
            self.store.update(payload)
        self.assertEqual(ctx.exception.status, 428)
        self.assertEqual(ctx.exception.code, 'asset_precondition_required')
        self.assertAssetUnchanged(revision, title)

    def test_expected_revisions_shape_refused(self):
        current_revision = self.store.get(self.asset)['metadata_revision']
        bad_expected_list = [
            [],
            None,
            'nope',
            123,
            {},
            {'other': current_revision},
            {self.asset: current_revision, 'extra': 0},
            {self.asset: True},
            {self.asset: False},
            {self.asset: -1},
            {self.asset: '0'},
            {self.asset: 1.5},
            {self.asset: None},
            {self.asset: workspace.MAX_REVISION + 1},
        ]
        for bad_expected in bad_expected_list:
            with self.subTest(expected=repr(bad_expected)[:80]):
                revision, title = self.snapshot_asset()
                payload = self.valid_payload(expected_revisions=bad_expected)
                with self.assertRaisesRegex(
                    workspace.WorkspaceError,
                    'Supply one nonnegative safe integer revision for every selected asset',
                ):
                    self.store.update(payload)
                self.assertAssetUnchanged(revision, title)

    def test_unknown_fields_refused(self):
        revision, title = self.snapshot_asset()
        payload = self.valid_payload()
        payload['bogus_field'] = 1
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Unknown asset command fields'):
            self.store.update(payload)
        self.assertAssetUnchanged(revision, title)

    def test_non_finite_values_refused(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=repr(value)):
                revision, title = self.snapshot_asset()
                payload = self.valid_payload(notes=value)
                with self.assertRaisesRegex(workspace.WorkspaceError, 'Asset command must contain finite JSON values'):
                    self.store.update(payload)
                self.assertAssetUnchanged(revision, title)

    def test_oversized_payload_refused(self):
        revision, title = self.snapshot_asset()
        payload = self.valid_payload(notes='x' * 140000)
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Asset command exceeds 128 KiB'):
            self.store.update(payload)
        self.assertAssetUnchanged(revision, title)

    def test_revision_limit_refused(self):
        with self.store.connection() as db:
            db.execute('UPDATE assets SET metadata_revision=? WHERE id=?', (workspace.MAX_REVISION, self.asset))
        revision, title = self.snapshot_asset()
        self.assertEqual(revision, workspace.MAX_REVISION)
        payload = {
            'ids': [self.asset],
            'action': 'edit',
            'title': 'Should not apply',
            'request_id': uuid.uuid4().hex,
            'expected_revisions': {self.asset: workspace.MAX_REVISION},
        }
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Asset revision limit reached; nothing changed'):
            self.store.update(payload)
        self.assertAssetUnchanged(revision, title)

    def test_scalar_field_shapes_refused_atomically(self):
        cases = (
            ('title', 123, 'title must be text up to 200 characters'),
            ('title', ['x'], 'title must be text up to 200 characters'),
            ('title', None, 'title must be text up to 200 characters'),
            ('title', 'x' * 201, 'title must be text up to 200 characters'),
            ('notes', 5, 'notes must be text up to 8000 characters'),
            ('notes', {'a': 1}, 'notes must be text up to 8000 characters'),
            ('notes', 'x' * 8001, 'notes must be text up to 8000 characters'),
            ('favorite', 1, 'Favorite must be true or false'),
            ('favorite', 0, 'Favorite must be true or false'),
            ('favorite', 'true', 'Favorite must be true or false'),
            ('favorite', None, 'Favorite must be true or false'),
            ('review', 'accepted', 'Unknown review state'),
            ('review', ['selected'], 'Unknown review state'),
            ('tags', 'ink', 'Use up to 30 tags'),
            ('tags', {'ink': True}, 'Use up to 30 tags'),
            ('tags', ['t%d' % i for i in range(31)], 'Use up to 30 tags'),
            ('tags', ['ink', 1], 'Tag must be text up to 60 characters'),
            ('tags', ['x' * 61], 'Tag must be text up to 60 characters'),
            ('tags', [['nested']], 'Tag must be text up to 60 characters'),
        )
        for field, value, message in cases:
            with self.subTest(field=field, value=repr(value)[:40]):
                before = self.store.get(self.asset)
                overrides = {field: value}
                if field != 'title':
                    overrides['title'] = 'Should not apply'
                with self.assertRaisesRegex(workspace.WorkspaceError, message):
                    self.store.update(self.valid_payload(**overrides))
                after = self.store.get(self.asset)
                for key in ('metadata_revision', 'title', 'notes', 'favorite', 'review', 'tags'):
                    self.assertEqual(after[key], before[key], key)

    def test_valid_payload_succeeds_control(self):
        revision, _ = self.snapshot_asset()
        payload = self.valid_payload()
        result = self.store.update(payload)
        self.assertEqual(result['status'], 'applied')
        current = self.store.get(self.asset)
        self.assertEqual(current['metadata_revision'], revision + 1)
        self.assertEqual(current['title'], 'Guard control title')


if __name__ == '__main__':
    unittest.main()
