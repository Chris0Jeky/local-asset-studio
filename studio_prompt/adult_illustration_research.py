"""Guarded read-only facade for Adult Illustration research catalogs."""
from __future__ import annotations

import json  # noqa: F401 -- re-exported: bounds tests patch research.json.loads.
from itertools import islice
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
    """Delegate to the private guarded reader (single source of truth)."""
    return _base._read_manifest(root, filename)


catalogs = _base.catalogs
programme_status = _base.programme_status
list_records = _base.list_records
get_record = _base.get_record


def _bounded_ids(name: str, values: Iterable[str], maximum: int) -> list[str]:
    """Consume only enough input to accept its size or prove it exceeds the cap."""
    result = list(islice(values, maximum + 1))
    if len(result) > maximum:
        raise ValueError(f"{name} must contain at most {maximum} ids")
    return result


def comparison_plan(
    root: Path | str,
    *,
    case_ids: Iterable[str],
    route_ids: Iterable[str],
    dialect_ids: Iterable[str] = (),
    technique_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a zero-authority plan while retaining technique revision gaps."""

    cases = _bounded_ids("case_ids", case_ids, MAX_CASES)
    routes = _bounded_ids("route_ids", route_ids, MAX_ROUTES)
    dialects = _bounded_ids("dialect_ids", dialect_ids, MAX_OPTIONAL)
    techniques = _bounded_ids("technique_ids", technique_ids, MAX_OPTIONAL)
    return _base.comparison_plan(
        root,
        case_ids=cases,
        route_ids=routes,
        dialect_ids=dialects,
        technique_ids=techniques,
    )


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
