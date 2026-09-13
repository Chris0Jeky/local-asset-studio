"""Offline browser intake using the pinned installer's lease and no-clobber publisher.

Copies are byte-checked, not source-authenticated. Browser originals are never deleted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time
import uuid

from download_contracts import InstallLease, file_identity, publish_verified, relative_model_path
from model_library import FOLDERS, ModelLibrary, RESERVE_BYTES

CHUNK_BYTES = 4 * 1024**2


def plain_path(path):
    """Reject observed links before resolving them away, including Windows junctions."""
    path = Path(os.path.abspath(path))
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or (hasattr(candidate, 'is_junction') and candidate.is_junction()):
            raise ValueError('Intake path is a link or junction; original preserved: ' + str(candidate))
    return path


def source_snapshot(path):
    path = plain_path(path)
    if not stat.S_ISREG(path.stat().st_mode):raise ValueError('Intake source must be a regular file')
    return file_identity(path)


def target_path(comfy_root, folder, name):
    if folder not in FOLDERS:raise ValueError('Unsupported destination folder')
    relative = relative_model_path(folder + '/' + name)
    if len(relative.parts) != 2 or relative.suffix != '.safetensors':raise ValueError('Expected one safetensors basename')
    return plain_path(Path(comfy_root).absolute() / 'models' / relative)


def _same_source(path, expected):
    if source_snapshot(path) != expected:raise ValueError('Source changed since intake planning; all files preserved')


def _handle_identity(stream):
    value = os.fstat(stream.fileno())
    return {'device': value.st_dev, 'inode': value.st_ino, 'size': value.st_size,
            'mtime_ns': value.st_mtime_ns, 'ctime_ns': value.st_ctime_ns}


def _save(path, record, phase, **updates):
    """One operation owns this journal; never rewrite the acquisition scripts' shared list."""
    plain_path(path)
    record.update(updates, status=phase, updated_at=time.time())
    record.setdefault('events', []).append({'status': phase, 'at': record['updated_at']})
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    # A failed write leaves its unique temporary file and the previous journal for inspection.
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
    plain_path(path); temporary.replace(path)


def _copy(source, staged, expected):
    digest = hashlib.sha256(); total = 0
    plain_path(staged); _same_source(source, expected)
    with source.open('rb') as reader:
        if _handle_identity(reader) != expected:raise ValueError('Opened source differs from the planned file')
        with staged.open('xb') as writer:
            while chunk := reader.read(CHUNK_BYTES):
                total += len(chunk)
                if total > expected['size']:raise ValueError('Source grew during intake; partial copy preserved')
                if shutil.disk_usage(staged.parent).free < len(chunk) + RESERVE_BYTES:
                    raise ValueError('Insufficient space during intake; partial copy preserved')
                writer.write(chunk); digest.update(chunk)
            writer.flush(); os.fsync(writer.fileno())
        if _handle_identity(reader) != expected:raise ValueError('Source changed during intake; partial copy preserved')
    _same_source(source, expected)
    if total != expected['size']:raise ValueError('Source size changed during intake; partial copy preserved')
    return digest.hexdigest()


def import_candidate(root, comfy_root, source, folder, name, expected_identity, folder_basis):
    """Publish an independent copy after an explicit caller action; never load weights.

    An expected stat identity binds this action to the earlier header inspection. The
    lease is shared with ModelLibrary, but is not a lock against arbitrary OS writers.
    """
    if folder_basis not in ('header-hint', 'operator-selected'):raise ValueError('A reviewed folder selection is required')
    source = plain_path(source); target = target_path(comfy_root, folder, name)
    if source == target:raise ValueError('Source is already the destination; original preserved')
    _same_source(source, expected_identity)
    if expected_identity['size'] <= 0:raise ValueError('Empty intake source; original preserved')
    if target.exists():raise ValueError('Destination already exists; nothing was overwritten')
    plain_path(Path(root) / '.runtime' / 'downloads')
    library = ModelLibrary(root, comfy_root)
    if library.destination({'file': folder + '/' + name}) != target:raise ValueError('Model root changed during intake')
    identifier = uuid.uuid4().hex
    lease = InstallLease(library.state / 'install.lock', 'intake-' + identifier)
    record = None; journal = library.state / 'intake' / (identifier + '.json')
    try:
        plain_path(journal); journal.parent.mkdir(parents=True, exist_ok=True)
        staged = target.with_name('.intake-' + identifier + '.part')
        record = {'version': 1, 'kind': 'browser-intake', 'id': identifier,
                  'origin': str(source), 'path': str(target), 'partial_path': str(staged),
                  'receipt_path': str(journal), 'file': name, 'folder': folder, 'folder_basis': folder_basis,
                  'source_identity': expected_identity, 'bytes': expected_identity['size'],
                  'sha256': None, 'expected_sha256': None, 'verified': False, 'runtime_compatible': None,
                  'source_cleanup': 'not-requested', 'licence': 'TODO: record source and licence'}
        _save(journal, record, 'intent')
        _same_source(source, expected_identity); plain_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(target.parent).free < expected_identity['size'] + RESERVE_BYTES:
            raise ValueError('More disk space is needed for a separate copy plus 20 GiB working headroom')
        _save(journal, record, 'copying')
        digest = _copy(source, staged, expected_identity)
        # Re-read the staged bytes; hashing the source stream alone would not check the copy.
        plain_path(staged)
        copied = library._verify(staged, {'bytes': expected_identity['size'], 'sha256': digest})
        _save(journal, record, 'prepared', sha256=digest, staged_identity=copied)
        _same_source(source, expected_identity); plain_path(staged); plain_path(target)
        identity = publish_verified(staged, target, copied)
        # Publication unlinks only the temporary copy, never the browser source.
        _same_source(source, expected_identity); plain_path(target)
        if file_identity(target) != identity:raise ValueError('Destination changed before receipt; inspect retained files')
        _save(journal, record, 'copied', file_identity=identity)
        return record
    except Exception as exc:
        if record is not None:
            try:_save(journal, record, 'needs_inspection', error=str(exc)[:500])
            except Exception as report_error:exc.add_note('Intake journal update failed: ' + str(report_error))
        exc.add_note('Intake evidence: ' + str(journal) + '; source cleanup was not requested')
        raise
    finally:
        lease.release()
