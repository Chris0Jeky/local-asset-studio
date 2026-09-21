"""Adversarial contracts for stable ``atexit`` callback ownership."""
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
    SUITE_COMPLETE,
    observe_shutdown,
)

ATEXIT_ENTER = "LIFETIME ATEXIT ENTER:"


class AtexitIdentitySnapshotTests(unittest.TestCase):
    def test_worker_emits_registered_owner_before_callback_metadata_can_block(self):
        worker = HERE / "full_suite_lifetime_worker.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_atexit_identity_block.py"
            path.write_text(
                textwrap.dedent(
                    """
                    import atexit
                    import threading
                    import unittest

                    release = threading.Event()
                    metadata_may_block = False

                    class BlockingIdentityCallback:
                        def __getattribute__(self, name):
                            if name in {"__module__", "__qualname__", "__name__"}:
                                if globals()["metadata_may_block"]:
                                    release.wait()
                            return object.__getattribute__(self, name)

                        def __call__(self):
                            release.wait()

                    callback = BlockingIdentityCallback()
                    atexit.register(callback)
                    metadata_may_block = True

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
                    "test_atexit_identity_block.py",
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
                        '"callback":"test_atexit_identity_block.BlockingIdentityCallback"',
                        '"file":"test_atexit_identity_block.py"',
                    ),
                )
                self.assertIsNone(process.poll(), observation["output"])
            finally:
                returncode, output = capture.reap()

        self.assertIsNotNone(returncode)
        self.assertIn(SUITE_COMPLETE, output)
        self.assertIn(ATEXIT_ENTER, output)
        self.assertIn(
            '"callback":"test_atexit_identity_block.BlockingIdentityCallback"',
            output,
        )
        self.assertIn('"file":"test_atexit_identity_block.py"', output)


if __name__ == "__main__":
    unittest.main()
