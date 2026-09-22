"""Cross-test ownership contracts for transport emitted by retained threads."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent


class ThreadOwnershipDiagnosticsTests(unittest.TestCase):
    def test_worker_attributes_cross_test_transport_to_starting_test(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_thread_owner_fixture.py"
            path.write_text(
                textwrap.dedent(
                    f"""
                    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
                    import queue
                    import sys
                    import threading
                    import unittest
                    from urllib.request import urlopen

                    sys.path.insert(0, {str(HERE)!r})
                    from loopback_transport_audit import LoopbackTransportAudit

                    work = queue.Queue()
                    failures = queue.Queue()
                    completed = threading.Event()
                    retained_worker = None

                    class Handler(BaseHTTPRequestHandler):
                        def do_GET(self):
                            body = b"{{}}"
                            self.send_response(200)
                            self.send_header("Content-Length", str(len(body)))
                            self.end_headers()
                            self.wfile.write(body)

                        def log_message(self, *_args):
                            pass

                    def request_later():
                        try:
                            url = work.get(timeout=5)
                            with urlopen(url, timeout=2) as response:
                                response.read()
                        except BaseException as error:
                            failures.put(type(error).__name__ + ": " + str(error))
                        finally:
                            completed.set()

                    class OwnershipLeakFixture(unittest.TestCase):
                        def test_01_start_background_worker(self):
                            global retained_worker
                            retained_worker = threading.Thread(
                                target=request_later,
                                name="retained-owner-worker",
                                daemon=True,
                            )
                            retained_worker.start()

                        def test_02_observe_connection(self):
                            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                            server_thread = threading.Thread(
                                target=server.serve_forever,
                                name="ownership-fixture-server",
                                daemon=True,
                            )
                            server_thread.start()
                            try:
                                audit = LoopbackTransportAudit(
                                    host="127.0.0.1",
                                    port=server.server_port,
                                    max_calls=4,
                                    max_frames=16,
                                )
                                with audit:
                                    work.put(
                                        f"http://127.0.0.1:{{server.server_port}}/object_info"
                                    )
                                    self.assertTrue(completed.wait(5))
                                retained_worker.join(timeout=5)
                                self.assertFalse(retained_worker.is_alive())
                                if not failures.empty():
                                    self.fail(failures.get())

                                snapshot = audit.snapshot()
                                self.assertEqual(snapshot["observed"], 1)
                                self.assertEqual(len(snapshot["retained"]), 1)
                                call = snapshot["retained"][0]
                                active = (
                                    "test_thread_owner_fixture.OwnershipLeakFixture."
                                    "test_02_observe_connection"
                                )
                                owner = (
                                    "test_thread_owner_fixture.OwnershipLeakFixture."
                                    "test_01_start_background_worker"
                                )
                                self.assertEqual(call["active_test"], active)
                                origin = call["thread_origin"]
                                self.assertEqual(origin["owner_test"], owner)
                                self.assertEqual(origin["started_during_test"], owner)
                                self.assertEqual(origin["parent_thread"], "MainThread")
                                self.assertIn(
                                    "test_01_start_background_worker",
                                    [frame["function"] for frame in origin["start_stack"]],
                                )
                                print("THREAD ORIGIN CONTRACT PASSED", flush=True)
                            finally:
                                server.shutdown()
                                server.server_close()
                                server_thread.join(timeout=5)
                                self.assertFalse(server_thread.is_alive())
                    """
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-u",
                    str(worker),
                    "--start-dir",
                    directory,
                    "--pattern",
                    "test_thread_owner_fixture.py",
                    "--traceback-after",
                    "8",
                    "--shutdown-traceback-after",
                    "0.5",
                ],
                cwd=HERE.parent,
                capture_output=True,
                text=True,
                timeout=20,
            )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("THREAD ORIGIN CONTRACT PASSED", output)


if __name__ == "__main__":
    unittest.main()
