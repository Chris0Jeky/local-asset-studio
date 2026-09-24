"""Bounded retry for transient Windows refusals of an atomic file replacement.

On Windows, replacing a file fails with ERROR_ACCESS_DENIED (5) or ERROR_SHARING_VIOLATION (32)
while another process (an agent reading receipts, antivirus, the search indexer) holds the target
open without FILE_SHARE_DELETE. Such holds are usually brief; observed live 24 Sep 2026 on a run's
state.json. Every other error, and every error on other platforms, propagates at once.
A refused replacement leaves the source in place, so retrying cannot publish twice.
"""
from __future__ import annotations

import time

TRANSIENT_WINERRORS = frozenset({5, 32})
DELAYS = (0.05, 0.1, 0.2, 0.4, 0.6)  # 1.35 s of waiting across six attempts at most


def transient(exc) -> bool:
    return isinstance(exc, PermissionError) and getattr(exc, 'winerror', None) in TRANSIENT_WINERRORS


def replace(source, target, sleep=None):
    """`source.replace(target)` (a Path), retried only on transient Windows refusals; returns the attempt count."""
    sleep = sleep or time.sleep
    for attempt, delay in enumerate(DELAYS, 1):
        try:
            source.replace(target); return attempt
        except PermissionError as exc:
            if not transient(exc): raise
        sleep(delay)
    try:
        source.replace(target); return len(DELAYS) + 1
    except PermissionError as exc:
        if transient(exc): exc.add_note(f'Replacement was refused {len(DELAYS) + 1} times over {sum(DELAYS):.2f} s; another program may hold the file open.')
        raise
