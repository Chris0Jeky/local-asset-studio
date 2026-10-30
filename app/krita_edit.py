"""#1860: Edit in Krita, and bring the repair back. Two explicit owner presses; nothing is generated or imported on its own.

1. `start` copies a live PNG picture to a working file the Studio names (`experiments/edits/<asset>/<session>.png`, or the same
   under private storage for a private picture), records a session next to it and launches the configured Krita GUI on that copy.
   The content-addressed original is only read. The client never supplies a path: the working file is derived from the asset
   record and a session id that must match `SESSION`.
2. `bring_back` reads the working file. Unchanged since the copy: nothing is imported. Changed: `Studio.import_image(parent=...)`
   (#1837) records it as an unreviewed repair of the picture; the session remembers what was imported so a second press on
   the same bytes does not duplicate it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

import creation_privacy as privacy_scope
import review_media

SESSION = re.compile(r'[0-9]{8}-[0-9]{6}-[0-9a-f]{8}')
SAFE_ID = re.compile(r'[0-9A-Za-z_-]{1,64}')
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
MAX_BYTES = 20 * 1024 * 1024  # the import limit: a larger file could not come back
NOTE = 'Edited in Krita'
_lock = threading.Lock()  # ponytail: one bring-back at a time (single owner); per-asset locks if that ever matters


class KritaEditError(ValueError):
    pass


def executable(studio):
    """(path, '') of the Krita GUI named by config/local.json `krita`, or (None, reason). No default location is guessed."""
    raw = studio.config.get('krita')
    if type(raw) is not str or not raw.strip(): return None, 'Krita is not configured. Set "krita" in config/local.json to the path of krita.exe.'
    path = Path(raw).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.exe': return None, 'The configured Krita executable was not found: ' + str(path)
    return path, ''


def availability(studio):
    path, reason = executable(studio)
    return {'available': path is not None, 'reason': reason}


def _picture(studio, asset_id, privacy, scope):
    """(store path, record) of a live PNG picture of the request's privacy; anything else is refused before anything is written."""
    privacy = privacy_scope.normalize(privacy)
    try: path, asset = studio.assets.file_entry(asset_id, privacy=scope)
    except (ValueError, TypeError, sqlite3.Error) as exc: raise KritaEditError('That picture is not in this Library') from exc
    if asset['media_type'] != 'image': raise KritaEditError('Only a picture can be opened in Krita')
    if asset.get('trashed_at'): raise KritaEditError('That picture is in the Bin; restore it before editing it')
    if asset.get('privacy', 'regular') != privacy: raise KritaEditError('A private picture and a regular one are never linked; edit it under the same privacy')
    if not SAFE_ID.fullmatch(asset['id']): raise KritaEditError('That picture has no safe identifier')
    return path, asset


def _directory(studio, asset):
    base = studio._private_directory('edits') if asset.get('privacy', 'regular') == 'private' else studio.experiments / 'edits'
    return base / asset['id']


def _write(record, session):
    temporary = record.with_suffix('.tmp')
    temporary.write_text(json.dumps(session, indent=2), encoding='utf-8'); os.replace(temporary, record)


def _public(session):
    return {key: session[key] for key in ('id', 'asset_id', 'privacy', 'source_sha256', 'working_path', 'created_at', 'brought_back') if key in session}


def start(studio, asset_id, *, privacy, scope):
    krita, reason = executable(studio)
    if krita is None: raise KritaEditError(reason)
    path, asset = _picture(studio, asset_id, privacy, scope)
    raw = review_media.checked_bytes(path, asset['sha256'])
    if not raw.startswith(PNG_MAGIC): raise KritaEditError('Only a PNG picture can be opened in Krita for now')
    directory = _directory(studio, asset); identifier = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    working, record = directory / (identifier + '.png'), directory / (identifier + '.json')
    directory.mkdir(parents=True, exist_ok=True)
    with working.open('xb') as stream: stream.write(raw)
    session = {'id': identifier, 'asset_id': asset['id'], 'privacy': asset.get('privacy', 'regular'), 'source_sha256': hashlib.sha256(raw).hexdigest(),
               'working_path': str(working.resolve()), 'created_at': time.time()}
    _write(record, session)
    try:
        subprocess.Popen([str(krita), session['working_path']], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    except OSError as exc:
        working.unlink(missing_ok=True); record.unlink(missing_ok=True)
        raise KritaEditError('Krita could not be started: ' + str(exc)[:200]) from exc
    return _public(session)


def _session(directory, identifier):
    """The named session, or the newest one (names start with their timestamp) when none is named."""
    if identifier is not None and (type(identifier) is not str or not SESSION.fullmatch(identifier)): raise KritaEditError('Unknown edit session')
    if identifier is None:
        found = sorted(p for p in directory.glob('*.json') if SESSION.fullmatch(p.stem)) if directory.is_dir() else []
        if not found: raise KritaEditError('Open this picture in Krita first; there is no edit to bring back')
        record = found[-1]
    else: record = directory / (identifier + '.json')
    try: session = json.loads(record.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc: raise KritaEditError('That edit session is unavailable') from exc
    if not isinstance(session, dict) or session.get('id') != record.stem: raise KritaEditError('That edit session is unavailable')
    return record, session


def bring_back(studio, asset_id, identifier, *, privacy, scope):
    with _lock:
        _, asset = _picture(studio, asset_id, privacy, scope)
        directory = _directory(studio, asset); record, session = _session(directory, identifier)
        working = directory / (session['id'] + '.png')
        if session.get('asset_id') != asset['id'] or not working.is_file(): raise KritaEditError('The Krita working file is gone; open the picture in Krita again')
        if working.stat().st_size > MAX_BYTES: raise KritaEditError('The saved file exceeds 20 MiB and cannot be imported')
        raw = working.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
        if digest == session['source_sha256']: return {'status': 'unchanged', 'session': _public(session)}
        done = session.get('brought_back')
        if isinstance(done, dict) and done.get('sha256') == digest: return {'status': 'already_imported', 'asset_id': done['asset_id'], 'session': _public(session)}
        result = studio.import_image(Path(asset['filename']).stem[:60] + '-krita.png', 'image/png', raw, privacy=privacy, parent=asset['id'], note=NOTE, scope=scope)
        session['brought_back'] = {'sha256': digest, 'asset_id': result['asset']['id'], 'at': time.time()}
        _write(record, session)
        return {'status': 'imported', 'asset': result['asset'], 'job': result['job'], 'session': _public(session)}
