#!/usr/bin/env python3
"""Validate non-executing prompt, technique, and source-intake research contracts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adult_illustration_intelligence_validation import validate_paths

__all__ = ["validate_paths", "main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    errors = validate_paths(parser.parse_args(argv).root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("adult illustration research intelligence: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
