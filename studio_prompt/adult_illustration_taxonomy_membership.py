"""Join validated compiled-prompt traces to bounded taxonomy membership evidence."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .adult_illustration_prompt_projection import validate_prompt_projection
from .adult_illustration_taxonomy import _validate_identity
from .adult_illustration_taxonomy_contracts import (
    AUTHORITY,
    canonical_bytes,
    load_taxonomy_contracts,
    normalise_term,
    sha256,
)

SCHEMA = "studio.adult-illustration.prompt-taxonomy-membership/v1"
MAX_MEMBERSHIPS = 512
MAX_REPORT_BYTES = 1_048_576
_SOURCE_FIELDS = (
    "provider",
    "repository",
    "revision",
    "selected_file",
    "bytes",
    "sha256",
    "records",
)
_REVIEW_FIELDS = (
    "source_name",
    "display",
    "aliases",
    "implications",
    "deprecated_by",
    "semantic_facets",
    "polarity",
    "profile_ids",
    "accepted_for_compilation",
)


def _validated_evidence(
    compiled: Any,
    source_projection: Any,
    taxonomy_index: Any,
    root: Path | str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prompt = validate_prompt_projection(compiled, source_projection, root)
    index = _validate_identity(taxonomy_index)
    contracts = load_taxonomy_contracts(root)
    source_contract, review_contract = contracts["source"], contracts["review"]

    expected_source = {
        key: source_contract["source"][key] for key in _SOURCE_FIELDS
    }
    if index["source"] != expected_source:
        raise ValueError("Taxonomy index does not match the current pinned source contract")
    expected_contracts = {
        "source_manifest_sha256": source_contract["manifest_sha256"],
        "review_manifest_sha256": review_contract["manifest_sha256"],
    }
    if index["contracts"] != expected_contracts:
        raise ValueError("Taxonomy index does not match the current source/review contract")

    expected_review = {
        entry["source_name"]: {field: copy.deepcopy(entry[field]) for field in _REVIEW_FIELDS}
        for entry in review_contract["entries"]
    }
    indexed_review = {
        entry["source_name"]: {field: copy.deepcopy(entry[field]) for field in _REVIEW_FIELDS}
        for entry in index["entries"]
        if entry["reviewed"]
    }
    if indexed_review != expected_review:
        raise ValueError("Taxonomy index reviewed entries do not match the current review contract")

    taxonomy = prompt.get("taxonomy")
    if not isinstance(taxonomy, dict):
        raise ValueError("Compiled prompt is missing taxonomy provenance")
    expected_prompt_identity = {
        "source_sha256": source_contract["source"]["sha256"],
        "source_revision": source_contract["source"]["revision"],
        "source_manifest_sha256": source_contract["manifest_sha256"],
        "review_manifest_sha256": review_contract["manifest_sha256"],
        "reviewed_entries": len(review_contract["entries"]),
    }
    for key, expected in expected_prompt_identity.items():
        if taxonomy.get(key) != expected:
            raise ValueError(f"Compiled prompt taxonomy {key} does not match validated index evidence")
    if index["counts"]["reviewed"] != expected_prompt_identity["reviewed_entries"]:
        raise ValueError("Taxonomy index reviewed count does not match the compiled prompt")
    return prompt, index, contracts


def _lookups(index: dict[str, Any]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    canonical: dict[str, dict[str, Any]] = {}
    displays: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, Any]] = {}
    for entry in index["entries"]:
        canonical[normalise_term(entry["source_name"])] = entry
        if entry["reviewed"]:
            normal_display = normalise_term(entry["display"])
            owner = displays.get(normal_display)
            if owner is not None and owner["source_name"] != entry["source_name"]:
                raise ValueError("Taxonomy index reviewed display forms collide")
            displays[normal_display] = entry
            for alias in entry["aliases"]:
                aliases[normalise_term(alias)] = entry
    return canonical, displays, aliases


def _membership(
    trace: dict[str, Any],
    position: int,
    canonical: dict[str, dict[str, Any]],
    displays: dict[str, dict[str, Any]],
    aliases: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    raw = trace.get("input")
    channel = trace.get("channel")
    if not isinstance(raw, str) or not raw or channel not in {"positive", "negative"}:
        raise ValueError("Compiled prompt contains an invalid vocabulary resolution")
    normal = normalise_term(raw)
    entry = canonical.get(normal)
    match_kind: str | None = None
    if entry is not None:
        match_kind = "canonical" if raw == entry["source_name"] else "normalised_space"
    else:
        entry = displays.get(normal)
        if entry is not None:
            match_kind = "display"
        else:
            entry = aliases.get(normal)
            if entry is not None:
                match_kind = "alias"

    compiler = {
        "source": trace.get("source"),
        "status": trace.get("status"),
        "match_kind": trace.get("match_kind"),
    }
    if entry is None:
        return {
            "position": position,
            "channel": channel,
            "input": raw,
            "normalised": normal,
            "compiler": compiler,
            "membership": "absent",
            "match_kind": None,
            "source_name": None,
            "tag_id": None,
            "source_category": None,
            "frequency": None,
            "reviewed": None,
            "accepted_for_compilation": None,
        }
    return {
        "position": position,
        "channel": channel,
        "input": raw,
        "normalised": normal,
        "compiler": compiler,
        "membership": "reviewed" if entry["reviewed"] else "source_known_unreviewed",
        "match_kind": match_kind,
        "source_name": entry["source_name"],
        "tag_id": entry["tag_id"],
        "source_category": entry["source_category"],
        "frequency": entry["frequency"],
        "reviewed": entry["reviewed"],
        "accepted_for_compilation": entry["accepted_for_compilation"],
    }


def inspect_prompt_taxonomy_membership(
    compiled: Any,
    source_projection: Any,
    taxonomy_index: Any,
    root: Path | str = ".",
) -> dict[str, Any]:
    """Return deterministic source-membership evidence without execution authority."""
    prompt, index, contracts = _validated_evidence(
        compiled, source_projection, taxonomy_index, root
    )
    resolutions = prompt.get("vocabulary_resolutions")
    if not isinstance(resolutions, list) or len(resolutions) > MAX_MEMBERSHIPS:
        raise ValueError("Compiled prompt vocabulary resolutions exceed the inspection bound")
    canonical, displays, aliases = _lookups(index)
    memberships = [
        _membership(trace, position, canonical, displays, aliases)
        for position, trace in enumerate(resolutions)
    ]
    counts = {
        name: sum(item["membership"] == name for item in memberships)
        for name in ("reviewed", "source_known_unreviewed", "absent")
    }
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "compiled_sha256": prompt["compiled_sha256"],
        "source_projection_sha256": prompt["source_projection_sha256"],
        "taxonomy_index_id": index["index_id"],
        "taxonomy_source_sha256": index["source"]["sha256"],
        "source_manifest_sha256": index["contracts"]["source_manifest_sha256"],
        "review_manifest_sha256": index["contracts"]["review_manifest_sha256"],
        "source_records": index["counts"]["source"],
        "reviewed_entries": index["counts"]["reviewed"],
        "source_revalidated": False,
        "memberships": memberships,
        "counts": counts,
        "authority": dict(AUTHORITY),
        "limits": [
            "The report validates index structure and content identity but does not rebuild it from retained source bytes.",
            "Membership does not promote a term, alter the compiled prompt, certify tokenizer behavior or authorize generation.",
            "Unreviewed source membership is descriptive evidence, not semantic, safety or quality approval.",
        ],
    }
    # Retain the loaded contracts in the validation path without copying their
    # full contents into the bounded report.
    if contracts["source"]["source"]["sha256"] != result["taxonomy_source_sha256"]:
        raise ValueError("Taxonomy source identity changed during membership inspection")
    result["report_sha256"] = sha256(canonical_bytes(result))
    if len(canonical_bytes(result)) > MAX_REPORT_BYTES:
        raise ValueError("Taxonomy membership report exceeds 1 MiB")
    return result


__all__ = ["SCHEMA", "inspect_prompt_taxonomy_membership"]
