"""Exact-identity cache for adult-illustration provider metadata responses."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ._adult_illustration_source_transport_common import (
    AUTHORITY,
    CACHE_SCHEMA,
    MAX_CACHE_RECORD_BYTES,
    MAX_PROVIDER_RESPONSE_BYTES,
    SHA256,
    HttpRequest,
    HttpResponse,
    cached_headers,
    endpoint_provider,
    parse_cache_json,
    parse_provider_json,
    request_identity,
    request_key,
    validate_json_media_type,
)


_MAX_STORED_AT_CHARS = 128
_CACHE_FUTURE_SKEW_SECONDS = 300


def _utcnow_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_stored_at(value: object) -> datetime:
    """Validate persisted UTC write-time evidence without trusting mtime."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_STORED_AT_CHARS
        or "\r" in value
        or "\n" in value
    ):
        raise ValueError("Source response cache write time is invalid")
    text = value.strip()
    if not text:
        raise ValueError("Source response cache write time is invalid")
    normalised = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError as exc:
        raise ValueError(
            "Source response cache write time is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError("Source response cache write time must carry UTC timezone")
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("Source response cache write time must be UTC")
    now = datetime.now(timezone.utc).timestamp()
    if parsed.timestamp() - now > _CACHE_FUTURE_SKEW_SECONDS:
        raise ValueError("Source response cache write time is in the future")
    return parsed


def _validate_response_routes(
    request: HttpRequest,
    final_url: object,
    redirects: object,
) -> tuple[str, tuple[str, ...]]:
    """Revalidate cached routes against the exact reviewed endpoint families."""

    provider = endpoint_provider(request.url, "cache request URL")
    if not isinstance(redirects, (list, tuple)) or len(redirects) > 5:
        raise ValueError("Source response cache redirect chain is invalid")
    validated_redirects: list[str] = []
    for redirect in redirects:
        if not isinstance(redirect, str):
            raise ValueError("Source response cache redirect URL is invalid")
        if endpoint_provider(redirect, "cached redirect URL") != provider:
            raise ValueError(
                "Source response cache redirect crosses the provider boundary"
            )
        validated_redirects.append(redirect)
    if endpoint_provider(final_url, "cached final URL") != provider:
        raise ValueError(
            "Source response cache final URL crosses the provider boundary"
        )
    return provider, tuple(validated_redirects)


class SnapshotResponseCache:
    """Cache exact public metadata responses, never model or package bytes."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ValueError("Source response cache root cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        self._resolved_root = self.root.resolve(strict=True)
        if not self._resolved_root.is_dir():
            raise ValueError("Source response cache root must be a directory")

    def path_for(self, request: HttpRequest) -> Path:
        return self._resolved_root / f"{request_key(request)}.json"

    def load_entry(
        self, request: HttpRequest
    ) -> tuple[HttpResponse | None, str | None]:
        """Load a validated cached response with its persisted write time.

        Returns ``(None, None)`` on a miss. Legacy v1 records without
        ``stored_at`` return ``(response, None)`` so receipts report age
        unknown instead of inventing a date.
        """
        path = self.path_for(request)
        if not path.exists():
            return None, None
        if path.is_symlink():
            raise ValueError("Source response cache entry cannot be a symlink")
        resolved = path.resolve(strict=True)
        if resolved.parent != self._resolved_root or not resolved.is_file():
            raise ValueError("Source response cache entry escapes its cache root")
        if resolved.stat().st_size > MAX_CACHE_RECORD_BYTES:
            raise ValueError("Source response cache record is oversized")
        record = parse_cache_json(resolved.read_bytes())
        base_keys = {
            "schema",
            "cache_key",
            "request",
            "response",
            "body_base64",
            "body_bytes",
            "body_sha256",
            *tuple(AUTHORITY),
        }
        keys = set(record)
        stored_at: str | None = None
        if keys == base_keys:
            stored_at = None
        elif keys == base_keys | {"stored_at"}:
            stored_at = record.get("stored_at")
            _parse_stored_at(stored_at)
        else:
            raise ValueError("Source response cache record has an invalid schema")
        if record.get("schema") != CACHE_SCHEMA:
            raise ValueError("Source response cache record has an invalid schema")
        for field, expected in AUTHORITY.items():
            if record.get(field) is not expected:
                raise ValueError(f"Source response cache must keep {field} false")
        expected_key = request_key(request)
        if record.get("cache_key") != expected_key:
            raise ValueError("Source response cache key does not match its request")
        if record.get("request") != request_identity(request):
            raise ValueError("Source response cache request identity does not match")

        encoded = record.get("body_base64")
        if not isinstance(encoded, str) or len(encoded) > MAX_CACHE_RECORD_BYTES:
            raise ValueError("Source response cache body is invalid")
        try:
            body = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("Source response cache body is not valid base64") from exc
        byte_count = record.get("body_bytes")
        if (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count != len(body)
            or len(body) > MAX_PROVIDER_RESPONSE_BYTES
        ):
            raise ValueError("Source response cache byte count is invalid")
        digest = record.get("body_sha256")
        actual_digest = hashlib.sha256(body).hexdigest()
        if (
            not isinstance(digest, str)
            or SHA256.fullmatch(digest) is None
            or digest != actual_digest
        ):
            raise ValueError("Source response cache SHA-256 does not match its body")
        parse_provider_json(body, MAX_PROVIDER_RESPONSE_BYTES)

        response = record.get("response")
        if not isinstance(response, dict) or set(response) != {
            "final_url",
            "status",
            "headers",
            "redirect_chain",
        }:
            raise ValueError("Source response cache response envelope is invalid")
        if response.get("status") != 200:
            raise ValueError("Source response cache response state is invalid")
        _, redirects = _validate_response_routes(
            request,
            response.get("final_url"),
            response.get("redirect_chain"),
        )
        headers = cached_headers(response.get("headers", {}))
        validate_json_media_type(headers)
        cached = HttpResponse(
            request_url=request.url,
            final_url=response.get("final_url"),
            status=200,
            headers=headers,
            body=body,
            redirect_chain=redirects,
        )
        return cached, stored_at

    def load(self, request: HttpRequest) -> HttpResponse | None:
        cached, _ = self.load_entry(request)
        return cached

    def store(self, request: HttpRequest, response: HttpResponse) -> str:
        if not isinstance(response, HttpResponse) or response.status != 200:
            raise ValueError("Only successful metadata responses can be cached")
        if response.request_url != request.url:
            raise ValueError("Source response cache request identity changed")
        _, redirects = _validate_response_routes(
            request,
            response.final_url,
            response.redirect_chain,
        )
        parse_provider_json(response.body, MAX_PROVIDER_RESPONSE_BYTES)
        validate_json_media_type(response.headers)
        key = request_key(request)
        path = self.path_for(request)
        if path.is_symlink():
            raise ValueError("Source response cache entry cannot be a symlink")
        record = {
            "schema": CACHE_SCHEMA,
            "cache_key": key,
            "request": request_identity(request),
            "response": {
                "final_url": response.final_url,
                "status": response.status,
                "headers": cached_headers(response.headers),
                "redirect_chain": list(redirects),
            },
            "body_base64": base64.b64encode(response.body).decode("ascii"),
            "body_bytes": len(response.body),
            "body_sha256": hashlib.sha256(response.body).hexdigest(),
            "stored_at": _utcnow_isoformat(),
            **AUTHORITY,
        }
        payload = (
            json.dumps(
                record,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if len(payload) > MAX_CACHE_RECORD_BYTES:
            raise ValueError("Source response cache record is oversized")

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="xb",
                prefix=f".{key}.",
                suffix=".tmp",
                dir=self._resolved_root,
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return key
