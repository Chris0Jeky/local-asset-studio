#!/usr/bin/env python3
"""Strict, bounded JSON decoding for persisted Local Asset Studio evidence."""
from __future__ import annotations

import json
from pathlib import Path


class StrictJsonError(ValueError):
    """Raised when persisted JSON is ambiguous, non-standard, or unreadable."""


def loads_strict(raw: bytes, *, label: str):
    """Decode UTF-8 JSON while rejecting duplicate keys and non-standard numbers."""
    if not isinstance(raw, bytes):
        raise StrictJsonError(f'{label} must be supplied as bytes')

    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StrictJsonError(f'{label} contains duplicate key {key!r}')
            result[key] = value
        return result

    def reject_constant(value):
        raise StrictJsonError(
            f'{label} contains non-standard numeric constant {value}'
        )

    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise StrictJsonError(f'{label} must be bounded UTF-8 JSON') from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except StrictJsonError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StrictJsonError(f'{label} must be bounded UTF-8 JSON') from exc


def load_bounded_json(path: Path, *, label: str, maximum_bytes: int):
    """Read one stable-size file and decode it with :func:`loads_strict`."""
    if type(maximum_bytes) is not int or maximum_bytes < 1:
        raise StrictJsonError('maximum_bytes must be a positive integer')
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise StrictJsonError(f'Cannot inspect {label}: {path}') from exc
    if not 1 <= size <= maximum_bytes:
        raise StrictJsonError(
            f'{label} must contain 1 to {maximum_bytes} bytes'
        )
    try:
        with path.open('rb') as stream:
            raw = stream.read(maximum_bytes + 1)
    except OSError as exc:
        raise StrictJsonError(f'Cannot read {label}: {path}') from exc
    if len(raw) != size or len(raw) > maximum_bytes:
        raise StrictJsonError(
            f'{label} changed while it was read or exceeded its byte limit'
        )
    return loads_strict(raw, label=label)
