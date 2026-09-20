"""Bounded transport hygiene for early local HTTP refusals."""
from __future__ import annotations

import time

DRAIN_LIMIT = 1024 * 1024
DRAIN_CHUNK = 64 * 1024
DRAIN_TIMEOUT_SECONDS = 1.0


def drain_declared_body(handler) -> bool:
    """Consume one already-declared small request body without trusting its content.

    This is best-effort transport cleanup after the request has already been
    rejected. It never reads a missing, malformed, chunked or oversized body,
    and it applies one total socket-backed deadline so trickle progress cannot
    turn an early refusal into an unbounded local read.
    """
    headers = handler.headers
    get_all = getattr(headers, 'get_all', None)
    if callable(get_all):
        # HTTPMessage preserves repeated fields. Any transfer coding or more
        # than one length makes the fixed-length framing ambiguous, even when
        # duplicate lengths happen to carry the same value.
        if get_all('Transfer-Encoding'):
            return False
        lengths = get_all('Content-Length') or []
        if len(lengths) > 1:
            return False
        if not lengths:
            return True
        raw = lengths[0]
    else:
        # Lightweight test and embedding mappings expose only get().
        if headers.get('Transfer-Encoding') is not None:
            return False
        raw = headers.get('Content-Length')
        if raw is None:
            return True

    text = raw.strip() if isinstance(raw, str) else ''
    if not text or any(character < '0' or character > '9' for character in text):
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
    reader = getattr(handler.rfile, 'read1', None)
    if not callable(reader):
        reader = handler.rfile.read
    deadline = time.monotonic() + DRAIN_TIMEOUT_SECONDS
    try:
        has_socket_timeout = (connection is not None and hasattr(connection, 'gettimeout')
                              and hasattr(connection, 'settimeout'))
        if has_socket_timeout:
            old_timeout = connection.gettimeout()
        remaining = size
        while remaining:
            budget = deadline - time.monotonic()
            if budget <= 0:
                return False
            if has_socket_timeout:
                connection.settimeout(budget if old_timeout is None else min(old_timeout, budget))
                restore_timeout = True
            # BufferedReader.read() may perform multiple socket reads and reset a
            # relative timeout after every trickled byte. read1() performs at most
            # one raw read, giving the absolute deadline a chance to run each time.
            chunk = reader(min(DRAIN_CHUNK, remaining))
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
            except (OSError, ValueError):
                pass


def reject_json(handler, status: int, value: dict):
    """Drain a safe declared body, then preserve the owner's JSON refusal."""
    drain_declared_body(handler)
    return handler._json(status, value)
