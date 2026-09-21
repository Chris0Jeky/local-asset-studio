import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from studio_prompt import http_extension


class ForeignWorkspaceError(ValueError):
    def __init__(self, message, code, status):
        super().__init__(message)
        self.code = code
        self.status = status

    def response(self):
        return {'error': str(self), 'code': self.code, 'generation_submitted': False}


class ForeignWorkspaceErrorHTTPTests(unittest.TestCase):
    def setUp(self):
        class Base(BaseHTTPRequestHandler):
            studio = SimpleNamespace(assets=object())

            def log_message(self, *args): pass
            def _safe_host(self): return True
            def _safe_mutation(self): return True

            def _content_length(self, limit):
                value = int(self.headers.get('Content-Length', '0'))
                if value > limit: raise ValueError('too large')
                return value

            def _json(self, status, value):
                raw = json.dumps(value).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self): self._json(404, {'error': 'base'})
            def do_GET(self): self._json(404, {'error': 'base'})

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), http_extension.extend_handler(Base))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(2)

    def post(self):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            raw = b'{}'
            connection.request('POST', '/api/assets/split-figures', raw, {'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_workspace_error_from_another_import_identity_keeps_typed_response(self):
        failure = ForeignWorkspaceError('request id changed', 'asset_request_reused', 409)
        with patch.object(http_extension, 'split_figures', side_effect=failure):
            status, body = self.post()
        self.assertEqual(status, 409)
        self.assertEqual(body['code'], 'asset_request_reused')
        self.assertFalse(body['generation_submitted'])

    def test_plain_value_error_remains_a_generic_bad_request(self):
        with patch.object(http_extension, 'split_figures', side_effect=ValueError('invalid rectangle')):
            status, body = self.post()
        self.assertEqual(status, 400)
        self.assertEqual(body, {'error': 'invalid rectangle', 'generation_submitted': False})


if __name__ == '__main__': unittest.main()
