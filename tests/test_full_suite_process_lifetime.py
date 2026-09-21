"""Shutdown-watchdog regression for a leaked multiprocessing child."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from test_full_suite_lifetime import (  # noqa: E402
    ProcessCapture,
    SHUTDOWN_WATCHDOG,
    SUITE_COMPLETE,
    observe_shutdown,
)


class ProcessLifetimeDiagnosticsTests(unittest.TestCase):
    def test_worker_names_process_and_arms_shutdown_watchdog(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_process_leak.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import multiprocessing
                    import time
                    import unittest

                    def wait_for_parent():
                        parent = multiprocessing.parent_process()
                        deadline = time.monotonic() + 10
                        while parent is not None and parent.is_alive() and time.monotonic() < deadline:
                            time.sleep(0.05)

                    class LeaksNonDaemonProcess(unittest.TestCase):
                        def test_returns_with_live_process(self):
                            context = multiprocessing.get_context('spawn')
                            process = context.Process(target=wait_for_parent, name='leaked-process')
                            process.daemon = False
                            process.start()
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
                    "test_process_leak.py",
                    "--traceback-after",
                    "4",
                    "--shutdown-traceback-after",
                    "0.4",
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
                    startup_timeout=4,
                    observation_timeout=1.5,
                    hard_timeout=7,
                    evidence=(
                        "LIFETIME SHUTDOWN RETAINED PROCESS:",
                        "name=leaked-process",
                        SHUTDOWN_WATCHDOG,
                        "Thread ",
                    ),
                )
                self.assertIsNone(process.poll(), observation["output"])
            finally:
                returncode, output = capture.reap()

        self.assertIsNotNone(returncode)
        self.assertIn(
            "END test_process_leak.LeaksNonDaemonProcess.test_returns_with_live_process",
            output,
        )
        self.assertIn(SUITE_COMPLETE, output)
        self.assertIn("LIFETIME SHUTDOWN RETAINED PROCESS:", output)
        self.assertIn("name=leaked-process", output)
        self.assertIn(SHUTDOWN_WATCHDOG, output)
        self.assertIn("Thread ", output)


if __name__ == "__main__":
    unittest.main()
