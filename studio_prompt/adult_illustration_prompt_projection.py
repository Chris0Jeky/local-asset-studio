"""Deterministic, zero-authority prompt projections for reviewed adult illustration intent."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .adult_illustration_projection import validate_projection
from .adult_illustration_prompt_catalog import load_catalog
from .adult_illustration_prompt_common import AUTHORITY, FORMAT, MAX_DIAGNOSTICS, _normalise_term

MAX_OUTPUT_BYTES = 131_072
MAX_TEXT = 16_384
MAX_ITEMS = 256


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, label: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded non-empty text")
    if any(ord(character) < 32 and character not in "\n\t\r" for character in value):
        raise ValueError(f"{label} contains a control character")
    return value.strip()


def _strings(value: Any, label: str, *, maximum: int = MAX_ITEMS, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{label} must be a bounded array")
    result = [_text(item, label, 1000) for item in value]
    if not allow_empty and not result:
        raise ValueError(f"{label} must not be empty")
    return result


def _validate_source_projection(value: Any) -> dict[str, Any]:
    try:
        source = validate_projection(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid adult illustration source projection: {exc}") from exc
    if source.get("state") == "blocked" or not isinstance(source.get("creative_intent"), dict):
        raise ValueError("Blocked adult illustration projection cannot compile a prompt")
    content = source["intent"]["content"]
    if content.get("adult_assertion") != "reviewed_owner_or_canon":
        raise ValueError("Prompt projection requires reviewed adult owner or canon metadata")
    if content.get("class") != "sensual_non_explicit":
        raise ValueError("This prompt profile slice supports only the sensual non-explicit content envelope")
    creative = source["creative_intent"]
    required = {"brief", "facets", "tags", "avoid", "constraints", "references"}
    if not required <= creative.keys():
        raise ValueError("CreativeIntent projection is missing required fields")
    _text(creative["brief"], "creative brief")
    if not isinstance(creative["facets"], dict) or len(creative["facets"]) > 32:
        raise ValueError("CreativeIntent facets must be a bounded object")
    for key, item in creative["facets"].items():
        _text(key, "facet name", 64)
        _text(item, f"facet {key}")
    _strings(creative["tags"], "creative tags")
    _strings(creative["avoid"], "creative avoidance terms")
    if not isinstance(creative["constraints"], list) or len(creative["constraints"]) > MAX_ITEMS:
        raise ValueError("CreativeIntent constraints must be a bounded array")
    if not isinstance(creative["references"], list) or len(creative["references"]) > 12:
        raise ValueError("CreativeIntent references must be a bounded array")
    return copy.deepcopy(source)


def _diag(diagnostics: list[dict[str, Any]], code: str, severity: str, message: str, **fields: Any) -> None:
    if len(diagnostics) >= MAX_DIAGNOSTICS:
        raise ValueError("Prompt projection produced too many diagnostics")
    diagnostics.append({"code": code, "severity": severity, "message": message, **fields})


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normal = _normalise_term(item)
        if normal not in seen:
            seen.add(normal)
            result.append(item)
    return result


def _entry_closure(entry_id: str, entries: dict[str, dict[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    def visit(current: str) -> None:
        if current in seen:
            return
        seen.add(current)
        result.append(current)
        for implied in entries[current]["implications"]:
            visit(implied)

    visit(entry_id)
    return result


def _resolve_terms(
    raw_terms: list[str],
    *,
    expected_polarity: str,
    profile_id: str,
    catalog: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries = catalog["entries"]
    aliases = catalog["aliases"]
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_terms:
        normalized = _normalise_term(raw)
        entry_id = aliases.get(normalized)
        if entry_id is None:
            _diag(
                diagnostics,
                "UNKNOWN_VOCABULARY" if expected_polarity == "positive" else "UNKNOWN_AVOID_TERM",
                "warning",
                f"Term {raw!r} is not in the pinned vocabulary and was not emitted.",
                term=raw,
            )
            continue
        for closure_id in _entry_closure(entry_id, entries):
            entry = entries[closure_id]
            if entry["polarity"] != expected_polarity:
                _diag(
                    diagnostics,
                    "VOCABULARY_POLARITY_MISMATCH",
                    "warning",
                    f"Term {raw!r} resolves to {entry['polarity']} vocabulary and was not emitted in the {expected_polarity} channel.",
                    term=raw,
                    entry_id=closure_id,
                )
                continue
            if profile_id not in entry["profile_ids"]:
                _diag(
                    diagnostics,
                    "VOCABULARY_UNSUPPORTED_FOR_PROFILE",
                    "warning",
                    f"Term {raw!r} is not verified for profile {profile_id!r}.",
                    term=raw,
                    entry_id=closure_id,
                    profile_id=profile_id,
                )
                continue
            if closure_id not in seen:
                seen.add(closure_id)
                resolved.append(entry)
    return resolved


def _ordered_tags(entries: list[dict[str, Any]], profile: dict[str, Any]) -> list[str]:
    rank = {facet: index for index, facet in enumerate(profile["facet_order"])}
    return [
        entry["canonical"]
        for _, entry in sorted(
            enumerate(entries),
            key=lambda pair: (rank.get(pair[1]["facet"], len(rank)), pair[0]),
        )
    ]


def _control_diagnostics(source: dict[str, Any], diagnostics: list[dict[str, Any]]) -> bool:
    requires_binding = False
    plan = source.get("control_plan", [])
    if not isinstance(plan, list) or len(plan) > MAX_ITEMS:
        raise ValueError("Control plan must be a bounded array")
    for control in plan:
        if not isinstance(control, dict):
            raise ValueError("Control plan entry must be an object")
        if control.get("status") == "requires_route_binding":
            requires_binding = True
            control_id = _text(control.get("id"), "control id", 128)
            mechanism = _text(control.get("mechanism"), "control mechanism", 128)
            _diag(
                diagnostics,
                "CONTROL_REQUIRES_ROUTE_BINDING",
                "requirement",
                f"Control {control_id!r} uses {mechanism!r} and was not converted into prompt prose.",
                control_id=control_id,
                mechanism=mechanism,
            )
    return requires_binding


def _validate_reference(reference: Any, index: int) -> dict[str, Any]:
    if not isinstance(reference, dict):
        raise ValueError(f"Reference {index} must be an object")
    reference_id = _text(reference.get("id"), f"reference {index} id", 128)
    role = _text(reference.get("role"), f"reference {reference_id} role", 64)
    sha256 = reference.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise ValueError(f"Reference {reference_id!r} needs a lowercase SHA-256")
    take = _strings(reference.get("take"), f"reference {reference_id} take", maximum=64)
    ignore = _strings(reference.get("ignore"), f"reference {reference_id} ignore", maximum=64)
    return {
        "index": index,
        "id": reference_id,
        "role": role,
        "sha256": sha256,
        "take": take,
        "ignore": ignore,
    }


def _reference_bindings(
    creative: dict[str, Any], profile: dict[str, Any], diagnostics: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    references = creative["references"]
    minimum = profile.get("min_references", 0)
    maximum = profile["max_references"]
    if len(references) < minimum:
        raise ValueError(f"Profile {profile['id']!r} requires at least {minimum} reference(s)")
    if len(references) > maximum:
        raise ValueError(f"Profile {profile['id']!r} supports at most {maximum} references")
    bindings = [_validate_reference(item, index) for index, item in enumerate(references, start=1)]
    requires_binding = bool(bindings)
    if profile["mode"] != "instruction":
        for binding in bindings:
            _diag(
                diagnostics,
                "REFERENCE_REQUIRES_ROUTE_BINDING",
                "requirement",
                f"Reference {binding['id']!r} retains role ownership but this prompt projection does not bind a model input.",
                reference_id=binding["id"],
                role=binding["role"],
            )
    elif bindings:
        _diag(
            diagnostics,
            "REFERENCE_STAGING_REQUIRED",
            "requirement",
            "Instruction ownership is compiled, but exact image staging and native graph slots remain a reviewed route binding.",
        )
    return bindings, requires_binding


def _hybrid_prose(creative: dict[str, Any], profile: dict[str, Any]) -> str:
    parts = [_text(creative["brief"], "creative brief")]
    facets = creative["facets"]
    ordered_sources = sorted(
        profile["facet_sources"],
        key=lambda source: profile["facet_order"].index(profile["facet_sources"][source]),
    )
    for source in ordered_sources:
        if source in facets:
            parts.append(f"{source.replace('_', ' ').title()}: {facets[source]}")
    return ". ".join(part.rstrip(". ") for part in parts) + "."


def _compile_tag_channels(
    creative: dict[str, Any],
    profile: dict[str, Any],
    catalog: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, str | None]:
    positive_entries = _resolve_terms(
        creative["tags"], expected_polarity="positive", profile_id=profile["id"],
        catalog=catalog, diagnostics=diagnostics,
    )
    negative_entries = _resolve_terms(
        creative["avoid"], expected_polarity="negative", profile_id=profile["id"],
        catalog=catalog, diagnostics=diagnostics,
    )
    positive_items = _dedupe([
        *profile["positive_prefix"],
        *_ordered_tags(positive_entries, profile),
        *profile["positive_suffix"],
    ])
    negative_items = _dedupe([
        *[entry["canonical"] for entry in negative_entries],
        *profile["negative_suffix"],
    ])
    separator = profile["separator"]
    positive = separator.join(positive_items)
    if profile["mode"] == "hybrid":
        prose = _hybrid_prose(creative, profile)
        positive = f"{positive}. {prose}" if positive else prose
    return {
        "positive": positive or None,
        "negative": separator.join(negative_items) or None,
        "instruction": None,
    }


def _compile_instruction(
    creative: dict[str, Any],
    bindings: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> dict[str, str | None]:
    lines = [
        "Create a new adult-only sensual non-explicit illustration.",
        f"Goal: {_text(creative['brief'], 'creative brief')}",
    ]
    for binding in bindings:
        take = ", ".join(binding["take"]) if binding["take"] else "the reviewed role only"
        ignore = ", ".join(binding["ignore"]) if binding["ignore"] else "all unlisted source traits"
        lines.append(
            f"Image {binding['index']} defines only {binding['role']}. "
            f"Use: {take}. Do not copy: {ignore}."
        )
    for key, value in creative["facets"].items():
        lines.append(f"{key.replace('_', ' ').title()}: {value}")
    for constraint in creative["constraints"]:
        if not isinstance(constraint, dict):
            raise ValueError("CreativeIntent constraint must be an object")
        text = _text(constraint.get("text"), "constraint text")
        lines.append(f"Preserve: {text}")
    if creative["avoid"]:
        lines.append("Exclude: " + ", ".join(creative["avoid"]) + ".")
    if creative["tags"]:
        _diag(
            diagnostics,
            "TAGS_NOT_EMITTED_FOR_INSTRUCTION_PROFILE",
            "information",
            "Tag vocabulary remains inspectable but is not dumped into the natural-language instruction profile.",
        )
    return {"positive": None, "negative": None, "instruction": "\n".join(lines)}


def compile_prompt(source_projection: Any, profile_id: str, root: Path | str) -> dict[str, Any]:
    """Compile a reviewed projection into deterministic, non-executing model-profile text."""
    source = _validate_source_projection(source_projection)
    catalog = load_catalog(root)
    if profile_id not in catalog["profiles"]:
        raise ValueError(f"Unknown prompt profile {profile_id!r}")
    profile = catalog["profiles"][profile_id]
    creative = source["creative_intent"]
    diagnostics: list[dict[str, Any]] = []
    control_binding = _control_diagnostics(source, diagnostics)
    bindings, reference_binding = _reference_bindings(creative, profile, diagnostics)
    if profile["mode"] == "instruction":
        channels = _compile_instruction(creative, bindings, diagnostics)
    else:
        channels = _compile_tag_channels(creative, profile, catalog, diagnostics)
    state = "requires_binding" if control_binding or reference_binding else "review_required"
    result: dict[str, Any] = {
        "format": FORMAT,
        "profile_id": profile_id,
        "route_candidate_id": profile["route_candidate_id"],
        "mode": profile["mode"],
        "state": state,
        "source_projection_sha256": source.get("projection_sha256"),
        "source_document_sha256": _digest(source),
        "catalog_manifest_sha256": catalog["manifest_sha256"],
        "profile_source": {
            "source_url": profile["source_url"],
            "source_revision": profile["source_revision"],
            "documentation_url": profile["documentation_url"],
            "documentation_revision": profile["documentation_revision"],
        },
        "channels": channels,
        "reference_bindings": bindings,
        "diagnostics": diagnostics,
        "authority": copy.deepcopy(AUTHORITY),
        "limits": [
            "This artifact formats reviewed intent; it is not an executable graph, route binding, resource reservation or approval.",
            "Prompt syntax, source review and deterministic tests do not establish artistic quality or local runtime compatibility.",
            "Adult status, consent context, coverage, artistic acceptance, rights and promotion remain separately reviewed facts.",
        ],
    }
    result["compiled_sha256"] = _digest(result)
    if len(_canonical(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("Prompt projection exceeds the 128 KiB contract")
    return result


def validate_prompt_projection(
    value: Any, source_projection: Any, root: Path | str
) -> dict[str, Any]:
    """Recompile a prompt projection so changed derived records fail closed."""
    if not isinstance(value, dict):
        raise ValueError("Prompt projection must be an object")
    profile_id = value.get("profile_id")
    if not isinstance(profile_id, str):
        raise ValueError("Prompt projection is missing a profile id")
    expected = compile_prompt(source_projection, profile_id, root)
    if _canonical(value) != _canonical(expected):
        raise ValueError("Changed or invalid prompt projection")
    return expected
