"""Run the complete offline suite in a fresh process and reject leaked resources.

The subprocess boundary makes interpreter-shutdown warnings observable. A single
tracemalloc frame retains the allocation line without multiplying the full suite's
runtime. The child emits unbuffered per-test boundaries and an all-thread dump
before this parent enforces its hard lifetime budget.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
LIFETIME_BUDGET_SECONDS = 600
TRACEBACK_MARGIN_SECONDS = 30
TRACEBACK_AFTER_SECONDS = LIFETIME_BUDGET_SECONDS - TRACEBACK_MARGIN_SECONDS
# A slower host raises the hard budget through the environment instead of
# lowering the default guard for every platform. Measured evidence for the
# hosted Windows runner: run 35339291681 reached test_review_desk at 570 s and
# was still running ordinary tests when the 600-second budget expired, with no
# hung test, no leaked thread and 2,236 of 2,968 tests started.
BUDGET_VARIABLE = "FULL_SUITE_LIFETIME_BUDGET_SECONDS"
# The worker refuses a deadline too short to keep its current-test marker clear
# of the C-level all-thread dump, so the parent refuses a budget that could only
# produce one.
MIN_TRACEBACK_DEADLINE_SECONDS = 1.0
# A full Windows interpreter can need several seconds to release thousands of
# test-owned modules, streams and executor objects after unittest completes.
# Keep this well inside the parent's hard budget while avoiding a false leak
# report during ordinary teardown. Focused leaked-thread tests pass 0.15 seconds.
SHUTDOWN_TRACEBACK_AFTER_SECONDS = 15.0


def lifetime_budget(environ=None) -> float:
    """Return the hard whole-suite budget, overridden only by an explicit value."""
    raw = (os.environ if environ is None else environ).get(BUDGET_VARIABLE, "").strip()
    if not raw:
        return float(LIFETIME_BUDGET_SECONDS)
    try:
        budget = float(raw)
    except ValueError:
        raise ValueError(f"{BUDGET_VARIABLE} must be a number of seconds, not {raw!r}") from None
    # An unusable deadline is as bad as a non-positive one: the worker refuses any
    # deadline that cannot hold the marker clear of the all-thread dump, so require
    # a finite budget that leaves the margin plus that separation.
    if not math.isfinite(budget) or budget <= TRACEBACK_MARGIN_SECONDS + MIN_TRACEBACK_DEADLINE_SECONDS:
        raise ValueError(
            f"{BUDGET_VARIABLE} must be a finite number exceeding the "
            f"{TRACEBACK_MARGIN_SECONDS}-second diagnostic margin by at least "
            f"{MIN_TRACEBACK_DEADLINE_SECONDS} seconds, not {raw!r}"
        )
    return budget


def traceback_deadline(budget: float) -> float:
    """Dump every thread stack while the child is still alive under `budget`."""
    return budget - TRACEBACK_MARGIN_SECONDS


def child_environment(environ=None) -> dict:
    """The parent owns the budget; the child is told its deadlines on argv.

    Leaving the override in the child's environment would reach the offline
    suite itself, where `test_full_suite_lifetime_guard` asserts the default
    600-second wording.
    """
    child = dict(os.environ if environ is None else environ)
    child.pop(BUDGET_VARIABLE, None)
    return child


def printable(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def suite_command(
    traceback_after: float = TRACEBACK_AFTER_SECONDS,
    shutdown_traceback_after: float = SHUTDOWN_TRACEBACK_AFTER_SECONDS,
) -> list[str]:
    return [
        sys.executable,
        "-u",
        "-X",
        "tracemalloc=1",
        "-W",
        "always::ResourceWarning",
        str(ROOT / "tests" / "full_suite_lifetime_worker.py"),
        "--start-dir",
        str(ROOT / "tests"),
        "--traceback-after",
        str(traceback_after),
        "--shutdown-traceback-after",
        str(shutdown_traceback_after),
    ]


def main() -> int:
    budget = lifetime_budget()
    command = suite_command(traceback_after=traceback_deadline(budget))
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=child_environment(),
            capture_output=True,
            text=True,
            timeout=budget,
        )
    except subprocess.TimeoutExpired as exc:
        output = printable(exc.stdout) + printable(exc.stderr)
        print(output, end="" if output.endswith("\n") else "\n")
        elapsed = time.monotonic() - started
        print(
            f"offline suite exceeded the {budget:g}-second lifetime budget "
            f"after {elapsed:.2f} seconds; the last START marker and lifetime watchdog dump "
            "identify the blocked test and threads",
            file=sys.stderr,
        )
        return 124
    output = result.stdout + result.stderr
    print(output, end="" if output.endswith("\n") else "\n")
    if result.returncode:
        print(f"offline suite exited {result.returncode}", file=sys.stderr)
        return result.returncode
    if "ResourceWarning" in output:
        print(
            "offline suite emitted ResourceWarning; inspect the allocation line above",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
