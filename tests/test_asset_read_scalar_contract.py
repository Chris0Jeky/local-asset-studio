"""Scalar corruption and empty labels stay bounded at the public read boundary."""
import unittest

import test_asset_read_encoding as encoding_tests
import test_asset_read_http as http_tests
from test_workspace import workspace


class AssetReadScalarContractTests(unittest.TestCase):
    def store(self, encoding='UTF-8'):
        fixture = encoding_tests.AssetReadEncodingTests()
        self.addCleanup(fixture.doCleanups)
        fixture.encoded_store(encoding)
        return fixture.store

    def unavailable(self, operation):
        try:
            operation()
        except Exception as error:
            self.assertIsInstance(error, workspace.WorkspaceError,
                                  'Corrupt stored text must not escape as a raw SQLite exception')
            self.assertEqual(error.code, 'asset_read_unavailable')
            self.assertEqual(error.status, 503)
        else:
            self.fail('Corrupt scalar metadata was accepted')

    def test_empty_display_labels_remain_empty_in_every_database_encoding(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            for field in ('title', 'filename', 'preset_name'):
                with self.subTest(encoding=encoding, field=field):
                    store = self.store(encoding)
                    with store.connection() as db:
                        db.execute('UPDATE assets SET ' + field + "='' WHERE id='asset-000006'")
                    before = store.snapshot()
                    page = store.asset_page()
                    selected = store.asset_selection(['asset-000006'], workspace_id=page['workspace_id'])
                    for item in (page['assets'][0], selected['items'][0]['asset']):
                        self.assertEqual(item[field], '')
                        self.assertNotIn(field, item['truncated_fields'])
                    self.assertEqual(store.snapshot(), before, 'Reading must not repair or rewrite stored text')

    def test_null_optional_label_is_not_converted_into_an_empty_label(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            with self.subTest(encoding=encoding):
                store = self.store(encoding)
                with store.connection() as db:
                    db.execute('UPDATE assets SET preset_name=NULL')
                page = store.asset_page()
                self.assertIsNone(page['assets'][0]['preset_name'])
                self.assertIsNone(store.asset_selection(['asset-000006'], workspace_id=page['workspace_id'])['items'][0]['asset']['preset_name'])

    def test_invalid_utf8_scalar_refuses_page_and_selection_without_repair(self):
        for field in ('sha256', 'media_type', 'review', 'preset_id'):
            with self.subTest(field=field):
                store = self.store()
                scope = store.asset_page()['workspace_id']
                with store.connection() as db:
                    db.execute('UPDATE assets SET ' + field + "=CAST(X'80' AS TEXT) WHERE id='asset-000006'")
                    stamp = tuple(db.execute('SELECT epoch,revision FROM asset_read_state_v1').fetchone())
                self.unavailable(lambda: store.asset_page())
                self.unavailable(lambda: store.asset_selection(['asset-000006'], workspace_id=scope))
                with store.connection() as db:
                    self.assertEqual(db.execute('SELECT hex(CAST(' + field + " AS BLOB)) FROM assets WHERE id='asset-000006'").fetchone()[0], '80')
                    self.assertEqual(tuple(db.execute('SELECT epoch,revision FROM asset_read_state_v1').fetchone()), stamp)
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0], 0)

    def test_corrupt_id_refuses_page_but_former_id_is_normally_missing(self):
        store = self.store()
        scope = store.asset_page()['workspace_id']
        with store.connection() as db:
            db.execute("UPDATE assets SET id=CAST(X'80' AS TEXT) WHERE id='asset-000006'")
        self.unavailable(lambda: store.asset_page())
        result = store.asset_selection(['asset-000006'], workspace_id=scope)
        self.assertEqual(result['items'], [{'id':'asset-000006', 'state':'missing', 'asset':None}])
        with store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assets WHERE hex(CAST(id AS BLOB))='80'").fetchone()[0], 1)

    def test_corrupt_scalar_http_reads_return_typed_503(self):
        fixture = http_tests.AssetReadHTTPTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with fixture.store.connection() as db:
            db.execute("UPDATE assets SET sha256=CAST(X'80' AS TEXT)")
        for method, route, body in (
            ('GET', http_tests.PAGE, None),
            ('POST', http_tests.SELECTION, {'workspace_id':fixture.scope, 'ids':[fixture.ids[0]]}),
        ):
            with self.subTest(method=method):
                status, result, _ = fixture.request(method, route, body)
                self.assertEqual(status, 503)
                self.assertEqual(result['code'], 'asset_read_unavailable')
                self.assertNotIn('assets', result)
                self.assertNotIn('items', result)


if __name__ == '__main__':
    unittest.main()
