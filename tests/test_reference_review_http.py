"""Real loopback HTTP, strict decoding and bounded source inspection; no Studio."""
import copy
import http.client
import json
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from http_test_server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from studio_prompt import reference_review
from studio_prompt import reference_intake
from studio_prompt.http_extension import extend_handler
from test_server import server
import test_reference_review as fixtures


class ReferenceReviewHttpTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReferenceReviewTests(); self.fixture.setUp()
        self.studio = Mock()
        class Base(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            _safe_host = server.Handler._safe_host
            _safe_mutation = server.Handler._safe_mutation
            _content_length = server.Handler._content_length
            def log_message(self, *args): pass
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
        self.assertEqual(status, 400); self.assertIn('large', result['error'])
    def test_fixture_accepts_both_production_loopback_origins(self):
        raw = json.dumps(self.fixture.payload).encode()
        status, result = self.call(
            'reference-review/preview',
            raw,
            Host='127.0.0.1:8191',
            Origin='http://127.0.0.1:8191',
        )
        self.assertEqual(status, 200, result)
        self.assertTrue(result['source_bytes_verified'])
    def test_fixture_uses_production_content_length_errors(self):
        status, result = self.call(
            'reference-review/preview',
            b'',
            **{'Content-Length': 'not-an-integer'},
        )
        self.assertEqual(status, 400)
        self.assertEqual(result['error'], 'Valid Content-Length required')

        status, result = self.call(
            'reference-review/preview',
            b'',
            **{'Content-Length': str(reference_review.HTTP_LIMIT + 1)},
        )
        self.assertEqual(status, 400)
        self.assertEqual(result['error'], 'Request body is too large')
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

    def raw_request(self, body=b'', *, lengths=(), extra='', half_close=False):
        sock = socket.create_connection(('127.0.0.1', self.server.server_port), timeout=2)
        self.addCleanup(sock.close)
        headers = 'POST /api/prompt/reference-review/preview HTTP/1.1\r\nHost: localhost:8191\r\nOrigin: http://localhost:8191\r\nContent-Type: application/json\r\n'
        headers += ''.join('Content-Length: %s\r\n' % length for length in lengths) + extra + '\r\n'
        sock.sendall(headers.encode() + body)
        if half_close: sock.shutdown(socket.SHUT_WR)
        response = http.client.HTTPResponse(sock); response.begin()
        result = json.loads(response.read())
        return sock, response.status, result

    def test_successful_preview_leaves_persistent_connection_ready_for_the_next_request(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=2)
        self.addCleanup(connection.close); original_socket = None
        for _ in range(2):
            connection.request('POST', '/api/prompt/reference-review/preview', json.dumps(self.fixture.payload),
                {'Host': 'localhost:8191', 'Origin': 'http://localhost:8191', 'Content-Type': 'application/json'})
            response = connection.getresponse(); result = json.loads(response.read())
            self.assertEqual(response.status, 200, result.get('error'))
            self.assertTrue(result['source_bytes_verified'])
            self.assertIsNotNone(connection.sock)
            if original_socket is not None: self.assertIs(connection.sock, original_socket)
            original_socket = connection.sock

    def test_incomplete_declared_body_closes_after_refusal_on_the_real_socket(self):
        raw = json.dumps(self.fixture.payload).encode()
        sock, status, result = self.raw_request(raw, lengths=[len(raw) + 1], half_close=True)
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('Incomplete', result['error'])
        self.assertEqual(sock.recv(1), b'')

    def test_ambiguous_headers_are_rejected_before_a_client_sends_their_body(self):
        for lengths, extra in (([100, 100], ''), ([100, 101], ''), ([100], 'Transfer-Encoding: chunked\r\n')):
            with self.subTest(lengths=lengths, extra=extra):
                sock, status, result = self.raw_request(lengths=lengths, extra=extra)
                self.assertEqual(status, 400, result.get('error'))
                self.assertEqual(sock.recv(1), b'')

    def test_stalled_body_releases_its_socket_with_a_bounded_error_response(self):
        with patch.object(reference_intake, 'READ_TIMEOUT_SECONDS', 0.05):
            sock, status, result = self.raw_request(b'{', lengths=[100])
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('timed out', result['error'])
        self.assertEqual(sock.recv(1), b'')


if __name__ == '__main__': unittest.main()
