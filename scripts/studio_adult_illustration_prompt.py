#!/usr/bin/env python3
"""Inspect and compile adult-illustration prompt profiles without runtime authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_prompt.adult_illustration_prompt_catalog import load_catalog  # noqa: E402
from studio_prompt.adult_illustration_prompt_projection import (  # noqa: E402
    compile_prompt,
    validate_prompt_projection,
)
from studio_prompt.adult_illustration_taxonomy_membership import (  # noqa: E402
    inspect_prompt_taxonomy_membership,
)

LIMIT = 1_048_576
INDEX_LIMIT = 67_108_864


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value!r}")


def _read_json(
    path: str | Path,
    maximum: int = LIMIT,
    label: str = "JSON",
) -> Any:
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(f"{label} exceeds {maximum} bytes")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid UTF-8 JSON: {exc}") from exc


def _write_new(path: str | Path, value: Any) -> None:
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def _emit(value: Any, output: str | None) -> None:
    if output:
        _write_new(output, value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    profiles = subparsers.add_parser("profiles", help="list pinned non-executing profiles")
    profiles.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))

    compile_parser = subparsers.add_parser("compile", help="compile a reviewed source projection")
    compile_parser.add_argument("source")
    compile_parser.add_argument("--profile", required=True)
    compile_parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    compile_parser.add_argument("--out")

    validate_parser = subparsers.add_parser("validate", help="recompute and verify a saved prompt projection")
    validate_parser.add_argument("compiled")
    validate_parser.add_argument("--source", required=True)
    validate_parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    validate_parser.add_argument("--out")

    membership = subparsers.add_parser(
        "inspect-membership",
        help="join a validated prompt artifact to a content-addressed taxonomy index",
    )
    membership.add_argument("compiled")
    membership.add_argument("--source", required=True)
    membership.add_argument("--taxonomy-index", required=True)
    membership.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    membership.add_argument("--out")
    return parser


def _profile_listing(root: str | Path) -> dict[str, Any]:
    catalog = load_catalog(root)
    rows = []
    for profile_id in sorted(catalog["profiles"]):
        profile = catalog["profiles"][profile_id]
        rows.append(
            {
                "id": profile_id,
                "route_candidate_id": profile["route_candidate_id"],
                "mode": profile["mode"],
                "source_revision": profile["source_revision"],
                "documentation_revision": profile["documentation_revision"],
                "min_references": profile.get("min_references", 0),
                "max_references": profile["max_references"],
                "execution_authorized": False,
                "generation_submitted": False,
            }
        )
    return {
        "schema": "studio.adult-illustration.prompt-profile-list/v1",
        "catalog_manifest_sha256": catalog["manifest_sha256"],
        "profiles": rows,
        "execution_authorized": False,
        "generation_submitted": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "profiles":
            value = _profile_listing(args.repo_root)
            _emit(value, None)
        elif args.command == "compile":
            source = _read_json(args.source)
            value = compile_prompt(source, args.profile, args.repo_root)
            _emit(value, args.out)
        elif args.command == "validate":
            compiled = _read_json(args.compiled)
            source = _read_json(args.source)
            value = validate_prompt_projection(compiled, source, args.repo_root)
            _emit(value, args.out)
        else:
            compiled = _read_json(args.compiled)
            source = _read_json(args.source)
            taxonomy_index = _read_json(
                args.taxonomy_index,
                INDEX_LIMIT,
                "Taxonomy index JSON",
            )
            value = inspect_prompt_taxonomy_membership(
                compiled,
                source,
                taxonomy_index,
                args.repo_root,
            )
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
