"""HTTP fixture teardown owns handlers, including timed-out SQLite writers."""
from http.server import BaseHTTPRequestHandler
import contextlib
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from http_test_server import ThreadingHTTPServer


class HTTPTestServerTests(unittest.TestCase):
    def test_partial_request_has_a_socket_timeout_and_does_not_hold_teardown(self):
        entered=threading.Event(); timeouts=[]
        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup(); timeouts.append(self.connection.gettimeout()); entered.set()
            def log_message(self, *args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler); server.request_timeout=.1
        listener=threading.Thread(target=server.serve_forever,daemon=True); listener.start()
        try:
            with socket.create_connection(server.server_address,timeout=2) as client:
                client.sendall(b'GET /'); self.assertTrue(entered.wait(5))
                self.assertEqual(timeouts,[.1])
                server.shutdown(); server.server_close()
                self.assertEqual(client.recv(1),b'')
        finally:server.shutdown(); server.server_close(); listener.join(2)

    def test_stuck_handler_teardown_is_bounded_and_names_thread_and_socket(self):
        entered, release = threading.Event(), threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass
            def do_GET(self):entered.set(); release.wait(10)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler); server.close_timeout=.05
        listener=threading.Thread(target=server.serve_forever,daemon=True); listener.start()
        try:
            with socket.create_connection(server.server_address,timeout=2) as client:
                client.sendall(b'GET / HTTP/1.0\r\n\r\n'); self.assertTrue(entered.wait(5))
                server.shutdown()
                with tempfile.TemporaryFile(mode='w+') as log,contextlib.redirect_stderr(log):
                    with self.assertRaisesRegex(RuntimeError,'retained 1 handler'):server.server_close()
                    log.seek(0); diagnostic=log.read()
                self.assertIn('HTTP FIXTURE TEARDOWN TIMEOUT',diagnostic)
                self.assertIn(f'http-fixture-{server.server_port}',diagnostic)
                self.assertIn('socket',diagnostic); self.assertIn('do_GET',diagnostic)
        finally:
            release.set(); server.close_timeout=5
            server.shutdown(); server.server_close(); listener.join(2)

    def test_close_waits_for_timed_out_handler_to_release_database(self):
        entered, release, finished, closed = (threading.Event() for _ in range(4))
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder)/'assets.sqlite3'
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def do_GET(self):
                    db=sqlite3.connect(database)
                    try:
                        db.execute('CREATE TABLE fixture (value)'); entered.set(); release.wait(10)
                    finally: db.close(); finished.set()
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            listener=threading.Thread(target=server.serve_forever,daemon=True); listener.start()
            closer=None
            try:
                with socket.create_connection(server.server_address,timeout=2) as client:
                    client.sendall(b'GET / HTTP/1.0\r\n\r\n'); self.assertTrue(entered.wait(5))
                    client.settimeout(.05)
                    with self.assertRaises(TimeoutError):client.recv(1)
                server.shutdown(); listener.join(2)
                def close():
                    try:server.server_close()
                    finally:closed.set()
                closer=threading.Thread(target=close,daemon=True); closer.start()
                self.assertFalse(closed.wait(.1),'server_close returned with a SQLite handler still running')
                release.set(); self.assertTrue(closed.wait(5)); self.assertTrue(finished.is_set())
                database.unlink()  # Windows refuses this while the handler still owns its connection.
            finally:
                release.set(); server.shutdown(); server.server_close(); listener.join(2)
                if closer:closer.join(5)
                self.assertTrue(finished.wait(5))
