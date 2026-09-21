"""Contract validators for adult-illustration research intelligence."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, urlparse

from adult_illustration_intelligence_common import (
    AVAILABILITY, EVIDENCE, REQUIRED, SHA256, SNAPSHOTS, TERMS,
    TECHNIQUE_CATEGORIES, _common, _dialects, _https, _id, _immutable,
    _items, _label, _load, _profile_vocab_refs, _route_ids, _strings,
    _text, _vocabulary,
)


def _techniques(value: dict[str, Any], errors: list[str]) -> None:
    name = "technique-candidates.json"
    label = _label(name)
    _common(name, value, "studio.adult-illustration-technique-candidates/v0", "technique-candidates", errors)
    if value.get("issue") != 403:
        errors.append(f"{label}: issue owner must be #403")
    candidates, _ = _items(name, value, "candidates", errors)
    for item in candidates:
        iid = item.get("id", "<invalid>")
        if item.get("category") not in TECHNIQUE_CATEGORIES:
            errors.append(f"{label}: candidate {iid!r} has invalid category")
        if item.get("evidence_state") not in EVIDENCE:
            errors.append(f"{label}: candidate {iid!r} has invalid evidence state")
        urls = item.get("source_urls")
        if not _strings(urls, 16) or not all(_https(url) for url in urls):
            errors.append(f"{label}: candidate {iid!r} source URLs must use HTTPS")
        if item.get("code_state") not in AVAILABILITY or item.get("weight_state") not in AVAILABILITY:
            errors.append(f"{label}: candidate {iid!r} availability state is invalid")
        if item.get("installed") not in {None, True, False} or item.get("executable") is not False:
            errors.append(f"{label}: candidate {iid!r} installation/execution state is invalid")
        if not isinstance(item.get("ready_for_qualification"), bool) or item.get("exact_compatibility_required") is not True:
            errors.append(f"{label}: candidate {iid!r} readiness/compatibility flags are invalid")
        if not _text(item.get("proposed_role"), 1000):
            errors.append(f"{label}: candidate {iid!r} needs proposed role")
        if not _strings(item.get("promotion_blockers"), 64, 1000) or not item.get("promotion_blockers"):
            errors.append(f"{label}: candidate {iid!r} needs promotion blockers")
        unavailable = item.get("code_state") == "not_released" or item.get("weight_state") == "not_released"
        if unavailable and item.get("ready_for_qualification"):
            errors.append(f"{label}: unreleased candidate {iid!r} cannot be ready for qualification")
        if item.get("ready_for_qualification") and not _immutable(item.get("source_revision")):
            errors.append(f"{label}: ready candidate {iid!r} needs immutable source revision")
        if not isinstance(item.get("issue_owner"), int) or isinstance(item.get("issue_owner"), bool) or item["issue_owner"] <= 0:
            errors.append(f"{label}: candidate {iid!r} needs issue owner")


def _safe_path(value: Any) -> bool:
    if not _text(value, 500) or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _sources(value: dict[str, Any], errors: list[str]) -> None:
    name = "source-intake-example.json"
    label = _label(name)
    _common(name, value, "studio.adult-illustration-source-intake/v0", "source-intake-examples", errors)
    if value.get("issue") != 433:
        errors.append(f"{label}: issue owner must be #433")
    records, _ = _items(name, value, "records", errors)
    for record in records:
        rid = record.get("id", "<invalid>")
        provider = record.get("provider")
        url = record.get("canonical_url")
        if provider not in {"huggingface", "civitai"}:
            errors.append(f"{label}: record {rid!r} has unsupported provider")
        if not isinstance(record.get("synthetic"), bool):
            errors.append(f"{label}: record {rid!r} synthetic must be boolean")
        if not _https(url):
            errors.append(f"{label}: record {rid!r} canonical URL must use HTTPS")
            host = ""
        else:
            host = (urlparse(url).hostname or "").casefold()
        parsed_url = urlparse(url) if _https(url) else None
        if provider == "huggingface":
            model_id = record.get("provider_model_id")
            valid_model_id = (
                isinstance(model_id, str)
                and model_id.count("/") == 1
                and all(_text(part, 96) for part in model_id.split("/"))
            )
            if host != "huggingface.co" or not valid_model_id:
                errors.append(
                    f"{label}: Hugging Face record {rid!r} needs huggingface.co org/model identity"
                )
            elif parsed_url is not None:
                path_identity = "/".join(
                    part for part in parsed_url.path.split("/") if part
                )
                if (
                    path_identity != model_id
                    or bool(parsed_url.query)
                    or bool(parsed_url.fragment)
                ):
                    errors.append(
                        f"{label}: Hugging Face record {rid!r} canonical URL identity "
                        "must match provider_model_id"
                    )
        if provider == "civitai":
            model_id = record.get("provider_model_id")
            version_id = record.get("provider_version_id")
            valid_model_id = (
                isinstance(model_id, int)
                and not isinstance(model_id, bool)
                and model_id > 0
            )
            valid_version_id = (
                isinstance(version_id, int)
                and not isinstance(version_id, bool)
                and version_id > 0
            )
            if host not in {"civitai.com", "www.civitai.com"}:
                errors.append(f"{label}: Civitai record {rid!r} must use civitai.com")
            if not valid_model_id:
                errors.append(f"{label}: Civitai record {rid!r} needs positive model ID")
            if not valid_version_id:
                errors.append(f"{label}: Civitai record {rid!r} needs positive version ID")
            if parsed_url is not None and valid_model_id and valid_version_id:
                parts = [part for part in parsed_url.path.split("/") if part]
                query = parse_qs(parsed_url.query, keep_blank_values=True)
                url_model = (
                    int(parts[1])
                    if len(parts) >= 2
                    and parts[0].casefold() == "models"
                    and parts[1].isdigit()
                    else None
                )
                versions = query.get("modelVersionId", [])
                url_version = (
                    int(versions[0])
                    if len(versions) == 1 and versions[0].isdigit()
                    else None
                )
                if (
                    url_model != model_id
                    or url_version != version_id
                    or bool(parsed_url.fragment)
                ):
                    errors.append(
                        f"{label}: Civitai record {rid!r} canonical URL identity "
                        "must match provider model/version IDs"
                    )
        revision = record.get("immutable_revision")
        if revision is not None and not _text(revision, 160):
            errors.append(f"{label}: record {rid!r} immutable revision is invalid")
        state = record.get("snapshot_state")
        if state not in SNAPSHOTS:
            errors.append(f"{label}: record {rid!r} has invalid snapshot state")
        if state in {"pinned", "hash_verified"} and not _immutable(revision):
            errors.append(f"{label}: pinned record {rid!r} needs immutable revision")
        if record.get("terms_state") not in TERMS:
            errors.append(f"{label}: record {rid!r} has invalid terms state")
        claims = record.get("claims")
        if not isinstance(claims, list) or len(claims) > 64:
            errors.append(f"{label}: record {rid!r} claims must be bounded")
        files = record.get("files")
        if not isinstance(files, list) or len(files) > 128:
            errors.append(f"{label}: record {rid!r} files must be bounded")
            files = []
        file_ids: set[str] = set()
        file_paths: set[str] = set()
        selected = 0
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                errors.append(f"{label}: record {rid!r} file {index} must be an object")
                continue
            fid = item.get("id")
            if not _id(fid) or fid in file_ids:
                errors.append(f"{label}: record {rid!r} has invalid/duplicate file id")
            else:
                file_ids.add(fid)
            raw_path = item.get("path")
            if not _safe_path(raw_path):
                errors.append(f"{label}: record {rid!r} file path is unsafe")
            else:
                normalized_path = PurePosixPath(raw_path).as_posix()
                if normalized_path in file_paths:
                    errors.append(
                        f"{label}: record {rid!r} has duplicate file path "
                        f"{normalized_path!r}"
                    )
                else:
                    file_paths.add(normalized_path)
            byte_count = item.get("bytes")
            if byte_count is not None and (not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count <= 0):
                errors.append(f"{label}: record {rid!r} file byte count is invalid")
            sha = item.get("sha256")
            if sha is not None and (not isinstance(sha, str) or SHA256.fullmatch(sha) is None):
                errors.append(f"{label}: record {rid!r} file SHA256 is invalid")
            hashes = item.get("provider_hashes")
            if not isinstance(hashes, dict) or len(hashes) > 16 or not all(_text(k, 32) and _text(v, 160) for k, v in hashes.items()):
                errors.append(f"{label}: record {rid!r} provider hashes are invalid")
            chosen = item.get("selected")
            if not isinstance(chosen, bool):
                errors.append(f"{label}: record {rid!r} file selected must be boolean")
            elif chosen:
                selected += 1
                if byte_count is None or sha is None:
                    errors.append(f"{label}: selected file in record {rid!r} needs byte count and SHA256")
        if state == "hash_verified" and selected == 0:
            errors.append(f"{label}: hash-verified record {rid!r} needs selected file")
        for field in ("download_authorized", "install_authorized", "execution_authorized"):
            if record.get(field) is not False:
                errors.append(f"{label}: record {rid!r} must keep {field} false")


def validate_paths(root: Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    routes = _route_ids(root, errors)
    documents = {name: _load(root, name, errors) for name in REQUIRED}
    profiles: list[dict[str, Any]] = []
    profile_ids: set[str] = set()
    dialects = documents.get("prompt-dialects.json")
    if dialects is not None:
        profiles, profile_ids = _dialects(dialects, routes, errors)
    vocabulary_ids: set[str] = set()
    vocabulary = documents.get("tag-vocabulary-example.json")
    if vocabulary is not None:
        vocabulary_ids = _vocabulary(vocabulary, profile_ids, errors)
    if profiles:
        _profile_vocab_refs(profiles, vocabulary_ids, errors)
    techniques = documents.get("technique-candidates.json")
    if techniques is not None:
        _techniques(techniques, errors)
    sources = documents.get("source-intake-example.json")
    if sources is not None:
        _sources(sources, errors)
    return sorted(set(errors))
