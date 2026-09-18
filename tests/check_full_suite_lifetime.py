"""Run the complete offline suite in a fresh process and reject leaked resources.

The subprocess boundary makes interpreter-shutdown warnings observable. A single
tracemalloc frame retains the allocation line without multiplying the full suite's
runtime. The child emits unbuffered per-test boundaries and an all-thread dump
before this parent enforces its hard lifetime budget.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
LIFETIME_BUDGET_SECONDS = 600
TRACEBACK_AFTER_SECONDS = 570
SHUTDOWN_TRACEBACK_AFTER_SECONDS = 2.0


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
    command = suite_command()
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=LIFETIME_BUDGET_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        output = printable(exc.stdout) + printable(exc.stderr)
        print(output, end="" if output.endswith("\n") else "\n")
        elapsed = time.monotonic() - started
        print(
            f"offline suite exceeded the {LIFETIME_BUDGET_SECONDS}-second lifetime budget "
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
