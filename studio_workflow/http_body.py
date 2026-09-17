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
    raw = handler.headers.get('Content-Length')
    if raw is None:
        return not handler.headers.get('Transfer-Encoding')
    text = raw.strip() if isinstance(raw, str) else ''
    if not text.isdigit():
        return False
    size = int(text)
    if size > DRAIN_LIMIT:
        return False

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
