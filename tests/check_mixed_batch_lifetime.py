"""Run the mixed-batch HTTP module in fresh interpreters and fail on socket leaks.

This is a Windows diagnostic gate for #227, not part of unittest discovery.  Fresh
interpreters make interpreter-shutdown ResourceWarnings visible, while tracemalloc
retains the allocation site if the intermittent loopback leak returns.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS = 2
TIMEOUT_SECONDS = 45
DIAGNOSTIC_TAIL_CHARS = 16_384


def printable_tail(value: str | bytes | None) -> str:
    if value is None:
        return ""
    output = value.decode(errors="replace") if isinstance(value, bytes) else value
    if len(output) > DIAGNOSTIC_TAIL_CHARS:
        return "[earlier output truncated]\n" + output[-DIAGNOSTIC_TAIL_CHARS:]
    return output


def run_once(attempt: int) -> None:
    environment = os.environ.copy()
    environment["PYTHONTRACEMALLOC"] = "25"
    command = [
        sys.executable,
        "-W",
        "always::ResourceWarning",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_mixed_batch_http.py",
        "-v",
    ]
    print(f"--- mixed-batch lifetime attempt {attempt}/{ATTEMPTS} ---", flush=True)
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        # subprocess.run kills and waits for its child before raising here.
        elapsed = time.monotonic() - started
        for label, value in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            output = printable_tail(value)
            print(f"--- child {label} (tail, at most {DIAGNOSTIC_TAIL_CHARS} characters) ---")
            print(output, end="" if output.endswith("\n") else "\n")
        print(
            f"mixed-batch lifetime attempt {attempt}/{ATTEMPTS} exceeded the "
            f"{TIMEOUT_SECONDS}-second lifetime budget ({elapsed:.3f}s elapsed)",
            file=sys.stderr,
        )
        raise SystemExit(124) from None
    output = result.stdout + result.stderr
    print(output, end="" if output.endswith("\n") else "\n")
    if result.returncode:
        raise SystemExit(
            f"mixed-batch lifetime attempt {attempt} exited {result.returncode}"
        )
    if "ResourceWarning" in output:
        raise SystemExit(
            f"mixed-batch lifetime attempt {attempt} emitted ResourceWarning; "
            "inspect the tracemalloc allocation traceback above"
        )


def main() -> int:
    for attempt in range(1, ATTEMPTS + 1):
        run_once(attempt)
    print(f"mixed-batch lifetime gate passed {ATTEMPTS} fresh-interpreter attempts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
