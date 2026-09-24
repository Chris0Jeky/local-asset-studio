"""Empty labels survive reopen without converting wrong-type storage into text."""
import unittest

import test_asset_read_encoding as encoding_tests
from test_workspace import workspace


class AssetReadReopenContractTests(unittest.TestCase):
    def store(self, encoding):
        fixture = encoding_tests.AssetReadEncodingTests()
        self.addCleanup(fixture.doCleanups)
        root = fixture.encoded_store(encoding)
        return root, fixture.store

    def test_empty_labels_survive_reopen_with_page_selection_parity(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            with self.subTest(encoding=encoding):
                root, store = self.store(encoding)
                with store.connection() as db:
                    db.execute("UPDATE assets SET title='',filename='',preset_name=''")
                before = store.asset_page(limit=2)
                store = workspace.AssetWorkspace(root)
                page = store.asset_page(limit=2)
                self.assertEqual(page, before)
                item = page['assets'][0]
                for key in ('title', 'filename', 'preset_name'):
                    self.assertEqual(item[key], '')
                self.assertEqual(item['truncated_fields'], [])
                selected = store.asset_selection([item['id']], workspace_id=page['workspace_id'])
                self.assertEqual(selected['items'][0]['asset'], item)
                self.assertIsNotNone(page['next_cursor'])
                self.assertEqual(len(store.asset_page(limit=2, cursor=page['next_cursor'])['assets']), 2)

    def test_empty_blobs_remain_invalid_in_page_and_selection(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            for key in ('title', 'filename', 'preset_name'):
                with self.subTest(encoding=encoding, key=key):
                    _, store = self.store(encoding)
                    page = store.asset_page(limit=1)
                    asset_id = page['assets'][0]['id']
                    with store.connection() as db:
                        db.execute('UPDATE assets SET ' + key + "=X''")
                    for operation in (lambda: store.asset_page(limit=1),
                                      lambda: store.asset_selection([asset_id], workspace_id=page['workspace_id'])):
                        with self.assertRaises(workspace.WorkspaceError) as error:
                            operation()
                        self.assertEqual((error.exception.code, error.exception.status), ('asset_read_unavailable', 503))


if __name__ == '__main__':
    unittest.main()
