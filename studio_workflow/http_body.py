"""Bounded transport hygiene for early local HTTP refusals."""
from __future__ import annotations

DRAIN_LIMIT = 1024 * 1024
DRAIN_CHUNK = 64 * 1024
DRAIN_TIMEOUT_SECONDS = 1.0


def drain_declared_body(handler) -> bool:
    """Consume one already-declared small request body without trusting its content.

    This is best-effort transport cleanup after the request has already been
    rejected. It never reads a missing, malformed, chunked or oversized body,
    and it temporarily bounds socket waiting so an early refusal cannot become
    an unbounded local read.
    """
    # A request carrying any transfer coding is not a fixed-length byte stream,
    # even when a conflicting Content-Length is also present. Never interpret
    # chunk framing through the fixed-length drain.
    if handler.headers.get('Transfer-Encoding') is not None:
        return False
    raw = handler.headers.get('Content-Length')
    if raw is None:
        return True
    text = raw.strip() if isinstance(raw, str) else ''
    if not text.isdigit():
        return False
    significant = text.lstrip('0') or '0'
    limit = str(DRAIN_LIMIT)
    # Compare decimal text before int conversion. Besides avoiding work for an
    # oversized claim, this prevents Python's long-integer digit guard from
    # escaping the early refusal when a pathological header is supplied.
    if len(significant) > len(limit) or (len(significant) == len(limit) and significant > limit):
        return False
    size = int(significant)

    connection = getattr(handler, 'connection', None)
    old_timeout = None
    restore_timeout = False
    try:
        if connection is not None and hasattr(connection, 'gettimeout') and hasattr(connection, 'settimeout'):
            old_timeout = connection.gettimeout()
            if old_timeout is None or old_timeout > DRAIN_TIMEOUT_SECONDS:
                connection.settimeout(DRAIN_TIMEOUT_SECONDS)
                restore_timeout = True
        remaining = size
        while remaining:
            chunk = handler.rfile.read(min(DRAIN_CHUNK, remaining))
            if not chunk:
                return False
            remaining -= len(chunk)
        return True
    except (OSError, TimeoutError, ValueError):
        return False
    finally:
        if restore_timeout:
            try:
                connection.settimeout(old_timeout)
            except OSError:
                pass


def reject_json(handler, status: int, value: dict):
    """Drain a safe declared body, then preserve the owner's JSON refusal."""
    drain_declared_body(handler)
    return handler._json(status, value)