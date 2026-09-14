"""Bounded local JSON capture for CLI authoring and execution tickets."""
from pathlib import Path

from .core import MAX_BYTES, decode


def read_document(path: str | Path):
    # Bound the allocation itself; a stat check alone cannot cover file growth.
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    return decode(raw)
