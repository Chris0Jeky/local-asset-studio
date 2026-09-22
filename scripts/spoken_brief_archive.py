"""Read-only, sample-exact verification of completed Spoken Brief archives."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import wave

from spoken_brief_compile import (
    MAX_NARRATED_CHARS, MAX_SEGMENTS, MAX_SOURCE_BYTES, SCHEMA_VERSION,
    SPEAKER_RE, SpokenBriefError, batch_segments, canonical_digest, digest_bytes,
)
from spoken_brief_inbox import HEX, _capture, _constant, _identity, _lineage, _object
from spoken_brief_transport import MAX_AUDIO_BYTES, MAX_JSON_BYTES, PROJECT_ID, validate_studio_record

SAMPLE_RATE = 48000
MAX_MASTER_BYTES = 1024 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


class ArchiveConflict(SpokenBriefError):
    """The caller's previously verified archive is no longer current."""


def require_archive(archive: dict, expected_sha256: str | None) -> None:
    if expected_sha256 is not None and (not _hash(expected_sha256)
            or archive['chapters_sha256'] != expected_sha256):
        raise ArchiveConflict('Archive identity changed; inspect it before another action')


def checked_directory(value) -> Path:
    """Keep lexical identity until linked ancestors have been refused."""
    path = Path(os.path.abspath(value))
    try:
        _lineage(path)
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise SpokenBriefError('An existing run directory is required')
        return path
    except OSError as exc:
        raise SpokenBriefError(f'Cannot inspect run directory: {exc}') from exc


def checked_json(path: Path) -> tuple[dict, str]:
    raw, _ = _capture(path, MAX_JSON_BYTES)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
        if not isinstance(value, dict):
            raise SpokenBriefError(f'Expected an object in {path.name}')
        return value, digest_bytes(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SpokenBriefError(f'Invalid JSON in {path.name}: {exc}') from exc


@contextmanager
def opened_file(path: Path, maximum: int):
    """Bound reads; compare complete before/after identity through the same APIs."""
    try:
        lineage = _lineage(path)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or not 1 <= before.st_size <= maximum:
            raise SpokenBriefError(f'Expected a regular file containing 1 to {maximum} bytes: {path}')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _identity(opened)[:4] != _identity(before)[:4]:
                raise SpokenBriefError(f'File changed during open: {path}')
            yield stream
            if (_identity(os.fstat(stream.fileno())) != _identity(opened)
                    or _lineage(path) != lineage or _identity(path.lstat()) != _identity(before)):
                raise SpokenBriefError(f'File changed during verification: {path}')
    except OSError as exc:
        raise SpokenBriefError(f'Cannot verify {path}: {exc}') from exc


def hash_stream(stream, maximum: int, sink=None) -> tuple[str, int]:
    stream.seek(0)
    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = stream.read(min(CHUNK_BYTES, maximum + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise SpokenBriefError('File exceeded its bounded read budget')
        hasher.update(chunk)
        if sink is not None:
            sink.write(chunk)
    return hasher.hexdigest(), total


def file_record(path: Path, maximum: int) -> dict:
    with opened_file(path, maximum) as stream:
        digest, size = hash_stream(stream, maximum)
    return {'sha256': digest, 'bytes': size}


def _hash(value) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _integer(value, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _bound_path(record, expected: Path) -> None:
    if (not isinstance(record, dict) or not isinstance(record.get('path'), str)
            or not Path(record['path']).is_absolute() or '..' in Path(record['path']).parts
            or Path(record['path']) != expected or not _hash(record.get('sha256'))):
        raise SpokenBriefError('Artifact path or hash differs from the retained run layout')


def _manifest_receipt(manifest: dict, receipt: dict) -> None:
    try:
        source = manifest['source']
        segments = manifest['segments']
        if (type(manifest['schema_version']) is not int or manifest['schema_version'] != SCHEMA_VERSION
                or manifest['kind'] != 'spoken-brief' or not _hash(manifest['manifest_sha256'])
                or canonical_digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'}) != manifest['manifest_sha256']
                or not isinstance(source, dict) or not _hash(source['sha256'])
                or not _integer(source['bytes'], 1, MAX_SOURCE_BYTES)
                or not isinstance(source['path'], str) or not isinstance(source['name'], str)
                or Path(source['path']).name != source['name'] or not source['name'].lower().endswith('.md')
                or not isinstance(manifest['speaker_id'], str) or not SPEAKER_RE.fullmatch(manifest['speaker_id'])
                or not isinstance(segments, list) or not 1 <= len(segments) <= MAX_SEGMENTS):
            raise SpokenBriefError('Invalid archival manifest identity or bounds')
        batch_segments(segments)
        if sum(len(x['text']) for x in segments) > MAX_NARRATED_CHARS:
            raise SpokenBriefError('Narration character budget exceeded')
        previous_block = -1
        block_kind = None
        for index, segment in enumerate(segments, 1):
            if (segment['id'] != f'segment-{index:04d}'
                    or segment['text_sha256'] != digest_bytes(segment['text'].encode('utf-8'))
                    or not _integer(segment['pause_after_ms'], 0, 5000)
                    or not _integer(segment['block'], 0, MAX_SEGMENTS)
                    or segment['block'] < previous_block
                    or segment['kind'] not in ('paragraph', 'heading', 'table')
                    or (segment['block'] == previous_block and segment['kind'] != block_kind)):
                raise SpokenBriefError('Invalid archival segment identity, ordering or pause')
            previous_block, block_kind = segment['block'], segment['kind']
        projects = receipt['projects']
        plans = receipt['project_plans']
        if (type(receipt['schema_version']) is not int or receipt['schema_version'] != SCHEMA_VERSION
                or receipt['manifest_sha256'] != manifest['manifest_sha256'] or canonical_digest(receipt['source']) != canonical_digest(source)
                or receipt['speaker_id'] != manifest['speaker_id'] or not _hash(receipt['producer_sha256'])
                or not isinstance(projects, list) or not 1 <= len(projects) <= MAX_SEGMENTS
                or any(not isinstance(x, str) or not PROJECT_ID.fullmatch(x) for x in projects)
                or len(set(projects)) != len(projects)
                or not isinstance(plans, list) or len(plans) != len(projects)
                or any(not isinstance(plan, dict) or set(plan) != {'id', 'sha256'}
                       or plan['id'] != projects[i] or not _hash(plan['sha256']) for i, plan in enumerate(plans))
                or canonical_digest(receipt['segments']) != canonical_digest([{key: x[key] for key in ('id', 'text_sha256', 'pause_after_ms')} for x in segments])):
            raise SpokenBriefError('Manifest and assembly receipt provenance disagree')
        validate_studio_record(receipt['studio'])
    except (KeyError, TypeError, AttributeError, UnicodeError) as exc:
        raise SpokenBriefError('Malformed archival manifest or assembly receipt') from exc


def wav_parameters(reader) -> int:
    if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.getcomptype()) != (1, 2, SAMPLE_RATE, 'NONE'):
        raise SpokenBriefError('Expected 48 kHz mono PCM16 WAV')
    count = reader.getnframes()
    if not _integer(count, 1, MAX_MASTER_BYTES // 2):
        raise SpokenBriefError('WAV frame count is empty or exceeds the archive budget')
    return count


def _chapters(segments: list[dict], total: int) -> list[dict]:
    chapters = []
    last_heading_block = None
    for item in segments:
        if item['kind'] == 'heading':
            if item['block'] == last_heading_block:
                chapters[-1]['title'] += ' ' + item['text']
                continue
            title = item['text']
            last_heading_block = item['block']
        elif not chapters:
            title = 'Introduction'
        else:
            continue
        if chapters:
            chapters[-1]['end_sample'] = item['start_sample']
        chapters.append({'id': f'chapter-{len(chapters) + 1:04d}', 'title': title,
                         'start_sample': item['start_sample'], 'end_sample': total})
    return chapters


def inspect_run(run_dir) -> dict:
    """Derive timestamps only after checking every segment against actual master PCM.

    Original Markdown and live Studio are deliberately unnecessary. Hashes bind
    local evidence, not authenticated claims about a voice or a human audition.
    """
    directory = checked_directory(run_dir)
    manifest, manifest_file_sha = checked_json(directory / 'manifest.json')
    receipt, receipt_file_sha = checked_json(directory / 'receipt.json')
    _manifest_receipt(manifest, receipt)
    master = directory / (Path(manifest['source']['name']).stem + '.spoken.wav')
    output = receipt.get('output')
    _bound_path(output, master)
    inputs = output.get('inputs')
    if (not isinstance(inputs, list) or len(inputs) != len(manifest['segments'])
            or output.get('format') != 'wav-pcm-s16le-mono-48000'
            or not _integer(output.get('samples'), 1, MAX_MASTER_BYTES // 2)):
        raise SpokenBriefError('Invalid assembly input layout or total sample count')
    cursor = 0
    measured = []
    try:
        with opened_file(master, MAX_MASTER_BYTES) as stream:
            master_sha, master_bytes = hash_stream(stream, MAX_MASTER_BYTES)
            if master_sha != output['sha256']:
                raise SpokenBriefError('Archival WAV hash no longer matches its receipt')
            stream.seek(0)
            with wave.open(stream, 'rb') as joined:
                total = wav_parameters(joined)
                for segment, entry in zip(manifest['segments'], inputs):
                    path = directory / 'segments' / (segment['id'] + '.wav')
                    _bound_path(entry, path)
                    if (entry.get('id') != segment['id'] or not _integer(entry.get('pause_after_ms'), 0, 5000)
                            or entry.get('pause_after_ms') != segment['pause_after_ms']
                            or not _integer(entry.get('samples'), 1, MAX_AUDIO_BYTES // 2)):
                        raise SpokenBriefError('Assembly input segment identity or sample count is invalid')
                    raw, _ = _capture(path, MAX_AUDIO_BYTES)
                    if digest_bytes(raw) != entry['sha256']:
                        raise SpokenBriefError('Retained segment audio hash changed')
                    with wave.open(io.BytesIO(raw), 'rb') as scene:
                        count = wav_parameters(scene)
                        frames = scene.readframes(count)
                    if count != entry['samples'] or len(frames) != count * 2 or joined.readframes(count) != frames:
                        raise SpokenBriefError('Segment samples do not match the archival PCM sequence')
                    silence = segment['pause_after_ms'] * (SAMPLE_RATE // 1000)
                    if joined.readframes(silence) != b'\0\0' * silence:
                        raise SpokenBriefError('Archival pause samples disagree with the assembly receipt')
                    measured.append({**segment, 'audio_sha256': entry['sha256'], 'samples': count,
                        'start_sample': cursor, 'speech_end_sample': cursor + count,
                        'end_sample': cursor + count + silence})
                    cursor += count + silence
                if cursor != total or cursor != output['samples'] or joined.readframes(1):
                    raise SpokenBriefError('Archival total sample count disagrees with verified inputs')
            if hash_stream(stream, MAX_MASTER_BYTES)[0] != master_sha:
                raise SpokenBriefError('Archival WAV changed during PCM verification')
    except (EOFError, wave.Error, KeyError, TypeError) as exc:
        raise SpokenBriefError(f'Malformed archival WAV or input: {exc}') from exc
    if (checked_json(directory / 'manifest.json')[1] != manifest_file_sha
            or checked_json(directory / 'receipt.json')[1] != receipt_file_sha):
        raise SpokenBriefError('Archive metadata changed during verification')
    result = {'schema_version': 1, 'kind': 'spoken-brief-chapters', 'sample_rate': SAMPLE_RATE,
        'manifest_sha256': manifest['manifest_sha256'], 'manifest_file_sha256': manifest_file_sha,
        'assembly_receipt_sha256': receipt_file_sha, 'source': manifest['source'],
        'speaker_id': manifest['speaker_id'], 'producer_sha256': receipt['producer_sha256'],
        'studio': receipt['studio'], 'project_plans': receipt['project_plans'],
        'master': {'name': master.name, 'sha256': master_sha, 'bytes': master_bytes, 'samples': total},
        'segments': measured, 'chapters': _chapters(measured, total)}
    result['chapters_sha256'] = canonical_digest(result)
    return result


def ffmetadata(sidecar: dict) -> str:
    def escape(value: str) -> str:
        return ''.join(('\\' + char) if char in '\\=;#\n' else char for char in value)
    identity = {key: sidecar[key] for key in ('manifest_sha256', 'producer_sha256')}
    identity.update(source_sha256=sidecar['source']['sha256'], master_sha256=sidecar['master']['sha256'])
    metadata = {'title': sidecar['chapters'][0]['title'],
                'comment': 'Spoken Brief; ' + '; '.join(key + '=' + value for key, value in identity.items()),
                **identity}
    lines = [';FFMETADATA1'] + [key + '=' + escape(value) for key, value in metadata.items()]
    for chapter in sidecar['chapters']:
        lines.extend(['[CHAPTER]', f'TIMEBASE=1/{SAMPLE_RATE}', f"START={chapter['start_sample']}",
                      f"END={chapter['end_sample']}", 'title=' + escape(chapter['title'])])
    return '\n'.join(lines) + '\n'
