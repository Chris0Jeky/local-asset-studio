"""Shared primitives for adult-illustration research-intelligence validation."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

DIR = Path("research/adult-illustration")
REQUIRED = (
    "prompt-dialects.json",
    "tag-vocabulary-example.json",
    "technique-candidates.json",
    "source-intake-example.json",
)
ROUTES = "route-candidates.json"
MAX_BYTES = 1_048_576
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
IDENT = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
MOVING = {"main", "master", "head", "latest", "trunk"}
EVIDENCE = {
    "discovered", "source_reviewed", "hash_verified", "installed",
    "graph_validated", "executed", "visually_reviewed", "task_accepted", "promoted",
}
PROMPT_MODES = {"tag", "hybrid", "instruction"}
NON_PROMPT = {
    "geometry_artifact", "appearance_adapter", "reference_binding",
    "mask_authority", "deterministic_operation", "review_decision",
}
VOCAB_STATUS = {"contract_example", "proposed", "verified", "deprecated"}
FACETS = {
    "subject_count", "identity", "body", "pose", "action", "contact", "wardrobe",
    "coverage", "expression", "camera", "composition", "environment", "lighting",
    "palette", "material", "style", "quality", "rating", "meta",
}
TECHNIQUE_CATEGORIES = {
    "appearance_adapter", "identity_adapter", "style_adapter", "geometry_preprocessor",
    "segmentation", "tag_analyzer", "captioner", "training_method", "training_runner",
    "finishing", "research_watch",
}
AVAILABILITY = {"source_available", "community_available", "not_released", "not_applicable", "unresolved"}
SNAPSHOTS = {"proposal", "source_reviewed", "pinned", "hash_verified"}
TERMS = {"unknown", "snapshotted", "restricted", "conflicting"}


class DuplicateKeyError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateKeyError(f"Duplicate JSON key {key!r}")
        value[key] = item
    return value


def _label(name: str) -> str:
    return f"{DIR.as_posix()}/{name}"


def _load(root: Path, name: str, errors: list[str], required: bool = True) -> dict[str, Any] | None:
    path = root / DIR / name
    label = _label(name)
    if not path.is_file():
        if required:
            errors.append(f"{label}: missing required manifest")
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            errors.append(f"{label}: exceeds {MAX_BYTES} bytes")
            return None
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
        errors.append(f"{label}: invalid UTF-8 JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: top level must be an object")
        return None
    return value


def _text(value: Any, limit: int = 500) -> bool:
    return isinstance(value, str) and value.strip() == value and 0 < len(value) <= limit


def _strings(value: Any, cap: int, limit: int = 500) -> bool:
    if not isinstance(value, list) or len(value) > cap:
        return False
    if not all(_text(item, limit) for item in value):
        return False
    return len(value) == len(set(value))


def _id(value: Any) -> bool:
    return isinstance(value, str) and IDENT.fullmatch(value) is not None


def _https(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and parsed.username is None


def _immutable(value: Any) -> bool:
    return isinstance(value, str) and 7 <= len(value) <= 160 and value.strip() == value and value.casefold() not in MOVING


def _common(name: str, value: dict[str, Any], schema: str, kind: str, errors: list[str]) -> None:
    label = _label(name)
    if value.get("schema") != schema:
        errors.append(f"{label}: schema must be {schema}")
    if value.get("kind") != kind:
        errors.append(f"{label}: kind must be {kind}")
    if value.get("executable") is not False:
        errors.append(f"{label}: research manifests must declare executable false")
    if value.get("authority") != "none":
        errors.append(f"{label}: research manifests must declare authority none")
    try:
        date.fromisoformat(value["research_date"])
    except (KeyError, TypeError, ValueError):
        errors.append(f"{label}: research_date must be ISO YYYY-MM-DD")
    if not isinstance(value.get("source_baseline"), str) or SHA40.fullmatch(value["source_baseline"]) is None:
        errors.append(f"{label}: source_baseline must be lowercase 40-hex")


def _items(name: str, value: Any, key: str, errors: list[str]) -> tuple[list[dict[str, Any]], set[str]]:
    label = _label(name)
    raw = value.get(key) if isinstance(value, dict) else None
    if not isinstance(raw, list) or len(raw) > 512:
        errors.append(f"{label}: {key} must be a bounded array")
        return [], set()
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"{label}: {key}[{index}] must be an object")
            continue
        item_id = item.get("id")
        if not _id(item_id) or item_id in ids:
            errors.append(f"{label}: {key}[{index}] has invalid or duplicate id")
        else:
            ids.add(item_id)
        result.append(item)
    return result, ids


def _route_ids(root: Path, errors: list[str]) -> set[str]:
    value = _load(root, ROUTES, errors)
    if value is None:
        return set()
    _, ids = _items(ROUTES, value, "candidates", errors)
    return ids


def _dialects(value: dict[str, Any], routes: set[str], errors: list[str]) -> tuple[list[dict[str, Any]], set[str]]:
    name = "prompt-dialects.json"
    label = _label(name)
    _common(name, value, "studio.adult-illustration-prompt-dialects/v0", "prompt-dialect-candidates", errors)
    if value.get("issue") != 432:
        errors.append(f"{label}: issue owner must be #432")
    profiles, ids = _items(name, value, "profiles", errors)
    for profile in profiles:
        pid = profile.get("id", "<invalid>")
        linked = profile.get("route_candidate_ids")
        if not _strings(linked, 16):
            errors.append(f"{label}: profile {pid!r} needs route_candidate_ids")
        else:
            for route in linked:
                if route not in routes:
                    errors.append(f"{label}: profile {pid!r} references unknown route {route!r}")
        mode = profile.get("mode")
        if mode not in PROMPT_MODES:
            errors.append(f"{label}: profile {pid!r} has unsupported prompt mode")
        if profile.get("evidence_state") not in EVIDENCE:
            errors.append(f"{label}: profile {pid!r} has invalid evidence state")
        if not isinstance(profile.get("ready_for_compilation"), bool):
            errors.append(f"{label}: profile {pid!r} readiness must be boolean")
        urls = profile.get("source_urls")
        if not _strings(urls, 16) or not all(_https(url) for url in urls):
            errors.append(f"{label}: profile {pid!r} source URLs must use HTTPS")
        revision = profile.get("source_revision")
        if revision is not None and not _text(revision, 160):
            errors.append(f"{label}: profile {pid!r} source revision is invalid")
        if profile.get("ready_for_compilation") and not _immutable(revision):
            errors.append(f"{label}: ready profile {pid!r} needs immutable source revision")
        separator = profile.get("tag_separator")
        if mode == "instruction" and separator is not None:
            errors.append(f"{label}: instruction profile {pid!r} cannot declare tag separator")
        if mode in {"tag", "hybrid"} and not (isinstance(separator, str) and 0 < len(separator) <= 16):
            errors.append(f"{label}: tag/hybrid profile {pid!r} needs tag separator")
        if not _strings(profile.get("ordered_sections"), 32):
            errors.append(f"{label}: profile {pid!r} needs ordered sections")
        if profile.get("negative_semantics") not in {"separate_channel", "prompt_instruction", "unsupported", "graph_specific", "unresolved"}:
            errors.append(f"{label}: profile {pid!r} has invalid negative semantics")
        if profile.get("weighting_semantics") not in {"supported", "unsupported", "graph_specific", "unresolved"}:
            errors.append(f"{label}: profile {pid!r} has invalid weighting semantics")
        if profile.get("natural_language") not in {"primary", "supported", "limited", "unsupported", "unresolved"}:
            errors.append(f"{label}: profile {pid!r} has invalid natural-language mode")
        if not _strings(profile.get("vocabulary_ids"), 512):
            errors.append(f"{label}: profile {pid!r} vocabulary IDs are invalid")
        mechanisms = profile.get("unsupported_mechanisms")
        if not _strings(mechanisms, 32) or not set(mechanisms) <= NON_PROMPT:
            errors.append(f"{label}: profile {pid!r} unsupported mechanisms are invalid")
        if not _strings(profile.get("unknowns"), 64, 1000):
            errors.append(f"{label}: profile {pid!r} needs explicit unknowns")
    return profiles, ids


def _vocabulary(value: dict[str, Any], profile_ids: set[str], errors: list[str]) -> set[str]:
    name = "tag-vocabulary-example.json"
    label = _label(name)
    _common(name, value, "studio.adult-illustration-tag-vocabulary/v0", "tag-vocabulary-contract", errors)
    if value.get("issue") != 432:
        errors.append(f"{label}: issue owner must be #432")
    if not isinstance(value.get("accepted_for_compilation"), bool):
        errors.append(f"{label}: accepted_for_compilation must be boolean")
    entries, ids = _items(name, value, "entries", errors)
    vocabulary: dict[str, str] = {}
    for entry in entries:
        eid = entry.get("id", "<invalid>")
        canonical = entry.get("canonical")
        aliases = entry.get("aliases")
        if not _text(canonical, 200) or not _text(entry.get("display"), 200):
            errors.append(f"{label}: entry {eid!r} needs canonical and display text")
        if not _strings(aliases, 32, 200):
            errors.append(f"{label}: entry {eid!r} aliases are invalid")
            aliases = []
        for term in [canonical, *aliases]:
            if not isinstance(term, str):
                continue
            normal = " ".join(term.casefold().replace("_", " ").split())
            owner = vocabulary.get(normal)
            if owner is not None and owner != eid:
                errors.append(f"{label}: vocabulary alias collision between {owner!r} and {eid!r}")
            vocabulary[normal] = eid
        if not _strings(entry.get("implications"), 32, 200):
            errors.append(f"{label}: entry {eid!r} implications are invalid")
        facets = entry.get("semantic_facets")
        if not _strings(facets, 16) or not set(facets) <= FACETS:
            errors.append(f"{label}: entry {eid!r} semantic facets are invalid")
        if entry.get("status") not in VOCAB_STATUS or not isinstance(entry.get("accepted"), bool):
            errors.append(f"{label}: entry {eid!r} status/acceptance is invalid")
        linked = entry.get("route_profile_ids")
        if not _strings(linked, 64):
            errors.append(f"{label}: entry {eid!r} route profiles are invalid")
        else:
            for profile in linked:
                if profile not in profile_ids:
                    errors.append(f"{label}: entry {eid!r} references unknown profile {profile!r}")
        source = entry.get("source")
        if not isinstance(source, dict):
            errors.append(f"{label}: entry {eid!r} source must be an object")
            source = {}
        status = entry.get("status")
        source_provenance = (
            _text(source.get("kind"), 100)
            and source.get("kind") != "contract_example"
            and _https(source.get("url"))
            and _immutable(source.get("revision"))
        )
        if status in {"verified", "deprecated"} and not source_provenance:
            errors.append(
                f"{label}: verified entry {eid!r} needs immutable source revision"
            )
        if entry.get("accepted"):
            if not value.get("accepted_for_compilation"):
                errors.append(
                    f"{label}: accepted entry {eid!r} needs top-level compilation approval"
                )
            if status != "verified":
                errors.append(
                    f"{label}: accepted entry {eid!r} needs verified status"
                )
            if not source_provenance:
                errors.append(
                    f"{label}: accepted entry {eid!r} needs immutable source provenance"
                )
    return ids


def _profile_vocab_refs(profiles: list[dict[str, Any]], vocabulary: set[str], errors: list[str]) -> None:
    label = _label("prompt-dialects.json")
    for profile in profiles:
        pid = profile.get("id", "<invalid>")
        raw = profile.get("vocabulary_ids")
        if isinstance(raw, list):
            for item in raw:
                if item not in vocabulary:
                    errors.append(f"{label}: profile {pid!r} references unknown vocabulary {item!r}")
