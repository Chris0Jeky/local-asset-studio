"""Confined, opt-in access to the existing Spoken Brief archive and QA owners."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys

# The CLI modules are also the archive authority. Keep one implementation.
_SCRIPTS = str(Path(__file__).resolve().parents[1] / 'scripts')
if _SCRIPTS not in sys.path: sys.path.append(_SCRIPTS)
from spoken_brief_archive import (
    ArchiveConflict, MAX_MASTER_BYTES, checked_directory, hash_stream,
    inspect_run, opened_file, require_archive,
)
from spoken_brief_compile import SpokenBriefError, canonical_digest
from spoken_brief_exports import _load_playback, save_playback
from spoken_brief_inbox import HEX, _lineage, _plain
from spoken_brief_qa import load_report, load_review, record_review
from spoken_brief_transport import MAX_AUDIO_BYTES

MAX_ENTRIES = 4096
MAX_ARCHIVES = 128
MAX_DEPTH = 20
MAX_RECORD_ENTRIES = 256
MAX_REFUSALS = 32


class AccessError(SpokenBriefError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise AccessError('Request fields do not match this operation')


def digest(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise AccessError('A full lowercase SHA-256 identity is required')
    return value


def _key(value):
    if value == '.': return ()
    if (not isinstance(value, str) or not 1 <= len(value) <= 1024
            or any(ord(c) < 32 or c in '\\:' for c in value)
            or any(p in ('', '.', '..') or p.rstrip(' .') != p for p in value.split('/'))):
        raise AccessError('Select a canonical relative archive path inside the configured root')
    try: value.encode('utf-8')
    except UnicodeError as exc: raise AccessError('Archive path must be valid UTF-8') from exc
    return tuple(value.split('/'))


class ArchiveAccess:
    def __init__(self, config):
        if config is None: config = {}
        if not isinstance(config, dict) or set(config) - {'archive_root'}:
            raise AccessError('Spoken Brief configuration accepts only archive_root')
        root = config.get('archive_root')
        if root is not None and (not isinstance(root, str) or not root or len(root) > 4096
                or '\x00' in root or not Path(root).is_absolute() or '..' in Path(root).parts
                or root.startswith(('//', '\\\\'))):
            raise AccessError('archive_root must be an absolute local directory, not a network path')
        if root is not None:
            try: root.encode('utf-8')
            except UnicodeError as exc: raise AccessError('archive_root must be valid UTF-8') from exc
        self.root = Path(root) if root is not None else None

    def status(self):
        return {'enabled': self.root is not None, 'generation_submitted': False,
                'mode': 'retained-archive-review', 'automatic_saves': False}

    def _root(self):
        if self.root is None:
            raise AccessError('Configure spoken_briefs.archive_root in config/local.json, then restart Studio', 409)
        # Check links before canonicalizing Windows short-path aliases.
        before = _lineage(checked_directory(self.root))
        root = checked_directory(self.root.resolve())
        if _lineage(self.root) != before:
            raise AccessError('Configured archive root changed', 409)
        return root

    @contextmanager
    def _directory(self, key):
        parts = _key(key); root = self._root(); lineage = _lineage(root)
        directory = checked_directory(root.joinpath(*parts))
        directory_lineage = _lineage(directory)
        try:
            yield directory
        finally:
            if _lineage(root) != lineage or _lineage(directory) != directory_lineage:
                raise AccessError('Archive directory changed during this operation', 409)

    def archives(self):
        root = self._root(); lineage = _lineage(root)
        result = {'archives': [], 'refusals': [], 'truncated': False, 'generation_submitted': False}
        pending = [(root, 0)]; visited = 0
        def refuse(key, error):
            if len(result['refusals']) < MAX_REFUSALS:
                result['refusals'].append({'key': key, 'error': str(error)[:400]})
            else: result['truncated'] = True
        try:
            while pending:
                directory, depth = pending.pop()
                key = directory.relative_to(root).as_posix()
                try:
                    directory_lineage = _lineage(checked_directory(directory))
                    entries = []
                    with os.scandir(directory) as iterator:
                        for entry in iterator:
                            visited += 1
                            if visited > MAX_ENTRIES:
                                result['truncated'] = True
                                return result
                            entries.append(entry.name)
                    if _lineage(directory) != directory_lineage:
                        raise AccessError('Archive directory changed during discovery', 409)
                    for name in sorted(entries):
                        path = directory / name
                        info = path.lstat()
                        if not _plain(info):
                            refuse(path.relative_to(root).as_posix(), 'Symlink/reparse point refused'); continue
                        if name == 'manifest.json' and stat.S_ISREG(info.st_mode):
                            if len(result['archives']) >= MAX_ARCHIVES:
                                result['truncated'] = True; return result
                            result['archives'].append({'key': key, 'verification': 'not-verified'})
                        elif stat.S_ISDIR(info.st_mode) and not name.startswith('.') and name not in ('segments', 'exports', 'qa', 'node_modules'):
                            if depth >= MAX_DEPTH: result['truncated'] = True
                            else: pending.append((path, depth + 1))
                except (OSError, SpokenBriefError) as exc: refuse(key, exc)
        finally:
            if _lineage(root) != lineage: raise AccessError('Archive root changed during discovery', 409)
        result['archives'].sort(key=lambda x: x['key'])
        return result

    def _records(self, directory, group):
        path = directory / 'qa' / group; identifiers = []; refusals = []; truncated = False
        if not os.path.lexists(path): return identifiers, refusals, truncated
        try:
            checked_directory(path)
            with os.scandir(path) as entries:
                for count, entry in enumerate(entries, 1):
                    if count > MAX_RECORD_ENTRIES:
                        truncated = True; break
                    info = entry.stat(follow_symlinks=False)
                    if not _plain(info):
                        if len(refusals) < MAX_REFUSALS: refusals.append(f'{group}: linked record refused')
                        else: truncated = True
                    elif stat.S_ISREG(info.st_mode) and entry.name.endswith('.json') and HEX.fullmatch(entry.name[:-5]):
                        identifiers.append(entry.name[:-5])
        except (OSError, SpokenBriefError) as exc: refusals.append(f'{group}: {str(exc)[:400]}')
        return sorted(identifiers), refusals, truncated

    def inspect(self, key):
        with self._directory(key) as directory:
            archive = inspect_run(directory)
            playback, _ = _load_playback(directory, archive)
            reports, report_errors, report_truncated = self._records(directory, 'reports')
            reviews, review_errors, review_truncated = self._records(directory, 'reviews')
            require_archive(inspect_run(directory), archive['chapters_sha256'])
            return {'archive': archive, 'archive_sha256': archive['chapters_sha256'],
                    'playback': playback, 'playback_sha256': canonical_digest(playback),
                    'reports': reports, 'reviews': reviews, 'record_refusals': report_errors + review_errors,
                    'record_lists_truncated': report_truncated or review_truncated, 'generation_submitted': False}

    def report(self, key, archive_sha256, identifier):
        return self._record(key, archive_sha256, identifier, load_report)

    def saved_review(self, key, archive_sha256, identifier):
        return self._record(key, archive_sha256, identifier, load_review)

    def _record(self, key, archive_sha256, identifier, reader):
        digest(archive_sha256); digest(identifier)
        with self._directory(key) as directory:
            require_archive(inspect_run(directory), archive_sha256)
            result = reader(directory, identifier)
            require_archive(inspect_run(directory), archive_sha256)
            return result

    def bookmark(self, key, value):
        fields(value, ('archive_sha256', 'expected_playback_sha256', 'sample', 'rate', 'loop'))
        digest(value['archive_sha256']); digest(value['expected_playback_sha256'])
        with self._directory(key) as directory:
            playback = save_playback(directory, sample=value['sample'], rate=value['rate'], loop=value['loop'],
                expected_archive_sha256=value['archive_sha256'], expected_playback_sha256=value['expected_playback_sha256'])
            return {'playback': playback, 'playback_sha256': canonical_digest(playback), 'generation_submitted': False}

    def review(self, key, value):
        fields(value, ('archive_sha256', 'target', 'audio_sha256', 'decision', 'findings', 'reviewer', 'reason', 'report_sha256'))
        digest(value['archive_sha256']); digest(value['audio_sha256'])
        if value['report_sha256'] is not None: digest(value['report_sha256'])
        with self._directory(key) as directory:
            result = record_review(directory, value['target'], value['audio_sha256'], decision=value['decision'],
                findings=value['findings'], reviewer=value['reviewer'], reason=value['reason'],
                report_sha256=value['report_sha256'], expected_archive_sha256=value['archive_sha256'])
            return {'id': result['id'], 'reused': result['reused'], 'generation_submitted': False}

    @contextmanager
    def audio(self, key, archive_sha256, target):
        digest(archive_sha256)
        with self._directory(key) as directory:
            archive = inspect_run(directory); require_archive(archive, archive_sha256)
            if target == 'master':
                path = directory / archive['master']['name']; expected = archive['master']['sha256']; limit = MAX_MASTER_BYTES
            else:
                segment = next((x for x in archive['segments'] if x['id'] == target), None)
                if segment is None: raise AccessError('Unknown audio target', 404)
                path = directory / 'segments' / (segment['id'] + '.wav'); expected = segment['audio_sha256']; limit = MAX_AUDIO_BYTES
            # Serve the checked handle, not an unchecked reopen of a pathname.
            with opened_file(path, limit) as stream:
                actual, size = hash_stream(stream, limit)
                if actual != expected: raise ArchiveConflict('Archive audio changed before playback')
                stream.seek(0)
                yield stream, size
