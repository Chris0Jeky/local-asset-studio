"""Proves the early-refusal test transport sends only the requested loopback payload."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from http_refusal_transport import atomic_json_post


class AtomicRefusalTransportTests(unittest.TestCase):
    def test_sends_exact_nonempty_payload_and_decodes_refusal(self):
        seen = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                size = int(self.headers['Content-Length'])
                seen.update(path=self.path, headers=dict(self.headers), body=self.rfile.read(size), client=self.client_address[0])
                reply = json.dumps({'error': 'refused'}).encode()
                self.send_response(403); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(reply)))
                self.end_headers(); self.wfile.write(reply)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            body = b'{"keep":"original"}'
            self.assertEqual(atomic_json_post(server.server_port, '/refuse', body, host='evil.invalid', origin='https://evil.invalid'), (403, {'error': 'refused'}))
            status, raw, pairs = atomic_json_post(server.server_port, '/refuse', body, host='evil.invalid', origin='https://evil.invalid', response_details=True)
            self.assertEqual((status, json.loads(raw)), (403, {'error': 'refused'})); self.assertIn(('Content-Type', 'application/json'), pairs)
        finally:
            server.shutdown(); server.server_close(); worker.join(2)
        self.assertEqual(seen['client'], '127.0.0.1')
        self.assertEqual(seen['path'], '/refuse'); self.assertEqual(seen['body'], body)
        self.assertEqual(seen['headers'], {'Host': 'evil.invalid', 'Origin': 'https://evil.invalid', 'Content-Type': 'application/json', 'Content-Length': str(len(body)), 'Connection': 'close'})
