"""Prove non-mutating revision paths retain every existing SQLite row exactly."""
from pathlib import Path
import tempfile
import unittest

from test_revision_consistency_matrix import ADAPTERS


def _rows(db, query, parameters=()):
    return tuple(tuple(row) for row in db.execute(query, parameters).fetchall())


def retained_evidence(adapter):
    """Capture every persisted row owned by one matrix subject."""
    if adapter.domain == "workflow-documents":
        with adapter.workspace.connection() as db:
            return (
                _rows(
                    db,
                    "SELECT id,head,origin,name FROM workflow_documents_v1 WHERE id=? ORDER BY id",
                    (adapter.key,),
                ),
                _rows(
                    db,
                    """SELECT document_id,revision,document,sha256,created_at,bytes
                       FROM workflow_revisions_v1 WHERE document_id=? ORDER BY revision""",
                    (adapter.key,),
                ),
                _rows(
                    db,
                    """SELECT request_id,sha256,document_id,revision,kind,summary
                       FROM workflow_requests_v1 WHERE document_id=? ORDER BY request_id""",
                    (adapter.key,),
                ),
            )
    if adapter.domain == "setup-drafts":
        with adapter.studio.assets.connection() as db:
            return (
                _rows(
                    db,
                    "SELECT id,head FROM setup_drafts_v1 WHERE id=? ORDER BY id",
                    (adapter.key,),
                ),
                _rows(
                    db,
                    """SELECT draft_id,revision,record,sha256,bytes
                       FROM setup_versions_v1 WHERE draft_id=? ORDER BY revision""",
                    (adapter.key,),
                ),
                _rows(
                    db,
                    """SELECT request_id,request_sha256,draft_id,receipt,sha256,bytes
                       FROM setup_operations_v1 WHERE draft_id=? ORDER BY request_id""",
                    (adapter.key,),
                ),
            )
    raise AssertionError(f"Unknown consistency-matrix domain: {adapter.domain}")


class RevisionConsistencyRetainedEvidenceTests(unittest.TestCase):
    def subject(self, factory):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        return factory(Path(root.name))

    def subjects(self):
        for factory in ADAPTERS:
            yield self.subject(factory)

    def test_budget_refusal_retains_every_existing_row_exactly(self):
        for adapter in self.subjects():
            with self.subTest(domain=adapter.domain):
                adapter.create()
                before = retained_evidence(adapter)
                with self.assertRaises(ValueError):
                    adapter.budget_refusal()
                self.assertEqual(retained_evidence(adapter), before)

    def test_replay_conflict_and_stale_refusal_do_not_rewrite_existing_rows(self):
        for adapter in self.subjects():
            with self.subTest(domain=adapter.domain):
                adapter.create()
                adapter.edit("retained-edit", 1, "Committed")
                before = retained_evidence(adapter)

                replay = adapter.edit("retained-edit", 1, "Committed", reordered=True)
                self.assertTrue(replay["replayed"])
                self.assertEqual(retained_evidence(adapter), before)

                with self.assertRaises(ValueError):
                    adapter.edit("retained-edit", 1, "Changed content")
                self.assertEqual(retained_evidence(adapter), before)

                with self.assertRaises(ValueError):
                    adapter.edit("retained-stale", 1, "Stale")
                self.assertEqual(retained_evidence(adapter), before)

    def test_reopen_replay_reads_original_rows_without_rewriting_them(self):
        for adapter in self.subjects():
            with self.subTest(domain=adapter.domain):
                adapter.create()
                adapter.edit("retained-lost-response", 1, "Recovered")
                before = retained_evidence(adapter)
                adapter.reopen()
                replay = adapter.edit(
                    "retained-lost-response", 1, "Recovered", reordered=True
                )
                self.assertTrue(replay["replayed"])
                self.assertEqual(retained_evidence(adapter), before)


if __name__ == "__main__":
    unittest.main()
