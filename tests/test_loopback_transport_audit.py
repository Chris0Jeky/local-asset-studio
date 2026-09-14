"""Bounded attribution for unexpected connections to loopback test fixtures."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from urllib.request import urlopen

from loopback_transport_audit import LoopbackTransportAudit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class LoopbackTransportAuditTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())

    def request(self, suffix):
        with urlopen(f"http://127.0.0.1:{self.server.server_port}/{suffix}", timeout=2) as response:
            response.read()

    def test_records_target_thread_and_python_caller_with_bounded_retention(self):
        audit = LoopbackTransportAudit(
            host="127.0.0.1",
            port=self.server.server_port,
            max_calls=1,
            max_frames=10,
        )
        with audit:
            self.request("first")
            self.request("second")

        snapshot = audit.snapshot()
        self.assertEqual(snapshot["observed"], 2)
        self.assertEqual(len(snapshot["retained"]), 1)
        self.assertTrue(snapshot["truncated"])
        call = snapshot["retained"][0]
        self.assertEqual(call["host"], "127.0.0.1")
        self.assertEqual(call["port"], self.server.server_port)
        self.assertEqual(call["thread"], "MainThread")
        self.assertIn(
            "test_records_target_thread_and_python_caller_with_bounded_retention",
            [frame["function"] for frame in call["stack"]],
        )
        diagnostic = audit.describe([("GET", "/first"), ("GET", "/second")])
        parsed = json.loads(diagnostic)
        self.assertEqual(parsed["routes"], [["GET", "/first"], ["GET", "/second"]])
        self.assertEqual(parsed["transport"]["observed"], 2)


if __name__ == "__main__":
    unittest.main()
