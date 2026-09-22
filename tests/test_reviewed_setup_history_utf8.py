"""Corrupt SQLite TEXT must remain typed, read-only history corruption."""
import tempfile
import unittest
from pathlib import Path

from studio_workflow.setup_history import HistoryReadError, SetupHistory
from test_revision_consistency_matrix import SetupAdapter


class HistoryInvalidUTF8Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.adapter = SetupAdapter(Path(temporary.name))
        self.adapter.create()
        self.history = SetupHistory(self.adapter.store.workspace)

    def evidence(self):
        with self.adapter.store.workspace.connection() as db:
            row = db.execute('''SELECT typeof(record), hex(CAST(record AS BLOB)),
                typeof(sha256), hex(CAST(sha256 AS BLOB)), typeof(bytes), bytes
                FROM setup_versions_v1 WHERE draft_id=? AND revision=1''',
                (self.adapter.key,)).fetchone()
        return tuple(row)

    def assert_typed_corruption(self):
        before = self.evidence()
        with self.assertRaises(HistoryReadError) as error:
            self.history.page(self.adapter.key, workspace_id=self.adapter.scope)
        self.assertEqual(error.exception.code, 'setup_history_corrupt')
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(before, self.evidence())

    def test_invalid_utf8_record_text_is_typed_corruption_without_repair(self):
        with self.adapter.store.workspace.connection() as db:
            db.execute("UPDATE setup_versions_v1 SET record=CAST(x'80' AS TEXT), bytes=1")
        self.assert_typed_corruption()

    def test_invalid_utf8_digest_text_is_typed_corruption_without_repair(self):
        with self.adapter.store.workspace.connection() as db:
            db.execute("UPDATE setup_versions_v1 SET sha256=CAST(zeroblob(63) || x'80' AS TEXT)")
        self.assert_typed_corruption()


if __name__ == '__main__':
    unittest.main()
