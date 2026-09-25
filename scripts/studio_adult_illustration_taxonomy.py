#!/usr/bin/env python3
"""Build and inspect the pinned adult-illustration taxonomy without network access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_prompt.adult_illustration_taxonomy import (  # noqa: E402
    AUTHORITY,
    build_taxonomy_index,
    load_taxonomy_contracts,
    lookup_taxonomy,
    render_taxonomy_index,
    validate_taxonomy_index,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MAX_INDEX_BYTES = 67_108_864


class DuplicateKeyError(ValueError):
    """Raised when a persisted index repeats an object key."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value!r} is not allowed")


def _read_bounded(path: str | Path, maximum: int, label: str) -> bytes:
    target = Path(path)
    with target.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(f"{label} exceeds {maximum} bytes")
    return raw


def _read_json(path: str | Path, maximum: int = MAX_INDEX_BYTES) -> Any:
    raw = _read_bounded(path, maximum, "Taxonomy index JSON")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        raise ValueError(f"Invalid taxonomy index JSON: {exc}") from exc


def _write_new(path: str | Path, raw: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise ValueError(f"Output already exists: {target}") from exc


def _emit(value: Any, output: str | None = None) -> None:
    raw = (
        render_taxonomy_index(value)
        if isinstance(value, dict) and value.get("schema") == "studio.adult-illustration-taxonomy-index/v1"
        else (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    )
    if output:
        _write_new(output, raw)
    else:
        sys.stdout.write(raw.decode("utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser("source", help="inspect checked-in source and review identities")
    source.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    source.add_argument("--out")

    build = subparsers.add_parser("build", help="build an index from exact retained source bytes")
    build.add_argument("source")
    build.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    build.add_argument("--out")

    validate = subparsers.add_parser("validate", help="rebuild and exactly validate a saved index")
    validate.add_argument("source")
    validate.add_argument("index")
    validate.add_argument("--repo-root", default=str(DEFAULT_ROOT))
    validate.add_argument("--out")

    lookup = subparsers.add_parser("lookup", help="resolve one source canonical or reviewed alias")
    lookup.add_argument("index")
    lookup.add_argument("term")
    lookup.add_argument("--out")
    return parser


def _source_listing(root: str | Path) -> dict[str, Any]:
    contracts = load_taxonomy_contracts(root)
    source = contracts["source"]
    review = contracts["review"]
    return {
        "schema": "studio.adult-illustration-taxonomy-source-list/v1",
        "source": {
            **source["source"],
            "manifest_sha256": source["manifest_sha256"],
        },
        "review": {
            "manifest_sha256": review["manifest_sha256"],
            "entries": len(review["entries"]),
            "source_sha256": review["source_sha256"],
        },
        "accepted_source_as_a_whole": False,
        "execution_authorized": False,
        "generation_submitted": False,
        "download_authorized": False,
        "install_authorized": False,
        "training_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "source":
            _emit(_source_listing(args.repo_root), args.out)
        elif args.command == "build":
            contracts = load_taxonomy_contracts(args.repo_root)
            maximum = contracts["source"]["bounds"]["max_source_bytes"]
            source_bytes = _read_bounded(args.source, maximum, "Taxonomy source")
            _emit(build_taxonomy_index(source_bytes, args.repo_root), args.out)
        elif args.command == "validate":
            contracts = load_taxonomy_contracts(args.repo_root)
            maximum = contracts["source"]["bounds"]["max_source_bytes"]
            source_bytes = _read_bounded(args.source, maximum, "Taxonomy source")
            index = _read_json(args.index, contracts["source"]["bounds"]["max_index_bytes"])
            _emit(validate_taxonomy_index(index, source_bytes, args.repo_root), args.out)
        else:
            index = _read_json(args.index)
            entry = lookup_taxonomy(index, args.term)
            _emit(
                {
                    "schema": "studio.adult-illustration-taxonomy-lookup/v1",
                    "term": args.term,
                    "matched": entry is not None,
                    "entry": entry,
                    "source_revalidated": False,
                    "execution_authorized": False,
                    "generation_submitted": False,
                },
                args.out,
            )
        return 0
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        error = {
            "error": str(exc),
            "operation": args.command,
            **AUTHORITY,
        }
        print(json.dumps(error, sort_keys=True, ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
