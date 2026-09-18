"""Unbuffered offline-suite worker with pre-timeout test and thread diagnostics.

The parent process owns the hard lifetime budget. This worker names every test as
it starts and arms a slightly earlier marker plus faulthandler dump so a hung
fixture leaves the current test ID and every Python thread stack in captured CI
output before the parent terminates it.
"""
from __future__ import annotations

import argparse
import faulthandler
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_CURRENT_TEST = "<not started>"
_CURRENT_LOCK = threading.Lock()


def set_current_test(value: str) -> None:
    global _CURRENT_TEST
    with _CURRENT_LOCK:
        _CURRENT_TEST = value


def current_test() -> str:
    with _CURRENT_LOCK:
        return _CURRENT_TEST


def emit_current_test(stream=sys.stderr, prefix: str = "LIFETIME") -> None:
    print(
        f"{prefix} WATCHDOG CURRENT TEST: {current_test()}",
        file=stream,
        flush=True,
    )


class TrackingTextResult(unittest.TextTestResult):
    """Flush test boundaries so partial captured output identifies the blocker."""

    def startTest(self, test):
        identifier = test.id()
        self._active_identifier = identifier
        set_current_test(identifier)
        self.stream.writeln(f"START {identifier}")
        self.stream.flush()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        identifier = self._active_identifier
        self.stream.writeln(f"END {identifier}")
        self.stream.flush()
        set_current_test("<between tests>")


class LifetimeDiagnostics:
    def __init__(
        self,
        seconds: float,
        *,
        prefix: str = "LIFETIME",
        stream=sys.stderr,
    ):
        if not seconds > 0:
            raise ValueError("traceback deadline must be positive")
        self.seconds = seconds
        self.prefix = prefix
        self.stream = stream
        self.marker: threading.Timer | None = None

    def arm(self) -> None:
        if self.marker is not None:
            raise RuntimeError("lifetime diagnostics are already armed")
        # Leave enough separation that the current-test marker normally appears
        # immediately before the C-level all-thread dump. The START line remains
        # the fallback if a test monopolizes the GIL and the Python timer cannot run.
        marker_delay = max(0.0, self.seconds - min(1.0, self.seconds / 3.0))
        self.marker = threading.Timer(
            marker_delay,
            emit_current_test,
            (self.stream, self.prefix),
        )
        self.marker.daemon = True
        self.marker.start()
        faulthandler.dump_traceback_later(
            self.seconds,
            repeat=False,
            file=self.stream,
            exit=False,
        )

    def cancel(self) -> None:
        """Cancel this phase before another faulthandler deadline is armed."""
        faulthandler.cancel_dump_traceback_later()
        marker = self.marker
        self.marker = None
        if marker is not None:
            marker.cancel()
            marker.join(timeout=1)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run the offline suite with lifetime diagnostics."
    )
    parser.add_argument("--start-dir", default=str(ROOT / "tests"))
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--traceback-after", type=float, required=True)
    parser.add_argument("--shutdown-traceback-after", type=float, required=True)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    start_dir = Path(args.start_dir).resolve()
    suite = unittest.defaultTestLoader.discover(str(start_dir), pattern=args.pattern)
    diagnostics = LifetimeDiagnostics(args.traceback_after)
    diagnostics.arm()
    try:
        result = unittest.TextTestRunner(
            stream=sys.stderr,
            verbosity=1,
            resultclass=TrackingTextResult,
        ).run(suite)
    finally:
        diagnostics.cancel()

    set_current_test("<suite complete>")
    disposition = "success" if result.wasSuccessful() else "failure"
    print(
        f"LIFETIME SUITE COMPLETE: {disposition}",
        file=sys.stderr,
        flush=True,
    )

    # Arm a fresh short deadline only after discovery and every test have
    # completed. Do not cancel it: if interpreter shutdown waits for a leaked
    # non-daemon thread, this marker and all-thread dump are the evidence.
    shutdown_diagnostics = LifetimeDiagnostics(
        args.shutdown_traceback_after,
        prefix="LIFETIME SHUTDOWN",
    )
    shutdown_diagnostics.arm()
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
