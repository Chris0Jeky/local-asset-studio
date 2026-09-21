"""Finalization diagnostics for retained ``atexit`` callbacks."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from test_full_suite_lifetime import (  # noqa: E402
    ProcessCapture,
    SUITE_COMPLETE,
    observe_shutdown,
)

ATEXIT_ENTER = "LIFETIME ATEXIT ENTER:"
ATEXIT_EXIT = "LIFETIME ATEXIT EXIT:"


class _FinishedProcess:
    def poll(self):
        return 0

    def wait(self, timeout):
        return 0


class _StuckReader:
    def join(self, timeout):
        pass

    def is_alive(self):
        return True


class AtexitLifetimeDiagnosticsTests(unittest.TestCase):
    def test_worker_names_blocking_atexit_callback_before_parent_timeout(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_atexit_block.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import atexit
                    import threading
                    import unittest

                    release = threading.Event()

                    def block_forever(secret):
                        release.wait()

                    atexit.register(block_forever, "callback-argument-must-not-be-retained")

                    class PassesBeforeFinalization(unittest.TestCase):
                        def test_passes(self):
                            self.assertTrue(True)
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
                    "test_atexit_block.py",
                    "--traceback-after",
                    "8",
                    "--shutdown-traceback-after",
                    "0.5",
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
                    startup_timeout=8,
                    observation_timeout=3,
                    hard_timeout=12,
                    evidence=(
                        ATEXIT_ENTER,
                        '"callback":"test_atexit_block.block_forever"',
                        '"file":"test_atexit_block.py"',
                    ),
                )
                self.assertIsNone(process.poll(), observation["output"])
            finally:
                returncode, output = capture.reap()

        self.assertIsNotNone(returncode)
        self.assertIn(SUITE_COMPLETE, output)
        self.assertIn(ATEXIT_ENTER, output)
        self.assertIn('"callback":"test_atexit_block.block_forever"', output)
        self.assertIn('"registered_thread":"MainThread"', output)
        self.assertNotIn("callback-argument-must-not-be-retained", output)
        self.assertNotIn(
            f'{ATEXIT_EXIT} {{"callback":"test_atexit_block.block_forever"',
            output,
        )

    def test_worker_marks_completed_callbacks_and_preserves_unregister(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_atexit_clean.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import atexit
                    import unittest

                    def completed_callback(secret):
                        pass

                    def removed_callback():
                        raise AssertionError("unregistered callback ran")

                    returned = atexit.register(
                        completed_callback,
                        "completed-callback-argument-must-not-be-retained",
                    )
                    if returned is not completed_callback:
                        raise AssertionError("atexit.register return identity changed")
                    atexit.register(removed_callback)
                    atexit.unregister(removed_callback)

                    class PassesBeforeFinalization(unittest.TestCase):
                        def test_passes(self):
                            self.assertTrue(True)
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
                    "test_atexit_clean.py",
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
        self.assertIn(SUITE_COMPLETE, output)
        self.assertIn(ATEXIT_ENTER, output)
        self.assertIn(ATEXIT_EXIT, output)
        self.assertIn('"callback":"test_atexit_clean.completed_callback"', output)
        self.assertIn('"outcome":"returned"', output)
        self.assertIn('"file":"test_atexit_clean.py"', output)
        self.assertNotIn("completed-callback-argument-must-not-be-retained", output)
        self.assertNotIn("removed_callback", output)

    def test_process_capture_cleanup_does_not_replace_primary_failure(self):
        capture = object.__new__(ProcessCapture)
        capture.process = _FinishedProcess()
        capture._condition = threading.Condition()
        capture._parts = []
        capture._closed = 2
        capture._threads = [_StuckReader()]

        with self.assertRaisesRegex(ValueError, "primary failure") as raised:
            try:
                raise ValueError("primary failure")
            finally:
                capture.reap()

        self.assertIn(
            "child output reader did not terminate",
            "\n".join(getattr(raised.exception, "__notes__", [])),
        )


if __name__ == "__main__":
    unittest.main()
