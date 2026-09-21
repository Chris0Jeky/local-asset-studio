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
    subtree_depth: dict[str, int] = {}

    def depth(node: str) -> int:
        if node in visiting:
            raise ValueError(f"Taxonomy {label} graph contains a cycle at {node!r}")
        cached = subtree_depth.get(node)
        if cached is not None:
            return cached
        if len(visiting) >= maximum_depth:
            raise ValueError(f"Taxonomy {label} graph exceeds depth {maximum_depth}")
        visiting.add(node)
        try:
            result = 1
            for target in graph.get(node, []):
                result = max(result, 1 + depth(target))
        finally:
            visiting.remove(node)
        subtree_depth[node] = result
        return result

    for node in sorted(graph):
        if depth(node) > maximum_depth:
            raise ValueError(f"Taxonomy {label} graph exceeds depth {maximum_depth}")


def _validate_reviewed_displays(
    source_names: set[str], reviews: list[dict[str, Any]],
) -> None:
    """Keep compiler display/alias ownership consistent with full-source lookup.

    The compiler deliberately loads only the reviewed overlay. Index construction
    and saved-index re-entry also know the unreviewed canonical namespace, so they
    must reject a reviewed display that would select a different source identity.
    """
    canonical_owner = {normalise_term(name): name for name in source_names}
    display_owner: dict[str, str] = {}
    for entry in reviews:
        name = entry["source_name"]
        display = normalise_term(entry["display"])
        if not display:
            raise ValueError(f"Taxonomy display for {name!r} is empty after normalisation")
        owner = canonical_owner.get(display) or display_owner.get(display)
        if owner is not None and owner != name:
            raise ValueError(
                f"Taxonomy display collision between {owner!r} and {name!r}"
            )
        display_owner[display] = name
    # Check after collecting every display: source/review ordering cannot decide
    # whether an alias is valid. The compiler also refuses own-display aliases.
    for entry in reviews:
        for alias in entry["aliases"]:
            owner = display_owner.get(normalise_term(alias))
            if owner is not None:
                raise ValueError(
                    f"Taxonomy alias {alias!r} collides with display owned by {owner!r}"
                )


def _validate_review(
    source_rows: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    contract: dict[str, Any],
) -> None:
    source_names = {row["source_name"] for row in source_rows}
    _validate_reviewed_displays(source_names, reviews)
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


def _validated_string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be an array of non-empty text")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} contains duplicates")
    return value


def _validate_index_structure(index: dict[str, Any]) -> None:
    expected_fields = {
        "schema", "kind", "executable", "authority", *AUTHORITY,
        "source", "contracts", "counts", "entries", "notes", "index_id",
    }
    if set(index) != expected_fields or index.get("kind") != "anime-tag-taxonomy-index":
        raise ValueError("Taxonomy index has missing, unknown or unsupported fields")

    source = index.get("source")
    source_fields = {"provider", "repository", "revision", "selected_file", "bytes", "sha256", "records"}
    if not isinstance(source, dict) or set(source) != source_fields:
        raise ValueError("Taxonomy index source has missing or unknown fields")
    if source.get("provider") != "huggingface":
        raise ValueError("Taxonomy index source provider is unsupported")
    for field in ("repository", "selected_file"):
        if not isinstance(source.get(field), str) or not source[field]:
            raise ValueError(f"Taxonomy index source {field} must be non-empty text")
    if not isinstance(source.get("revision"), str) or len(source["revision"]) != 40:
        raise ValueError("Taxonomy index source revision must be 40-hex")
    if not all(character in "0123456789abcdef" for character in source["revision"]):
        raise ValueError("Taxonomy index source revision must be lowercase 40-hex")
    if not isinstance(source.get("sha256"), str) or SHA256.fullmatch(source["sha256"]) is None:
        raise ValueError("Taxonomy index source SHA-256 is invalid")
    for field in ("bytes", "records"):
        value = source.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"Taxonomy index source {field} must be a positive integer")

    contracts = index.get("contracts")
    contract_fields = {"source_manifest_sha256", "review_manifest_sha256"}
    if not isinstance(contracts, dict) or set(contracts) != contract_fields:
        raise ValueError("Taxonomy index contracts have missing or unknown fields")
    if any(not isinstance(value, str) or SHA256.fullmatch(value) is None for value in contracts.values()):
        raise ValueError("Taxonomy index contract identity is invalid")

    counts = index.get("counts")
    count_fields = {"source", "reviewed", "accepted", "aliases"}
    if not isinstance(counts, dict) or set(counts) != count_fields:
        raise ValueError("Taxonomy index counts have missing or unknown fields")
    for field, value in counts.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Taxonomy index count {field} must be a non-negative integer")

    entries = index.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Taxonomy index entries must be an array")
    if len(entries) != counts["source"] or len(entries) != source["records"]:
        raise ValueError("Taxonomy index source count does not match entries")
    _validated_string_array(index.get("notes"), "Taxonomy index notes")

    entry_fields = {
        "tag_id", "source_name", "source_category", "source_category_value", "frequency",
        "reviewed", "display", "aliases", "implications", "deprecated_by",
        "semantic_facets", "polarity", "profile_ids", "accepted_for_compilation",
    }
    tag_ids: set[int] = set()
    canonical_names: set[str] = set()
    canonical_normalised: dict[str, str] = {}
    reviewed_count = accepted_count = alias_count = 0
    previous_sort_key: tuple[str, int] | None = None

    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != entry_fields:
            raise ValueError("Taxonomy index entry has missing or unknown fields")
        tag_id = entry.get("tag_id")
        category_value = entry.get("source_category_value")
        frequency = entry.get("frequency")
        if not isinstance(tag_id, int) or isinstance(tag_id, bool) or tag_id < 1:
            raise ValueError("Taxonomy index entry tag_id must be a positive integer")
        if tag_id in tag_ids:
            raise ValueError(f"Taxonomy index contains duplicate tag_id {tag_id}")
        tag_ids.add(tag_id)
        if not isinstance(category_value, int) or isinstance(category_value, bool) or category_value < 0:
            raise ValueError("Taxonomy index entry source_category_value is invalid")
        if not isinstance(frequency, int) or isinstance(frequency, bool) or frequency < 0:
            raise ValueError("Taxonomy index entry frequency is invalid")
        source_name = entry.get("source_name")
        category = entry.get("source_category")
        display = entry.get("display")
        if not isinstance(source_name, str) or not source_name:
            raise ValueError("Taxonomy index entry source_name must be non-empty text")
        if not isinstance(category, str) or not category:
            raise ValueError("Taxonomy index entry source_category must be non-empty text")
        if not isinstance(display, str) or not display:
            raise ValueError("Taxonomy index entry display must be non-empty text")
        normalised = normalise_term(source_name)
        if source_name in canonical_names or normalised in canonical_normalised:
            raise ValueError(f"Taxonomy index contains duplicate canonical name {source_name!r}")
        canonical_names.add(source_name)
        canonical_normalised[normalised] = source_name
        sort_key = (source_name.casefold(), tag_id)
        if previous_sort_key is not None and sort_key < previous_sort_key:
            raise ValueError("Taxonomy index entries are not deterministically sorted")
        previous_sort_key = sort_key

        reviewed = entry.get("reviewed")
        accepted = entry.get("accepted_for_compilation")
        if not isinstance(reviewed, bool) or not isinstance(accepted, bool):
            raise ValueError("Taxonomy index review flags must be boolean")
        aliases = _validated_string_array(entry.get("aliases"), f"Taxonomy index {source_name} aliases")
        implications = _validated_string_array(
            entry.get("implications"), f"Taxonomy index {source_name} implications"
        )
        facets = _validated_string_array(
            entry.get("semantic_facets"), f"Taxonomy index {source_name} semantic facets"
        )
        profiles = _validated_string_array(
            entry.get("profile_ids"), f"Taxonomy index {source_name} profile ids"
        )
        deprecated_by = entry.get("deprecated_by")
        if deprecated_by is not None and (not isinstance(deprecated_by, str) or not deprecated_by):
            raise ValueError("Taxonomy index deprecated_by must be null or non-empty text")
        polarity = entry.get("polarity")
        if polarity not in {None, "positive", "negative"}:
            raise ValueError("Taxonomy index polarity is invalid")
        if not reviewed and (
            aliases or implications or deprecated_by is not None or facets or polarity is not None
            or profiles or accepted
        ):
            raise ValueError(f"Unreviewed taxonomy entry {source_name!r} contains reviewed semantics")
        if accepted and (not reviewed or not facets or not profiles or polarity is None or deprecated_by is not None):
            raise ValueError(f"Accepted taxonomy entry {source_name!r} is incomplete or deprecated")
        reviewed_count += int(reviewed)
        accepted_count += int(accepted)
        alias_count += len(aliases)

    _validate_reviewed_displays(
        canonical_names, [entry for entry in entries if entry["reviewed"]]
    )
    alias_owner: dict[str, str] = {}
    for entry in entries:
        source_name = entry["source_name"]
        for alias in entry["aliases"]:
            normalised = normalise_term(alias)
            if not normalised or normalised in canonical_normalised:
                raise ValueError(f"Taxonomy index alias {alias!r} collides with a canonical name")
            if normalised in alias_owner:
                raise ValueError(
                    f"Taxonomy index contains duplicate alias {alias!r}; first owned by {alias_owner[normalised]!r}"
                )
            alias_owner[normalised] = source_name
        for target in entry["implications"]:
            if target not in canonical_names:
                raise ValueError(f"Taxonomy index implication target {target!r} is missing")
        replacement = entry["deprecated_by"]
        if replacement is not None and replacement not in canonical_names:
            raise ValueError(f"Taxonomy index deprecation target {replacement!r} is missing")

    expected_counts = {
        "source": len(entries),
        "reviewed": reviewed_count,
        "accepted": accepted_count,
        "aliases": alias_count,
    }
    if counts != expected_counts:
        raise ValueError("Taxonomy index counts do not match entry content")


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
    _validate_index_structure(index)
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
