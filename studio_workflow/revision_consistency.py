"""Pure value facts shared by revisioned stores; no SQL or side effects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Any

from .core import MAX_BYTES, canonical, decode, need


@dataclass(frozen=True)
class CanonicalValue:
    """One bounded canonical JSON value and its exact persisted-byte binding."""

    value: Any
    raw: bytes
    sha256: str
    bytes: int


@dataclass(frozen=True)
class StoredValue:
    """Decoded stored JSON plus its observed and recorded digest fact."""

    value: Any
    observed_sha256: str
    stored_sha256: str

    @property
    def matches(self) -> bool:
        return self.observed_sha256 == self.stored_sha256


class RequestState(Enum):
    ABSENT = 'absent'
    REPLAY = 'replay'
    CONFLICT = 'conflict'


@dataclass(frozen=True)
class HeadComparison:
    expected: int
    current: int
    current_sha256: str | None = None

    @property
    def matches(self) -> bool:
        return self.expected == self.current


@dataclass(frozen=True)
class ByteBudget:
    used: int
    added: int
    limit: int

    @property
    def total(self) -> int:
        return self.used + self.added

    @property
    def fits(self) -> bool:
        return self.total <= self.limit


def canonical_sha256(value: Any) -> str:
    """Hash canonical bytes without imposing a second payload-size boundary.

    Use this only for internal identity envelopes assembled from values that have
    already passed their domain validator. The envelope is not itself persisted
    or accepted as another public payload.
    """
    return hashlib.sha256(canonical(value)).hexdigest()


def canonical_value(value: Any) -> CanonicalValue:
    """Canonicalize once, enforce the shared JSON bound, and bind exact bytes."""
    raw = canonical(value)
    normalized = decode(raw)
    return CanonicalValue(
        value=normalized,
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def stored_value(raw: bytes | str, stored_sha256: str) -> StoredValue:
    value = decode(raw)
    observed = canonical_value(value).sha256
    return StoredValue(value=value, observed_sha256=observed, stored_sha256=stored_sha256)


def classify_request(stored_sha256: str | None, supplied_sha256: str) -> RequestState:
    if stored_sha256 is None:
        return RequestState.ABSENT
    return RequestState.REPLAY if stored_sha256 == supplied_sha256 else RequestState.CONFLICT


def compare_head(expected: int, current: int, current_sha256: str | None = None) -> HeadComparison:
    return HeadComparison(expected=expected, current=current, current_sha256=current_sha256)


def byte_budget(used: int, added: int, limit: int) -> ByteBudget:
    return ByteBudget(used=used, added=added, limit=limit)


@dataclass(frozen=True)
class StoredBytes(StoredValue):
    """Exact received bytes and digest facts, without rewriting stored evidence."""

    raw: bytes

    @property
    def bytes(self) -> int:
        return len(self.raw)


def exact_stored_value(raw: bytes | str, stored_sha256: str, *, max_bytes: int) -> StoredBytes:
    """Opt-in UTF-8 byte binding for new receipt formats, not a legacy migration.

    Unlike stored_value(), whitespace and key order affect this digest. The
    caller owns schema validation and the decision to refuse a mismatched fact.
    A smaller domain bound is enforced before decoding; the shared JSON ceiling
    cannot be increased through this API.
    """
    need(type(max_bytes) is int and 0 < max_bytes <= MAX_BYTES, 'Invalid stored JSON byte limit')
    need(type(raw) in (bytes, str), 'Stored JSON must be UTF-8 bytes or text')
    need(len(raw) <= max_bytes, 'Stored JSON exceeds its byte limit')
    raw = raw.encode('utf-8') if isinstance(raw, str) else raw
    need(len(raw) <= max_bytes, 'Stored JSON exceeds its byte limit')
    raw.decode('utf-8')
    # A BOM-less UTF-16/32 document can also be valid UTF-8 with NULs.
    # Literal NUL is never legal JSON, but json.loads(bytes) autodetects it.
    need(b'\x00' not in raw, 'Stored JSON must use UTF-8 without literal NUL')
    value = decode(raw)
    return StoredBytes(value=value, raw=raw,
                       observed_sha256=hashlib.sha256(raw).hexdigest(), stored_sha256=stored_sha256)
