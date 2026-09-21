#!/usr/bin/env python3
"""Validate the checked-in Adult Illustration benchmark-result contract offline."""
from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_prompt.adult_illustration_benchmark_result import (  # noqa: E402
    git_blob_sha,
    validate_benchmark_result,
)


MAX_JSON_BYTES = 1_048_576
RESULT_PATH = Path("research/adult-illustration/benchmark-result-example.json")
CORPUS_PATH = Path("research/adult-illustration/benchmark-corpus.json")
ROUTES_PATH = Path("research/adult-illustration/route-candidates.json")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        if key in value:
            raise ValueError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value {value!r}")


def _read_json(root: Path, relative: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    path = root / relative
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label} is missing: {relative.as_posix()}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise ValueError(f"{label} cannot be a symlink")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if info.st_size > MAX_JSON_BYTES:
        raise ValueError(f"{label} exceeds {MAX_JSON_BYTES} bytes")
    data = path.read_bytes()
    if len(data) != info.st_size:
        raise ValueError(f"{label} changed while it was read")
    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data, value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        _, result = _read_json(root, RESULT_PATH, "benchmark result")
        corpus_bytes, corpus = _read_json(root, CORPUS_PATH, "benchmark corpus")
        routes_bytes, routes = _read_json(root, ROUTES_PATH, "route manifest")
        validate_benchmark_result(
            result,
            corpus,
            routes,
            corpus_blob_sha=git_blob_sha(corpus_bytes),
            route_blob_sha=git_blob_sha(routes_bytes),
        )
    except (ValueError, TypeError, OSError, RecursionError) as exc:
        print(
            json.dumps(
                {
                    "schema": "studio.adult-illustration-benchmark-result-error/v1",
                    "kind": "benchmark-result-validation-error",
                    "error": str(exc),
                    "executable": False,
                    "authority": "none",
                    "download_authorized": False,
                    "install_authorized": False,
                    "execution_authorized": False,
                    "generation_submitted": False,
                    "training_authorized": False,
                    "promotion_authorized": False,
                },
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print("adult illustration benchmark result: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
