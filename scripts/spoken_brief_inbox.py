#!/usr/bin/env python3
"""Bounded, review-only handoff discovery. This module cannot submit TTS."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

from spoken_brief_compile import (MAX_SOURCE_BYTES, SPEAKER_RE,
    SpokenBriefError, batch_segments, canonical_digest, compile_snapshot, digest_bytes)

MAX_CANDIDATES = 64
MAX_STATE_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_SCAN_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 6
MAX_ALIASES = 16
MAX_REFUSALS = 128
SETTLE_SECONDS = 2.0
HEX = re.compile(r'[0-9a-f]{64}\Z')


def _plain(info):
    return not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def _lineage(path: Path):
    """Inspect before resolving: resolve() alone would hide junctions/symlinks."""
    result = []
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        if not _plain(info):
            raise SpokenBriefError(f'Symlink/reparse point refused: {item}')
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise SpokenBriefError(f'Non-directory ancestor refused: {item}')
        result.append((str(item), info.st_dev, info.st_ino))
    return result


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _capture(path: Path, limit: int):
    """Accept only a bounded, regular-file snapshot with unchanged path/handle identity."""
    try:
        lineage = _lineage(path)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise SpokenBriefError(f'Non-regular file refused: {path}')
        if not 1 <= before.st_size <= limit:
            raise SpokenBriefError(f'File must contain 1 to {limit} bytes: {path}')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            # Windows path stat and fstat may expose different ctime meanings.
            # Compare their common identity here, then each full timestamp
            # signature against a second observation from the same API.
            if not stat.S_ISREG(opened.st_mode) or _identity(opened)[:4] != _identity(before)[:4]:
                raise SpokenBriefError(f'File changed while opening: {path}')
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        if (not 1 <= len(raw) <= limit or len(raw) != before.st_size
                or _identity(opened) != _identity(after) or _lineage(path) != lineage
                or _identity(path.lstat()) != _identity(before)):
            raise SpokenBriefError(f'File changed while reading: {path}')
        return raw, (*_identity(before), digest_bytes(raw))
    except OSError as exc:
        raise SpokenBriefError(f'Cannot capture {path}: {exc}') from exc


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise SpokenBriefError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _constant(value):
    raise SpokenBriefError(f'Non-standard JSON number: {value}')


def _candidate_id(manifest):
    return canonical_digest({'source_sha256': manifest['source']['sha256'],
        'compiler': manifest['compiler'], 'speaker_id': manifest['speaker_id']})


class Inbox:
    """One allow-listed root, one durable bounded inbox, no generation authority.

    Stability timers are deliberately process-local: restart requires two fresh
    observations, while already-published candidates and Ignore decisions survive.
    """
    def __init__(self, root, state_path=None, *, speaker_id='brief-narrator', clock=time.monotonic):
        self.root = Path(os.path.abspath(Path(root).expanduser()))
        if self.root.drive.startswith('\\\\'): raise SpokenBriefError('A local handoff root is required')
        try:
            self.root_identity = _lineage(self.root)
            if not self.root.is_dir(): raise SpokenBriefError('Handoff root must be a directory')
        except OSError as exc: raise SpokenBriefError(f'Cannot inspect handoff root: {exc}') from exc
        self.state_path = Path(os.path.abspath(state_path or self.root / '_spoken-inbox.json'))
        if not isinstance(speaker_id, str) or not SPEAKER_RE.fullmatch(speaker_id):
            raise SpokenBriefError('Invalid speaker metadata ID')
        self.speaker_id = speaker_id
        self.clock = clock
        self.observations = {}

    def _root_check(self):
        if _lineage(self.root) != self.root_identity:
            raise SpokenBriefError('Configured handoff root was replaced')

    def _new(self):
        return {'schema_version': 1, 'kind': 'spoken-brief-inbox', 'root': str(self.root),
            'speaker_id': self.speaker_id, 'candidates': [], 'refusals': []}

    def _load(self):
        if not os.path.lexists(self.state_path): return self._new(), None
        raw, _ = _capture(self.state_path, MAX_STATE_BYTES)
        try:
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise SpokenBriefError(f'Invalid inbox JSON: {exc}') from exc
        if (not isinstance(value, dict) or set(value) != set(self._new()) or value['schema_version'] != 1
                or type(value['schema_version']) is not int or value['kind'] != 'spoken-brief-inbox' or value['root'] != str(self.root)
                or value['speaker_id'] != self.speaker_id):
            raise SpokenBriefError('Inbox schema/root/speaker binding differs')
        candidates = value['candidates']; ids = set()
        if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
            raise SpokenBriefError('Invalid inbox candidate capacity')
        try:
            for item in candidates:
                manifest = item['manifest']; source = manifest['source']
                raw_source = item['source_text'].encode('utf-8')
                unsigned = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
                if (item['id'] in ids or not HEX.fullmatch(item['id']) or item['id'] != _candidate_id(manifest)
                        or item['status'] not in ('pending', 'ignored') or item['generation_submitted'] is not False
                        or not 1 <= len(raw_source) <= MAX_SOURCE_BYTES
                        or digest_bytes(raw_source) != item['source_sha256'] or source['sha256'] != item['source_sha256']
                        or source['bytes'] != len(raw_source) or manifest['kind'] != 'spoken-brief'
                        or manifest['speaker_id'] != self.speaker_id
                        or canonical_digest(unsigned) != manifest['manifest_sha256']
                        or not Path(source['path']).is_relative_to(self.root)
                        or not isinstance(item['sources'], list) or not 1 <= len(item['sources']) <= MAX_ALIASES
                        or not isinstance(item['supersedes'], list) or len(item['supersedes']) > MAX_CANDIDATES):
                    raise SpokenBriefError('Corrupt inbox candidate/source/manifest identity')
                for relative in item['sources']:
                    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
                        raise SpokenBriefError('Invalid candidate source alias')
                segments = manifest['segments']
                if (not isinstance(segments, list) or not 1 <= len(segments) <= 240
                        or not isinstance(manifest['omissions'], dict)
                        or any(type(v) is not int or v < 0 for v in manifest['omissions'].values())
                        or '..' in Path(source['path']).parts or not Path(source['path']).is_absolute()):
                    raise SpokenBriefError('Invalid retained preview structure')
                batch_segments(segments)
                for index, segment in enumerate(segments, 1):
                    if (segment['id'] != f'segment-{index:04d}'
                            or segment['text_sha256'] != digest_bytes(segment['text'].encode('utf-8'))
                            or type(segment['pause_after_ms']) is not int or not 0 <= segment['pause_after_ms'] <= 5000
                            or type(segment['block']) is not int or segment['block'] < 0
                            or segment['kind'] not in ('heading', 'paragraph', 'table')):
                        raise SpokenBriefError('Invalid retained segment identity/structure')
                ids.add(item['id'])
            refusals = value['refusals']
            if (not isinstance(refusals, list) or len(refusals) > MAX_REFUSALS
                    or any(not isinstance(x, dict) or set(x) != {'path', 'error'}
                           or not all(isinstance(v, str) for v in x.values()) for x in refusals)):
                raise SpokenBriefError('Invalid inbox refusal records')
        except (KeyError, TypeError, AttributeError, UnicodeError) as exc:
            raise SpokenBriefError('Malformed inbox candidate') from exc
        return value, digest_bytes(raw)

    @contextmanager
    def _lock(self):
        """OS-held lock, released on process death; never delete a live lock inode."""
        lock = self.state_path.with_name(self.state_path.name + '.lock')
        descriptor = None
        try:
            self._root_check(); _lineage(lock.parent)
            if os.path.lexists(lock): _lineage(lock)
            descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode): raise SpokenBriefError('Invalid inbox lock')
            if os.fstat(descriptor).st_size == 0: os.write(descriptor, b'\0')
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lineage(lock)
            if (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) != (lock.lstat().st_dev, lock.lstat().st_ino):
                raise SpokenBriefError('Inbox lock was replaced')
            yield descriptor
        except OSError as exc:
            raise SpokenBriefError(f'Inbox is busy or inaccessible: {exc}') from exc
        finally:
            if descriptor is not None: os.close(descriptor)

    def _unchanged(self, expected_sha256):
        if os.path.lexists(self.state_path):
            current, _ = _capture(self.state_path, MAX_STATE_BYTES)
            if digest_bytes(current) != expected_sha256: raise SpokenBriefError('Inbox changed outside the owned lock')
        elif expected_sha256 is not None: raise SpokenBriefError('Inbox disappeared outside the owned lock')

    def _save(self, value, expected_sha256, lock_descriptor):
        raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        if len(raw) > MAX_STATE_BYTES: raise SpokenBriefError('Inbox byte capacity reached; archive it explicitly')
        temporary = None
        try:
            parent = _lineage(self.state_path.parent)
            self._unchanged(expected_sha256)
            descriptor, name = tempfile.mkstemp(prefix='.spoken-inbox-', suffix='.tmp', dir=self.state_path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            self._root_check()
            if _lineage(self.state_path.parent) != parent: raise SpokenBriefError('Inbox parent was replaced')
            lock = self.state_path.with_name(self.state_path.name + '.lock')
            _lineage(lock)
            if (os.fstat(lock_descriptor).st_dev, os.fstat(lock_descriptor).st_ino) != (lock.lstat().st_dev, lock.lstat().st_ino):
                raise SpokenBriefError('Inbox lock was replaced')
            self._unchanged(expected_sha256)
            os.replace(temporary, self.state_path)
            if os.name != 'nt':
                descriptor = os.open(self.state_path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
        except OSError as exc: raise SpokenBriefError(f'Cannot persist inbox: {exc}') from exc
        finally:
            if temporary is not None:
                try: temporary.unlink()
                except FileNotFoundError: pass

    @staticmethod
    def _refuse(refusals, path, error):
        if len(refusals) < MAX_REFUSALS:
            refusals.append({'path': str(path), 'error': str(error)[:1000]})
        elif refusals:
            refusals[-1] = {'path': '.', 'error': 'Further refusals omitted: scan refusal capacity reached'}

    def _sources(self, refusals):
        found = []; remaining = MAX_ENTRIES
        def walk(folder, depth):
            nonlocal remaining
            try:
                before = _lineage(folder)
                entries = []
                with os.scandir(folder) as iterator:
                    for entry in iterator:
                        remaining -= 1
                        if remaining < 0:
                            self._refuse(refusals, folder, 'Directory scan capacity reached'); break
                        entries.append(entry)
                if _lineage(folder) != before: raise SpokenBriefError('Directory changed during discovery')
                for name in ('COMPRESSED.md', 'INDEX.md'):
                    candidate = folder / name
                    if os.path.lexists(candidate): found.append(candidate); break
                for entry in sorted(entries, key=lambda x: x.name):
                    if entry.name.startswith(('.', '_')): continue
                    info = entry.stat(follow_symlinks=False)
                    if not _plain(info):
                        self._refuse(refusals, entry.path, 'Symlink/reparse point refused'); continue
                    if stat.S_ISDIR(info.st_mode):
                        if depth >= MAX_DEPTH: self._refuse(refusals, entry.path, 'Directory depth capacity reached')
                        elif remaining >= 0: walk(Path(entry.path), depth + 1)
            except (OSError, SpokenBriefError) as exc: self._refuse(refusals, folder, exc)
        walk(self.root, 0)
        return found

    def scan(self):
        """One observation. Call again after the settle interval, or use CLI scan/watch."""
        with self._lock() as lock_descriptor:
            value, expected = self._load(); refusals = []; seen = set(); now = self.clock(); captured_bytes = 0
            if not isinstance(now, (int, float)) or not math.isfinite(now): raise SpokenBriefError('Invalid observation clock')
            for source in self._sources(refusals):
                relative = source.relative_to(self.root).as_posix(); seen.add(relative)
                try:
                    self._root_check()
                    if captured_bytes >= MAX_SCAN_BYTES:
                        self._refuse(refusals, '.', 'Source byte scan capacity reached'); break
                    raw, signature = _capture(source, MAX_SOURCE_BYTES); captured_bytes += len(raw)
                    manifest = compile_snapshot(source, raw, speaker_id=self.speaker_id)
                    preferred = next((source.parent / name for name in ('COMPRESSED.md', 'INDEX.md')
                                      if os.path.lexists(source.parent / name)), None)
                    if preferred != source: raise SpokenBriefError('Preferred source changed during discovery')
                    observed = self.observations.get(relative)
                    if observed is None or observed[0] != signature or now < observed[1]:
                        self.observations[relative] = (signature, now); continue
                    if now - observed[1] < SETTLE_SECONDS: continue
                    identifier = _candidate_id(manifest)
                    existing = next((x for x in value['candidates'] if x['id'] == identifier), None)
                    if existing is not None:
                        if relative not in existing['sources']:
                            if len(existing['sources']) >= MAX_ALIASES: raise SpokenBriefError('Duplicate source alias capacity reached')
                            existing['sources'].append(relative)
                        continue
                    if len(value['candidates']) >= MAX_CANDIDATES: raise SpokenBriefError('Inbox candidate capacity reached; archive it explicitly')
                    supersedes = [x['id'] for x in value['candidates']
                        if any(Path(alias).parent == Path(relative).parent for alias in x['sources'])]
                    value['candidates'].append({'id': identifier, 'source_sha256': manifest['source']['sha256'],
                        'source_text': raw.decode('utf-8'), 'sources': [relative], 'manifest': manifest,
                        'status': 'pending', 'detected_at': datetime.now(timezone.utc).isoformat(),
                        'supersedes': supersedes, 'generation_submitted': False})
                except (OSError, SpokenBriefError) as exc:
                    self.observations.pop(relative, None); self._refuse(refusals, relative, exc)
            self.observations = {key: val for key, val in self.observations.items() if key in seen}
            value['refusals'] = refusals
            self._save(value, expected, lock_descriptor)
            return self._summary(value)

    def _summary(self, value):
        candidates = []
        for item in value['candidates']:
            manifest = item['manifest']; words = sum(len(x['text'].split()) for x in manifest['segments'])
            pauses = sum(x['pause_after_ms'] for x in manifest['segments']) / 1000
            candidates.append({key: copy.deepcopy(item[key]) for key in ('id', 'source_sha256', 'sources', 'status', 'detected_at', 'supersedes')})
            candidates[-1].update(manifest_sha256=manifest['manifest_sha256'], segments=len(manifest['segments']),
                batches=len(batch_segments(manifest['segments'])), omissions=manifest['omissions'],
                estimated_duration_seconds={'min': round(words * 60 / 200 + pauses, 2), 'max': round(words * 60 / 120 + pauses, 2)},
                profile={'id': 'kokoro-af-heart-control-v1', 'status': 'built-in-baseline', 'speaker_id': self.speaker_id})
        return {'kind': 'spoken-brief-inbox', 'root': str(self.root), 'policy': 'review-first',
            'generation_submitted': False, 'candidates': candidates, 'refusals': copy.deepcopy(value['refusals'])}

    def list(self):
        return self._summary(self._load()[0])

    def _find(self, value, identifier):
        if not isinstance(identifier, str) or not HEX.fullmatch(identifier): raise SpokenBriefError('Invalid candidate ID')
        item = next((x for x in value['candidates'] if x['id'] == identifier), None)
        if item is None: raise SpokenBriefError('Unknown candidate ID')
        return item

    def preview(self, identifier):
        return copy.deepcopy(self._find(self._load()[0], identifier))

    def ignore(self, identifier):
        with self._lock() as lock_descriptor:
            value, expected = self._load(); item = self._find(value, identifier); item['status'] = 'ignored'
            self._save(value, expected, lock_descriptor); return copy.deepcopy(item)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path); parser.add_argument('--state', type=Path)
    parser.add_argument('--speaker-id', default='brief-narrator')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('scan', 'list', 'watch'): commands.add_parser(name)
    for name in ('preview', 'ignore'): commands.add_parser(name).add_argument('id')
    parser.add_argument('--interval', type=float, default=5.0)
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.interval) or not 5 <= args.interval <= 3600:
            raise SpokenBriefError('Watch interval must be between 5 and 3600 seconds')
        inbox = Inbox(args.root, args.state, speaker_id=args.speaker_id)
        if args.command == 'watch':
            while True:
                print(json.dumps(inbox.scan(), ensure_ascii=False), flush=True); time.sleep(args.interval)
        if args.command == 'scan':
            inbox.scan(); time.sleep(SETTLE_SECONDS); result = inbox.scan()
        elif args.command == 'list': result = inbox.list()
        else: result = getattr(inbox, args.command)(args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except KeyboardInterrupt: return 0
    except (OSError, SpokenBriefError) as exc:
        print('spoken brief inbox: ' + str(exc), file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
