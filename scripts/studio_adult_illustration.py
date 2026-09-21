"""Validate or project controlled adult-illustration records; never submit generation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_prompt.adult_illustration import (  # noqa: E402
    project,
    validate_intent,
    validate_projection,
)
from studio_prompt.schema import read_json, write_new  # noqa: E402


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("validate-intent", "validate and normalize a source intent"),
        ("project", "project a source intent into existing CreativeIntent semantics"),
        ("validate-projection", "recompute and verify a saved projection"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("source")
        child.add_argument("--out")
    return parser


def _emit(value, output):
    if output:
        write_new(output, value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        source = read_json(args.source)
        if args.command == "validate-intent":
            value = validate_intent(source)
        elif args.command == "project":
            value = project(source)
        else:
            value = validate_projection(source)
        _emit(value, args.out)
        return 0
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "operation": args.command,
                    "execution_authorized": False,
                    "generation_submitted": False,
                },
                ensure_ascii=False,
                allow_nan=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
