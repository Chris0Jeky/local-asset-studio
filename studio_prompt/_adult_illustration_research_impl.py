"""Read-only adult-illustration research catalogs and zero-authority plans."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MAX_MANIFEST_BYTES = 1_048_576
MAX_RECORDS = 512
MAX_CASES = 32
MAX_ROUTES = 16
MAX_OPTIONAL = 16
MAX_ESTIMATED_CANDIDATES = 128
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_MOVING_REVISIONS = {"main", "master", "head", "latest", "trunk"}


class DuplicateKeyError(ValueError):
    """Raised when JSON contains repeated object keys."""


@dataclass(frozen=True)
class CatalogSpec:
    filename: str
    item_key: str
    summary_fields: tuple[str, ...]


CATALOG_SPECS: dict[str, CatalogSpec] = {
    "cases": CatalogSpec(
        "benchmark-corpus.json",
        "cases",
        ("kind", "content_class", "proposed_smoke_candidates", "authorized_candidate_cap"),
    ),
    "controls": CatalogSpec(
        "control-ontology.json",
        "controls",
        ("domain", "description", "mechanisms"),
    ),
    "dialects": CatalogSpec(
        "prompt-dialects.json",
        "profiles",
        ("mode", "evidence_state", "ready_for_compilation", "route_candidate_ids"),
    ),
    "packs": CatalogSpec(
        "genre-packs.json",
        "packs",
        ("title", "content_class", "defaults_evidence", "authorized_candidate_cap"),
    ),
    "routes": CatalogSpec(
        "route-candidates.json",
        "candidates",
        ("lane", "evidence_state", "installed", "prompt_mode", "reference_mode"),
    ),
    "sources": CatalogSpec(
        "source-intake-example.json",
        "records",
        ("provider", "snapshot_state", "terms_state", "immutable_revision"),
    ),
    "techniques": CatalogSpec(
        "technique-candidates.json",
        "candidates",
        ("category", "evidence_state", "installed", "ready_for_qualification"),
    ),
}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value!r} is not allowed")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _manifest_directory(root: Path | str) -> Path:
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ValueError("Repository root must be a directory")
    current = root_path
    for part in ("research", "adult-illustration"):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Research manifest directory cannot be a symlink: {current}")
        current = current.resolve(strict=True)
        if not current.is_dir():
            raise ValueError(f"Research manifest directory is missing: {current}")
    return current


def _read_manifest(root: Path | str, filename: str) -> tuple[dict[str, Any], str]:
    directory = _manifest_directory(root)
    path = directory / filename
    if path.is_symlink():
        raise ValueError(f"Research manifest cannot be a symlink: {filename}")
    resolved = path.resolve(strict=True)
    if resolved.parent != directory:
        raise ValueError(f"Research manifest escapes its directory: {filename}")
    if not resolved.is_file():
        raise ValueError(f"Research manifest is not a file: {filename}")
    data = resolved.read_bytes()
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError(f"Research manifest exceeds {MAX_MANIFEST_BYTES} bytes: {filename}")
    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        raise ValueError(f"Invalid research manifest {filename}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Research manifest must contain a JSON object: {filename}")
    if value.get("executable") is not False or value.get("authority") != "none":
        raise ValueError(f"Research manifest must be non-executing with authority none: {filename}")
    if not isinstance(value.get("schema"), str) or not isinstance(value.get("kind"), str):
        raise ValueError(f"Research manifest needs schema and kind: {filename}")
    return value, hashlib.sha256(data).hexdigest()


def _spec(catalog: str) -> CatalogSpec:
    try:
        return CATALOG_SPECS[catalog]
    except KeyError as exc:
        allowed = ", ".join(sorted(CATALOG_SPECS))
        raise ValueError(f"Unknown catalog {catalog!r}; expected one of: {allowed}") from exc


def _records(root: Path | str, catalog: str) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    spec = _spec(catalog)
    manifest, digest = _read_manifest(root, spec.filename)
    raw = manifest.get(spec.item_key)
    if not isinstance(raw, list) or len(raw) > MAX_RECORDS:
        raise ValueError(f"Catalog {catalog!r} must contain a bounded {spec.item_key!r} array")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Catalog {catalog!r} record {index} must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or _ID.fullmatch(item_id) is None:
            raise ValueError(f"Catalog {catalog!r} record {index} has invalid id")
        if item_id in seen:
            raise ValueError(f"Catalog {catalog!r} has duplicate id {item_id!r}")
        seen.add(item_id)
        records.append(item)
    records.sort(key=lambda item: item["id"])
    return records, manifest, digest


def _base(format_name: str) -> dict[str, Any]:
    return {
        "format": format_name,
        "authority": "none",
        "execution_authorized": False,
        "generation_submitted": False,
        "download_authorized": False,
        "install_authorized": False,
        "training_authorized": False,
    }


def catalogs(root: Path | str) -> dict[str, Any]:
    result = _base("studio.adult-illustration.research-catalogs/v1")
    items: list[dict[str, Any]] = []
    for catalog in sorted(CATALOG_SPECS):
        spec = CATALOG_SPECS[catalog]
        records, manifest, digest = _records(root, catalog)
        items.append(
            {
                "id": catalog,
                "filename": spec.filename,
                "item_key": spec.item_key,
                "schema": manifest["schema"],
                "kind": manifest["kind"],
                "count": len(records),
                "manifest_sha256": digest,
            }
        )
    result["catalogs"] = items
    return result


def programme_status(root: Path | str) -> dict[str, Any]:
    programme, digest = _read_manifest(root, "programme.json")
    result = _base("studio.adult-illustration.programme-status/v1")
    result.update(
        {
            "programme_manifest_sha256": digest,
            "source_baseline": programme.get("source_baseline"),
            "epic": programme.get("epic"),
            "issues": programme.get("issues"),
            "milestones": programme.get("milestones"),
            "requirements": programme.get("requirements"),
            "next_issue": programme.get("next_issue"),
            "catalog_count": len(CATALOG_SPECS),
        }
    )
    return result


def _summary(record: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    value = {"id": record["id"]}
    for field in fields:
        if field in record:
            value[field] = record[field]
    return value


def list_records(root: Path | str, catalog: str) -> dict[str, Any]:
    spec = _spec(catalog)
    records, manifest, digest = _records(root, catalog)
    result = _base("studio.adult-illustration.research-list/v1")
    result.update(
        {
            "catalog": catalog,
            "source_schema": manifest["schema"],
            "manifest_sha256": digest,
            "count": len(records),
            "records": [_summary(record, spec.summary_fields) for record in records],
        }
    )
    return result


def get_record(root: Path | str, catalog: str, record_id: str) -> dict[str, Any]:
    if not isinstance(record_id, str) or _ID.fullmatch(record_id) is None:
        raise ValueError("Record ID is invalid")
    records, manifest, digest = _records(root, catalog)
    for record in records:
        if record["id"] == record_id:
            result = _base("studio.adult-illustration.research-record/v1")
            result.update(
                {
                    "catalog": catalog,
                    "source_schema": manifest["schema"],
                    "manifest_sha256": digest,
                    "record": record,
                }
            )
            return result
    raise KeyError(f"Catalog {catalog!r} has no record {record_id!r}")


def _requested_ids(name: str, values: Iterable[str], *, minimum: int, maximum: int) -> list[str]:
    result = list(values)
    if len(result) < minimum:
        raise ValueError(f"{name} requires at least {minimum} value(s)")
    if len(result) > maximum:
        raise ValueError(f"{name} accepts at most {maximum} values")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} contains duplicate values")
    for value in result:
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            raise ValueError(f"{name} contains invalid ID {value!r}")
    return sorted(result)


def _selected(root: Path | str, catalog: str, ids: list[str]) -> tuple[list[dict[str, Any]], str]:
    records, _, digest = _records(root, catalog)
    by_id = {record["id"]: record for record in records}
    missing = [item for item in ids if item not in by_id]
    if missing:
        raise KeyError(f"Catalog {catalog!r} has no record(s): {', '.join(missing)}")
    return [by_id[item] for item in ids], digest


def _moving(value: Any) -> bool:
    return isinstance(value, str) and value.casefold() in _MOVING_REVISIONS


def _append_gap(gaps: list[str], prefix: str, value: Any) -> None:
    if isinstance(value, str) and value.strip():
        gaps.append(f"{prefix}: {value.strip()}")


def comparison_plan(
    root: Path | str,
    *,
    case_ids: Iterable[str],
    route_ids: Iterable[str],
    dialect_ids: Iterable[str] = (),
    technique_ids: Iterable[str] = (),
) -> dict[str, Any]:
    cases_requested = _requested_ids("case_ids", case_ids, minimum=1, maximum=MAX_CASES)
    routes_requested = _requested_ids("route_ids", route_ids, minimum=1, maximum=MAX_ROUTES)
    dialects_requested = _requested_ids("dialect_ids", dialect_ids, minimum=0, maximum=MAX_OPTIONAL)
    techniques_requested = _requested_ids("technique_ids", technique_ids, minimum=0, maximum=MAX_OPTIONAL)

    cases, cases_hash = _selected(root, "cases", cases_requested)
    routes, routes_hash = _selected(root, "routes", routes_requested)
    dialects, dialects_hash = _selected(root, "dialects", dialects_requested)
    techniques, techniques_hash = _selected(root, "techniques", techniques_requested)
    controls, _, controls_hash = _records(root, "controls")
    control_ids = {item["id"] for item in controls}

    required_controls: set[str] = set()
    estimated = 0
    for case in cases:
        if case.get("authorized_candidate_cap") != 0:
            raise ValueError(f"Case {case['id']!r} does not have zero authorized candidate cap")
        if case.get("real_sources_in_git") is not False:
            raise ValueError(f"Case {case['id']!r} must not contain real sources in Git")
        count = case.get("proposed_smoke_candidates")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > 32:
            raise ValueError(f"Case {case['id']!r} has invalid proposed candidate count")
        estimated += count * len(routes)
        raw_controls = case.get("required_controls")
        if not isinstance(raw_controls, list) or not all(isinstance(item, str) for item in raw_controls):
            raise ValueError(f"Case {case['id']!r} has invalid required controls")
        required_controls.update(raw_controls)
    unknown_controls = sorted(required_controls - control_ids)
    if unknown_controls:
        raise ValueError(f"Benchmark cases reference unknown controls: {', '.join(unknown_controls)}")
    if estimated > MAX_ESTIMATED_CANDIDATES:
        raise ValueError(
            f"Estimated comparison size {estimated} exceeds {MAX_ESTIMATED_CANDIDATES}; split the plan"
        )

    selected_route_ids = set(routes_requested)
    for dialect in dialects:
        targets = dialect.get("route_candidate_ids")
        if not isinstance(targets, list) or not selected_route_ids.intersection(targets):
            raise ValueError(
                f"Dialect {dialect['id']!r} does not target any selected route"
            )

    gaps: list[str] = []
    for route in routes:
        prefix = f"route {route['id']}"
        for unknown in route.get("unknowns", []):
            _append_gap(gaps, prefix, unknown)
        if route.get("installed") is not True:
            gaps.append(f"{prefix}: installed state is not verified")
        if route.get("evidence_state") not in {"graph_validated", "executed", "visually_reviewed", "task_accepted", "promoted"}:
            gaps.append(f"{prefix}: graph/runtime evidence is not established")
        if route.get("source_revision") is None or _moving(route.get("source_revision")):
            gaps.append(f"{prefix}: immutable source revision is unresolved")
        terms = route.get("terms")
        if not isinstance(terms, str) or "unknown" in terms.casefold() or "required" in terms.casefold():
            gaps.append(f"{prefix}: exact terms snapshot remains unresolved")
    for dialect in dialects:
        prefix = f"dialect {dialect['id']}"
        for unknown in dialect.get("unknowns", []):
            _append_gap(gaps, prefix, unknown)
        if dialect.get("ready_for_compilation") is not True:
            gaps.append(f"{prefix}: compiler profile is not qualified")
        if dialect.get("source_revision") is None or _moving(dialect.get("source_revision")):
            gaps.append(f"{prefix}: immutable source revision is unresolved")
    for technique in techniques:
        prefix = f"technique {technique['id']}"
        for blocker in technique.get("promotion_blockers", []):
            _append_gap(gaps, prefix, blocker)
        if technique.get("ready_for_qualification") is not True:
            gaps.append(f"{prefix}: not ready for qualification")
        if technique.get("installed") is not True:
            gaps.append(f"{prefix}: installed state is not verified")

    result = _base("studio.adult-illustration.comparison-plan/v1")
    result.update(
        {
            "issue": 435,
            "cases": cases_requested,
            "routes": routes_requested,
            "dialects": dialects_requested,
            "techniques": techniques_requested,
            "required_controls": sorted(required_controls),
            "estimated_candidate_count": estimated,
            "authorized_candidate_cap": 0,
            "compatibility_gaps": sorted(set(gaps)),
            "input_manifests": {
                "cases": cases_hash,
                "controls": controls_hash,
                "routes": routes_hash,
                "dialects": dialects_hash,
                "techniques": techniques_hash,
            },
            "stale_when_any_input_manifest_changes": True,
        }
    )
    result["plan_id"] = hashlib.sha256(_canonical_bytes(result)).hexdigest()
    return result


__all__ = [
    "CATALOG_SPECS",
    "catalogs",
    "programme_status",
    "list_records",
    "get_record",
    "comparison_plan",
]
