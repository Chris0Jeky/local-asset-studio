"""Real loopback protocol checks, including lost/ambiguous commit responses."""
from contextlib import contextmanager
from http.client import HTTPConnection, RemoteDisconnected
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from workspace import AssetWorkspace
from studio_workflow.core import canonical
from test_collection_commands import FORMAT

PREFIX = '/api/collections'


class CollectionHTTPTests(unittest.TestCase):
    def setUp(self):
        from importlib.util import find_spec
        self.assertIsNotNone(find_spec('studio_workflow.collection_http'), 'Collection protocol handler is missing')
        from studio_workflow.collection_http import extend_handler
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = AssetWorkspace(self.temp.name)
        self.scope = self.workspace.snapshot()['workspace_id']
        self.studio = SimpleNamespace(assets=self.workspace)
        self.flags = flags = {'lose': False}
        class Base(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://' + self.headers.get('Host', '')
            def _content_length(self, cap):
                size = int(self.headers['Content-Length'])
                if not 0 <= size <= cap: raise ValueError('Body too large')
                return size
            def _json(self, status, value):
                if self.path == PREFIX and status == 200 and flags['lose']:
                    flags['lose'] = False; self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR); return
                raw = canonical(value); self.send_response(status)
                self.send_header('Content-Length', str(len(raw))); self.send_header('Content-Type', 'application/json')
                self.end_headers(); self.wfile.write(raw)
            def do_GET(self): return self._json(404, {'error': 'Unclaimed route'})
            def do_POST(self): return self._json(404, {'error': 'Unclaimed route'})
        self.handler = extend_handler(Base); self.handler.studio = self.studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start(); self.addCleanup(self.close)
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)

    def payload(self, **extra):
        return {'format': FORMAT, 'action': 'create', 'request_id': 'http-create-0001', 'workspace_id': self.scope,
                'name': 'HTTP collection', 'description': 'Typed result', **extra}

    def call(self, suffix='', value=None, *, raw=None, origin=None, host=None):
        body = raw if raw is not None else canonical(value) if value is not None else None
        headers = {'Content-Type': 'application/json', 'Origin': origin or self.origin}
        if host: headers['Host'] = host
        request = Request(self.origin + PREFIX + suffix, data=body, headers=headers)
        try:
            with urlopen(request, timeout=5) as response: return response.status, json.load(response)
        except HTTPError as error: return error.code, json.loads(error.read())

    def status(self, request='http-create-0001', scope=None):
        return self.call('/commands/' + request + '?' + urlencode({'workspace_id': scope or self.scope}))

    def test_create_and_status_use_the_typed_service_and_original_receipt(self):
        status, first = self.call(value=self.payload())
        self.assertEqual(status, 200, first)
        status, found = self.status()
        self.assertEqual(status, 200, found)
        self.assertEqual(found['receipt_json'], first['receipt_json'])
        self.assertEqual(found['receipt']['result']['revision'], 1)
        self.assertTrue(found['replayed'])
        self.assertEqual(self.call(value=self.payload(name='Different'))[0], 409)
        self.assertEqual(len(self.workspace.snapshot()['collections']), 1)

    def test_commit_survives_a_lost_response_and_reopen(self):
        self.flags['lose'] = True
        with self.assertRaises((RemoteDisconnected, ConnectionError)):
            self.call(value=self.payload())
        self.studio.assets = AssetWorkspace(self.temp.name)
        status, found = self.status()
        self.assertEqual(status, 200, found); self.assertEqual(found['status'], 'committed')
        status, replay = self.call(value=self.payload())
        self.assertEqual(status, 200, replay); self.assertTrue(replay['replayed'])
        self.assertEqual(found['receipt_json'], replay['receipt_json'])
        self.assertEqual(len(self.studio.assets.snapshot()['collections']), 1)

    def test_post_commit_failure_is_503_not_a_new_request_or_false_rollback(self):
        original = self.workspace.connection
        @contextmanager
        def failed_acknowledgement():
            with original() as db: yield db
            raise OSError('Acknowledgement failed after the transaction committed')
        with patch.object(self.workspace, 'connection', failed_acknowledgement):
            status, error = self.call(value=self.payload())
        self.assertEqual(status, 503, error)
        self.assertEqual(error['code'], 'collection_storage_unconfirmed')
        self.assertEqual(error['outcome'], 'unknown')
        status, found = self.status()
        self.assertEqual(status, 200, found); self.assertEqual(found['status'], 'committed')
        self.assertEqual(self.call(value=self.payload())[1]['receipt_json'], found['receipt_json'])

    def test_workspace_at_same_address_is_not_the_same_recovery_scope(self):
        self.assertEqual(self.call(value=self.payload())[0], 200)
        with tempfile.TemporaryDirectory() as other:
            self.studio.assets = AssetWorkspace(other)
            other_scope = self.studio.assets.snapshot()['workspace_id']
            self.assertEqual(self.status()[0], 409)
            self.assertEqual(self.call(value=self.payload())[0], 409)
            status, result = self.status(scope=other_scope)
            self.assertEqual(status, 200, result); self.assertEqual(result['status'], 'unknown')
            self.assertEqual(self.studio.assets.snapshot()['collections'], [])
            self.assertEqual(len(self.workspace.snapshot()['collections']), 1)

    def test_status_requires_exact_scope_query_and_never_reserves_unknown_id(self):
        for suffix, expected in [('/commands/http-create-0001', 428),
                                 ('/commands/http-create-0001?workspace_id=' + self.scope + '&workspace_id=' + self.scope, 400),
                                 ('/commands/http-create-0001?workspace_id=' + self.scope + '&other=x', 400),
                                 ('/commands/short?workspace_id=' + self.scope, 400),
                                 ('/commands/http-create-0001?wrong=' + self.scope, 400)]:
            with self.subTest(suffix=suffix): self.assertEqual(self.call(suffix)[0], expected)
        self.assertEqual(self.status()[1]['status'], 'unknown')
        self.assertEqual(self.call(value=self.payload())[0], 200)

    def test_host_origin_malformed_json_and_non_utf8_are_refused_before_writing(self):
        self.assertEqual(self.call(value=self.payload(), origin='https://evil.example')[0], 403)
        self.assertEqual(self.call(value=self.payload(), host='evil.example')[0], 403)
        for raw in (b'{"name":1,"name":2}', b'{"__proto__":1}', b'null', b'[]', b'{"name":NaN}',
                    json.dumps(self.payload()).encode('utf-16-le')):
            with self.subTest(raw=raw[:20]): self.assertEqual(self.call(raw=raw)[0], 400)
        self.assertEqual(self.call('?ignored=true', self.payload())[0], 400)
        self.assertEqual(self.workspace.snapshot()['collections'], [])

    def test_ambiguous_http_framing_is_refused(self):
        for headers in ([('Content-Length', '2'), ('Content-Length', '2')],
                        [('Content-Length', '2'), ('Transfer-Encoding', 'chunked')],
                        [('Content-Length', '+2')]):
            with self.subTest(headers=headers):
                conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
                try:
                    conn.putrequest('POST', PREFIX)
                    conn.putheader('Origin', self.origin); conn.putheader('Content-Type', 'application/json')
                    for key, value in headers: conn.putheader(key, value)
                    conn.endheaders(b'{}')
                    response = conn.getresponse(); self.assertEqual(response.status, 400); response.read()
                finally: conn.close()
        self.assertEqual(self.workspace.snapshot()['collections'], [])

    def test_ambiguous_unread_body_closes_instead_of_reusing_connection(self):
        self.handler.protocol_version = 'HTTP/1.1'
        host = '127.0.0.1:' + str(self.server.server_port)
        raw = ('POST /api/collections HTTP/1.1\r\nHost: ' + host + '\r\nOrigin: http://' + host +
               '\r\nContent-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}' +
               'GET /api/collections/commands/http-create-0001?workspace_id=' + self.scope +
               ' HTTP/1.1\r\nHost: ' + host + '\r\nConnection: close\r\n\r\n').encode()
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=5) as sock:
            sock.sendall(raw); chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk: break
                chunks.append(chunk)
        response = b''.join(chunks)
        self.assertEqual(response.count(b'HTTP/1.1 '), 1, response)
        self.assertIn(b'HTTP/1.1 400', response)

    def test_malformed_consumed_body_does_not_drain_the_next_pipelined_request(self):
        self.handler.protocol_version = 'HTTP/1.1'
        host = '127.0.0.1:' + str(self.server.server_port)
        first = ('POST /api/collections HTTP/1.1\r\nHost: ' + host + '\r\nOrigin: ' + self.origin +
                 '\r\nContent-Type: application/json\r\nContent-Length: 4\r\n\r\nnull')
        second = ('GET /api/collections/commands/http-create-0001?workspace_id=' + self.scope +
                  ' HTTP/1.1\r\nHost: ' + host + '\r\nConnection: close\r\n\r\n')
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=5) as stream:
            stream.sendall((first + second).encode('ascii'))
            raw = b''
            while True:
                chunk = stream.recv(65536)
                if not chunk: break
                raw += chunk
        self.assertIn(b'HTTP/1.1 400', raw)
        self.assertIn(b'HTTP/1.1 200', raw, 'The rejected body consumed bytes from the next request')
        self.assertIn(b'"status":"unknown"', raw)
        self.assertEqual(self.workspace.snapshot()['collections'], [])

    def test_legacy_path_is_unscoped_only_and_error_versions_remain_explicit(self):
        status, legacy = self.call(value={'name': 'Legacy'})
        self.assertEqual(status, 200, legacy); self.assertEqual(set(legacy), {'id', 'name', 'description'})
        status, missing = self.call(value={'name': 'Old scoped', 'workspace_id': self.scope})
        self.assertEqual(status, 428, missing); self.assertEqual(missing['format'], 'studio.collection-error/v1')
        self.assertEqual(self.call('/commands/http-create-0001', value=self.payload())[0], 405)

    def test_storage_and_corrupt_evidence_errors_remain_structured(self):
        self.assertEqual(self.call(value=self.payload())[0], 200)
        with self.workspace.connection() as db: db.execute('UPDATE collection_commands_v1 SET receipt=?', ('{',))
        status, error = self.status()
        self.assertEqual(status, 503, error); self.assertEqual(error['code'], 'collection_storage_corrupt')
        with patch.object(self.workspace, 'connection', side_effect=sqlite3.OperationalError('unavailable')):
            status, error = self.status()
        self.assertEqual(status, 503, error); self.assertEqual(error['code'], 'collection_storage_unconfirmed')


if __name__ == '__main__':
    unittest.main()
