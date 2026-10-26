"""Core mutations require the entire declared body, including on a real EOF."""
import json
import socket
import tempfile
import threading
import unittest
from http.client import HTTPResponse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from http_test_server import ThreadingHTTPServer
from test_server import server
from workspace import AssetWorkspace


class RequestBodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.assets = AssetWorkspace(Path(temporary.name))
        self.studio = SimpleNamespace(assets=self.assets, upload=Mock(return_value={'file': 'fixture.png'}),
                                      import_image=Mock(return_value={'asset': 'fixture'}))
        class Handler(server.Handler): pass
        handler = server.extend_handler(Handler); handler.studio = self.studio
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.http.serve_forever)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.http.shutdown(); self.thread.join(); self.http.server_close()

    def post(self, path, body, *, missing=0, content_type='application/json'):
        headers = (f'POST {path} HTTP/1.1\r\nHost: localhost:8191\r\n'
                   f'Origin: http://localhost:8191\r\nContent-Type: {content_type}\r\n'
                   f'Content-Length: {len(body) + missing}\r\nConnection: close\r\n\r\n')
        with socket.create_connection(self.http.server_address, timeout=5) as sock:
            sock.sendall(headers.encode() + body)
            sock.shutdown(socket.SHUT_WR)
            with HTTPResponse(sock) as response:
                response.begin()
                return response.status, json.loads(response.read())

    def setup(self):
        return {'id': 'body-fixture', 'name': 'Keep this setup', 'recipe': {'controls': {'seed': 7}}}

    def test_incomplete_create_does_not_save_a_valid_json_prefix(self):
        status, result = self.post('/api/setups', json.dumps(self.setup()).encode(), missing=10)
        self.assertEqual(status, 400, result)
        self.assertIn('Incomplete request body', result['error'])
        self.assertEqual(self.assets.setups(), [])

    def test_incomplete_delete_preserves_the_saved_setup(self):
        self.assets.save_setup(self.setup()); before = self.assets.setups()
        body = json.dumps({'id': 'body-fixture', 'action': 'delete'}).encode()
        status, result = self.post('/api/setups', body, missing=1)
        self.assertEqual(status, 400, result)
        self.assertEqual(self.assets.setups(), before)

    def test_incomplete_binary_bodies_never_reach_upload_or_import(self):
        for route, operation in (('/api/upload', self.studio.upload),
                                 ('/api/assets/import', self.studio.import_image)):
            with self.subTest(route=route):
                status, result = self.post(route, b'fixture image bytes', missing=1, content_type='image/png')
                self.assertEqual(status, 400, result)
                self.assertIn('Incomplete request body', result['error'])
                operation.assert_not_called()

    def test_complete_create_and_delete_still_mutate_the_database(self):
        status, result = self.post('/api/setups', json.dumps(self.setup()).encode())
        self.assertEqual(status, 200, result)
        self.assertEqual(len(self.assets.setups()), 1)
        self.assertEqual(self.assets.setups()[0]['recipe'], self.setup()['recipe'])
        status, result = self.post('/api/setups', b'{"id":"body-fixture","action":"delete"}')
        self.assertEqual(status, 200, result)
        self.assertEqual(self.assets.setups(), [])

    def test_complete_binary_bodies_reach_upload_and_import_unchanged(self):
        body = b'fixture image bytes'
        for route, operation in (('/api/upload', self.studio.upload),
                                 ('/api/assets/import', self.studio.import_image)):
            with self.subTest(route=route):
                status, result = self.post(route, body, content_type='image/png')
                self.assertEqual(status, 201, result)
                operation.assert_called_once_with('reference', 'image/png', body, privacy='regular')
