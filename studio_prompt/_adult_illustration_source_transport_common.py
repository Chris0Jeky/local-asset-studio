"""Shared contracts for explicit adult-illustration metadata transport."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from . import _adult_illustration_source_intake_impl as _source

HttpRequest = _source.HttpRequest
HttpResponse = _source.HttpResponse
MAX_PROVIDER_RESPONSE_BYTES = _source.MAX_RESPONSE_BYTES
MAX_CACHE_RECORD_BYTES = 4_194_304
USER_AGENT = "local-asset-studio-source-snapshot/1"
CACHE_SCHEMA = "studio.adult-illustration-source-response-cache/v1"
FETCH_SCHEMA = "studio.adult-illustration-source-fetch/v1"
RECEIPT_SCHEMA = "studio.adult-illustration-source-transport-receipt/v1"

AUTHORITY = {
    "download_authorized": False,
    "install_authorized": False,
    "execution_authorized": False,
    "generation_submitted": False,
    "training_authorized": False,
}
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}
REQUEST_IDENTITY_HEADERS = {"accept", "user-agent"}
INTERNAL_REQUEST_HEADERS = {
    "accept",
    "user-agent",
    "if-none-match",
    "if-modified-since",
    "accept-encoding",
}
RESPONSE_CACHE_HEADERS = set(_source._HEADER_ALLOWLIST)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
TRANSIENT_STATUSES = {429, 502, 503, 504}
SHA256 = re.compile(r"[0-9a-f]{64}")
HF_METADATA_PATH = re.compile(
    r"/api/models/[A-Za-z0-9][A-Za-z0-9._-]{0,95}/"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/revision/[^/]+"
)
CIVITAI_METADATA_PATH = re.compile(r"/api/v1/model-versions/[1-9][0-9]*")


def normalise_headers(headers: Mapping[str, str], label: str) -> dict[str, str]:
    try:
        return _source._normalise_headers(headers)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {exc}") from exc


def endpoint_provider(url: str, label: str = "metadata URL") -> str:
    if not isinstance(url, str) or not url or len(url) > 4_096:
        raise ValueError(f"{label} is invalid")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (parsed.port is not None and parsed.port != 443)
    ):
        raise ValueError(f"{label} must be credential-free HTTPS")
    host = parsed.hostname.casefold()
    if host == "huggingface.co":
        if HF_METADATA_PATH.fullmatch(parsed.path) is None:
            raise ValueError("Hugging Face URL is not a supported metadata endpoint")
        try:
            query = parse_qs(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
            )
        except ValueError as exc:
            raise ValueError("Hugging Face metadata query is invalid") from exc
        if query != {"blobs": ["true"]}:
            raise ValueError("Hugging Face metadata endpoint requires blobs=true only")
        return "huggingface"
    if host in {"civitai.com", "www.civitai.com"}:
        if CIVITAI_METADATA_PATH.fullmatch(parsed.path) is None or parsed.query:
            raise ValueError("Civitai URL is not a supported metadata endpoint")
        return "civitai"
    raise ValueError(f"{label} host is not supported")


def validate_base_request(request: HttpRequest) -> str:
    if not isinstance(request, HttpRequest) or request.method != "GET":
        raise ValueError("Provider metadata transport accepts HttpRequest GET only")
    provider = endpoint_provider(request.url, "request URL")
    headers = normalise_headers(request.headers, "request headers")
    if set(headers).intersection(SENSITIVE_HEADERS):
        raise ValueError("Provider metadata request cannot contain credential headers")
    if set(headers) != REQUEST_IDENTITY_HEADERS:
        raise ValueError("Provider metadata request has unsupported headers")
    if "application/json" not in headers["accept"].casefold():
        raise ValueError("Provider metadata request must accept JSON")
    if headers["user-agent"] != USER_AGENT:
        raise ValueError("Provider metadata request user-agent is not the reviewed value")
    return provider


def identity_headers(headers: Mapping[str, str]) -> dict[str, str]:
    values = normalise_headers(headers, "request headers")
    return {
        key: values[key]
        for key in sorted(REQUEST_IDENTITY_HEADERS)
        if key in values
    }


def request_identity(request: HttpRequest) -> dict[str, Any]:
    return {
        "method": request.method,
        "url": request.url,
        "headers": identity_headers(request.headers),
    }


def request_key(request: HttpRequest) -> str:
    encoded = json.dumps(
        request_identity(request),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_validator(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 2_048
        or "\r" in value
        or "\n" in value
    ):
        raise ValueError(f"Cached {label} validator is invalid")
    return value.strip()


def cached_headers(headers: Mapping[str, str]) -> dict[str, str]:
    values = normalise_headers(headers, "response headers")
    return {
        key: value
        for key, value in sorted(values.items())
        if key in RESPONSE_CACHE_HEADERS
    }


def validate_json_media_type(headers: Mapping[str, str]) -> None:
    values = normalise_headers(headers, "response headers")
    encoding = values.get("content-encoding", "identity").casefold()
    if encoding not in {"", "identity"}:
        raise ValueError("Compressed provider metadata responses are not supported")
    media = values.get("content-type", "").split(";", 1)[0].strip().casefold()
    if media != "application/json" and not media.endswith("+json"):
        raise ValueError("Provider response content type is not JSON")


def parse_provider_json(body: bytes, maximum: int) -> dict[str, Any]:
    if len(body) > maximum:
        raise ValueError(f"Provider response exceeds {maximum} bytes")
    return _source._parse_json(body)


def parse_cache_json(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_CACHE_RECORD_BYTES:
        raise ValueError("Source response cache record is oversized")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_source._pairs,
            parse_constant=_source._reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("Source response cache is not valid UTF-8") from exc
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"Invalid source response cache JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Source response cache top level must be an object")
    return value


@dataclass(frozen=True)
class MetadataPolicy:
    """Reviewed limits for one explicit metadata fetch."""

    timeout_seconds: float = 15.0
    max_attempts: int = 2
    max_redirects: int = 3
    max_response_bytes: int = MAX_PROVIDER_RESPONSE_BYTES
    retry_backoff_seconds: float = 0.25

    def __post_init__(self) -> None:
        timeout = self.timeout_seconds
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(float(timeout))
            or not 0 < float(timeout) <= 120
        ):
            raise ValueError("timeout_seconds must be finite and in (0, 120]")
        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or not 1 <= self.max_attempts <= 4
        ):
            raise ValueError("max_attempts must be between 1 and 4")
        if (
            not isinstance(self.max_redirects, int)
            or isinstance(self.max_redirects, bool)
            or not 0 <= self.max_redirects <= 5
        ):
            raise ValueError("max_redirects must be between 0 and 5")
        if (
            not isinstance(self.max_response_bytes, int)
            or isinstance(self.max_response_bytes, bool)
            or not 1 <= self.max_response_bytes <= MAX_PROVIDER_RESPONSE_BYTES
        ):
            raise ValueError(
                f"max_response_bytes must be between 1 and {MAX_PROVIDER_RESPONSE_BYTES}"
            )
        backoff = self.retry_backoff_seconds
        if (
            not isinstance(backoff, (int, float))
            or isinstance(backoff, bool)
            or not math.isfinite(float(backoff))
            or not 0 <= float(backoff) <= 10
        ):
            raise ValueError("retry_backoff_seconds must be finite and in [0, 10]")


@dataclass(frozen=True)
class WireResponse:
    """One non-following HTTP exchange response."""

    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url:
            raise ValueError("Wire response URL is invalid")
        if not isinstance(self.status, int) or isinstance(self.status, bool):
            raise TypeError("Wire response status must be an integer")
        if not isinstance(self.body, bytes):
            raise TypeError("Wire response body must be bytes")
        object.__setattr__(
            self,
            "headers",
            MappingProxyType(normalise_headers(self.headers, "wire response headers")),
        )
