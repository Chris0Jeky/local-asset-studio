"""Bounded provider metadata snapshots for adult-illustration research.

The module deliberately has no default network client. Callers must inject a
single-request transport. Returned records are provenance proposals only: they
never authorize downloading, installation, model execution, or generation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlparse

MAX_RESPONSE_BYTES = 2_097_152
MAX_REDIRECTS = 5
MAX_JSON_DEPTH = 20
MAX_JSON_NODES = 50_000
MAX_STRING_CHARS = 262_144
MAX_FILES = 1_024
MAX_TAGS = 2_048
MAX_CLAIMS = 128

_SHA40 = re.compile(r"[0-9a-fA-F]{40}")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_HF_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
_HEADER_ALLOWLIST = {
    "content-type",
    "etag",
    "last-modified",
    "x-request-id",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "retry-after",
}


class DuplicateKeyError(ValueError):
    """Raised when an external JSON object repeats a key."""


@dataclass(frozen=True)
class HttpRequest:
    """One immutable provider metadata request."""

    url: str
    headers: Mapping[str, str]
    method: str = "GET"

    def __post_init__(self) -> None:
        if self.method != "GET":
            raise ValueError("Source snapshot requests must use GET")
        _require_https(self.url, "request URL")
        object.__setattr__(self, "headers", MappingProxyType(_normalise_headers(self.headers)))


@dataclass(frozen=True)
class HttpResponse:
    """Injected transport response.

    ``redirect_chain`` contains every redirect destination observed by the
    transport. The final URL is validated independently.
    """

    request_url: str
    final_url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    redirect_chain: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, int) or isinstance(self.status, bool):
            raise TypeError("HTTP status must be an integer")
        if not isinstance(self.body, bytes):
            raise TypeError("HTTP body must be bytes")
        if not isinstance(self.redirect_chain, tuple) or not all(
            isinstance(item, str) for item in self.redirect_chain
        ):
            raise TypeError("redirect_chain must be a tuple of URLs")
        object.__setattr__(self, "headers", MappingProxyType(_normalise_headers(self.headers)))


Transport = Callable[[HttpRequest], HttpResponse]


def _normalise_headers(headers: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(headers, Mapping) or len(headers) > 128:
        raise ValueError("HTTP headers must be a bounded mapping")
    result: dict[str, str] = {}
    for raw_key, raw_value in headers.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError("HTTP header names and values must be strings")
        key = raw_key.strip().casefold()
        value = raw_value.strip()
        if not key or len(key) > 128 or len(value) > 8_192:
            raise ValueError("HTTP header is empty or oversized")
        if "\r" in key or "\n" in key or "\r" in value or "\n" in value:
            raise ValueError("HTTP headers cannot contain line breaks")
        if key in result:
            raise ValueError(f"Duplicate HTTP header {key!r}")
        result[key] = value
    return result


def _require_https(url: str, label: str) -> str:
    if not isinstance(url, str) or len(url) > 4_096:
        raise ValueError(f"{label} is invalid")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} must be an HTTPS URL without credentials")
    return parsed.hostname.casefold()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value!r} is not allowed")


def _check_json_bounds(value: Any) -> None:
    nodes = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ValueError(f"JSON node count exceeds {MAX_JSON_NODES}")
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"JSON nesting depth exceeds {MAX_JSON_DEPTH}")
        if isinstance(item, str):
            if len(item) > MAX_STRING_CHARS:
                raise ValueError(f"JSON string exceeds {MAX_STRING_CHARS} characters")
        elif isinstance(item, dict):
            if len(item) > 4_096:
                raise ValueError("JSON object has too many keys")
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object key is not a string")
                if len(key) > 512:
                    raise ValueError("JSON object key is oversized")
                stack.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > 10_000:
                raise ValueError("JSON array is oversized")
            for child in item:
                stack.append((child, depth + 1))
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Non-finite JSON number is not allowed")
        elif item is not None and not isinstance(item, (bool, int, float)):
            raise ValueError(f"Unsupported JSON value type {type(item).__name__}")


def _parse_json(body: bytes) -> dict[str, Any]:
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Provider response exceeds {MAX_RESPONSE_BYTES} bytes")
    try:
        text = body.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError(f"Provider response is not valid UTF-8: {exc}") from exc
    except (json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        raise ValueError(f"Invalid provider JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Provider JSON top level must be an object")
    _check_json_bounds(value)
    return value


def _validate_response(request: HttpRequest, response: HttpResponse, allowed_hosts: set[str]) -> dict[str, Any]:
    if not isinstance(response, HttpResponse):
        raise TypeError("Injected transport must return HttpResponse")
    if response.request_url != request.url:
        raise ValueError("Transport response request identity does not match the request")
    request_host = _require_https(request.url, "request URL")
    if request_host not in allowed_hosts:
        raise ValueError("Request host is not supported for this provider")
    if len(response.redirect_chain) > MAX_REDIRECTS:
        raise ValueError(f"Provider redirect chain exceeds {MAX_REDIRECTS}")
    for redirect in response.redirect_chain:
        host = _require_https(redirect, "redirect URL")
        if host not in allowed_hosts:
            raise ValueError("Cross-provider redirect is not allowed")
    final_host = _require_https(response.final_url, "final URL")
    if final_host not in allowed_hosts:
        raise ValueError("Cross-provider redirect is not allowed")
    if response.status != 200:
        raise ValueError(f"Provider returned HTTP {response.status}")
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.casefold():
        raise ValueError("Provider response content type is not JSON")
    return _parse_json(response.body)


def _safe_file_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 1_024:
        raise ValueError("Provider file path is unsafe")
    if "\\" in value or "\x00" in value or ":" in value:
        raise ValueError(f"Provider file path is unsafe: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Provider file path is unsafe: {value!r}")
    return path.as_posix()


def _positive_int(value: Any, label: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _optional_positive_int(value: Any, label: str) -> int | None:
    return _positive_int(value, label, allow_none=True)


def _sha256(value: Any, label: str, *, allow_none: bool = True) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a 64-character hexadecimal SHA-256")
    return value.casefold()


def _bounded_strings(value: Any, label: str, *, maximum: int = MAX_TAGS, item_limit: int = 1_024) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{label} must be a bounded array")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item) > item_limit:
            raise ValueError(f"{label} contains an invalid string")
        normal = item.strip()
        if normal not in seen:
            seen.add(normal)
            result.append(normal)
    return result


def _response_record(response: HttpResponse) -> dict[str, Any]:
    headers = {
        key: value
        for key, value in sorted(response.headers.items())
        if key in _HEADER_ALLOWLIST
    }
    return {
        "status": response.status,
        "final_url": response.final_url,
        "redirect_chain": list(response.redirect_chain),
        "headers": headers,
    }


def _base_snapshot(provider: str, request: HttpRequest, response: HttpResponse) -> dict[str, Any]:
    return {
        "schema": "studio.adult-illustration-source-snapshot/v1",
        "kind": "source-snapshot-proposal",
        "executable": False,
        "authority": "none",
        "provider": provider,
        "raw_payload_sha256": hashlib.sha256(response.body).hexdigest(),
        "request": {
            "method": request.method,
            "url": request.url,
            "headers": dict(sorted(request.headers.items())),
        },
        "response": _response_record(response),
        "download_authorized": False,
        "install_authorized": False,
        "execution_authorized": False,
        "generation_submitted": False,
        "training_authorized": False,
    }


def _claims(*items: tuple[str, str]) -> list[dict[str, str]]:
    if len(items) > MAX_CLAIMS:
        raise ValueError("Too many source claims")
    return [
        {"status": status, "claim": claim}
        for status, claim in items
        if claim
    ]


def _hf_access_state(payload: Mapping[str, Any]) -> str:
    private = payload.get("private") is True
    gated = payload.get("gated") not in (None, False)
    if private and gated:
        return "private_gated"
    if private:
        return "private"
    if gated:
        return "gated"
    return "public"


def snapshot_huggingface(repo_id: str, revision: str, transport: Transport) -> dict[str, Any]:
    """Create one zero-authority Hugging Face model metadata snapshot."""

    if not isinstance(repo_id, str) or _HF_REPO.fullmatch(repo_id) is None:
        raise ValueError("Hugging Face repository identity must be owner/model")
    if not isinstance(revision, str) or not revision.strip() or len(revision) > 200:
        raise ValueError("An explicit Hugging Face revision is required")
    revision = revision.strip()
    encoded_revision = quote(revision, safe="")
    url = f"https://huggingface.co/api/models/{repo_id}/revision/{encoded_revision}?blobs=true"
    request = HttpRequest(
        url=url,
        headers={
            "accept": "application/json",
            "user-agent": "local-asset-studio-source-snapshot/1",
        },
    )
    response = transport(request)
    payload = _validate_response(request, response, {"huggingface.co"})

    if payload.get("id") != repo_id:
        raise ValueError("Hugging Face response repository identity does not match the request")
    commit = payload.get("sha")
    if not isinstance(commit, str) or _SHA40.fullmatch(commit) is None:
        raise ValueError("Hugging Face response does not provide an immutable 40-hex revision")
    commit = commit.casefold()

    raw_files = payload.get("siblings", [])
    if not isinstance(raw_files, list) or len(raw_files) > MAX_FILES:
        raise ValueError(f"Hugging Face file list must contain at most {MAX_FILES} files")
    files: list[dict[str, Any]] = []
    paths: set[str] = set()
    for index, item in enumerate(raw_files):
        if not isinstance(item, dict):
            raise ValueError(f"Hugging Face file {index} must be an object")
        path = _safe_file_path(item.get("rfilename"))
        if path in paths:
            raise ValueError(f"Hugging Face response has duplicate file path {path!r}")
        paths.add(path)
        lfs = item.get("lfs")
        if lfs is not None and not isinstance(lfs, dict):
            raise ValueError(f"Hugging Face LFS metadata for {path!r} must be an object")
        lfs = lfs or {}
        byte_count = item.get("size")
        if byte_count is None:
            byte_count = lfs.get("size")
        byte_count = _optional_positive_int(byte_count, f"Hugging Face file {path!r} byte count")
        digest = item.get("sha256")
        if digest is None:
            digest = lfs.get("sha256")
        digest = _sha256(digest, f"Hugging Face file {path!r} SHA-256")
        provider_hashes: dict[str, str] = {}
        xet = item.get("xetHash")
        if xet is not None:
            if not isinstance(xet, str) or not xet.strip() or len(xet) > 256:
                raise ValueError(f"Hugging Face file {path!r} has invalid Xet identity")
            provider_hashes["xet"] = xet.strip()
        pointer_size = lfs.get("pointerSize")
        if pointer_size is not None:
            provider_hashes["lfs_pointer_size"] = str(
                _positive_int(pointer_size, f"Hugging Face file {path!r} LFS pointer size")
            )
        files.append(
            {
                "id": f"hf-file-{index + 1}",
                "path": path,
                "bytes": byte_count,
                "sha256": digest,
                "provider_hashes": provider_hashes,
                "selected": False,
            }
        )

    card = payload.get("cardData")
    if card is not None and not isinstance(card, dict):
        raise ValueError("Hugging Face cardData must be an object")
    card = card or {}
    licence = card.get("license")
    if licence is not None and (not isinstance(licence, str) or len(licence) > 1_024):
        raise ValueError("Hugging Face licence metadata is invalid")
    base_model = card.get("base_model")
    if isinstance(base_model, list):
        base_models = _bounded_strings(base_model, "Hugging Face base_model", maximum=128)
    elif isinstance(base_model, str) and base_model.strip():
        base_models = [base_model.strip()]
    elif base_model is None:
        base_models = []
    else:
        raise ValueError("Hugging Face base_model metadata is invalid")

    access_state = _hf_access_state(payload)
    record = {
        "id": f"huggingface-{repo_id.replace('/', '--').casefold()}-{commit[:12]}",
        "provider": "huggingface",
        "synthetic": False,
        "canonical_url": f"https://huggingface.co/{repo_id}/tree/{commit}",
        "provider_model_id": repo_id,
        "provider_version_id": None,
        "immutable_revision": commit,
        "requested_revision": revision,
        "snapshot_state": "pinned",
        "terms_state": "snapshotted" if isinstance(licence, str) and licence.strip() else "unknown",
        "access_state": access_state,
        "lineage": {
            "base_models": base_models,
            "pipeline_tag": payload.get("pipeline_tag") if isinstance(payload.get("pipeline_tag"), str) else None,
            "library_name": payload.get("library_name") if isinstance(payload.get("library_name"), str) else None,
        },
        "terms": {
            "license": licence.strip() if isinstance(licence, str) and licence.strip() else None,
        },
        "metadata": {
            "last_modified": payload.get("lastModified") if isinstance(payload.get("lastModified"), str) else None,
            "disabled": payload.get("disabled") is True,
            "tags": _bounded_strings(payload.get("tags"), "Hugging Face tags"),
            "languages": _bounded_strings(card.get("language"), "Hugging Face languages", maximum=128),
        },
        "claims": _claims(
            ("source_claim", f"Hugging Face repository metadata resolved requested revision {revision!r} to commit {commit}"),
            ("source_claim", f"Provider reports access state {access_state}"),
            ("unverified_local", "No local file, runner, graph, compatibility, performance, artistic quality, or rights decision is established"),
        ),
        "files": files,
        "download_authorized": False,
        "install_authorized": False,
        "execution_authorized": False,
    }
    snapshot = _base_snapshot("huggingface", request, response)
    snapshot["record"] = record
    return snapshot


def snapshot_civitai(version_id: int, transport: Transport) -> dict[str, Any]:
    """Create one zero-authority Civitai model-version metadata snapshot."""

    version_id = _positive_int(version_id, "Civitai version ID")  # type: ignore[assignment]
    url = f"https://civitai.com/api/v1/model-versions/{version_id}"
    request = HttpRequest(
        url=url,
        headers={
            "accept": "application/json",
            "user-agent": "local-asset-studio-source-snapshot/1",
        },
    )
    response = transport(request)
    payload = _validate_response(request, response, {"civitai.com", "www.civitai.com"})

    actual_version = payload.get("id")
    if actual_version != version_id:
        raise ValueError("Civitai response version identity does not match the request")
    model_id = _positive_int(payload.get("modelId"), "Civitai model ID")
    model = payload.get("model")
    if model is not None and not isinstance(model, dict):
        raise ValueError("Civitai model metadata must be an object")
    model = model or {}
    if model.get("id") is not None and model.get("id") != model_id:
        raise ValueError("Civitai model identity is inconsistent inside the response")

    raw_files = payload.get("files", [])
    if not isinstance(raw_files, list) or len(raw_files) > MAX_FILES:
        raise ValueError(f"Civitai file list must contain at most {MAX_FILES} files")
    files: list[dict[str, Any]] = []
    paths: set[str] = set()
    file_ids: set[int] = set()
    for index, item in enumerate(raw_files):
        if not isinstance(item, dict):
            raise ValueError(f"Civitai file {index} must be an object")
        provider_file_id = _positive_int(item.get("id"), f"Civitai file {index} ID")
        if provider_file_id in file_ids:
            raise ValueError(f"Civitai response has duplicate file ID {provider_file_id}")
        file_ids.add(provider_file_id)  # type: ignore[arg-type]
        path = _safe_file_path(item.get("name"))
        if path in paths:
            raise ValueError(f"Civitai response has duplicate file path {path!r}")
        paths.add(path)
        size_kb = item.get("sizeKB")
        if not isinstance(size_kb, (int, float)) or isinstance(size_kb, bool) or not math.isfinite(float(size_kb)) or size_kb <= 0:
            raise ValueError(f"Civitai file {path!r} sizeKB must be positive and finite")
        byte_count = int(round(float(size_kb) * 1024))
        if byte_count <= 0:
            raise ValueError(f"Civitai file {path!r} byte count is invalid")
        raw_hashes = item.get("hashes")
        if raw_hashes is None:
            raw_hashes = {}
        if not isinstance(raw_hashes, dict) or len(raw_hashes) > 32:
            raise ValueError(f"Civitai file {path!r} hashes must be a bounded object")
        provider_hashes: dict[str, str] = {}
        sha: str | None = None
        for raw_key, raw_value in raw_hashes.items():
            if not isinstance(raw_key, str) or not isinstance(raw_value, str):
                raise ValueError(f"Civitai file {path!r} hash keys and values must be strings")
            key = raw_key.strip().casefold()
            value = raw_value.strip()
            if not key or len(key) > 64 or not value or len(value) > 256:
                raise ValueError(f"Civitai file {path!r} contains invalid provider hash")
            if key in provider_hashes:
                raise ValueError(f"Civitai file {path!r} contains duplicate provider hash {key!r}")
            provider_hashes[key] = value
            if key == "sha256":
                sha = _sha256(value, f"Civitai file {path!r} SHA-256", allow_none=False)
        metadata = item.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError(f"Civitai file {path!r} metadata must be an object")
        metadata = metadata or {}
        files.append(
            {
                "id": f"civitai-file-{provider_file_id}",
                "provider_file_id": provider_file_id,
                "path": path,
                "bytes": byte_count,
                "sha256": sha,
                "provider_hashes": provider_hashes,
                "file_type": item.get("type") if isinstance(item.get("type"), str) else None,
                "primary": item.get("primary") is True,
                "metadata": {
                    str(key): value
                    for key, value in sorted(metadata.items(), key=lambda pair: str(pair[0]))
                    if isinstance(key, str)
                    and isinstance(value, (str, int, float, bool, type(None)))
                },
                "selected": False,
            }
        )

    permission_fields = {
        "allow_no_credit": model.get("allowNoCredit"),
        "allow_commercial_use": model.get("allowCommercialUse"),
        "allow_derivatives": model.get("allowDerivatives"),
        "allow_different_license": model.get("allowDifferentLicense"),
    }
    has_terms = any(value is not None for value in permission_fields.values())
    air = payload.get("air")
    if air is not None and (not isinstance(air, str) or not air.strip() or len(air) > 1_024):
        raise ValueError("Civitai AIR identity is invalid")
    base_model = payload.get("baseModel")
    base_model_type = payload.get("baseModelType")
    for label, value in (("baseModel", base_model), ("baseModelType", base_model_type)):
        if value is not None and (not isinstance(value, str) or len(value) > 1_024):
            raise ValueError(f"Civitai {label} claim is invalid")

    record = {
        "id": f"civitai-{model_id}-{version_id}",
        "provider": "civitai",
        "synthetic": False,
        "canonical_url": f"https://civitai.com/models/{model_id}?modelVersionId={version_id}",
        "provider_model_id": model_id,
        "provider_version_id": version_id,
        "immutable_revision": str(version_id),
        "snapshot_state": "pinned",
        "terms_state": "snapshotted" if has_terms else "unknown",
        "access_state": "public_metadata",
        "air": air.strip() if isinstance(air, str) else None,
        "lineage": {
            "base_model": base_model.strip() if isinstance(base_model, str) and base_model.strip() else None,
            "base_model_type": base_model_type.strip() if isinstance(base_model_type, str) and base_model_type.strip() else None,
        },
        "terms": permission_fields,
        "metadata": {
            "version_name": payload.get("name") if isinstance(payload.get("name"), str) else None,
            "model_name": model.get("name") if isinstance(model.get("name"), str) else None,
            "model_type": model.get("type") if isinstance(model.get("type"), str) else None,
            "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
            "created_at": payload.get("createdAt") if isinstance(payload.get("createdAt"), str) else None,
            "updated_at": payload.get("updatedAt") if isinstance(payload.get("updatedAt"), str) else None,
            "published_at": payload.get("publishedAt") if isinstance(payload.get("publishedAt"), str) else None,
            "trained_words": _bounded_strings(payload.get("trainedWords"), "Civitai trained words"),
        },
        "claims": _claims(
            ("source_claim", f"Civitai API returned model {model_id}, version {version_id}, and {len(files)} file record(s)"),
            ("source_claim", "Base-model, trigger, metadata, and permission fields remain creator/provider claims"),
            ("unverified_local", "No local bytes, graph compatibility, runtime behavior, artistic quality, or rights decision is established"),
        ),
        "files": files,
        "download_authorized": False,
        "install_authorized": False,
        "execution_authorized": False,
    }
    snapshot = _base_snapshot("civitai", request, response)
    snapshot["record"] = record
    return snapshot


def _validate_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Source snapshot must be an object")
    if value.get("schema") != "studio.adult-illustration-source-snapshot/v1":
        raise ValueError("Unsupported source snapshot schema")
    if value.get("kind") != "source-snapshot-proposal":
        raise ValueError("Unsupported source snapshot kind")
    if value.get("executable") is not False or value.get("authority") != "none":
        raise ValueError("Source snapshot must remain non-executing with authority none")
    for field in (
        "download_authorized",
        "install_authorized",
        "execution_authorized",
        "generation_submitted",
        "training_authorized",
    ):
        if value.get(field) is not False:
            raise ValueError(f"Source snapshot must keep {field} false")
    record = value.get("record")
    if not isinstance(record, dict):
        raise ValueError("Source snapshot record must be an object")
    return value


def _source_identity(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    record = snapshot["record"]
    provider = snapshot.get("provider")
    if provider == "huggingface":
        return (provider, record.get("provider_model_id"))
    if provider == "civitai":
        return (
            provider,
            record.get("provider_model_id"),
            record.get("provider_version_id"),
        )
    raise ValueError(f"Unsupported snapshot provider {provider!r}")


def _file_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = snapshot["record"].get("files")
    if not isinstance(raw, list) or len(raw) > MAX_FILES:
        raise ValueError("Snapshot files must be a bounded array")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Snapshot file record must be an object")
        path = _safe_file_path(item.get("path"))
        if path in result:
            raise ValueError(f"Snapshot contains duplicate file path {path!r}")
        result[path] = item
    return result


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare two immutable proposals for the same provider source identity."""

    before = _validate_snapshot(before)
    after = _validate_snapshot(after)
    identity = _source_identity(before)
    if _source_identity(after) != identity:
        raise ValueError("Source snapshot identities do not match")
    before_files = _file_map(before)
    after_files = _file_map(after)
    added = sorted(set(after_files) - set(before_files))
    removed = sorted(set(before_files) - set(after_files))
    changed = sorted(
        path
        for path in set(before_files).intersection(after_files)
        if before_files[path] != after_files[path]
    )
    before_record = before["record"]
    after_record = after["record"]
    provider = before.get("provider")
    result = {
        "schema": "studio.adult-illustration-source-snapshot-diff/v1",
        "kind": "source-snapshot-diff",
        "executable": False,
        "authority": "none",
        "provider": provider,
        "source_identity": list(identity[1:]),
        "before_payload_sha256": before.get("raw_payload_sha256"),
        "after_payload_sha256": after.get("raw_payload_sha256"),
        "payload_changed": before.get("raw_payload_sha256") != after.get("raw_payload_sha256"),
        "added_files": added,
        "removed_files": removed,
        "changed_files": changed,
        "terms_changed": (
            before_record.get("terms_state"),
            before_record.get("terms"),
        )
        != (
            after_record.get("terms_state"),
            after_record.get("terms"),
        ),
        "lineage_changed": before_record.get("lineage") != after_record.get("lineage"),
        "access_changed": before_record.get("access_state") != after_record.get("access_state"),
        "metadata_changed": before_record.get("metadata") != after_record.get("metadata"),
        "download_authorized": False,
        "install_authorized": False,
        "execution_authorized": False,
        "generation_submitted": False,
        "training_authorized": False,
    }
    result["diff_id"] = hashlib.sha256(
        json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return result


def read_snapshot_json(data: bytes) -> dict[str, Any]:
    """Parse and validate a stored source snapshot without network access."""

    return _validate_snapshot(_parse_json(data))


__all__ = [
    "HttpRequest",
    "HttpResponse",
    "snapshot_huggingface",
    "snapshot_civitai",
    "diff_snapshots",
    "read_snapshot_json",
]
