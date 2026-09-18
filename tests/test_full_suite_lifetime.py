from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
SUITE_COMPLETE = "LIFETIME SUITE COMPLETE:"
SHUTDOWN_WATCHDOG = "LIFETIME SHUTDOWN WATCHDOG CURRENT TEST:"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrapper = load("lifetime_wrapper", HERE / "check_full_suite_lifetime.py")


class ProcessCapture:
    """Drain a child continuously and retain each byte exactly once."""

    def __init__(self, process):
        self.process = process
        self.started_at = time.monotonic()
        self._condition = threading.Condition()
        self._parts = []
        self._closed = 0
        self._threads = []
        for stream in (process.stdout, process.stderr):
            thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _read(self, stream):
        try:
            for line in iter(stream.readline, ""):
                with self._condition:
                    self._parts.append(line)
                    self._condition.notify_all()
        finally:
            stream.close()
            with self._condition:
                self._closed += 1
                self._condition.notify_all()

    def output(self):
        with self._condition:
            return "".join(self._parts)

    def wait_for(self, marker, timeout):
        deadline = time.monotonic() + timeout
        with self._condition:
            while marker not in "".join(self._parts):
                if self.process.poll() is not None and self._closed == 2:
                    return False
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(min(remaining, 0.05))
            return True

    def reap(self):
        if self.process.poll() is None:
            self.process.kill()
        returncode = self.process.wait(timeout=5)
        for thread in self._threads:
            thread.join(timeout=5)
            if thread.is_alive():
                raise AssertionError("child output reader did not terminate")
        return returncode, self.output()


def observe_shutdown(
    capture,
    *,
    startup_timeout,
    observation_timeout,
    hard_timeout,
    evidence=(SHUTDOWN_WATCHDOG, "Thread "),
):
    """Wait for suite completion, then start a distinct bounded shutdown window."""
    hard_deadline = capture.started_at + hard_timeout

    def remaining(requested, phase):
        value = hard_deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError(f"hard lifetime budget expired during {phase}")
        return min(requested, value)

    if not capture.wait_for(
        SUITE_COMPLETE,
        remaining(startup_timeout, "startup/test completion"),
    ):
        output = capture.output()
        returncode = capture.process.poll()
        if returncode is not None:
            raise RuntimeError(
                f"worker exited {returncode} before suite completion:\n{output}"
            )
        raise TimeoutError(
            "suite completion was not observed within the startup/test budget:\n"
            + output
        )

    completed_at = time.monotonic()
    for marker in evidence:
        if capture.wait_for(
            marker,
            remaining(observation_timeout, "shutdown observation"),
        ):
            continue
        output = capture.output()
        returncode = capture.process.poll()
        if returncode is not None:
            raise RuntimeError(
                f"worker exited {returncode} before shutdown watchdog evidence "
                f"{marker!r}:\n{output}"
            )
        raise TimeoutError(
            f"shutdown watchdog evidence {marker!r} was not observed:\n{output}"
        )

    return {
        "startup_seconds": completed_at - capture.started_at,
        "shutdown_seconds": time.monotonic() - completed_at,
        "output": capture.output(),
    }


class LifetimeDiagnosticsTests(unittest.TestCase):
    def test_wrapper_uses_unbuffered_diagnostic_worker(self):
        command = wrapper.suite_command(
            traceback_after=12.5,
            shutdown_traceback_after=0.75,
        )
        self.assertIn("-u", command)
        self.assertIn(str(HERE / "full_suite_lifetime_worker.py"), command)
        traceback_index = command.index("--traceback-after")
        shutdown_index = command.index("--shutdown-traceback-after")
        self.assertEqual(command[traceback_index + 1], "12.5")
        self.assertEqual(command[shutdown_index + 1], "0.75")

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
                    "--shutdown-traceback-after",
                    "0.15",
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
                    import time
                    import unittest

                    time.sleep(0.45)
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
                    "4",
                    "--shutdown-traceback-after",
                    "0.15",
                ],
                cwd=HERE.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            capture = ProcessCapture(process)
            try:
                observation = observe_shutdown(
                    capture,
                    startup_timeout=3,
                    observation_timeout=1,
                    hard_timeout=5,
                )
                self.assertIsNone(process.poll(), observation["output"])
            finally:
                returncode, output = capture.reap()

        self.assertIsNotNone(returncode)
        self.assertGreaterEqual(observation["startup_seconds"], 0.35)
        self.assertLess(observation["shutdown_seconds"], 1.0)
        self.assertIn("END test_leak.LeaksNonDaemon.test_returns_with_live_thread", output)
        self.assertIn(SUITE_COMPLETE, output)
        self.assertIn(SHUTDOWN_WATCHDOG, output)
        self.assertIn("Thread ", output)

    def test_shutdown_probe_reports_absent_watchdog_and_reaps_child(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                (
                    "import sys,time; "
                    f"print({SUITE_COMPLETE!r} + ' success', file=sys.stderr, flush=True); "
                    "time.sleep(5)"
                ),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        capture = ProcessCapture(process)
        try:
            with self.assertRaisesRegex(TimeoutError, "shutdown watchdog evidence"):
                observe_shutdown(
                    capture,
                    startup_timeout=1,
                    observation_timeout=0.15,
                    hard_timeout=1,
                )
        finally:
            returncode, output = capture.reap()
        self.assertIsNotNone(returncode)
        self.assertIn(SUITE_COMPLETE, output)

    def test_shutdown_probe_reports_unexpected_child_exit(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                (
                    "import sys; "
                    f"print({SUITE_COMPLETE!r} + ' success', file=sys.stderr, flush=True); "
                    "raise SystemExit(7)"
                ),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        capture = ProcessCapture(process)
        try:
            with self.assertRaisesRegex(RuntimeError, "exited 7"):
                observe_shutdown(
                    capture,
                    startup_timeout=1,
                    observation_timeout=1,
                    hard_timeout=2,
                )
        finally:
            returncode, output = capture.reap()
        self.assertEqual(returncode, 7, output)

    def test_shutdown_probe_keeps_a_hard_total_budget(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                "import time; time.sleep(5)",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        capture = ProcessCapture(process)
        try:
            with self.assertRaisesRegex(TimeoutError, "hard lifetime budget"):
                observe_shutdown(
                    capture,
                    startup_timeout=5,
                    observation_timeout=5,
                    hard_timeout=0.15,
                )
        finally:
            returncode, output = capture.reap()
        self.assertIsNotNone(returncode)
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
