"""History reads must preserve valid setup rows in every supported SQLite encoding."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from studio_workflow.setup_history import SetupHistory
from test_revision_consistency_matrix import SetupAdapter


class HistoryDatabaseEncodingTests(unittest.TestCase):
    def adapter(self, encoding):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        database = root / 'workspace' / 'assets.sqlite3'
        database.parent.mkdir(parents=True)
        db = sqlite3.connect(database)
        try:
            db.execute("PRAGMA encoding='" + encoding + "'")
            db.execute('CREATE TABLE encoding_seed(value TEXT)')
            db.commit()
        finally:
            db.close()
        adapter = SetupAdapter(root)
        adapter.draft['recipe']['controls']['positive'] = 'Café · 雪 · 😀'
        adapter.create()
        return adapter

    @staticmethod
    def evidence(adapter):
        with adapter.store.workspace.connection() as db:
            row = db.execute('''SELECT typeof(record),hex(CAST(record AS BLOB)),
                typeof(sha256),hex(CAST(sha256 AS BLOB)),typeof(bytes),bytes
                FROM setup_versions_v1 WHERE draft_id=? AND revision=1''',
                (adapter.key,)).fetchone()
            return tuple(row)

    def test_utf16_workspaces_keep_valid_history_readable_without_rewriting_rows(self):
        for encoding in ('UTF-16le', 'UTF-16be'):
            with self.subTest(encoding=encoding):
                adapter = self.adapter(encoding)
                original = adapter.store.get(adapter.key, 1)
                before = self.evidence(adapter)
                with adapter.store.workspace.connection() as db:
                    self.assertEqual(db.execute('PRAGMA encoding').fetchone()[0].lower(), encoding.lower())
                history = SetupHistory(adapter.store.workspace)
                page = history.page(adapter.key, workspace_id=adapter.scope)
                comparison = history.compare(adapter.key, 1, 1, workspace_id=adapter.scope)
                exported = history.export_revision(adapter.key, 1, workspace_id=adapter.scope)
                self.assertEqual(page['head_record_sha256'], original['record_sha256'])
                self.assertEqual(original['draft']['recipe']['controls']['positive'], 'Café · 雪 · 😀')
                self.assertEqual(page['revisions'][0]['record_bytes'], len(original['record_json'].encode('utf-8')))
                self.assertEqual(comparison['left_record_sha256'], original['record_sha256'])
                self.assertEqual(exported['export']['source_record_sha256'], original['record_sha256'])
                self.assertEqual(before, self.evidence(adapter))


if __name__ == '__main__':
    unittest.main()
