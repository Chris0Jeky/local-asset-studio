"""Publication and bounded retained reads owned only by RuntimeRecovery.

Completion means content synchronization, replacement and the supported parent
barrier completed. Windows has no directory barrier here. Readable bytes never
acknowledge a failed publication or authorize another recovery launch.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import stat
import uuid

import file_replace

MAX_BYTES = 128 * 1024
DIRECTORY_SYNC_SUPPORTED = os.name != 'nt'
_LEGACY_FIELDS = ('status', 'attempts', 'startup_pid', 'startup_at', 'breaker_until', 'launch_pending', 'updated_at')


def _bytes(value):
    if not isinstance(value, dict): raise ValueError('Recovery state must be a JSON object')
    raw = bytearray()
    try:
        for chunk in json.JSONEncoder(indent=2, allow_nan=False).iterencode(value):
            part = chunk.encode('utf-8')
            if len(raw) + len(part) > MAX_BYTES: raise ValueError('Recovery state exceeds its 128 KiB byte budget')
            raw.extend(part)
    except (TypeError, RecursionError, UnicodeError) as exc:
        raise ValueError('Recovery state must be bounded finite JSON') from exc
    return bytes(raw)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Recovery state has duplicate fields')
        result[key] = value
    return result


def _finite(value):
    try: return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError: return False


def _validate_observation(value):
    if (not isinstance(value.get('status'), str) or not value['status']
            or type(value.get('attempts')) is not int or not 0 <= value['attempts'] <= 10):
        raise ValueError('Recovery state has an invalid status or attempt count')
    for key in ('updated_at', 'startup_at', 'breaker_until'):
        if key in value and not _finite(value[key]): raise ValueError('Recovery state has an invalid ' + key)
    if 'startup_pid' in value and (type(value['startup_pid']) is not int or not 0 < value['startup_pid'] <= 2**32 - 1):
        raise ValueError('Recovery state has an invalid startup PID')
    if 'launch_pending' in value and type(value['launch_pending']) is not bool:
        raise ValueError('Recovery state has an invalid launch intent')


def legacy_attempt(value):
    """Retain only observed old-format fields; never invent an attempt identity."""
    if 'last_attempt' in value or 'legacy_attempt' in value: return None
    if (value.get('launch_pending') or value.get('startup_pid') or value.get('attempts')
            or value.get('status') in ('launching', 'startup')):
        return {'version': 1, 'evidence': {key: value[key] for key in _LEGACY_FIELDS if key in value}}
    return None


def read(path):
    """Only a missing record is first use; invalid saved allowance stays blocked."""
    path = Path(path)
    try: info = path.lstat()
    except FileNotFoundError: return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Recovery state must be a regular file without links')
    with path.open('rb') as stream: raw = stream.read(MAX_BYTES + 1)
    if not 1 <= len(raw) <= MAX_BYTES: raise ValueError('Recovery state has an invalid size')
    value = json.loads(raw, object_pairs_hook=_object)
    _bytes(value)  # Reject non-finite values, including overflowing JSON exponents.
    _validate_observation(value)
    if 'last_attempt' in value:
        attempt = value['last_attempt']
        if (not isinstance(attempt, dict) or type(attempt.get('version')) is not int or attempt['version'] != 1
                or not isinstance(attempt.get('id'), str) or len(attempt['id']) != 32
                or any(character not in '0123456789abcdef' for character in attempt['id'])
                or not isinstance(attempt.get('backend'), str) or not attempt['backend']
                or type(attempt.get('number')) is not int or not 1 <= attempt['number'] <= 10
                or not _finite(attempt.get('at'))
                or ('pid' in attempt and (type(attempt['pid']) is not int or not 0 < attempt['pid'] <= 2**32 - 1))):
            raise ValueError('Recovery state has invalid retained attempt evidence')
    if 'legacy_attempt' in value:
        attempt = value['legacy_attempt']
        if (not isinstance(attempt, dict) or set(attempt) != {'version', 'evidence'}
                or type(attempt.get('version')) is not int or attempt['version'] != 1
                or not isinstance(attempt['evidence'], dict) or set(attempt['evidence']) - set(_LEGACY_FIELDS)):
            raise ValueError('Recovery state has invalid legacy attempt evidence')
        _validate_observation(attempt['evidence'])
        if legacy_attempt(attempt['evidence']) is None:
            raise ValueError('Recovery state has no recognized legacy attempt evidence')
    return value


def sync_parent_directory(parent):
    if not DIRECTORY_SYNC_SUPPORTED: return False
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(descriptor)
    except BaseException as exc:
        try: os.close(descriptor)
        except OSError as cleanup_error: exc.add_note('Recovery directory close failed: ' + str(cleanup_error))
        raise
    os.close(descriptor)
    return True


def publish(path, value):
    """Replace only this owner's record after bounded serialization and content sync."""
    raw = _bytes(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    owner = None; content_error = None
    try:
        with temp.open('xb') as stream:
            try:
                info = os.fstat(stream.fileno()); owner = info.st_dev, info.st_ino
                if stream.write(raw) != len(raw): raise OSError('Recovery state write was incomplete')
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException as exc: content_error = exc; raise
        file_replace.replace(temp, path)
        owner = None  # The consumed name no longer belongs to this invocation.
        directory_synced = sync_parent_directory(path.parent)
        return {'content_synced': True, 'directory_synced': directory_synced}
    except BaseException as exc:
        failure = content_error or exc
        if failure is not exc: failure.add_note('Recovery temporary-file close failed: ' + str(exc))
        if owner is not None:
            try:
                current = temp.lstat()
                if (current.st_dev, current.st_ino) == owner: temp.unlink()
            except FileNotFoundError: pass
            except OSError as cleanup_error: failure.add_note('Owned recovery temporary-file cleanup failed: ' + str(cleanup_error))
        if failure is exc: raise
        raise failure
