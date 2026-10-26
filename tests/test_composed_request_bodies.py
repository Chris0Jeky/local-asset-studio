"""A valid JSON prefix at socket EOF must not authorize a composed-route mutation."""
from http.client import HTTPResponse
from pathlib import Path
import json
import socket
import tempfile
import threading
from types import SimpleNamespace
import unittest

from http_test_server import ThreadingHTTPServer
from studio_prompt.core import new_brief
from studio_workflow.core import catalog, new_document
from studio_workflow.document_http import PREFIX, store
from test_addressable_figures import register_sheet
from test_server import server
from test_workflow_documents import GRAPH, INFO


class ComposedRequestBodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = server.AssetWorkspace(self.root)
        self.studio = SimpleNamespace(assets=self.assets, lock=threading.RLock())

        class Handler(server.extend_handler(server.Handler)):
            studio = self.studio

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)
        self.document = new_document(GRAPH, catalog(INFO, 'primary'), 'Original')

    def post(self, path, value, *, missing=0):
        # The omitted bytes could have been trailing whitespace: JSON parsing
        # alone succeeds even though the declared request has not arrived.
        raw = json.dumps(value).encode()
        headers = (f'POST {path} HTTP/1.1\r\nHost: 127.0.0.1:8191\r\n'
                   'Origin: http://127.0.0.1:8191\r\nContent-Type: application/json\r\n'
                   f'Content-Length: {len(raw) + missing}\r\n\r\n').encode()
        with socket.create_connection(('127.0.0.1', self.http.server_port), timeout=5) as peer:
            peer.sendall(headers + raw)
            peer.shutdown(socket.SHUT_WR)
            with HTTPResponse(peer) as response:
                response.begin()
                return response.status, json.loads(response.read())

    def assert_incomplete(self, status, value):
        self.assertEqual(status, 400, value)
        self.assertEqual(value['error'], 'Incomplete request body')
        self.assertIs(value['generation_submitted'], False)

    def test_truncated_create_leaves_no_document_or_request_receipt(self):
        payload = {'request_id': 'create', 'document': self.document}
        self.assert_incomplete(*self.post(PREFIX, payload, missing=1))
        repository = store(self.studio)
        self.assertEqual(repository.list()['documents'], [])
        with self.assets.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_requests_v1').fetchone()[0], 0)
        # The same request ID and content must still be usable after a refusal.
        status, created = self.post(PREFIX, payload)
        self.assertEqual(status, 200, created)
        self.assertFalse(created['replayed'])

    def test_truncated_edit_preserves_revision_history_and_receipts(self):
        repository = store(self.studio)
        created = repository.create({'request_id': 'create', 'document': self.document})
        key = created['id']
        payload = {'request_id': 'rename', 'expected_revision': 1,
                   'commands': [{'op': 'rename', 'name': 'Changed'}]}
        self.assert_incomplete(*self.post(f'{PREFIX}/{key}/commands', payload, missing=7))
        self.assertEqual(repository.get(key)['document']['name'], 'Original')
        self.assertEqual(repository.get(key)['revision'], 1)
        self.assertEqual(len(repository.history(key)['revisions']), 1)
        with self.assets.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_requests_v1').fetchone()[0], 1)
        status, result = self.post(f'{PREFIX}/{key}/commands', payload)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['revision'], 2)
        self.assertFalse(result['replayed'])

    def test_truncated_prompt_is_refused_and_complete_prompt_compiles(self):
        payload = {'intent': new_brief('Keeper'), 'profile_id': 'sdxl-prose-v1'}
        self.assert_incomplete(*self.post('/api/prompt/compile', payload, missing=1))
        status, compiled = self.post('/api/prompt/compile', payload)
        self.assertEqual(status, 200, compiled)
        self.assertIn('Keeper', compiled['fields']['positive'])
        self.assertFalse(compiled['generation_submitted'])

    def test_truncated_figure_split_creates_no_children_or_receipt(self):
        parent, _ = register_sheet(self.assets, self.root)
        payload = {
            'workspace_id': self.assets.snapshot()['workspace_id'], 'request_id': 'split-http-body-0001',
            'asset_id': parent, 'parent_sha256': self.assets.get(parent)['sha256'],
            'rectangles': [{'x': 0, 'y': 0, 'width': 5000, 'height': 10000}],
        }
        self.assert_incomplete(*self.post('/api/assets/split-figures', payload, missing=1))
        self.assertEqual(len(self.assets.snapshot()['assets']), 1)
        with self.assets.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0], 0)
        status, result = self.post('/api/assets/split-figures', payload)
        self.assertEqual(status, 201, result)
        self.assertEqual(len(result['created']), 1)
        self.assertEqual(len(self.assets.snapshot()['assets']), 2)
        with self.assets.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
