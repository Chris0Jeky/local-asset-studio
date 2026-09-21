import copy
from pathlib import Path
import tempfile
import unittest

from studio_workflow.core import MAX_BYTES, canonical, catalog, new_document
from studio_workflow.documents import WorkflowDocuments
from test_workflow_documents import GRAPH, INFO, SQLiteWorkspace


class RevisionRequestEnvelopeBoundaryTests(unittest.TestCase):
    def test_create_hash_envelope_does_not_narrow_the_accepted_request_limit(self):
        with tempfile.TemporaryDirectory() as root:
            document = new_document(copy.deepcopy(GRAPH), catalog(INFO, 'primary'), 'Boundary')
            document['nodes']['1']['_meta']['boundary_padding'] = ''
            request = {'request_id': 'boundary-create', 'document': document}
            padding = MAX_BYTES - len(canonical(request))
            self.assertGreater(padding, 0)
            document['nodes']['1']['_meta']['boundary_padding'] = 'x' * padding
            request = {'request_id': 'boundary-create', 'document': document}

            self.assertEqual(len(canonical(request)), MAX_BYTES)
            self.assertGreater(len(canonical({'action': 'create', **request})), MAX_BYTES)

            store = WorkflowDocuments(SQLiteWorkspace(Path(root)))
            result = store.create(request)
            self.assertEqual(result['document']['nodes']['1']['_meta']['boundary_padding'], 'x' * padding)


if __name__ == '__main__':
    unittest.main()
