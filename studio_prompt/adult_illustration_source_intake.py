"""Guarded facade for bounded adult-illustration provider snapshots.

The parser implementation lives in the private
:mod:`_adult_illustration_source_intake_impl` module. This facade adds stable
file identities, pre-conversion numeric bounds, and strict validation whenever
stored snapshot JSON re-enters the trust boundary.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping
from urllib.parse import quote

from . import _adult_illustration_source_intake_impl as _base

HttpRequest = _base.HttpRequest
HttpResponse = _base.HttpResponse
Transport = _base.Transport

_MAX_FILE_BYTES = (1 << 63) - 1
_PROVIDER_HOSTS = {
    "huggingface": {"huggingface.co"},
    "civitai": {"civitai.com", "www.civitai.com"},
}
_SENSITIVE_REQUEST_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}


def _hf_file_id(path: str) -> str:
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:20]
    return f"hf-file-{digest}"


def snapshot_huggingface(
    repo_id: str,
    revision: str,
    transport: Transport,
) -> dict[str, Any]:
    """Create a snapshot with path-stable Hugging Face file identities."""

    def guarded(request: HttpRequest) -> HttpResponse:
        response = transport(request)
        payload = _base._validate_response(
            request, response, _PROVIDER_HOSTS["huggingface"]
        )
        requested = revision.strip()
        if _base._SHA40.fullmatch(requested) is not None and (
            not isinstance(payload.get("sha"), str)
            or payload["sha"].casefold() != requested.casefold()
        ):
            raise ValueError("Hugging Face response commit conflicts with requested revision")
        files = payload.get("siblings", [])
        if not isinstance(files, list) or len(files) > _base.MAX_FILES:
            raise ValueError("Hugging Face file list must be bounded")
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Hugging Face file must be an object")
            lfs = item.get("lfs")
            if lfs is None:
                lfs = {}
            if not isinstance(lfs, dict):
                raise ValueError("Hugging Face LFS metadata must be an object")
            sizes = [
                _base._optional_nonnegative_int(row.get("size"), "Hugging Face byte count")
                for row in (item, lfs)
            ]
            hashes = [
                _base._sha256(row.get("sha256"), "Hugging Face SHA-256")
                for row in (item, lfs)
            ]
            if any(size is not None and size > _MAX_FILE_BYTES for size in sizes):
                raise ValueError("Hugging Face byte count exceeds the snapshot bound")
            for label, values in (("byte count", sizes), ("SHA-256", hashes)):
                known = {value for value in values if value is not None}
                if len(known) > 1:
                    raise ValueError(f"Hugging Face file has conflicting {label} claims")
        return response

    snapshot = _base.snapshot_huggingface(repo_id, revision, guarded)
    for item in snapshot["record"]["files"]:
        item["id"] = _hf_file_id(item["path"])
    return _validate_snapshot(snapshot)


def _bounded_civitai_size(size_kb: Any, path: str) -> int:
    if not isinstance(size_kb, (int, float)) or isinstance(size_kb, bool):
        raise ValueError(
            f"Civitai file {path!r} sizeKB must be positive and finite"
        )
    try:
        numeric = float(size_kb)
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            f"Civitai file {path!r} sizeKB must be positive and finite"
        ) from exc
    if (
        not math.isfinite(numeric)
        or numeric <= 0
        or numeric > _MAX_FILE_BYTES / 1024
    ):
        raise ValueError(
            f"Civitai file {path!r} sizeKB must be positive, finite, and bounded"
        )
    byte_count = int(round(numeric * 1024))
    if byte_count <= 0 or byte_count > _MAX_FILE_BYTES:
        raise ValueError(f"Civitai file {path!r} byte count is invalid")
    return byte_count


def snapshot_civitai(version_id: int, transport: Transport) -> dict[str, Any]:
    """Create a Civitai snapshot after safely bounding every declared size."""

    def guarded(request: HttpRequest) -> HttpResponse:
        response = transport(request)
        payload = _base._validate_response(
            request,
            response,
            _PROVIDER_HOSTS["civitai"],
        )
        _base._positive_int(payload.get("id"), "Civitai returned version ID")
        model = payload.get("model")
        if isinstance(model, dict) and model.get("id") is not None:
            _base._positive_int(model["id"], "Civitai returned model ID")
        files = payload.get("files", [])
        if not isinstance(files, list) or len(files) > _base.MAX_FILES:
            raise ValueError(
                f"Civitai file list must contain at most {_base.MAX_FILES} files"
            )
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                raise ValueError(f"Civitai file {index} must be an object")
            path = _base._safe_file_path(item.get("name"))
            _bounded_civitai_size(item.get("sizeKB"), path)
        return response

    return _validate_snapshot(_base.snapshot_civitai(version_id, guarded))


def _require_false_authority(value: Mapping[str, Any], label: str) -> None:
    for field in (
        "download_authorized",
        "install_authorized",
        "execution_authorized",
    ):
        if value.get(field) is not False:
            raise ValueError(f"{label} must keep {field} false")


def _validate_stored_http(snapshot: Mapping[str, Any], provider: str) -> None:
    hosts = _PROVIDER_HOSTS[provider]
    request = snapshot.get("request")
    if not isinstance(request, dict) or request.get("method") != "GET":
        raise ValueError("Stored source snapshot request must be GET")
    if _base._require_https(request.get("url"), "stored request URL") not in hosts:
        raise ValueError("Stored request host does not match the provider")
    headers = _base._normalise_headers(request.get("headers", {}))
    if set(headers).intersection(_SENSITIVE_REQUEST_HEADERS):
        raise ValueError("Stored source snapshot cannot retain credential headers")

    response = snapshot.get("response")
    if (
        not isinstance(response, dict)
        or type(response.get("status")) is not int
        or response["status"] != 200
    ):
        raise ValueError("Stored source snapshot response must be HTTP 200")
    if _base._require_https(
        response.get("final_url"), "stored final URL"
    ) not in hosts:
        raise ValueError("Stored response host does not match the provider")
    redirects = response.get("redirect_chain")
    if not isinstance(redirects, list) or len(redirects) > _base.MAX_REDIRECTS:
        raise ValueError("Stored response redirect chain is invalid")
    for redirect in redirects:
        if _base._require_https(redirect, "stored redirect URL") not in hosts:
            raise ValueError("Stored response contains a cross-provider redirect")
    response_headers = _base._normalise_headers(response.get("headers", {}))
    if not set(response_headers).issubset(_base._HEADER_ALLOWLIST):
        raise ValueError("Stored response contains an unsupported header")


def _validate_record_routes(
    snapshot: Mapping[str, Any], expected_request: str, allowed_routes: set[str],
) -> None:
    """A provider host alone cannot bind a response to the selected source."""
    if snapshot["request"]["url"] != expected_request:
        raise ValueError("Stored request source identity does not match its record")
    response = snapshot["response"]
    final = response["final_url"]
    redirects = response["redirect_chain"]
    if final not in allowed_routes or any(url not in allowed_routes for url in redirects):
        raise ValueError("Snapshot response route does not match its source identity")
    if final != (redirects[-1] if redirects else expected_request):
        raise ValueError("Snapshot final URL does not match its observed redirect chain")


def _validate_claims(record: Mapping[str, Any]) -> None:
    claims = record.get("claims")
    if not isinstance(claims, list) or len(claims) > _base.MAX_CLAIMS:
        raise ValueError("Stored source claims must be a bounded array")
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Stored source claim must be an object")
        status = claim.get("status")
        text = claim.get("claim")
        if (
            not isinstance(status, str)
            or not status
            or len(status) > 128
            or not isinstance(text, str)
            or not text
            or len(text) > 8_192
        ):
            raise ValueError("Stored source claim is invalid")


def _validate_provider_hashes(value: Any, path: str) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError(f"Stored file {path!r} provider hashes are invalid")
    result: dict[str, str] = {}
    for key, digest in value.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 64
            or not isinstance(digest, str)
            or not digest
            or len(digest) > 256
        ):
            raise ValueError(f"Stored file {path!r} provider hash is invalid")
        folded = key.casefold()
        if folded in result:
            raise ValueError(
                f"Stored file {path!r} has duplicate provider hash {folded!r}"
            )
        result[folded] = digest
    return result


def _validate_files(record: Mapping[str, Any], provider: str) -> None:
    raw = record.get("files")
    if not isinstance(raw, list) or len(raw) > _base.MAX_FILES:
        raise ValueError("Snapshot files must be a bounded array")
    paths: set[str] = set()
    ids: set[str] = set()
    provider_ids: set[int] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Snapshot file record must be an object")
        path = _base._safe_file_path(item.get("path"))
        if path in paths:
            raise ValueError(f"Snapshot contains duplicate file path {path!r}")
        paths.add(path)
        file_id = item.get("id")
        if not isinstance(file_id, str) or not file_id or len(file_id) > 256:
            raise ValueError(f"Stored file {path!r} identity is invalid")
        if file_id in ids:
            raise ValueError(f"Snapshot contains duplicate file identity {file_id!r}")
        ids.add(file_id)
        if item.get("selected") is not False:
            raise ValueError(f"Stored file {path!r} must remain unselected")
        byte_count = item.get("bytes")
        if byte_count is not None and (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or byte_count > _MAX_FILE_BYTES
        ):
            raise ValueError(f"Stored file {path!r} byte count is invalid")
        digest = _base._sha256(
            item.get("sha256"),
            f"Stored file {path!r} SHA-256",
        )
        provider_hashes = _validate_provider_hashes(
            item.get("provider_hashes"), path
        )
        if "sha256" in provider_hashes and (
            digest is None or provider_hashes["sha256"].casefold() != digest
        ):
            raise ValueError(
                f"Stored file {path!r} has conflicting SHA-256 claims"
            )
        if provider == "huggingface":
            if file_id != _hf_file_id(path):
                raise ValueError(
                    f"Stored Hugging Face file {path!r} identity is not stable"
                )
        else:
            provider_file_id = _base._positive_int(
                item.get("provider_file_id"),
                f"Stored Civitai file {path!r} provider ID",
            )
            if provider_file_id in provider_ids:
                raise ValueError(
                    f"Snapshot contains duplicate Civitai file ID {provider_file_id}"
                )
            provider_ids.add(provider_file_id)
            if file_id != f"civitai-file-{provider_file_id}":
                raise ValueError(
                    f"Stored Civitai file {path!r} identity is inconsistent"
                )


def _validate_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Source snapshot must be an object")
    if value.get("schema") != "studio.adult-illustration-source-snapshot/v1":
        raise ValueError("Unsupported source snapshot schema")
    if value.get("kind") != "source-snapshot-proposal":
        raise ValueError("Unsupported source snapshot kind")
    if value.get("executable") is not False or value.get("authority") != "none":
        raise ValueError(
            "Source snapshot must remain non-executing with authority none"
        )
    for field in (
        "download_authorized",
        "install_authorized",
        "execution_authorized",
        "generation_submitted",
        "training_authorized",
    ):
        if value.get(field) is not False:
            raise ValueError(f"Source snapshot must keep {field} false")
    _base._sha256(
        value.get("raw_payload_sha256"),
        "Source snapshot payload SHA-256",
        allow_none=False,
    )
    provider = value.get("provider")
    if provider not in _PROVIDER_HOSTS:
        raise ValueError(f"Unsupported snapshot provider {provider!r}")
    _validate_stored_http(value, provider)

    record = value.get("record")
    if not isinstance(record, dict):
        raise ValueError("Source snapshot record must be an object")
    if record.get("provider") != provider or record.get("synthetic") is not False:
        raise ValueError("Stored source record provider identity is inconsistent")
    if record.get("snapshot_state") != "pinned":
        raise ValueError("Stored source record must remain pinned")
    if record.get("terms_state") not in {"snapshotted", "unknown"}:
        raise ValueError("Stored source record terms state is invalid")
    _require_false_authority(record, "Stored source record")
    _validate_claims(record)

    canonical_host = _base._require_https(
        record.get("canonical_url"), "stored canonical URL"
    )
    if canonical_host not in _PROVIDER_HOSTS[provider]:
        raise ValueError("Stored canonical URL does not match the provider")

    if provider == "huggingface":
        repo_id = record.get("provider_model_id")
        revision = record.get("immutable_revision")
        if not isinstance(repo_id, str) or _base._HF_REPO.fullmatch(repo_id) is None:
            raise ValueError("Stored Hugging Face repository identity is invalid")
        if record.get("provider_version_id") is not None:
            raise ValueError("Stored Hugging Face version identity must be null")
        if not isinstance(revision, str) or _base._SHA40.fullmatch(revision) is None:
            raise ValueError("Stored Hugging Face immutable revision is invalid")
        requested = record.get("requested_revision")
        if (
            not isinstance(requested, str) or not requested or len(requested) > 200
            or requested != requested.strip()
        ):
            raise ValueError("Stored Hugging Face requested revision is invalid")
        if _base._SHA40.fullmatch(requested) is not None and (
            requested.casefold() != revision.casefold()
        ):
            raise ValueError("Stored immutable revision conflicts with requested commit")
        metadata = f"https://huggingface.co/api/models/{repo_id}/revision/"
        expected_request = f"{metadata}{quote(requested, safe='')}?blobs=true"
        allowed_routes = {
            expected_request, f"{metadata}{revision.casefold()}?blobs=true",
        }
        expected_id = (
            f"huggingface-{repo_id.replace('/', '--').casefold()}-"
            f"{revision.casefold()[:12]}"
        )
        expected_url = (
            f"https://huggingface.co/{repo_id}/tree/{revision.casefold()}"
        )
        if (
            record.get("id") != expected_id
            or record.get("canonical_url") != expected_url
        ):
            raise ValueError("Stored Hugging Face source identity is inconsistent")
    else:
        model_id = _base._positive_int(
            record.get("provider_model_id"), "Stored Civitai model ID"
        )
        version_id = _base._positive_int(
            record.get("provider_version_id"), "Stored Civitai version ID"
        )
        if record.get("immutable_revision") != str(version_id):
            raise ValueError("Stored Civitai immutable revision is inconsistent")
        expected_request = f"https://civitai.com/api/v1/model-versions/{version_id}"
        allowed_routes = {
            expected_request, f"https://www.civitai.com/api/v1/model-versions/{version_id}",
        }
        expected_id = f"civitai-{model_id}-{version_id}"
        expected_url = (
            f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
        )
        if (
            record.get("id") != expected_id
            or record.get("canonical_url") != expected_url
        ):
            raise ValueError("Stored Civitai source identity is inconsistent")

    _validate_record_routes(value, expected_request, allowed_routes)
    _validate_files(record, provider)
    return value


def diff_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare two fully validated immutable source proposals."""

    _validate_snapshot(before)
    _validate_snapshot(after)
    return _base.diff_snapshots(before, after)


def read_snapshot_json(data: bytes) -> dict[str, Any]:
    """Parse and fully validate a stored source snapshot without network access."""

    return _validate_snapshot(_base._parse_json(data))


__all__ = [
    "HttpRequest",
    "HttpResponse",
    "snapshot_huggingface",
    "snapshot_civitai",
    "diff_snapshots",
    "read_snapshot_json",
]
