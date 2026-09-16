"""Pure value facts shared by revisioned stores; no SQL or side effects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Any

from .core import canonical, decode


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
