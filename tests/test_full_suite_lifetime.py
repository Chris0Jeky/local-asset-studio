from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrapper = load("lifetime_wrapper", HERE / "check_full_suite_lifetime.py")


class LifetimeDiagnosticsTests(unittest.TestCase):
    def test_wrapper_uses_unbuffered_diagnostic_worker(self):
        command = wrapper.suite_command(traceback_after=12.5)
        self.assertIn("-u", command)
        self.assertIn(str(HERE / "full_suite_lifetime_worker.py"), command)
        self.assertEqual(command[-2:], ["--traceback-after", "12.5"])

    def test_worker_names_current_test_and_dumps_threads_before_parent_budget(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_hang.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import time
                    import unittest

                    from studio_workflow.addressable_figures import split_figures

                    class HangsBriefly(unittest.TestCase):
                        def test_wait(self):
                            self.id = "fixture-status"
                            self.assertTrue(callable(split_figures))
                            time.sleep(0.15)
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
                    "test_hang.py",
                    "--traceback-after",
                    "0.03",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("START test_hang.HangsBriefly.test_wait", output)
        self.assertIn(
            "LIFETIME WATCHDOG CURRENT TEST: test_hang.HangsBriefly.test_wait",
            output,
        )
        self.assertIn("Thread ", output)
        self.assertIn("END test_hang.HangsBriefly.test_wait", output)

    def test_worker_keeps_shutdown_watchdog_armed_for_leaked_thread(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_leak.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import threading
                    import unittest

                    leaked = threading.Event()

                    class LeaksNonDaemon(unittest.TestCase):
                        def test_returns_with_live_thread(self):
                            thread = threading.Thread(target=leaked.wait, name="leaked-non-daemon")
                            thread.daemon = False
                            thread.start()
                    """
                ),
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    str(worker),
                    "--start-dir",
                    directory,
                    "--pattern",
                    "test_leak.py",
                    "--traceback-after",
                    "0.15",
                ],
                cwd=HERE.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=0.8)
                self.fail(f"worker exited despite the leaked non-daemon thread:\n{stdout}\n{stderr}")
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
                process.kill()
                tail_stdout, tail_stderr = process.communicate(timeout=5)
                def text(value):
                    return value.decode(errors="replace") if isinstance(value, bytes) else value
                output = text(stdout) + text(stderr) + text(tail_stdout) + text(tail_stderr)
        self.assertIn("END test_leak.LeaksNonDaemon.test_returns_with_live_thread", output)
        self.assertIn("LIFETIME WATCHDOG CURRENT TEST:", output)
        self.assertIn("Thread ", output)


if __name__ == "__main__":
    unittest.main()
