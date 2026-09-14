"""Run the complete offline suite in a fresh process and reject leaked resources.

The subprocess boundary makes interpreter-shutdown warnings observable.  Tracemalloc
keeps the allocation traceback so a failing CI run points at the owner instead of
leaving a bare socket descriptor.  This wrapper is intentionally outside unittest
discovery to avoid recursively launching the suite.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "-X",
        "tracemalloc=25",
        "-W",
        "always::ResourceWarning",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    print(output, end="" if output.endswith("\n") else "\n")
    if result.returncode:
        print(f"offline suite exited {result.returncode}", file=sys.stderr)
        return result.returncode
    if "ResourceWarning" in output:
        print(
            "offline suite emitted ResourceWarning; inspect the tracemalloc "
            "allocation traceback above",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
