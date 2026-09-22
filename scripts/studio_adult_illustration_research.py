#!/usr/bin/env python3
"""Inspect adult-illustration research and prepare zero-authority comparisons."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_prompt.adult_illustration_research import (  # noqa: E402
    CATALOG_SPECS,
    catalogs,
    comparison_plan,
    get_record,
    list_records,
    programme_status,
)


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="exclusive-create JSON output path")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root containing research/adult-illustration",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("programme-status", help="show programme and catalog status")
    _add_output(status)
    catalog_parser = subparsers.add_parser("catalogs", help="list supported research catalogs")
    _add_output(catalog_parser)

    listing = subparsers.add_parser("list", help="list bounded catalog summaries")
    listing.add_argument("catalog", choices=sorted(CATALOG_SPECS))
    _add_output(listing)

    getter = subparsers.add_parser("get", help="read one exact catalog record")
    getter.add_argument("catalog", choices=sorted(CATALOG_SPECS))
    getter.add_argument("record_id")
    _add_output(getter)

    plan = subparsers.add_parser(
        "comparison-plan",
        help="prepare a finite comparison with authorized candidate cap zero",
    )
    plan.add_argument("--case", action="append", required=True, dest="case_ids")
    plan.add_argument("--route", action="append", required=True, dest="route_ids")
    plan.add_argument("--dialect", action="append", default=[], dest="dialect_ids")
    plan.add_argument("--technique", action="append", default=[], dest="technique_ids")
    _add_output(plan)
    return parser


def _render(value: object) -> str:
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


def _emit(value: object, output: str | None) -> None:
    text = _render(value)
    if output:
        target = Path(output)
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "programme-status":
            value = programme_status(args.root)
        elif args.command == "catalogs":
            value = catalogs(args.root)
        elif args.command == "list":
            value = list_records(args.root, args.catalog)
        elif args.command == "get":
            value = get_record(args.root, args.catalog, args.record_id)
        else:
            value = comparison_plan(
                args.root,
                case_ids=args.case_ids,
                route_ids=args.route_ids,
                dialect_ids=args.dialect_ids,
                technique_ids=args.technique_ids,
            )
        _emit(value, args.out)
        return 0
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        error = {
            "error": str(exc),
            "operation": args.command,
            "authority": "none",
            "execution_authorized": False,
            "generation_submitted": False,
            "download_authorized": False,
            "install_authorized": False,
            "training_authorized": False,
        }
        sys.stderr.write(_render(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
