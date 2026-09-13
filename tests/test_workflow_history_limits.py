"""Review regressions: bounded history and correct persisted-data error class."""
import json
import tempfile
import threading
from types import SimpleNamespace
import unittest
from studio_workflow.core import catalog, new_document, canonical
from studio_workflow.documents import WorkflowDocuments, DocumentError, history_summary
from studio_workflow.document_http import extend_handler, PREFIX
from test_workflow_documents import SQLiteWorkspace, INFO, GRAPH


class HistoryLimitsTests(unittest.TestCase):
    def test_full_maximum_history_fits_transport_and_retains_counts(self):
        ids = ['n' + str(i).zfill(95) for i in range(256)]
        raw = canonical({'added_nodes': ids, 'removed_nodes': ids, 'changed_nodes': ids,
                         'changed_fields': ['name'], 'execution_inputs_changed': True}).decode()
        result = history_summary(raw)
        self.assertTrue(result['truncated']); self.assertEqual(result['added_nodes_count'], 256)
        self.assertEqual(len(result['added_nodes']), 16)
        rows = [{'revision': i, 'sha256': 'f' * 64, 'request_id': 'r' * 96, 'summary': result} for i in range(1024)]
        self.assertLess(len(json.dumps({'revisions': rows}, indent=2).encode()), 8 * 1024 * 1024)
        self.assertEqual(len(json.loads(raw)['added_nodes']), 256)
    def test_corrupt_history_is_storage_failure(self):
        for raw in ('{', '[]', '{"added_nodes":"not a list"}', '{"execution_inputs_changed":1}'):
            with self.assertRaises(DocumentError) as caught: history_summary(raw)
            self.assertEqual(caught.exception.status, 503); self.assertEqual(caught.exception.code, 'storage_unavailable')
    def test_read_routes_report_corruption_as_503_not_bad_command(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = SQLiteWorkspace(root); store = WorkflowDocuments(workspace)
            created = store.create({'request_id': 'create', 'document': new_document(GRAPH, catalog(INFO, 'primary'))})
            class Base:
                def _safe_host(self): return True
                def _json(self, status, result): return status, result
            Handler = extend_handler(Base); handler = Handler()
            handler.studio = SimpleNamespace(assets=workspace, lock=threading.RLock())
            with workspace.connection() as db: db.execute("UPDATE workflow_requests_v1 SET summary='['")
            handler.path = PREFIX + '/' + created['id'] + '/history'
            status, result = handler.do_GET(); self.assertEqual(status, 503); self.assertEqual(result['code'], 'storage_unavailable')
            with workspace.connection() as db: db.execute("UPDATE workflow_revisions_v1 SET sha256='changed'")
            handler.path = PREFIX + '/' + created['id']
            status, result = handler.do_GET(); self.assertEqual(status, 503); self.assertEqual(result['code'], 'storage_unavailable')
