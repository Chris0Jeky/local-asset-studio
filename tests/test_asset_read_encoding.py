"""Catalogue observations retain their bounds in every SQLite text encoding."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_asset_reads
from test_workspace import workspace
from studio_workflow import asset_reads


class AssetReadEncodingTests(unittest.TestCase):
    seed = test_asset_reads.AssetReadTests.seed

    def encoded_store(self, encoding):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        database = root / 'workspace' / 'assets.sqlite3'
        database.parent.mkdir()
        with sqlite3.connect(database) as db:
            db.execute("PRAGMA encoding='" + encoding + "'")
            db.execute('CREATE TABLE encoding_seed(value TEXT)')
        db.close()
        self.store = workspace.AssetWorkspace(root)
        self.seed(7)
        return root

    def test_pages_selection_labels_and_restart_preserve_encoding(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            with self.subTest(encoding=encoding):
                root = self.encoded_store(encoding)
                title = 'Café\0 · 雪 · 😀'
                with self.store.connection() as db:
                    db.execute('UPDATE assets SET title=?,filename=?', (title, '雪😀.png'))
                    before = tuple(db.execute('SELECT hex(CAST(title AS BLOB)),sha256 FROM assets LIMIT 1').fetchone())
                first = self.store.asset_page(limit=2)
                item = first['assets'][0]
                self.assertEqual(item['title'], title)
                self.assertEqual(item['filename'], '雪😀.png')
                self.assertEqual(item['sha256'], 'a' * 64)
                self.assertNotIn('_text_encoding', item)
                selected = self.store.asset_selection([item['id']], workspace_id=first['workspace_id'])
                self.assertEqual(selected['items'][0]['asset'], item)
                self.store = workspace.AssetWorkspace(root)
                second = self.store.asset_page(limit=2, cursor=first['next_cursor'])
                self.assertEqual(second['catalogue'], first['catalogue'])
                with self.store.connection() as db:
                    self.assertEqual(tuple(db.execute('SELECT hex(CAST(title AS BLOB)),sha256 FROM assets LIMIT 1').fetchone()), before)
                    self.assertEqual(db.execute('PRAGMA encoding').fetchone()[0].lower(), encoding.lower())
                    db.execute("UPDATE assets SET notes='changed'")
                with self.assertRaises(workspace.WorkspaceError) as error:
                    self.store.asset_page(limit=2, cursor=first['next_cursor'])
                self.assertEqual(error.exception.code, 'asset_cursor_stale')

    def test_text_encoding_stays_local_to_each_workspace_connection(self):
        stores = []
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            self.encoded_store(encoding)
            with self.store.connection() as db:
                db.execute('UPDATE assets SET title=?', ('雪😀\0end',))
            stores.append(self.store)
        for store in reversed(stores):
            self.assertEqual(store.asset_page(limit=1)['assets'][0]['title'], '雪😀\0end')

    def test_display_prefixes_and_identity_projection_remain_bounded(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            with self.subTest(encoding=encoding):
                self.encoded_store(encoding)
                with self.store.connection() as db:
                    db.execute('UPDATE assets SET title=?', ('😀' * 500,))
                item = self.store.asset_page(limit=1)['assets'][0]
                self.assertEqual(item['title'], '😀' * 200)
                self.assertIn('title', item['truncated_fields'])
                with self.store.connection() as db:
                    db.execute('UPDATE assets SET preset_id=?', ('x' * 200000,))
                sizes = []
                original = asset_reads._summary
                def observed(row):
                    sizes.extend(len(value) for value in row if type(value) in (str, bytes))
                    return original(row)
                with patch.object(asset_reads, '_summary', observed):
                    with self.assertRaises(workspace.WorkspaceError) as error:
                        self.store.asset_page(limit=1)
                self.assertEqual(error.exception.code, 'asset_read_unavailable')
                self.assertLess(max(sizes), 1024)

    def test_corrupt_epoch_refuses_reads_and_mutations_without_reset(self):
        for encoding in ('UTF-8', 'UTF-16le', 'UTF-16be'):
            with self.subTest(encoding=encoding):
                self.encoded_store(encoding)
                for invalid in ('a' * 31, 'g' * 32, 'a' * 31 + '\0', 'a' * 32 + '\0hidden'):
                    with self.subTest(epoch=repr(invalid)):
                        with self.store.connection() as db:
                            db.execute('UPDATE asset_read_state_v1 SET epoch=?', (invalid,))
                        with self.assertRaises(workspace.WorkspaceError) as error:
                            self.store.asset_page(limit=1)
                        self.assertEqual(error.exception.code, 'asset_read_unavailable')
                        with self.store.connection() as db:
                            with self.assertRaises(sqlite3.IntegrityError):
                                db.execute("UPDATE assets SET notes='must not commit'")
                            self.assertEqual(db.execute('SELECT epoch FROM asset_read_state_v1').fetchone()[0], invalid)
                            self.assertEqual(db.execute('SELECT notes FROM assets LIMIT 1').fetchone()[0], 'private notes')


if __name__ == '__main__':
    unittest.main()
