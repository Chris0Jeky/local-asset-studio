"""Actual loopback transport for the shared document reducer and persistence."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from workspace import AssetWorkspace
from studio_workflow.core import canonical, digest
from studio_workflow.document_http import extend_handler, PREFIX
from test_workflow_module_commands import fixture, import_command, plan


class ModuleHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = AssetWorkspace(self.temp.name)
        studio = SimpleNamespace(assets=self.workspace, lock=threading.RLock())
        class Base(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers.get('Host', '')
            def _content_length(self, cap):
                lengths = self.headers.get_all('Content-Length') or []
                if len(lengths) != 1 or self.headers.get('Transfer-Encoding'): raise ValueError('Invalid framing')
                size = int(lengths[0])
                if not 0 <= size <= cap: raise ValueError('Body limit')
                return size
            def _json(self, status, value):
                raw = canonical(value); self.send_response(status)
                self.send_header('Content-Length', str(len(raw))); self.send_header('Content-Type', 'application/json')
                self.end_headers(); self.wfile.write(raw)
            def do_GET(self): return self._json(404, {'error': 'Unclaimed route'})
            def do_POST(self): return self._json(404, {'error': 'Unclaimed route'})
        handler = extend_handler(Base); handler.studio = studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start(); self.addCleanup(self.close)
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.doc, self.schema = fixture()

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)

    def call(self, route, value=None, *, raw=None, origin=None, host=None):
        headers = {'Content-Type': 'application/json', 'Origin': origin or self.origin}
        if host: headers['Host'] = host
        body = raw if raw is not None else canonical(value) if value is not None else None
        request = Request(self.origin + PREFIX + route, data=body, headers=headers)
        try:
            with urlopen(request, timeout=5) as response: return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_export_inspect_reduce_plan_and_commit_have_identical_hashes(self):
        status, exported = self.call('/modules/export', {'document': self.doc, 'step_id': 'pipeline'})
        self.assertEqual(status, 200, exported)
        status, inspected = self.call('/modules/inspect', {'module': exported['module']})
        self.assertEqual(status, 200, inspected)
        self.assertEqual(inspected['module_sha256'], exported['module_sha256'])
        self.assertIsNone(exported['module']['origin']['document_id'])
        edits = [import_command(exported['module'])]
        status, reduced = self.call('/reduce', {'document': self.doc, 'commands': edits})
        self.assertEqual(status, 200, reduced)
        status, pure_plan = self.call('/plan', {'document': self.doc, 'commands': edits})
        self.assertEqual(status, 200, pure_plan)
        self.assertEqual(digest(reduced['document']), pure_plan['after_document_sha256'])
        self.assertEqual(pure_plan, plan(self.doc, edits))
        status, created = self.call('', {'request_id': 'http-create', 'document': self.doc})
        self.assertEqual(status, 200, created); key = created['id']
        status, saved_export = self.call('/' + key + '/revisions/1/modules/pipeline')
        self.assertEqual(status, 200, saved_export)
        self.assertEqual(saved_export['module']['origin']['document_id'], key)
        self.assertEqual(saved_export['module']['origin']['revision'], 1)
        status, planned = self.call('/' + key + '/plan', {'expected_revision': 1, 'commands': edits})
        self.assertEqual(status, 200, planned)
        status, committed = self.call('/' + key + '/commands', {'request_id': 'http-import', 'expected_revision': 1, 'commands': edits})
        self.assertEqual(status, 200, committed)
        self.assertEqual(committed['document_sha256'], planned['document_sha256'])
        status, undone = self.call('/' + key + '/commands', {'request_id': 'http-undo', 'expected_revision': 2,
                                                          'commands': planned['inverse_commands']})
        self.assertEqual(status, 200, undone)
        self.assertEqual(undone['document'], created['document'] | {'revision': 3})

    def test_state_conflict_is_409_and_malformed_assertion_is_400(self):
        status, result = self.call('/plan', {'document': self.doc, 'commands': [{'op': 'rename', 'name': 'After'}]})
        self.assertEqual(status, 200, result)
        changed = copy.deepcopy(result['document']); changed['name'] = 'Unexpected'
        status, conflict = self.call('/reduce', {'document': changed, 'commands': result['inverse_commands']})
        self.assertEqual(status, 409, conflict)
        self.assertEqual(conflict['code'], 'document_state_conflict')
        self.assertNotEqual(conflict['expected_sha256'], conflict['current_sha256'])
        self.assertFalse(conflict['generation_submitted'])
        self.assertEqual(self.call('/reduce', {'document': changed, 'commands': [{'op': 'assert_state', 'sha256': 'bad'}]})[0], 400)

    def test_origin_host_duplicate_keys_and_query_rejections_do_not_write(self):
        payload = {'document': self.doc, 'step_id': 'pipeline'}
        self.assertEqual(self.call('/modules/export', payload, origin='https://evil.example')[0], 403)
        self.assertEqual(self.call('/modules/export', payload, host='evil.example')[0], 403)
        self.assertEqual(self.call('/modules/export?extra=1', payload)[0], 400)
        self.assertEqual(self.call('/modules/export', raw=b'{"document":{},"document":{}}')[0], 400)
        self.assertEqual(self.call('/modules/export', raw=b'null')[0], 400)
        self.assertEqual(self.call('/modules/inspect', {'module': {'format': 'unsupported'}})[0], 400)
        with self.workspace.connection() as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn('workflow_documents_v1', tables)

    def test_pure_routes_do_not_initialize_the_document_store(self):
        status, result = self.call('/modules/export', {'document': self.doc, 'step_id': 'pipeline'})
        self.assertEqual(status, 200, result)
        status, result = self.call('/plan', {'document': self.doc, 'commands': [{'op': 'rename', 'name': 'Preview'}]})
        self.assertEqual(status, 200, result)
        with self.workspace.connection() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='workflow_documents_v1'").fetchone())


if __name__ == '__main__':
    unittest.main()
