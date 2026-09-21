"""Reviewed taxonomy overlay for deterministic adult prompt compilation."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .adult_illustration_taxonomy_contracts import (
    load_taxonomy_contracts,
    normalise_term,
)

__all__ = [
    "load_prompt_taxonomy",
    "resolve_prompt_taxonomy",
    "taxonomy_identity",
]


def _validate_graph(graph: dict[str, list[str]], label: str, limit: int) -> None:
    visiting: set[str] = set()
    depths: dict[str, int] = {}

    def visit(node: str) -> int:
        if node in visiting:
            raise ValueError(f"Taxonomy prompt {label} graph contains a cycle at {node!r}")
        if node in depths:
            return depths[node]
        visiting.add(node)
        depth = max(
            [1, *(1 + visit(target) for target in graph.get(node, []))]
        )
        visiting.remove(node)
        if depth > limit:
            raise ValueError(f"Taxonomy prompt {label} graph exceeds depth {limit}")
        depths[node] = depth
        return depth

    for node in sorted(graph):
        visit(node)


def _build_lookup(entries: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    canonicals = {normalise_term(name): name for name in entries}
    if len(canonicals) != len(entries):
        raise ValueError("Taxonomy prompt canonical collision")

    displays: dict[str, str] = {}
    for name, entry in entries.items():
        normal = normalise_term(entry["display"])
        owner = canonicals.get(normal) or displays.get(normal)
        if owner is not None and owner != name:
            raise ValueError(
                f"Taxonomy prompt display collision between {owner!r} and {name!r}"
            )
        displays[normal] = name

    aliases: dict[str, str] = {}
    for name, entry in entries.items():
        for alias in entry["aliases"]:
            normal = normalise_term(alias)
            owner = canonicals.get(normal) or displays.get(normal) or aliases.get(normal)
            if owner is not None:
                raise ValueError(
                    f"Taxonomy prompt alias collision for {alias!r}: "
                    f"{name!r} conflicts with {owner!r}"
                )
            aliases[normal] = name

    for normal, name in canonicals.items():
        lookup[normal] = {"source_name": name, "match_kind": "source_name"}
    for normal, name in displays.items():
        lookup.setdefault(normal, {"source_name": name, "match_kind": "display"})
    for normal, name in aliases.items():
        lookup[normal] = {"source_name": name, "match_kind": "alias"}
    return lookup


def _validate_relationships(entries: dict[str, dict[str, Any]], limit: int) -> None:
    for name, entry in entries.items():
        profiles = set(entry["profile_ids"])
        for target_name in entry["implications"]:
            target = entries.get(target_name)
            if target is None:
                raise ValueError(
                    f"Taxonomy prompt implication target {target_name!r} is not reviewed"
                )
            if target["polarity"] != entry["polarity"]:
                raise ValueError(
                    f"Taxonomy prompt implication {name!r} -> {target_name!r} "
                    "changes polarity"
                )
            if not profiles <= set(target["profile_ids"]):
                raise ValueError(
                    f"Taxonomy prompt implication {name!r} -> {target_name!r} "
                    "loses profile support"
                )
        replacement = entry["deprecated_by"]
        if replacement is not None and replacement not in entries:
            raise ValueError(
                f"Taxonomy prompt deprecation target {replacement!r} is not reviewed"
            )

    _validate_graph(
        {name: list(entry["implications"]) for name, entry in entries.items()},
        "implication",
        limit,
    )
    _validate_graph(
        {
            name: [] if entry["deprecated_by"] is None else [entry["deprecated_by"]]
            for name, entry in entries.items()
        },
        "deprecation",
        limit,
    )


def load_prompt_taxonomy(root: Path | str = ".") -> dict[str, Any]:
    """Load the checked-in review without the external CSV or generated index."""
    contracts = load_taxonomy_contracts(root)
    source, review = contracts["source"], contracts["review"]
    entries = {
        entry["source_name"]: copy.deepcopy(entry) for entry in review["entries"]
    }
    _validate_relationships(entries, source["bounds"]["max_relationship_depth"])
    return {
        "source_sha256": source["source"]["sha256"],
        "source_revision": source["source"]["revision"],
        "source_manifest_sha256": source["manifest_sha256"],
        "review_manifest_sha256": review["manifest_sha256"],
        "profile_ids": list(source["profile_ids"]),
        "reviewed_entries": len(entries),
        "entries": entries,
        "lookup": _build_lookup(entries),
    }


def _closure(taxonomy: dict[str, Any], source_name: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        entry = taxonomy["entries"][name]
        result.append(entry)
        for target in entry["implications"]:
            visit(target)

    visit(source_name)
    return result


def _diagnostic(
    code: str, message: str, raw: str, entry: dict[str, Any], **fields: Any
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "warning",
        "message": message,
        "term": raw,
        "source_name": entry["source_name"],
        **fields,
    }


def _trace(
    raw: str,
    channel: str,
    status: str,
    match_kind: str,
    entries: list[dict[str, Any]],
    emitted: list[str],
) -> dict[str, Any]:
    facets: list[str] = []
    for entry in entries:
        for facet in entry["semantic_facets"]:
            if facet not in facets:
                facets.append(facet)
    return {
        "channel": channel,
        "input": raw,
        "normalised": normalise_term(raw),
        "source": "reviewed_taxonomy",
        "status": status,
        "match_kind": match_kind,
        "entry_ids": [entry["source_name"] for entry in entries],
        "emitted": emitted,
        "semantic_facets": facets,
    }


def _rejected(
    raw: str,
    channel: str,
    match_kind: str,
    entry: dict[str, Any],
    status: str,
    code: str,
    message: str,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "entries": [],
        "trace": _trace(raw, channel, status, match_kind, [entry], []),
        "diagnostics": [_diagnostic(code, message, raw, entry, **fields)],
    }


def resolve_prompt_taxonomy(
    taxonomy: dict[str, Any],
    raw: str,
    *,
    channel: str,
    expected_polarity: str,
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve one term. A taxonomy match is authoritative, including rejection."""
    match = taxonomy["lookup"].get(normalise_term(raw))
    if match is None:
        return None
    root = taxonomy["entries"][match["source_name"]]
    kind = match["match_kind"]

    if root["deprecated_by"] is not None:
        return _rejected(
            raw, channel, kind, root, "deprecated", "TAXONOMY_DEPRECATED_TERM",
            f"Term {raw!r} resolves to deprecated taxonomy entry "
            f"{root['source_name']!r} and was not emitted.",
            deprecated_by=root["deprecated_by"],
        )
    if not root["accepted_for_compilation"]:
        return _rejected(
            raw, channel, kind, root, "not_accepted", "TAXONOMY_TERM_NOT_ACCEPTED",
            f"Term {raw!r} is reviewed but not accepted for prompt compilation.",
        )
    if root["polarity"] != expected_polarity:
        return _rejected(
            raw, channel, kind, root, "polarity_mismatch",
            "TAXONOMY_POLARITY_MISMATCH",
            f"Term {raw!r} resolves to {root['polarity']} taxonomy and was not "
            f"emitted in the {expected_polarity} channel.",
            expected_polarity=expected_polarity,
            actual_polarity=root["polarity"],
        )
    if profile["id"] not in root["profile_ids"]:
        return _rejected(
            raw, channel, kind, root, "unsupported_profile",
            "TAXONOMY_UNSUPPORTED_FOR_PROFILE",
            f"Term {raw!r} is reviewed but not accepted for profile "
            f"{profile['id']!r}.",
            profile_id=profile["id"],
        )

    closure = _closure(taxonomy, root["source_name"])
    prompt_entries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    emitted: list[str] = []
    rejected_status: str | None = None
    ordered_facets = set(profile["facet_order"])
    for entry in closure:
        status: tuple[str, str, str, dict[str, Any]] | None = None
        if not entry["accepted_for_compilation"]:
            status = (
                "implication_not_accepted",
                "TAXONOMY_IMPLICATION_NOT_ACCEPTED",
                f"Taxonomy implication {entry['source_name']!r} is not accepted.",
                {},
            )
        elif entry["polarity"] != expected_polarity:
            status = (
                "polarity_mismatch",
                "TAXONOMY_POLARITY_MISMATCH",
                f"Taxonomy implication {entry['source_name']!r} changes polarity.",
                {"actual_polarity": entry["polarity"]},
            )
        elif profile["id"] not in entry["profile_ids"]:
            status = (
                "unsupported_profile",
                "TAXONOMY_UNSUPPORTED_FOR_PROFILE",
                f"Taxonomy implication {entry['source_name']!r} is unavailable "
                f"to profile {profile['id']!r}.",
                {"profile_id": profile["id"]},
            )
        elif not ordered_facets.intersection(entry["semantic_facets"]):
            status = (
                "unordered_for_profile",
                "TAXONOMY_UNORDERED_FOR_PROFILE",
                f"Taxonomy entry {entry['source_name']!r} has no profile ordering facet.",
                {"profile_id": profile["id"]},
            )

        if status is not None:
            rejected_status = rejected_status or status[0]
            diagnostics.append(
                _diagnostic(status[1], status[2], raw, entry, **status[3])
            )
            continue

        rendered = (
            entry["source_name"]
            if profile["mode"] == "tag"
            else entry["display"]
            if profile["mode"] == "hybrid"
            else None
        )
        if rendered is None:
            rejected_status = rejected_status or "not_emitted"
            continue
        emitted.append(rendered)
        prompt_entries.append(
            {
                "source": "reviewed_taxonomy",
                "id": entry["source_name"],
                "canonical": rendered,
                "facets": list(entry["semantic_facets"]),
            }
        )

    result_status = (
        "partially_emitted"
        if prompt_entries and rejected_status
        else "emitted"
        if prompt_entries
        else rejected_status or "not_emitted"
    )
    return {
        "entries": prompt_entries,
        "trace": _trace(raw, channel, result_status, kind, closure, emitted),
        "diagnostics": diagnostics,
    }


def taxonomy_identity(
    taxonomy: dict[str, Any], resolutions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return bounded provenance for the compiled artifact."""
    return {
        "source_sha256": taxonomy["source_sha256"],
        "source_revision": taxonomy["source_revision"],
        "source_manifest_sha256": taxonomy["source_manifest_sha256"],
        "review_manifest_sha256": taxonomy["review_manifest_sha256"],
        "reviewed_entries": taxonomy["reviewed_entries"],
        "used_for_emission": any(
            item["source"] == "reviewed_taxonomy" and item["emitted"]
            for item in resolutions
        ),
        "source_bytes_loaded": False,
        "generated_index_loaded": False,
    }
