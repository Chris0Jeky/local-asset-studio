"""Run the complete offline suite in a fresh process and reject leaked resources.

The subprocess boundary makes interpreter-shutdown warnings observable.  A single
tracemalloc frame retains the allocation line without multiplying the full suite's
runtime.  This wrapper is intentionally outside unittest discovery to avoid
recursively launching the suite.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def printable(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def main() -> int:
    command = [
        sys.executable,
        "-X",
        "tracemalloc=1",
        "-W",
        "always::ResourceWarning",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=420,
        )
    except subprocess.TimeoutExpired as exc:
        output = printable(exc.stdout) + printable(exc.stderr)
        print(output, end="" if output.endswith("\n") else "\n")
        print("offline suite exceeded the 420-second lifetime budget", file=sys.stderr)
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
