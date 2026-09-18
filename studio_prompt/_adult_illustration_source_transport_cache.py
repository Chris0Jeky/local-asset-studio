"""Exact-identity cache for adult-illustration provider metadata responses."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
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
    parse_cache_json,
    parse_provider_json,
    request_identity,
    request_key,
    validate_json_media_type,
)


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

    def load(self, request: HttpRequest) -> HttpResponse | None:
        path = self.path_for(request)
        if not path.exists():
            return None
        if path.is_symlink():
            raise ValueError("Source response cache entry cannot be a symlink")
        resolved = path.resolve(strict=True)
        if resolved.parent != self._resolved_root or not resolved.is_file():
            raise ValueError("Source response cache entry escapes its cache root")
        if resolved.stat().st_size > MAX_CACHE_RECORD_BYTES:
            raise ValueError("Source response cache record is oversized")
        record = parse_cache_json(resolved.read_bytes())
        expected_keys = {
            "schema",
            "cache_key",
            "request",
            "response",
            "body_base64",
            "body_bytes",
            "body_sha256",
            *tuple(AUTHORITY),
        }
        if set(record) != expected_keys or record.get("schema") != CACHE_SCHEMA:
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
        redirects = response.get("redirect_chain")
        if (
            response.get("status") != 200
            or not isinstance(redirects, list)
            or len(redirects) > 5
            or not all(isinstance(item, str) for item in redirects)
        ):
            raise ValueError("Source response cache response state is invalid")
        headers = cached_headers(response.get("headers", {}))
        validate_json_media_type(headers)
        return HttpResponse(
            request_url=request.url,
            final_url=response.get("final_url"),
            status=200,
            headers=headers,
            body=body,
            redirect_chain=tuple(redirects),
        )

    def store(self, request: HttpRequest, response: HttpResponse) -> str:
        if not isinstance(response, HttpResponse) or response.status != 200:
            raise ValueError("Only successful metadata responses can be cached")
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
                "redirect_chain": list(response.redirect_chain),
            },
            "body_base64": base64.b64encode(response.body).decode("ascii"),
            "body_bytes": len(response.body),
            "body_sha256": hashlib.sha256(response.body).hexdigest(),
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
