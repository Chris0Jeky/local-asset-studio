"""Bounded GET-only HTTP machinery for adult-illustration metadata."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
from http.client import HTTPException
from threading import Lock
import time
from typing import Any, Callable, Iterator, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ._adult_illustration_source_transport_cache import SnapshotResponseCache
from ._adult_illustration_source_transport_common import (
    AUTHORITY,
    INTERNAL_REQUEST_HEADERS,
    MAX_PROVIDER_RESPONSE_BYTES,
    RECEIPT_SCHEMA,
    REDIRECT_STATUSES,
    TRANSIENT_STATUSES,
    HttpRequest,
    HttpResponse,
    MetadataPolicy,
    WireResponse,
    cached_headers,
    endpoint_provider,
    normalise_headers,
    parse_provider_json,
    request_key,
    safe_validator,
    validate_base_request,
    validate_json_media_type,
)

Exchange = Callable[[HttpRequest, float], WireResponse]
Sleeper = Callable[[float], None]


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _read_bounded_stream(stream: Any, maximum: int) -> bytes:
    try:
        data = stream.read(maximum + 1)
    except HTTPException as exc:
        raise ConnectionError(
            f"Provider metadata response read failed: {exc}"
        ) from exc
    if not isinstance(data, bytes):
        raise ValueError("HTTP response reader did not return bytes")
    if len(data) > maximum:
        raise ValueError(f"Provider response exceeds {maximum} bytes")
    return data


class StdlibMetadataExchange:
    """Credential-free stdlib exchange with proxy discovery and redirects off."""

    def __init__(self, maximum_bytes: int = MAX_PROVIDER_RESPONSE_BYTES):
        if (
            not isinstance(maximum_bytes, int)
            or isinstance(maximum_bytes, bool)
            or not 1 <= maximum_bytes <= MAX_PROVIDER_RESPONSE_BYTES
        ):
            raise ValueError("maximum_bytes is invalid")
        self.maximum_bytes = maximum_bytes
        self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def __call__(self, request: HttpRequest, timeout: float) -> WireResponse:
        wire = Request(request.url, headers=dict(request.headers), method="GET")
        try:
            with self._opener.open(wire, timeout=timeout) as response:
                return WireResponse(
                    url=response.geturl(),
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=_read_bounded_stream(response, self.maximum_bytes),
                )
        except HTTPError as exc:
            try:
                body = _read_bounded_stream(exc, self.maximum_bytes)
            finally:
                exc.close()
            return WireResponse(
                url=exc.geturl() or request.url,
                status=exc.code,
                headers=dict(exc.headers.items()) if exc.headers else {},
                body=body,
            )
        except TimeoutError:
            raise
        except HTTPException as exc:
            raise ConnectionError(
                f"Provider metadata request failed: {exc}"
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(str(exc.reason)) from exc
            raise ConnectionError(
                f"Provider metadata request failed: {exc.reason}"
            ) from exc


def _validator_headers(cached: HttpResponse | None) -> dict[str, str]:
    if cached is None:
        return {}
    result: dict[str, str] = {}
    if "etag" in cached.headers:
        result["if-none-match"] = safe_validator(cached.headers["etag"], "ETag")
    if "last-modified" in cached.headers:
        result["if-modified-since"] = safe_validator(
            cached.headers["last-modified"],
            "Last-Modified",
        )
    return result


def _wire_request(request: HttpRequest, validators: Mapping[str, str]) -> HttpRequest:
    headers = dict(request.headers)
    headers.update(validators)
    headers["accept-encoding"] = "identity"
    values = normalise_headers(headers, "wire request headers")
    if set(values).difference(INTERNAL_REQUEST_HEADERS):
        raise ValueError("Wire metadata request has unsupported headers")
    return HttpRequest(url=request.url, headers=values)


def _validate_not_modified(
    wire: WireResponse,
    cached: HttpResponse,
    validators: Mapping[str, str],
    redirects: tuple[str, ...],
) -> None:
    if not validators:
        raise ValueError("HTTP 304 cannot be accepted without a cache validator")
    if wire.url != cached.final_url or redirects != cached.redirect_chain:
        raise ValueError("HTTP 304 metadata route does not match cached response")
    checks = {
        "etag": "if-none-match",
        "last-modified": "if-modified-since",
    }
    for response_name, request_name in checks.items():
        returned = wire.headers.get(response_name)
        sent = validators.get(request_name)
        cached_value = cached.headers.get(response_name)
        if returned is not None and sent is not None and returned != sent:
            raise ValueError(
                f"HTTP 304 returned a conflicting {response_name} validator"
            )
        if returned is not None and cached_value is not None and returned != cached_value:
            raise ValueError(f"HTTP 304 returned a stale {response_name} validator")


def _validate_cached_policy(
    cached: HttpResponse,
    policy: MetadataPolicy,
) -> None:
    """Apply the active fetch limits even when no network request is needed."""

    if len(cached.body) > policy.max_response_bytes:
        raise ValueError(
            "Cached provider response exceeds the current response byte limit"
        )
    if len(cached.redirect_chain) > policy.max_redirects:
        raise ValueError(
            "Cached provider redirect chain exceeds the current redirect limit"
        )


class BoundedProviderTransport:
    """Implement the source parser's injected transport interface safely."""

    def __init__(
        self,
        *,
        exchange: Exchange | None = None,
        policy: MetadataPolicy | None = None,
        cache: SnapshotResponseCache | None = None,
        refresh: bool = False,
        sleeper: Sleeper = time.sleep,
    ):
        self.policy = policy or MetadataPolicy()
        self.exchange = exchange or StdlibMetadataExchange(
            self.policy.max_response_bytes
        )
        if not callable(self.exchange):
            raise TypeError("exchange must be callable")
        if cache is not None and not isinstance(cache, SnapshotResponseCache):
            raise TypeError("cache must be SnapshotResponseCache")
        if not isinstance(refresh, bool):
            raise TypeError("refresh must be boolean")
        if not callable(sleeper):
            raise TypeError("sleeper must be callable")
        self.cache = cache
        self.refresh = refresh
        self.sleeper = sleeper
        self._fetch_lock = Lock()
        self._awaiting_finalization = False
        self._receipt: dict[str, Any] | None = None
        self._pending: tuple[HttpRequest, HttpResponse] | None = None

    @contextmanager
    def _fetch_scope(self) -> Iterator[None]:
        """Own a complete facade fetch, including parsing and receipt capture."""
        if not self._fetch_lock.acquire(blocking=False):
            raise RuntimeError("Provider metadata transport is already in use")
        try:
            # A raw caller may already own a response awaiting finalization.
            # Refusing this new fetch must not abort that caller's pending data.
            if self._pending is not None or self._awaiting_finalization:
                raise RuntimeError("Previous provider response was not finalized")
            self._receipt = None
            try:
                yield
            except BaseException:
                self.abort()
                raise
        finally:
            self._fetch_lock.release()

    @property
    def receipt(self) -> dict[str, Any]:
        if self._receipt is None:
            raise RuntimeError("No provider metadata request has completed")
        return copy.deepcopy(self._receipt)

    def _exchange_with_retries(
        self,
        request: HttpRequest,
    ) -> tuple[WireResponse, int]:
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                response = self.exchange(request, float(self.policy.timeout_seconds))
                if not isinstance(response, WireResponse):
                    raise TypeError("Metadata exchange must return WireResponse")
                if response.url != request.url:
                    raise ValueError(
                        "Wire response URL does not match the exchange request"
                    )
                if len(response.body) > self.policy.max_response_bytes:
                    raise ValueError(
                        f"Provider response exceeds {self.policy.max_response_bytes} bytes"
                    )
            except (TimeoutError, ConnectionError, OSError) as exc:
                if attempt >= self.policy.max_attempts:
                    raise ValueError(
                        f"Provider metadata GET failed after {attempt} attempt(s): {exc}"
                    ) from exc
                self.sleeper(
                    float(self.policy.retry_backoff_seconds) * (2 ** (attempt - 1))
                )
                continue
            if (
                response.status in TRANSIENT_STATUSES
                and attempt < self.policy.max_attempts
            ):
                self.sleeper(
                    float(self.policy.retry_backoff_seconds) * (2 ** (attempt - 1))
                )
                continue
            return response, attempt
        raise AssertionError("unreachable retry state")

    def _perform(
        self,
        provider: str,
        request: HttpRequest,
    ) -> tuple[HttpResponse | None, WireResponse, int, tuple[str, ...]]:
        current = request
        redirects: list[str] = []
        total_attempts = 0
        while True:
            wire, attempts = self._exchange_with_retries(current)
            total_attempts += attempts
            if wire.status not in REDIRECT_STATUSES:
                break
            location = wire.headers.get("location")
            if not isinstance(location, str) or not location:
                raise ValueError("Provider redirect is missing a Location header")
            destination = urljoin(current.url, location)
            target_provider = endpoint_provider(destination, "redirect URL")
            if target_provider != provider:
                raise ValueError("Cross-provider redirect is not allowed")
            redirects.append(destination)
            if len(redirects) > self.policy.max_redirects:
                raise ValueError(
                    f"Provider redirect chain exceeds {self.policy.max_redirects}"
                )
            current = HttpRequest(url=destination, headers=dict(current.headers))

        if wire.status == 304:
            return None, wire, total_attempts, tuple(redirects)
        if wire.status == 200:
            validate_json_media_type(wire.headers)
            parse_provider_json(wire.body, self.policy.max_response_bytes)
        response = HttpResponse(
            request_url=request.url,
            final_url=current.url,
            status=wire.status,
            headers=cached_headers(wire.headers),
            body=wire.body,
            redirect_chain=tuple(redirects),
        )
        return response, wire, total_attempts, tuple(redirects)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._pending is not None or self._awaiting_finalization:
            raise RuntimeError("Previous provider response was not finalized")
        provider = validate_base_request(request)
        key = request_key(request)
        cached = self.cache.load(request) if self.cache is not None else None
        if cached is not None:
            _validate_cached_policy(cached, self.policy)
        if cached is not None and not self.refresh:
            self._receipt = self._make_receipt(
                provider=provider,
                request=request,
                response=cached,
                key=key,
                cache_state="hit",
                network_performed=False,
                attempts=0,
                redirects=len(cached.redirect_chain),
                validators=(),
                wire_status=200,
            )
            self._awaiting_finalization = True
            return cached

        validators = _validator_headers(cached)
        outbound = _wire_request(request, validators)
        response, wire, attempts, redirects = self._perform(provider, outbound)
        if wire.status == 304:
            if cached is None:
                raise ValueError("HTTP 304 cannot be accepted without a cached response")
            _validate_not_modified(wire, cached, validators, redirects)
            response = cached
            cache_state = "revalidated"
        else:
            if response is None:
                raise AssertionError("missing provider response")
            cache_state = (
                "disabled"
                if self.cache is None
                else ("refreshed" if cached is not None else "miss")
            )
            if response.status == 200 and self.cache is not None:
                self._pending = (request, response)

        self._receipt = self._make_receipt(
            provider=provider,
            request=request,
            response=response,
            key=key,
            cache_state=cache_state,
            network_performed=True,
            attempts=attempts,
            redirects=len(redirects),
            validators=tuple(sorted(validators)),
            wire_status=wire.status,
        )
        self._awaiting_finalization = True
        return response

    def _make_receipt(
        self,
        *,
        provider: str,
        request: HttpRequest,
        response: HttpResponse,
        key: str,
        cache_state: str,
        network_performed: bool,
        attempts: int,
        redirects: int,
        validators: tuple[str, ...],
        wire_status: int,
    ) -> dict[str, Any]:
        return {
            "schema": RECEIPT_SCHEMA,
            "kind": "provider-metadata-transport-receipt",
            "executable": False,
            "authority": "none",
            "provider": provider,
            "request_url": request.url,
            "request_key": key,
            "cache_state": cache_state,
            "network_performed": network_performed,
            "attempts": attempts,
            "redirects": redirects,
            "timeout_seconds": float(self.policy.timeout_seconds),
            "max_attempts": self.policy.max_attempts,
            "max_redirects": self.policy.max_redirects,
            "max_response_bytes": self.policy.max_response_bytes,
            "validators_sent": list(validators),
            "wire_status": wire_status,
            "effective_status": response.status,
            "final_url": response.final_url,
            "response_payload_sha256": hashlib.sha256(response.body).hexdigest(),
            "credentials_used": False,
            "model_bytes_downloaded": False,
            **AUTHORITY,
        }

    def finalize(self, raw_payload_sha256: str) -> None:
        if self._receipt is None:
            raise RuntimeError("No provider metadata request has completed")
        if (
            not isinstance(raw_payload_sha256, str)
            or raw_payload_sha256
            != self._receipt["response_payload_sha256"]
        ):
            self.abort()
            raise ValueError("Parsed snapshot payload identity does not match transport")
        if self._pending is not None:
            request, response = self._pending
            if self.cache is None:
                raise AssertionError("pending cache write without cache")
            stored_key = self.cache.store(request, response)
            if stored_key != self._receipt["request_key"]:
                raise ValueError("Stored cache identity changed during finalization")
            self._pending = None
        self._awaiting_finalization = False

    def abort(self) -> None:
        self._awaiting_finalization = False
        self._pending = None
        self._receipt = None
