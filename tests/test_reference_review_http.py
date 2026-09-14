"""Real loopback HTTP, strict decoding and bounded source inspection; no Studio."""
import copy
import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from studio_prompt import reference_review
from studio_prompt.http_extension import extend_handler
import test_reference_review as fixtures


class ReferenceReviewHttpTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReferenceReviewTests(); self.fixture.setUp()
        self.studio = Mock()
        class Base(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def _safe_host(self): return self.headers.get('Host') == 'localhost:8191'
            def _safe_mutation(self): return self._safe_host() and self.headers.get('Origin') == 'http://localhost:8191'
            def _content_length(self, limit):
                n = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= n <= limit: raise ValueError('Request exceeds route limit')
                return n
            def _json(self, status, value):
                raw = json.dumps(value).encode(); self.send_response(status)
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        handler = extend_handler(Base); handler.studio = self.studio
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever); self.thread.start()
        self.addCleanup(self.close)
    def close(self):
        self.server.shutdown(); self.thread.join(); self.server.server_close()
        self.assertEqual(self.studio.mock_calls, [])
    def call(self, path, raw, **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('POST', '/api/prompt/' + path, raw, {'Host':'localhost:8191',
                'Origin':'http://localhost:8191', 'Content-Type':'application/json', **headers})
            response = connection.getresponse(); return response.status, json.loads(response.read())
        finally: connection.close()
    def test_preview_accepts_larger_body_only_on_exact_source_route(self):
        raw = json.dumps(self.fixture.payload).encode() + b' ' * (1024 * 1024)
        status, result = self.call('reference-review/preview', raw)
        self.assertEqual(status, 200); self.assertTrue(result['source_bytes_verified'])
        for route in ('reference-review/inspect', 'compile', 'reference-review/preview?anything'):
            # The server rejects an oversized Content-Length before consuming its body.
            with self.subTest(route=route):
                self.assertEqual(self.call(route, b'', **{'Content-Length': str(len(raw))})[0], 400)
    def test_route_header_cap_refuses_before_reading_body(self):
        status, result = self.call('reference-review/preview', b'', **{'Content-Length': str(reference_review.HTTP_LIMIT+1)})
        self.assertEqual(status, 400); self.assertIn('limit', result['error'])
    def test_origin_host_and_content_type_are_required(self):
        raw = json.dumps(self.fixture.payload).encode()
        for headers, code in (({'Host':'evil.invalid'},403), ({'Origin':'http://evil.invalid'},403), ({'Content-Type':'text/plain'},400)):
            with self.subTest(headers=headers): self.assertEqual(self.call('reference-review/preview', raw, **headers)[0], code)
    def test_duplicate_nonfinite_and_incomplete_json_are_not_normalized(self):
        for raw in (b'{"analysis":{},"analysis":{}}', b'{"analysis":NaN}', b'{"analysis":'):
            with self.subTest(raw=raw): self.assertEqual(self.call('reference-review/inspect', raw)[0], 400)
    def test_decoded_pixel_and_encoded_byte_caps_are_enforced(self):
        with patch.object(reference_review, 'PIXEL_LIMIT', 4):
            with self.assertRaisesRegex(ValueError, 'pixel'): self.fixture.preview()
        with patch.object(reference_review, 'ENCODED_LIMIT', 4):
            with self.assertRaisesRegex(ValueError, '8 MiB'): self.fixture.preview()
    def test_transport_error_response_preserves_original_and_current_intent(self):
        before = copy.deepcopy(self.fixture.payload); payload = copy.deepcopy(before)
        payload['images'][1]['media_base64'] = payload['images'][0]['media_base64']
        status, result = self.call('reference-review/preview', json.dumps(payload).encode())
        self.assertEqual(status, 400); self.assertIn('changed', result['error'])
        self.assertEqual(self.fixture.payload, before)


if __name__ == '__main__': unittest.main()
