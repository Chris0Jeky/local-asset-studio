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


ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS = 2


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
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )
    output = result.stdout + result.stderr
    print(f"--- mixed-batch lifetime attempt {attempt}/{ATTEMPTS} ---")
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
