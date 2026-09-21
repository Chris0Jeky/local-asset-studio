"""Guarded read-only facade for Adult Illustration research catalogs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from . import _adult_illustration_research_impl as _base


CatalogSpec = _base.CatalogSpec
DuplicateKeyError = _base.DuplicateKeyError
CATALOG_SPECS = _base.CATALOG_SPECS
MAX_MANIFEST_BYTES = _base.MAX_MANIFEST_BYTES
MAX_RECORDS = _base.MAX_RECORDS
MAX_CASES = _base.MAX_CASES
MAX_ROUTES = _base.MAX_ROUTES
MAX_OPTIONAL = _base.MAX_OPTIONAL
MAX_ESTIMATED_CANDIDATES = _base.MAX_ESTIMATED_CANDIDATES


def _read_manifest(root: Path | str, filename: str) -> tuple[dict[str, Any], str]:
    """Read one regular manifest only after enforcing its byte bound."""

    directory = _base._manifest_directory(root)
    path = directory / filename
    if path.is_symlink():
        raise ValueError(f"Research manifest cannot be a symlink: {filename}")
    resolved = path.resolve(strict=True)
    if resolved.parent != directory:
        raise ValueError(f"Research manifest escapes its directory: {filename}")
    if not resolved.is_file():
        raise ValueError(f"Research manifest is not a file: {filename}")
    info = resolved.stat()
    if info.st_size > MAX_MANIFEST_BYTES:
        raise ValueError(
            f"Research manifest exceeds {MAX_MANIFEST_BYTES} bytes: {filename}"
        )
    data = resolved.read_bytes()
    if len(data) != info.st_size:
        raise ValueError(f"Research manifest changed while being read: {filename}")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_base._pairs,
            parse_constant=_base._reject_constant,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateKeyError,
        ValueError,
    ) as exc:
        raise ValueError(f"Invalid research manifest {filename}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(
            f"Research manifest must contain a JSON object: {filename}"
        )
    if value.get("executable") is not False or value.get("authority") != "none":
        raise ValueError(
            "Research manifest must be non-executing with authority none: "
            f"{filename}"
        )
    if not isinstance(value.get("schema"), str) or not isinstance(
        value.get("kind"), str
    ):
        raise ValueError(f"Research manifest needs schema and kind: {filename}")
    return value, hashlib.sha256(data).hexdigest()


# The implementation resolves this name from its own module at call time. Patch the
# guarded reader once during this side-effect-free import so every public operation
# receives the same pre-allocation bound.
_base._read_manifest = _read_manifest

catalogs = _base.catalogs
programme_status = _base.programme_status
list_records = _base.list_records
get_record = _base.get_record


def comparison_plan(
    root: Path | str,
    *,
    case_ids: Iterable[str],
    route_ids: Iterable[str],
    dialect_ids: Iterable[str] = (),
    technique_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a zero-authority plan while retaining technique revision gaps."""

    cases = list(case_ids)
    routes = list(route_ids)
    dialects = list(dialect_ids)
    techniques = list(technique_ids)
    result = _base.comparison_plan(
        root,
        case_ids=cases,
        route_ids=routes,
        dialect_ids=dialects,
        technique_ids=techniques,
    )
    selected, _ = _base._selected(root, "techniques", result["techniques"])
    gaps = set(result["compatibility_gaps"])
    for technique in selected:
        revision = technique.get("source_revision")
        if (
            not isinstance(revision, str)
            or not revision.strip()
            or _base._moving(revision)
        ):
            gaps.add(
                f"technique {technique['id']}: immutable source revision is unresolved"
            )
    result["compatibility_gaps"] = sorted(gaps)
    unsigned = dict(result)
    unsigned.pop("plan_id", None)
    result["plan_id"] = hashlib.sha256(_base._canonical_bytes(unsigned)).hexdigest()
    return result


__all__ = [
    "CATALOG_SPECS",
    "CatalogSpec",
    "DuplicateKeyError",
    "MAX_MANIFEST_BYTES",
    "catalogs",
    "programme_status",
    "list_records",
    "get_record",
    "comparison_plan",
]
