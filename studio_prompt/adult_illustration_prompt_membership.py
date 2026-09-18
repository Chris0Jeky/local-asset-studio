"""Zero-authority membership inspection for compiled adult prompt inputs."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .adult_illustration_prompt_projection import validate_prompt_projection
from .adult_illustration_taxonomy import _validate_identity
from .adult_illustration_taxonomy_contracts import (
    AUTHORITY,
    canonical_bytes,
    normalise_term,
    sha256,
)

REPORT_FORMAT = "studio.adult-illustration.prompt-membership-report/v1"
MAX_INSPECTIONS = 512
MAX_REPORT_BYTES = 262_144

__all__ = [
    "REPORT_FORMAT",
    "inspect_prompt_membership",
    "validate_prompt_membership_report",
]


def _canonical(value: Any) -> bytes:
    return canonical_bytes(value)


def _validated_index(value: Any) -> dict[str, Any]:
    """Validate a saved index without implying reconstruction from source bytes."""
    return copy.deepcopy(_validate_identity(value))


def _require_compatible(
    compiled: dict[str, Any], index: dict[str, Any]
) -> None:
    taxonomy = compiled.get("taxonomy")
    if not isinstance(taxonomy, dict):
        raise ValueError("Compiled prompt lacks taxonomy identity")
    expected = {
        "source_sha256": index["source"]["sha256"],
        "source_revision": index["source"]["revision"],
        "source_manifest_sha256": index["contracts"]["source_manifest_sha256"],
        "review_manifest_sha256": index["contracts"]["review_manifest_sha256"],
        "reviewed_entries": index["counts"]["reviewed"],
    }
    actual = {key: taxonomy.get(key) for key in expected}
    if actual != expected:
        raise ValueError(
            "Taxonomy index contract identity does not match compiled prompt"
        )


def _membership_maps(
    index: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    canonical: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, Any]] = {}
    for entry in index["entries"]:
        canonical[normalise_term(entry["source_name"])] = entry
        for alias in entry["aliases"]:
            aliases[normalise_term(alias)] = entry
    return canonical, aliases


def _classification(entry: dict[str, Any] | None) -> str:
    if entry is None:
        return "not_in_pinned_source"
    if not entry["reviewed"]:
        return "source_known_unreviewed"
    if entry["accepted_for_compilation"]:
        return "source_known_reviewed_accepted"
    return "source_known_reviewed_ineligible"


def _membership(
    raw: str,
    canonical: dict[str, dict[str, Any]],
    aliases: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    normalised = normalise_term(raw)
    entry = canonical.get(normalised)
    match_kind: str | None = "canonical"
    if entry is None:
        entry = aliases.get(normalised)
        match_kind = "alias" if entry is not None else None
    return {
        "classification": _classification(entry),
        "match_kind": match_kind,
        "source_name": None if entry is None else entry["source_name"],
        "tag_id": None if entry is None else entry["tag_id"],
        "source_category": None if entry is None else entry["source_category"],
        "source_category_value": (
            None if entry is None else entry["source_category_value"]
        ),
        "frequency": None if entry is None else entry["frequency"],
        "reviewed": None if entry is None else entry["reviewed"],
        "accepted_for_compilation": (
            None if entry is None else entry["accepted_for_compilation"]
        ),
    }


def _compiler_resolution(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": value["source"],
        "status": value["status"],
        "match_kind": value["match_kind"],
        "entry_ids": copy.deepcopy(value["entry_ids"]),
        "emitted": copy.deepcopy(value["emitted"]),
        "semantic_facets": copy.deepcopy(value["semantic_facets"]),
    }


def inspect_prompt_membership(
    compiled_prompt: Any,
    source_projection: Any,
    taxonomy_index: Any,
    root: Path | str = ".",
) -> dict[str, Any]:
    """Inspect original compiler terms against one strict saved taxonomy index."""
    compiled = validate_prompt_projection(compiled_prompt, source_projection, root)
    index = _validated_index(taxonomy_index)
    _require_compatible(compiled, index)

    raw_resolutions = compiled.get("vocabulary_resolutions")
    if not isinstance(raw_resolutions, list) or len(raw_resolutions) > MAX_INSPECTIONS:
        raise ValueError("Compiled prompt has an invalid membership inspection set")
    canonical, aliases = _membership_maps(index)
    inspections: list[dict[str, Any]] = []
    counts = {
        "inputs": len(raw_resolutions),
        "source_known_reviewed_accepted": 0,
        "source_known_reviewed_ineligible": 0,
        "source_known_unreviewed": 0,
        "not_in_pinned_source": 0,
    }
    for resolution in raw_resolutions:
        if not isinstance(resolution, dict):
            raise ValueError("Compiled prompt resolution must be an object")
        channel = resolution.get("channel")
        raw = resolution.get("input")
        if channel not in {"positive", "negative"} or not isinstance(raw, str):
            raise ValueError("Compiled prompt resolution has invalid input identity")
        membership = _membership(raw, canonical, aliases)
        counts[membership["classification"]] += 1
        inspections.append(
            {
                "channel": channel,
                "input": raw,
                "normalised": normalise_term(raw),
                "compiler": _compiler_resolution(resolution),
                "membership": membership,
            }
        )

    body: dict[str, Any] = {
        "format": REPORT_FORMAT,
        "kind": "adult-prompt-taxonomy-membership-report",
        "executable": False,
        "prompt": {
            "profile_id": compiled["profile_id"],
            "compiled_sha256": compiled["compiled_sha256"],
            "source_projection_sha256": compiled["source_projection_sha256"],
            "catalog_manifest_sha256": compiled["catalog_manifest_sha256"],
        },
        "taxonomy": {
            "index_id": index["index_id"],
            "source_sha256": index["source"]["sha256"],
            "source_revision": index["source"]["revision"],
            "source_manifest_sha256": index["contracts"][
                "source_manifest_sha256"
            ],
            "review_manifest_sha256": index["contracts"][
                "review_manifest_sha256"
            ],
            "source_records": index["counts"]["source"],
            "reviewed_entries": index["counts"]["reviewed"],
            "index_identity_validated": True,
            "source_revalidated": False,
        },
        "counts": counts,
        "inspections": inspections,
        "authority": dict(AUTHORITY),
        **AUTHORITY,
        "limits": [
            "This report inspects evidence and does not alter prompt emission, "
            "vocabulary acceptance or route selection.",
            "The saved index content identity was validated, but exact source "
            "bytes were not rebuilt; source_revalidated remains false.",
            "Source membership does not establish adulthood, consent, content "
            "approval, tokenizer behavior, artistic quality or generation authority.",
        ],
    }
    body["report_sha256"] = sha256(_canonical(body))
    if len(json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Prompt membership report exceeds configured byte bound")
    return body


def validate_prompt_membership_report(
    value: Any,
    compiled_prompt: Any,
    source_projection: Any,
    taxonomy_index: Any,
    root: Path | str = ".",
) -> dict[str, Any]:
    """Recompute a retained report so changed derived evidence fails closed."""
    if not isinstance(value, dict) or value.get("format") != REPORT_FORMAT:
        raise ValueError("Unsupported prompt membership report")
    expected = inspect_prompt_membership(
        compiled_prompt, source_projection, taxonomy_index, root
    )
    if _canonical(value) != _canonical(expected):
        raise ValueError("Changed or invalid prompt membership report")
    return expected
