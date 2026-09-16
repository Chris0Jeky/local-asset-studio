"""Public request bounds must not shrink when server hash metadata is added."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio_workflow.core import canonical, catalog, new_document
from studio_workflow.documents import WorkflowDocuments
from test_workflow_documents import GRAPH, INFO, SQLiteWorkspace


class RevisionRequestBoundaryTests(unittest.TestCase):
    def test_create_accepts_payload_at_existing_request_bound(self):
        with tempfile.TemporaryDirectory() as root:
            document = new_document(GRAPH, catalog(INFO, "primary"), "Boundary")
            payload = {"request_id": "boundary-create", "document": document}
            request_bytes = len(canonical(payload))
            envelope_bytes = len(canonical({"action": "create", **payload}))
            self.assertLess(len(canonical(document)), request_bytes)
            self.assertGreater(envelope_bytes, request_bytes)

            store = WorkflowDocuments(SQLiteWorkspace(Path(root)))
            with patch("studio_workflow.core.MAX_BYTES", request_bytes):
                result = store.create(payload)

            self.assertEqual(result["document"]["name"], "Boundary")
            self.assertEqual(result["revision"], 1)


if __name__ == "__main__":
    unittest.main()
