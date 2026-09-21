"""Unbuffered offline-suite worker with pre-timeout resource diagnostics.

The parent process owns the hard lifetime budget. This worker names every test as
it starts and arms a slightly earlier marker plus faulthandler dump so a hung
fixture leaves the current test ID and every Python thread stack in captured CI
output before the parent terminates it. It attributes thread starts and executor
task submissions to the active test, records active child processes and wraps
later atexit registrations so retained runtime work has bounded origin evidence.
"""
from __future__ import annotations

import argparse
import faulthandler
import multiprocessing
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from executor_work_observability import ExecutorWorkObserver  # noqa: E402
from runtime_observability import (  # noqa: E402
    AtexitCallbackObserver,
    ThreadOwnershipObserver,
    current_test,
    set_current_test,
)

# faulthandler walks every thread's frames from C without the GIL. The hosted
# Windows runner crashed the worker with an access violation (0xC0000005, run
# 35391373354) when the Python marker timer was still inside its own print as
# the C dump traversed it. Keep the two writers a real interval apart instead of
# a fraction of a deadline that is only milliseconds long in a focused fixture.
MARKER_SEPARATION_SECONDS = 0.25


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
        if not seconds > MARKER_SEPARATION_SECONDS:
            raise ValueError(
                f"traceback deadline must exceed the {MARKER_SEPARATION_SECONDS}-second "
                "marker separation"
            )
        self.seconds = seconds
        self.prefix = prefix
        self.stream = stream
        self.marker: threading.Timer | None = None

    def arm(self) -> None:
        if self.marker is not None:
            raise RuntimeError("lifetime diagnostics are already armed")
        # Leave enough separation that the current-test marker is written, flushed
        # and its timer thread finished before the C-level all-thread dump traverses
        # it. The START line remains the fallback if a test monopolizes the GIL and
        # the Python timer cannot run.
        marker_delay = max(
            0.0,
            self.seconds
            - max(
                MARKER_SEPARATION_SECONDS,
                min(1.0, self.seconds / 3.0),
            ),
        )
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


def retained_threads() -> list[threading.Thread]:
    """Non-daemon threads that will hold this interpreter open after main returns."""
    current = threading.current_thread()
    return [
        thread
        for thread in threading.enumerate()
        if thread is not current and thread.is_alive() and not thread.daemon
    ]


def retained_processes() -> list[multiprocessing.Process]:
    """Live direct children that multiprocessing finalization must handle."""
    return [
        process
        for process in multiprocessing.active_children()
        if process.is_alive()
    ]


def emit_retained_processes(
    processes: list[multiprocessing.Process],
    *,
    stream=sys.stderr,
    prefix: str = "LIFETIME SHUTDOWN",
) -> None:
    """Name non-thread shutdown blockers before the stack watchdog fires."""
    for process in processes:
        name = process.name.replace("\r", "\\r").replace("\n", "\\n")
        print(
            f"{prefix} RETAINED PROCESS: name={name} pid={process.pid} "
            f"daemon={process.daemon} exitcode={process.exitcode}",
            file=stream,
            flush=True,
        )


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
    # Install before discovery so threads, pooled tasks and module-level atexit
    # registrations created while importing tests are attributed, while importing
    # this worker itself remains side-effect free for focused contract tests.
    set_current_test("<discovery>")
    thread_observer = ThreadOwnershipObserver()
    thread_observer.install()
    work_observer = ExecutorWorkObserver()
    work_observer.install()
    atexit_observer = AtexitCallbackObserver()
    atexit_observer.install()
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
    # completed, and only while a resource can actually retain interpreter
    # shutdown. A live multiprocessing child is handled by Python's atexit
    # finalizer even when no non-daemon Python thread remains, so record its
    # identity before returning into that potentially blocking finalizer. Atexit
    # callbacks themselves emit their owner marker immediately before invocation.
    threads = retained_threads()
    processes = retained_processes()
    if not threads and not processes:
        print(
            "LIFETIME SHUTDOWN: no retained non-daemon thread or active child process",
            file=sys.stderr,
            flush=True,
        )
        return 0 if result.wasSuccessful() else 1
    emit_retained_processes(processes)
    shutdown_diagnostics = LifetimeDiagnostics(
        args.shutdown_traceback_after,
        prefix="LIFETIME SHUTDOWN",
    )
    shutdown_diagnostics.arm()
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
