"""Cross-test ownership contracts for transport emitted by pooled work."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent


class ExecutorWorkOwnershipDiagnosticsTests(unittest.TestCase):
    def test_worker_attributes_reused_pool_transport_to_submitting_test(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_executor_owner_fixture.py"
            path.write_text(
                textwrap.dedent(
                    f"""
                    from concurrent.futures import ThreadPoolExecutor
                    from http.client import HTTPConnection
                    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
                    import sys
                    import threading
                    import unittest

                    sys.path.insert(0, {str(HERE)!r})
                    from loopback_transport_audit import LoopbackTransportAudit

                    executor = None

                    class Handler(BaseHTTPRequestHandler):
                        def do_GET(self):
                            body = b"{{}}"
                            self.send_response(200)
                            self.send_header("Content-Length", str(len(body)))
                            self.end_headers()
                            self.wfile.write(body)

                        def log_message(self, *_args):
                            pass

                    def request_object_info(port):
                        connection = HTTPConnection("127.0.0.1", port, timeout=2)
                        try:
                            connection.request("GET", "/object_info")
                            response = connection.getresponse()
                            response.read()
                            return response.status
                        finally:
                            connection.close()

                    class PooledOwnershipFixture(unittest.TestCase):
                        @classmethod
                        def tearDownClass(cls):
                            global executor
                            if executor is not None:
                                executor.shutdown(wait=True, cancel_futures=True)
                                executor = None

                        def test_01_create_and_prime_pool(self):
                            global executor
                            executor = ThreadPoolExecutor(
                                max_workers=1,
                                thread_name_prefix="retained-owner-pool",
                            )
                            worker_name = executor.submit(
                                lambda: threading.current_thread().name
                            ).result(timeout=5)
                            self.assertTrue(worker_name.startswith("retained-owner-pool"))

                        def test_02_submit_transport_to_reused_worker(self):
                            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                            server_thread = threading.Thread(
                                target=server.serve_forever,
                                name="executor-ownership-fixture-server",
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
                                    status = executor.submit(
                                        request_object_info,
                                        server.server_port,
                                    ).result(timeout=5)
                                self.assertEqual(status, 200)

                                snapshot = audit.snapshot()
                                self.assertEqual(snapshot["observed"], 1)
                                self.assertEqual(len(snapshot["retained"]), 1)
                                call = snapshot["retained"][0]
                                creator = (
                                    "test_executor_owner_fixture.PooledOwnershipFixture."
                                    "test_01_create_and_prime_pool"
                                )
                                submitter = (
                                    "test_executor_owner_fixture.PooledOwnershipFixture."
                                    "test_02_submit_transport_to_reused_worker"
                                )
                                self.assertEqual(call["active_test"], submitter)
                                thread_origin = call["thread_origin"]
                                self.assertEqual(thread_origin["owner_test"], creator)
                                self.assertEqual(
                                    thread_origin["started_during_test"],
                                    creator,
                                )

                                work_origin = call.get("work_origin")
                                self.assertIsNotNone(work_origin, call)
                                self.assertEqual(work_origin["status"], "observed")
                                self.assertEqual(work_origin["owner_test"], submitter)
                                self.assertEqual(
                                    work_origin["submitted_during_test"],
                                    submitter,
                                )
                                self.assertEqual(
                                    work_origin["submitter_thread"],
                                    "MainThread",
                                )
                                self.assertIn(
                                    "test_02_submit_transport_to_reused_worker",
                                    [
                                        frame["function"]
                                        for frame in work_origin["submit_stack"]
                                    ],
                                )
                                print("EXECUTOR WORK ORIGIN CONTRACT PASSED", flush=True)
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
                    "test_executor_owner_fixture.py",
                    "--traceback-after",
                    "10",
                    "--shutdown-traceback-after",
                    "1",
                ],
                cwd=HERE.parent,
                capture_output=True,
                text=True,
                timeout=30,
            )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("EXECUTOR WORK ORIGIN CONTRACT PASSED", output)


if __name__ == "__main__":
    unittest.main()
