"""Contracts and bounded primitives for adult-illustration taxonomy intake."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

SOURCE_MANIFEST = Path("research/adult-illustration/taxonomy-source.json")
REVIEW_MANIFEST = Path("research/adult-illustration/taxonomy-review.json")
SOURCE_SCHEMA = "studio.adult-illustration-taxonomy-source/v1"
REVIEW_SCHEMA = "studio.adult-illustration-taxonomy-review/v1"
INDEX_SCHEMA = "studio.adult-illustration-taxonomy-index/v1"
EXPECTED_COLUMNS = ["tag_id", "name", "category", "count"]
MAX_CONTRACT_BYTES = 1_048_576
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
AUTHORITY = {
    "execution_authorized": False,
    "generation_submitted": False,
    "download_authorized": False,
    "install_authorized": False,
    "training_authorized": False,
}


class DuplicateKeyError(ValueError):
    """Raised when trusted JSON repeats an object key."""


def pairs(pairs_value: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs_value:
        if key in result:
            raise DuplicateKeyError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value!r} is not allowed")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text(value: Any, label: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded text")
    if value != value.strip():
        raise ValueError(f"{label} must be trimmed")
    if any(ord(character) < 32 and character not in "\n\t\r" for character in value):
        raise ValueError(f"{label} contains a control character")
    return value


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} is not a valid identifier")
    return value


def integer(
    value: Any, label: str, *, minimum: int = 0, maximum: int | None = None
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{label} must be an integer at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must not exceed {maximum}")
    return value


def strings(value: Any, label: str, count: int, item_limit: int = 256) -> list[str]:
    if not isinstance(value, list) or len(value) > count:
        raise ValueError(f"{label} must be a bounded array")
    result = [text(item, label, item_limit) for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} contains duplicates")
    return result


def https(value: Any, label: str) -> str:
    result = text(value, label)
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} must be an HTTPS URL without credentials")
    return result


def iso_date(value: Any, label: str) -> str:
    result = text(value, label, 10)
    try:
        parsed = date.fromisoformat(result)
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != result:
        raise ValueError(f"{label} must use canonical YYYY-MM-DD")
    return result


def normalise_term(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def authority(value: Any, label: str) -> dict[str, bool]:
    if not isinstance(value, dict) or set(value) != set(AUTHORITY):
        raise ValueError(f"{label} has an invalid authority declaration")
    if any(value.get(key) is not False for key in AUTHORITY):
        raise ValueError(f"{label} must keep every authority false")
    return dict(AUTHORITY)


def exact_fields(value: Any, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label} has missing or unknown fields")
    return value


def _repo_file(root: Path | str, relative: Path, label: str) -> Path:
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ValueError("Repository root must be a directory")
    candidate = root_path
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            raise ValueError(f"{label} cannot use a symlink: {candidate}")
    resolved = candidate.resolve(strict=True)
    expected_parent = (root_path / relative.parent).resolve(strict=True)
    if resolved.parent != expected_parent or not resolved.is_file():
        raise ValueError(f"{label} escapes its repository directory")
    return resolved


def _load(root: Path | str, relative: Path, label: str) -> tuple[dict[str, Any], str]:
    raw = _repo_file(root, relative, label).read_bytes()
    if len(raw) > MAX_CONTRACT_BYTES:
        raise ValueError(f"{label} exceeds {MAX_CONTRACT_BYTES} bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} top level must be an object")
    return value, sha256(raw)


def _bounds(value: Any) -> dict[str, int]:
    ceilings = {
        "max_source_bytes": 16_777_216,
        "max_records": 100_000,
        "max_term_length": 1024,
        "max_review_entries": 20_000,
        "max_aliases_per_entry": 128,
        "max_implications_per_entry": 128,
        "max_relationship_depth": 64,
        "max_index_bytes": 67_108_864,
    }
    exact_fields(value, set(ceilings), "Taxonomy bounds")
    return {
        key: integer(value[key], key, minimum=1, maximum=ceiling)
        for key, ceiling in sorted(ceilings.items())
    }


def _source_contract(value: dict[str, Any], manifest_sha: str) -> dict[str, Any]:
    required = {
        "schema", "kind", "executable", "authority", "research_date",
        "source_baseline", "issue", "source", "categories", "published_fields",
        "semantic_facets", "profile_ids", "bounds", "accepted_for_compilation", "notes",
    }
    exact_fields(value, required, "Taxonomy source contract")
    if value["schema"] != SOURCE_SCHEMA or value["kind"] != "anime-tag-taxonomy-source":
        raise ValueError("Unsupported taxonomy source contract")
    if value["executable"] is not False or value["accepted_for_compilation"] is not False:
        raise ValueError("Taxonomy source must be non-executable and not accepted wholesale")
    result_authority = authority(value["authority"], "Taxonomy source contract")
    research_date = iso_date(value["research_date"], "taxonomy research date")
    baseline = value["source_baseline"]
    if not isinstance(baseline, str) or SHA40.fullmatch(baseline) is None:
        raise ValueError("Taxonomy source baseline must be immutable 40-hex")
    if value["issue"] != 437:
        raise ValueError("Taxonomy source issue owner must be #437")
    bounds = _bounds(value["bounds"])

    source = exact_fields(
        value["source"],
        {"provider", "repository", "revision", "selected_file", "source_url",
         "selected_file_url", "download_url", "bytes", "sha256", "records",
         "columns", "license_claim"},
        "Taxonomy source identity",
    )
    if source["provider"] != "huggingface":
        raise ValueError("Taxonomy source provider must be huggingface")
    repository = text(source["repository"], "taxonomy repository", 256)
    if repository.count("/") != 1 or any(part in {"", ".", ".."} for part in repository.split("/")):
        raise ValueError("Taxonomy repository must be owner/model")
    revision = source["revision"]
    if not isinstance(revision, str) or SHA40.fullmatch(revision) is None:
        raise ValueError("Taxonomy source revision must be immutable 40-hex")
    selected_file = text(source["selected_file"], "taxonomy selected file", 256)
    if any(mark in selected_file for mark in ("/", "\\", ":")) or selected_file in {".", ".."}:
        raise ValueError("Taxonomy selected file must be a safe top-level path")
    base_url = f"https://huggingface.co/{repository}"
    source_url = https(source["source_url"], "taxonomy source URL")
    selected_url = https(source["selected_file_url"], "taxonomy selected-file URL")
    download_url = https(source["download_url"], "taxonomy download URL")
    if source_url != base_url:
        raise ValueError("Taxonomy source URL does not match repository")
    if selected_url != f"{base_url}/blob/{revision}/{selected_file}":
        raise ValueError("Taxonomy selected-file URL is not pinned")
    if download_url != f"{base_url}/resolve/{revision}/{selected_file}?download=true":
        raise ValueError("Taxonomy download URL is not pinned")
    byte_count = integer(source["bytes"], "taxonomy source bytes", minimum=1)
    record_count = integer(source["records"], "taxonomy source records", minimum=1)
    if byte_count > bounds["max_source_bytes"] or record_count > bounds["max_records"]:
        raise ValueError("Taxonomy source exceeds an intake bound")
    source_sha = source["sha256"]
    if not isinstance(source_sha, str) or SHA256.fullmatch(source_sha) is None:
        raise ValueError("Taxonomy source SHA-256 must be lowercase 64-hex")
    if source["columns"] != EXPECTED_COLUMNS:
        raise ValueError(f"Taxonomy columns must be exactly {EXPECTED_COLUMNS}")

    licence = exact_fields(
        source["license_claim"], {"value", "source_url", "reviewed_at"},
        "Taxonomy license claim",
    )
    text(licence["value"], "taxonomy license claim", 128)
    licence_url = https(licence["source_url"], "taxonomy license source URL")
    if not licence_url.startswith(f"{base_url}/blob/{revision}/"):
        raise ValueError("Taxonomy license source URL is not pinned")
    iso_date(licence["reviewed_at"], "taxonomy license review date")

    raw_categories = value["categories"]
    if not isinstance(raw_categories, list) or not 1 <= len(raw_categories) <= 32:
        raise ValueError("Taxonomy categories must be a bounded non-empty array")
    categories: dict[int, dict[str, Any]] = {}
    category_ids: set[str] = set()
    for item in raw_categories:
        exact_fields(item, {"source_value", "id", "display"}, "Taxonomy category")
        source_value = integer(item["source_value"], "taxonomy category value")
        category_id = identifier(item["id"], "taxonomy category id")
        if source_value in categories or category_id in category_ids:
            raise ValueError("Taxonomy categories contain duplicate values or ids")
        categories[source_value] = {
            "source_value": source_value,
            "id": category_id,
            "display": text(item["display"], "taxonomy category display", 128),
        }
        category_ids.add(category_id)

    published = {
        "canonical": "name", "source_category": "category", "frequency": "count",
        "aliases": None, "implications": None, "deprecations": None,
    }
    if value["published_fields"] != published:
        raise ValueError("Taxonomy published-field mapping is unsupported")
    facets = strings(value["semantic_facets"], "taxonomy semantic facets", 64, 64)
    profiles = strings(value["profile_ids"], "taxonomy profile ids", 32, 128)
    if not facets or not profiles:
        raise ValueError("Taxonomy facets and profiles must be non-empty")
    for item in facets:
        identifier(item, "taxonomy semantic facet")
    for item in profiles:
        identifier(item, "taxonomy profile id")

    return {
        "schema": SOURCE_SCHEMA,
        "kind": "anime-tag-taxonomy-source",
        "authority": result_authority,
        "research_date": research_date,
        "source_baseline": baseline,
        "issue": 437,
        "source": {
            "provider": "huggingface", "repository": repository, "revision": revision,
            "selected_file": selected_file, "source_url": source_url,
            "selected_file_url": selected_url, "download_url": download_url,
            "bytes": byte_count, "sha256": source_sha, "records": record_count,
            "columns": list(EXPECTED_COLUMNS), "license_claim": dict(licence),
        },
        "categories": categories,
        "published_fields": published,
        "semantic_facets": facets,
        "profile_ids": profiles,
        "bounds": bounds,
        "accepted_for_compilation": False,
        "notes": strings(value["notes"], "taxonomy source notes", 32, 1000),
        "manifest_sha256": manifest_sha,
    }


def _review_entry(value: Any, source: dict[str, Any]) -> dict[str, Any]:
    required = {
        "source_name", "display", "aliases", "implications", "deprecated_by",
        "semantic_facets", "polarity", "profile_ids", "accepted_for_compilation",
    }
    exact_fields(value, required, "Taxonomy review entry")
    bounds = source["bounds"]
    name = text(value["source_name"], "taxonomy review source name", bounds["max_term_length"])
    aliases = strings(value["aliases"], f"review {name} aliases", bounds["max_aliases_per_entry"], bounds["max_term_length"])
    implications = strings(value["implications"], f"review {name} implications", bounds["max_implications_per_entry"], bounds["max_term_length"])
    deprecated_by = value["deprecated_by"]
    if deprecated_by is not None:
        deprecated_by = text(deprecated_by, f"review {name} deprecated_by", bounds["max_term_length"])
    facets = strings(value["semantic_facets"], f"review {name} facets", 32, 64)
    profiles = strings(value["profile_ids"], f"review {name} profiles", 32, 128)
    unknown_facets = set(facets) - set(source["semantic_facets"])
    unknown_profiles = set(profiles) - set(source["profile_ids"])
    if unknown_facets or unknown_profiles:
        raise ValueError(f"Review {name!r} uses unknown facets or profiles")
    polarity = value["polarity"]
    if polarity not in {"positive", "negative"}:
        raise ValueError(f"Review {name!r} has invalid polarity")
    accepted = value["accepted_for_compilation"]
    if not isinstance(accepted, bool):
        raise ValueError(f"Review {name!r} acceptance must be boolean")
    if accepted and (not facets or not profiles or deprecated_by is not None):
        raise ValueError(f"Accepted review {name!r} is incomplete or deprecated")
    return {
        "source_name": name,
        "display": text(value["display"], f"review {name} display", bounds["max_term_length"]),
        "aliases": aliases,
        "implications": implications,
        "deprecated_by": deprecated_by,
        "semantic_facets": facets,
        "polarity": polarity,
        "profile_ids": profiles,
        "accepted_for_compilation": accepted,
    }


def _review_contract(
    value: dict[str, Any], manifest_sha: str, source: dict[str, Any]
) -> dict[str, Any]:
    required = {
        "schema", "kind", "executable", "authority", "research_date", "issue",
        "source_sha256", "entries", "notes",
    }
    exact_fields(value, required, "Taxonomy review contract")
    if value["schema"] != REVIEW_SCHEMA or value["kind"] != "anime-tag-taxonomy-review":
        raise ValueError("Unsupported taxonomy review contract")
    if value["executable"] is not False or value["issue"] != 437:
        raise ValueError("Taxonomy review must be non-executable and owned by #437")
    if value["source_sha256"] != source["source"]["sha256"]:
        raise ValueError("Taxonomy review does not target the pinned source SHA-256")
    raw_entries = value["entries"]
    if not isinstance(raw_entries, list) or len(raw_entries) > source["bounds"]["max_review_entries"]:
        raise ValueError("Taxonomy review entries must be a bounded array")
    entries = [_review_entry(item, source) for item in raw_entries]
    names = [entry["source_name"] for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError("Taxonomy review contains duplicate source names")
    return {
        "schema": REVIEW_SCHEMA,
        "kind": "anime-tag-taxonomy-review",
        "authority": authority(value["authority"], "Taxonomy review contract"),
        "research_date": iso_date(value["research_date"], "taxonomy review date"),
        "issue": 437,
        "source_sha256": value["source_sha256"],
        "entries": entries,
        "notes": strings(value["notes"], "taxonomy review notes", 32, 1000),
        "manifest_sha256": manifest_sha,
    }


def load_taxonomy_contracts(root: Path | str = ".") -> dict[str, dict[str, Any]]:
    """Load and validate the checked-in source and review contracts."""
    source_raw, source_sha = _load(root, SOURCE_MANIFEST, "taxonomy source contract")
    source = _source_contract(source_raw, source_sha)
    review_raw, review_sha = _load(root, REVIEW_MANIFEST, "taxonomy review contract")
    return {"source": source, "review": _review_contract(review_raw, review_sha, source)}
