"""Strict loader for the checked-in adult prompt-profile catalog."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from .adult_illustration_prompt_common import (
    AUTHORITY, MANIFEST, MAX_ENTRIES, MAX_MANIFEST_BYTES, MAX_PROFILES,
    MODES, POLARITIES, SHA40, DuplicateKeyError, _https, _id,
    _normalise_term, _pairs, _reject_constant, _strings, _text,
)


def _manifest_path(root: Path | str) -> Path:
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ValueError("Repository root must be a directory")
    path = root_path
    for part in MANIFEST.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Prompt-profile manifest cannot use a symlink: {path}")
    resolved = path.resolve(strict=True)
    expected_parent = (root_path / MANIFEST.parent).resolve(strict=True)
    if resolved.parent != expected_parent or not resolved.is_file():
        raise ValueError("Prompt-profile manifest escapes its repository directory")
    return resolved


def _load_raw(root: Path | str) -> tuple[dict[str, Any], str]:
    path = _manifest_path(root)
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError(f"Prompt-profile manifest exceeds {MAX_MANIFEST_BYTES} bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        raise ValueError(f"Invalid prompt-profile manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Prompt-profile manifest top level must be an object")
    return value, hashlib.sha256(raw).hexdigest()


def _validate_authority(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict) or set(value) != set(AUTHORITY):
        raise ValueError("Prompt-profile manifest has an invalid authority declaration")
    for key, expected in AUTHORITY.items():
        if value.get(key) is not expected:
            raise ValueError(f"Prompt-profile manifest must keep {key} false")
    return dict(AUTHORITY)


def _validate_profile(item: Any, profile_ids: set[str]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("Prompt profile must be an object")
    required = {
        "id",
        "route_candidate_id",
        "mode",
        "source_url",
        "source_revision",
        "documentation_url",
        "documentation_revision",
        "separator",
        "facet_order",
        "facet_sources",
        "positive_prefix",
        "positive_suffix",
        "negative_suffix",
        "natural_language",
        "max_references",
        "tokenizer",
        "notes",
    }
    optional = {"min_references"}
    if not required <= item.keys() <= required | optional:
        raise ValueError("Prompt profile has missing or unknown fields")
    profile_id = _id(item["id"], "profile id")
    if profile_id in profile_ids:
        raise ValueError(f"Duplicate prompt profile {profile_id!r}")
    profile_ids.add(profile_id)
    _id(item["route_candidate_id"], f"profile {profile_id} route")
    if item["mode"] not in MODES:
        raise ValueError(f"Profile {profile_id!r} has unsupported mode")
    _https(item["source_url"], f"profile {profile_id} source URL")
    _https(item["documentation_url"], f"profile {profile_id} documentation URL")
    if not isinstance(item["source_revision"], str) or SHA40.fullmatch(item["source_revision"]) is None:
        raise ValueError(f"Profile {profile_id!r} needs a pinned 40-hex source revision")
    if not isinstance(item["documentation_revision"], str) or SHA40.fullmatch(item["documentation_revision"]) is None:
        raise ValueError(f"Profile {profile_id!r} needs a pinned 40-hex documentation revision")
    separator = item["separator"]
    if item["mode"] == "instruction":
        if separator is not None:
            raise ValueError(f"Instruction profile {profile_id!r} cannot use a tag separator")
    elif not isinstance(separator, str) or not separator or len(separator) > 16:
        raise ValueError(f"Tag profile {profile_id!r} needs a bounded separator")
    facet_order = _strings(item["facet_order"], f"profile {profile_id} facet order", 32, 64)
    if not isinstance(item["facet_sources"], dict) or len(item["facet_sources"]) > 32:
        raise ValueError(f"Profile {profile_id!r} facet_sources must be bounded")
    for source, target in item["facet_sources"].items():
        _text(source, f"profile {profile_id} facet source", 64)
        _text(target, f"profile {profile_id} facet target", 64)
        if target not in facet_order:
            raise ValueError(f"Profile {profile_id!r} maps to an unordered facet {target!r}")
    _strings(item["positive_prefix"], f"profile {profile_id} positive prefix", 32, 120)
    _strings(item["positive_suffix"], f"profile {profile_id} positive suffix", 32, 120)
    _strings(item["negative_suffix"], f"profile {profile_id} negative suffix", 64, 120)
    if not isinstance(item["natural_language"], bool):
        raise ValueError(f"Profile {profile_id!r} natural_language must be boolean")
    minimum = item.get("min_references", 0)
    maximum = item["max_references"]
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or minimum < 0
        or maximum < minimum
        or maximum > 12
    ):
        raise ValueError(f"Profile {profile_id!r} has invalid reference bounds")
    if item["tokenizer"] is not None:
        _text(item["tokenizer"], f"profile {profile_id} tokenizer", 256)
    _strings(item["notes"], f"profile {profile_id} notes", 16, 1000)
    return copy.deepcopy(item)


def _validate_entry(item: Any, entry_ids: set[str], profile_ids: set[str]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("Vocabulary entry must be an object")
    required = {
        "id",
        "canonical",
        "aliases",
        "implications",
        "facet",
        "polarity",
        "profile_ids",
    }
    if set(item) != required:
        raise ValueError("Vocabulary entry has missing or unknown fields")
    entry_id = _id(item["id"], "vocabulary entry id")
    if entry_id in entry_ids:
        raise ValueError(f"Duplicate vocabulary entry {entry_id!r}")
    entry_ids.add(entry_id)
    canonical_term = _text(item["canonical"], f"entry {entry_id} canonical", 120)
    if canonical_term != canonical_term.strip() or canonical_term != canonical_term.casefold():
        raise ValueError(f"Entry {entry_id!r} canonical form must be trimmed lowercase text")
    _strings(item["aliases"], f"entry {entry_id} aliases", 32, 120)
    implications = _strings(item["implications"], f"entry {entry_id} implications", 32, 128)
    for target in implications:
        _id(target, f"entry {entry_id} implication")
    _text(item["facet"], f"entry {entry_id} facet", 64)
    if item["polarity"] not in POLARITIES:
        raise ValueError(f"Entry {entry_id!r} has invalid polarity")
    supported = _strings(item["profile_ids"], f"entry {entry_id} profiles", MAX_PROFILES, 128)
    if not supported:
        raise ValueError(f"Entry {entry_id!r} needs at least one profile")
    unknown = set(supported) - profile_ids
    if unknown:
        raise ValueError(f"Entry {entry_id!r} references unknown profile(s): {sorted(unknown)}")
    return copy.deepcopy(item)


def _alias_map(entries: dict[str, dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry_id, entry in entries.items():
        for term in [entry["canonical"], *entry["aliases"]]:
            normal = _normalise_term(term)
            owner = result.get(normal)
            if owner is not None and owner != entry_id:
                raise ValueError(
                    f"Vocabulary alias collision between {owner!r} and {entry_id!r} for {term!r}"
                )
            result[normal] = entry_id
    return result


def _validate_implications(entries: dict[str, dict[str, Any]]) -> None:
    known_ids = set(entries)
    for entry_id, entry in entries.items():
        unknown = set(entry["implications"]) - known_ids
        if unknown:
            raise ValueError(f"Entry {entry_id!r} implies unknown vocabulary: {sorted(unknown)}")
        source_profiles = set(entry["profile_ids"])
        for target_id in entry["implications"]:
            target = entries[target_id]
            target_profiles = set(target["profile_ids"])
            if not source_profiles <= target_profiles:
                raise ValueError(
                    f"Vocabulary implication profile mismatch: {entry_id!r} implies "
                    f"{target_id!r}, which is unavailable to {sorted(source_profiles - target_profiles)}"
                )
            if entry["polarity"] != target["polarity"]:
                raise ValueError(
                    f"Vocabulary implication polarity mismatch: {entry_id!r} is "
                    f"{entry['polarity']} but {target_id!r} is {target['polarity']}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    # Explicit DFS frames preserve recursion's active-path cycle semantics while
    # accepting every graph within the manifest/entry bounds, independent of the
    # interpreter's call-stack limit. Shared tails are validated only once.
    for entry_id in entries:
        if entry_id in visited:
            continue
        visiting.add(entry_id)
        stack: list[tuple[str, Iterator[str]]] = [
            (entry_id, iter(entries[entry_id]["implications"]))
        ]
        while stack:
            current, children = stack[-1]
            target = next(children, None)
            if target is None:
                stack.pop()
                visiting.remove(current)
                visited.add(current)
                continue
            if target in visiting:
                raise ValueError(f"Vocabulary implication cycle contains {target!r}")
            if target not in visited:
                visiting.add(target)
                stack.append((target, iter(entries[target]["implications"])))


def load_catalog(root: Path | str) -> dict[str, Any]:
    """Load and strictly validate the checked-in prompt-profile catalog."""

    value, manifest_sha256 = _load_raw(root)
    required = {
        "schema",
        "kind",
        "executable",
        "authority",
        "research_date",
        "source_baseline",
        "issue",
        "profiles",
        "entries",
        "notes",
    }
    if set(value) != required:
        raise ValueError("Prompt-profile manifest has missing or unknown fields")
    if value["schema"] != "studio.adult-illustration-prompt-profile-vocabulary/v1":
        raise ValueError("Unsupported prompt-profile manifest schema")
    if value["kind"] != "prompt-profile-vocabulary":
        raise ValueError("Unsupported prompt-profile manifest kind")
    if value["executable"] is not False:
        raise ValueError("Prompt-profile manifest must be non-executable")
    authority = _validate_authority(value["authority"])
    _text(value["research_date"], "research date", 32)
    if not isinstance(value["source_baseline"], str) or SHA40.fullmatch(value["source_baseline"]) is None:
        raise ValueError("Prompt-profile manifest needs a 40-hex source baseline")
    if value["issue"] != 437:
        raise ValueError("Prompt-profile manifest issue owner must be #437")
    if not isinstance(value["profiles"], list) or not 1 <= len(value["profiles"]) <= MAX_PROFILES:
        raise ValueError("Prompt-profile manifest profiles must be a bounded non-empty array")
    profile_ids: set[str] = set()
    profiles: dict[str, dict[str, Any]] = {}
    for raw in value["profiles"]:
        profile = _validate_profile(raw, profile_ids)
        profiles[profile["id"]] = profile
    if not isinstance(value["entries"], list) or len(value["entries"]) > MAX_ENTRIES:
        raise ValueError("Prompt-profile vocabulary must be a bounded array")
    entry_ids: set[str] = set()
    entries: dict[str, dict[str, Any]] = {}
    for raw in value["entries"]:
        entry = _validate_entry(raw, entry_ids, profile_ids)
        entries[entry["id"]] = entry
    aliases = _alias_map(entries)
    _validate_implications(entries)
    _strings(value["notes"], "prompt-profile notes", 32, 1000)
    return {
        "schema": value["schema"],
        "kind": value["kind"],
        "research_date": value["research_date"],
        "source_baseline": value["source_baseline"],
        "issue": value["issue"],
        "manifest_sha256": manifest_sha256,
        "authority": authority,
        "profiles": profiles,
        "entries": entries,
        "aliases": aliases,
        "notes": copy.deepcopy(value["notes"]),
    }
