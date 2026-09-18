"""Strict offline index builder for the pinned adult-illustration anime taxonomy."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .adult_illustration_taxonomy_contracts import (
    AUTHORITY,
    EXPECTED_COLUMNS,
    INDEX_SCHEMA,
    SHA256,
    authority,
    canonical_bytes,
    load_taxonomy_contracts,
    normalise_term,
    sha256,
    text,
)

__all__ = [
    "AUTHORITY",
    "build_taxonomy_index",
    "load_taxonomy_contracts",
    "lookup_taxonomy",
    "render_taxonomy_index",
    "validate_taxonomy_index",
]


def _parse_source(source_bytes: bytes, contract: dict[str, Any]) -> list[dict[str, Any]]:
    source, bounds = contract["source"], contract["bounds"]
    if not isinstance(source_bytes, bytes):
        raise TypeError("Taxonomy source must be bytes")
    if len(source_bytes) != source["bytes"]:
        raise ValueError(
            f"Taxonomy source byte count {len(source_bytes)} does not match pinned {source['bytes']}"
        )
    if len(source_bytes) > bounds["max_source_bytes"]:
        raise ValueError("Taxonomy source exceeds configured byte bound")
    if sha256(source_bytes) != source["sha256"]:
        raise ValueError("Taxonomy source SHA-256 does not match pinned source")
    try:
        decoded = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Taxonomy source must be UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if reader.fieldnames != EXPECTED_COLUMNS:
        raise ValueError(f"Taxonomy source header must be exactly {EXPECTED_COLUMNS}")

    rows: list[dict[str, Any]] = []
    ids: set[int] = set()
    names: set[str] = set()
    normalised_names: set[str] = set()
    for line, row in enumerate(reader, start=2):
        if None in row or set(row) != set(EXPECTED_COLUMNS) or any(value is None for value in row.values()):
            raise ValueError(f"Taxonomy source row {line} has an invalid column shape")
        try:
            tag_id, category, frequency = int(row["tag_id"]), int(row["category"]), int(row["count"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Taxonomy source row {line} has a non-integer field") from exc
        name = text(row["name"], f"taxonomy source row {line} name", bounds["max_term_length"])
        normalised = normalise_term(name)
        if tag_id < 1 or frequency < 0:
            raise ValueError(f"Taxonomy source row {line} has an invalid id or frequency")
        if category not in contract["categories"]:
            raise ValueError(f"Taxonomy source row {line} has unknown category {category}")
        if tag_id in ids or name in names or normalised in normalised_names:
            raise ValueError(f"Taxonomy source row {line} has a duplicate id or canonical name")
        ids.add(tag_id)
        names.add(name)
        normalised_names.add(normalised)
        rows.append({
            "tag_id": tag_id,
            "source_name": name,
            "source_category": contract["categories"][category]["id"],
            "source_category_value": category,
            "frequency": frequency,
            "normalised": normalised,
        })
        if len(rows) > bounds["max_records"]:
            raise ValueError("Taxonomy source exceeds configured record bound")
    if len(rows) != source["records"]:
        raise ValueError(
            f"Taxonomy source record count {len(rows)} does not match pinned {source['records']}"
        )
    return rows


def _acyclic(graph: dict[str, list[str]], label: str, maximum_depth: int) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, depth: int) -> None:
        if depth > maximum_depth:
            raise ValueError(f"Taxonomy {label} graph exceeds depth {maximum_depth}")
        if node in visiting:
            raise ValueError(f"Taxonomy {label} graph contains a cycle at {node!r}")
        if node in visited:
            return
        visiting.add(node)
        for target in graph.get(node, []):
            visit(target, depth + 1)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node, 1)


def _validate_review(
    source_rows: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    contract: dict[str, Any],
) -> None:
    source_names = {row["source_name"] for row in source_rows}
    source_normalised = {row["normalised"]: row["source_name"] for row in source_rows}
    by_name = {entry["source_name"]: entry for entry in reviews}
    alias_owner: dict[str, str] = {}
    for entry in reviews:
        name = entry["source_name"]
        if name not in source_names:
            raise ValueError(f"Taxonomy review source name {name!r} is absent from pinned source")
        for alias in entry["aliases"]:
            normalised = normalise_term(alias)
            if not normalised:
                raise ValueError(f"Review {name!r} contains an empty alias")
            if normalised in source_normalised:
                raise ValueError(
                    f"Review {name!r} alias {alias!r} collides with source canonical "
                    f"{source_normalised[normalised]!r}"
                )
            if normalised in alias_owner:
                raise ValueError(
                    f"Review alias {alias!r} collides with alias owned by {alias_owner[normalised]!r}"
                )
            alias_owner[normalised] = name
        for target_name in entry["implications"]:
            target = by_name.get(target_name)
            if target is None:
                raise ValueError(f"Review {name!r} implication target {target_name!r} is not reviewed")
            if target["polarity"] != entry["polarity"]:
                raise ValueError(f"Review {name!r} implication {target_name!r} changes polarity")
            if not set(entry["profile_ids"]).issubset(target["profile_ids"]):
                raise ValueError(f"Review {name!r} implication {target_name!r} lacks profile support")
        replacement = entry["deprecated_by"]
        if replacement is not None and replacement not in by_name:
            raise ValueError(f"Review {name!r} deprecation target {replacement!r} is not reviewed")

    maximum = contract["bounds"]["max_relationship_depth"]
    _acyclic({entry["source_name"]: entry["implications"] for entry in reviews}, "implication", maximum)
    _acyclic({
        entry["source_name"]: ([] if entry["deprecated_by"] is None else [entry["deprecated_by"]])
        for entry in reviews
    }, "deprecation", maximum)


def build_taxonomy_index(source_bytes: bytes, root: Path | str = ".") -> dict[str, Any]:
    """Build a deterministic zero-authority index from exact source bytes and review."""
    contracts = load_taxonomy_contracts(root)
    source_contract, review_contract = contracts["source"], contracts["review"]
    source_rows = _parse_source(source_bytes, source_contract)
    reviews = review_contract["entries"]
    _validate_review(source_rows, reviews, source_contract)
    review_by_name = {entry["source_name"]: entry for entry in reviews}
    entries: list[dict[str, Any]] = []
    alias_count = accepted_count = 0
    for row in sorted(source_rows, key=lambda item: (item["source_name"].casefold(), item["tag_id"])):
        review = review_by_name.get(row["source_name"])
        if review is None:
            overlay = {
                "reviewed": False,
                "display": row["source_name"].replace("_", " "),
                "aliases": [], "implications": [], "deprecated_by": None,
                "semantic_facets": [], "polarity": None, "profile_ids": [],
                "accepted_for_compilation": False,
            }
        else:
            overlay = {
                "reviewed": True,
                "display": review["display"],
                "aliases": list(review["aliases"]),
                "implications": list(review["implications"]),
                "deprecated_by": review["deprecated_by"],
                "semantic_facets": list(review["semantic_facets"]),
                "polarity": review["polarity"],
                "profile_ids": list(review["profile_ids"]),
                "accepted_for_compilation": review["accepted_for_compilation"],
            }
            alias_count += len(review["aliases"])
            accepted_count += int(review["accepted_for_compilation"])
        entries.append({
            "tag_id": row["tag_id"],
            "source_name": row["source_name"],
            "source_category": row["source_category"],
            "source_category_value": row["source_category_value"],
            "frequency": row["frequency"],
            **overlay,
        })

    body: dict[str, Any] = {
        "schema": INDEX_SCHEMA,
        "kind": "anime-tag-taxonomy-index",
        "executable": False,
        "authority": dict(AUTHORITY),
        **AUTHORITY,
        "source": {
            key: source_contract["source"][key]
            for key in ("provider", "repository", "revision", "selected_file", "bytes", "sha256", "records")
        },
        "contracts": {
            "source_manifest_sha256": source_contract["manifest_sha256"],
            "review_manifest_sha256": review_contract["manifest_sha256"],
        },
        "counts": {
            "source": len(entries), "reviewed": len(reviews),
            "accepted": accepted_count, "aliases": alias_count,
        },
        "entries": entries,
        "notes": [
            "Known upstream does not mean reviewed or eligible for prompt compilation.",
            "Subject adulthood and content envelope are reviewed intent/canon metadata, never taxonomy inference.",
            "Source frequency is descriptive metadata, not a quality, safety or recommendation score.",
        ],
    }
    body["index_id"] = sha256(canonical_bytes(body))
    if len(render_taxonomy_index(body)) > source_contract["bounds"]["max_index_bytes"]:
        raise ValueError("Rendered taxonomy index exceeds configured byte bound")
    return body


def render_taxonomy_index(value: dict[str, Any]) -> bytes:
    """Render an index deterministically for exclusive-create persistence."""
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def _validate_identity(index: Any) -> dict[str, Any]:
    if not isinstance(index, dict) or index.get("schema") != INDEX_SCHEMA:
        raise ValueError("Unsupported taxonomy index")
    if index.get("executable") is not False:
        raise ValueError("Taxonomy index must be non-executable")
    authority(index.get("authority"), "Taxonomy index")
    if any(index.get(key) is not expected for key, expected in AUTHORITY.items()):
        raise ValueError("Taxonomy index has non-zero authority")
    index_id = index.get("index_id")
    if not isinstance(index_id, str) or SHA256.fullmatch(index_id) is None:
        raise ValueError("Taxonomy index has invalid identity")
    unsigned = dict(index)
    unsigned.pop("index_id", None)
    if sha256(canonical_bytes(unsigned)) != index_id:
        raise ValueError("Taxonomy index identity does not match content")
    return index


def validate_taxonomy_index(
    index: Any, source_bytes: bytes, root: Path | str = "."
) -> dict[str, Any]:
    """Rebuild an index and require an exact deterministic match."""
    candidate = _validate_identity(index)
    expected = build_taxonomy_index(source_bytes, root)
    if candidate != expected:
        raise ValueError("Saved taxonomy index does not match exact source and review contracts")
    return expected


def lookup_taxonomy(index: Any, term: str) -> dict[str, Any] | None:
    """Resolve a source canonical or explicitly reviewed alias in a saved index."""
    candidate = _validate_identity(index)
    query = text(term, "taxonomy lookup term", 1024)
    canonical: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, Any]] = {}
    entries = candidate.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Taxonomy index entries must be an array")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("source_name"), str):
            raise ValueError("Taxonomy index entry lacks source name")
        canonical[normalise_term(entry["source_name"])] = entry
        raw_aliases = entry.get("aliases")
        if not isinstance(raw_aliases, list) or not all(isinstance(alias, str) for alias in raw_aliases):
            raise ValueError("Taxonomy index aliases must be an array of text")
        for alias in raw_aliases:
            aliases[normalise_term(alias)] = entry
    normalised = normalise_term(query)
    entry = canonical.get(normalised)
    match_kind = "canonical"
    if entry is None:
        entry = aliases.get(normalised)
        match_kind = "alias"
    return None if entry is None else {**entry, "match_kind": match_kind, "query": query}
