"""Scoped publication barriers for ordinary observation admission, not all job saves.

A return proves the requested OS operations completed, not physical-media survival.
Windows has file synchronization and replacement here, but no directory barrier.
Any exception, even after a visible replacement, must not grant queue ownership.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

MAX_BYTES = 16 * 1024 * 1024
DIRECTORY_SYNC_SUPPORTED = os.name != 'nt'


def sync_parent_directory(parent: Path) -> bool:
    """Return False on Windows; elsewhere propagate an unavailable/failed barrier."""
    if not DIRECTORY_SYNC_SUPPORTED:
        return False
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return True


def _bytes(value: dict) -> bytes:
    if not isinstance(value, dict):
        raise ValueError('Observation state must be a JSON object')
    raw = bytearray()
    try:
        for chunk in json.JSONEncoder(indent=2, allow_nan=False).iterencode(value):
            part = chunk.encode('utf-8')
            if len(raw) + len(part) > MAX_BYTES:
                raise ValueError('Observation state exceeds byte budget')
            raw.extend(part)
    except (TypeError, RecursionError, UnicodeError) as exc:
        raise ValueError('Observation state must be bounded finite JSON') from exc
    return bytes(raw)


def publish(path: Path, value: dict, sync_parent=sync_parent_directory) -> dict:
    """Synchronize an exclusively owned temp file before replacement, then its parent.

    Callers own path containment and serialization of command writers. This is not
    a cross-process compare-and-swap, multi-file transaction or restart replay.
    The existing target is replaced only after successful content synchronization.
    """
    raw = _bytes(value)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    owner = None
    try:
        with temp.open('xb') as stream:
            info = os.fstat(stream.fileno())
            owner = (info.st_dev, info.st_ino)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
        owner = None  # The temp entry is gone; never unlink a later occupant.
        directory_synced = sync_parent(path.parent)
        return {'content_synced': True, 'directory_synced': directory_synced}
    except BaseException as exc:
        if owner is not None:
            try:
                current = temp.lstat()
                if (current.st_dev, current.st_ino) == owner:
                    temp.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                exc.add_note('Owned observation temporary-file cleanup failed: ' + str(cleanup_error))
        raise
