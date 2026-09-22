"""Bound the actual retained-revision walk, not only Python result allocation."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from studio_workflow.setup_drafts import SetupError
import test_reviewed_setup_history_reconciled as fixture


class HistoryQueryPlanTests(unittest.TestCase):
    setUp = fixture.ReconciledHistoryTests.setUp

    def test_integrity_walk_uses_index_order_without_sorting_the_entire_line(self):
        statements = []
        connect = self.store.workspace.connection
        @contextmanager
        def traced():
            with connect() as db:
                db.set_trace_callback(statements.append)
                yield db
        with patch.object(self.store.workspace, 'connection', side_effect=traced):
            self.history.page(self.key, workspace_id=self.scope)
        walks = [sql for sql in statements if "CASE WHEN typeof(revision)='integer'" in sql]
        self.assertEqual(len(walks), 1, statements)
        with connect() as db:
            plan = [row['detail'].upper() for row in db.execute('EXPLAIN QUERY PLAN ' + walks[0])]
        self.assertFalse(any('TEMP B-TREE' in step for step in plan), plan)
        self.assertTrue(any('COVERING INDEX' in step for step in plan), plan)

    def test_excess_revision_refusal_stops_under_a_bounded_vm_budget(self):
        connect = self.store.workspace.connection
        with connect() as db:
            row = db.execute('SELECT record,sha256,bytes FROM setup_versions_v1').fetchone()
            db.executemany('INSERT INTO setup_versions_v1 VALUES (?,?,?,?,?)',
                           ((self.key, revision, *row) for revision in range(2, 10001)))
        progress = 0
        def budget():
            nonlocal progress
            progress += 1
            return progress > 100
        @contextmanager
        def bounded():
            with connect() as db:
                db.set_progress_handler(budget, 100)
                yield db
        with patch.object(self.store.workspace, 'connection', side_effect=bounded):
            with self.assertRaises(ValueError) as error:
                try:
                    self.history.page(self.key, workspace_id=self.scope)
                except Exception as exc:
                    if not isinstance(exc, ValueError):
                        self.fail('History exhausted the SQLite work budget instead of bounded refusal: ' + str(exc))
                    raise
        self.assertIsInstance(error.exception, SetupError)
        self.assertEqual(error.exception.code, 'setup_history_corrupt')
        self.assertLessEqual(progress, 100)
        with connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM setup_versions_v1').fetchone()[0], 10000)
            self.assertEqual(db.execute('SELECT head FROM setup_drafts_v1').fetchone()[0], 1)
