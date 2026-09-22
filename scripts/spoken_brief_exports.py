#!/usr/bin/env python3
"""Explicit, immutable listening exports from verified WAV archives; never TTS."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import wave

from spoken_brief_archive import (
    CHUNK_BYTES, MAX_MASTER_BYTES, SAMPLE_RATE, checked_directory, checked_json,
    ffmetadata, file_record, hash_stream, inspect_run, opened_file, wav_parameters, require_archive,
)
from spoken_brief_compile import SpokenBriefError, canonical_digest, digest_bytes
from spoken_brief_inbox import HEX, _capture, _lineage
from spoken_brief_transport import (
    MAX_JSON_BYTES, _sync_parent, acquire_run_claim, release_run_claim,
)

EXPORT_VERSION = 1
MAX_EXPORTS = 32
MAX_DERIVATIVE_BYTES = 256 * 1024 * 1024
MAX_TOOL_BYTES = 256 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
DECODE_TOLERANCE_SAMPLES = 2400  # 50 ms accommodates codec padding; not a speech-quality score.
PRESETS = {'quick': '96k', 'high': '192k'}


def _json_bytes(value) -> bytes:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > MAX_JSON_BYTES:
        raise SpokenBriefError('Export metadata byte budget exceeded')
    return raw


def _new_file(path: Path, raw: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def _claim(directory: Path, manifest_sha256: str):
    lineage = _lineage(directory)
    lock = acquire_run_claim(directory, manifest_sha256)
    lock_record = file_record(lock, MAX_JSON_BYTES)

    def verify():
        if _lineage(directory) != lineage or file_record(lock, MAX_JSON_BYTES) != lock_record:
            raise SpokenBriefError('Run directory or owned export claim changed')
    try:
        yield verify
    finally:
        verify()
        release_run_claim(lock)


def _tool(path, pin) -> dict:
    if (path is None or not Path(path).is_absolute() or not isinstance(pin, str) or not HEX.fullmatch(pin)):
        raise SpokenBriefError('Lossy export requires an absolute owned FFmpeg path and its full SHA-256')
    path = Path(path)
    if path.suffix.lower() in ('.cmd', '.bat'):
        raise SpokenBriefError('Select the FFmpeg executable, not a shell wrapper')
    record = file_record(path, MAX_TOOL_BYTES)
    if record['sha256'] != pin:
        raise SpokenBriefError('Owned FFmpeg executable hash differs; nothing was executed')
    return {'path': str(path), **record}


def _run_tool(argv: list[str], cwd: Path, *, outputs: dict[str, int] | None = None, timeout: float = 600) -> str:
    """Own the child process, bound logs/time/output, kill and reap on every failure."""
    outputs = outputs or {}
    process = None
    started = time.monotonic()
    with tempfile.TemporaryFile(dir=cwd) as log:
        try:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, shell=False)
            while True:
                if os.fstat(log.fileno()).st_size > MAX_LOG_BYTES:
                    raise SpokenBriefError('FFmpeg log byte limit exceeded')
                for name, maximum in outputs.items():
                    path = cwd / name
                    if os.path.lexists(path):
                        _lineage(path)
                        if path.stat().st_size > maximum:
                            raise SpokenBriefError('FFmpeg output byte limit exceeded')
                if process.poll() is not None:
                    break
                if time.monotonic() - started > timeout:
                    raise SpokenBriefError('FFmpeg time budget exceeded')
                time.sleep(0.05)
            log.seek(0)
            text = log.read(MAX_LOG_BYTES + 1).decode('utf-8', errors='replace')
            if process.returncode != 0:
                raise SpokenBriefError(f'FFmpeg failed ({process.returncode}): {text[:2000]}')
            return text
        except OSError as exc:
            raise SpokenBriefError(f'Cannot run the owned FFmpeg executable: {exc}') from exc
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()


def _run_pinned(tool: dict, argv: list[str], cwd: Path, **kwargs) -> str:
    if _tool(tool['path'], tool['sha256']) != tool or argv[0] != tool['path']:
        raise SpokenBriefError('Owned FFmpeg changed before invocation')
    return _run_tool(argv, cwd, **kwargs)


def _commands(tool: dict, format: str, preset: str) -> tuple[list[str], list[str]]:
    common = [tool['path'], '-hide_banner', '-nostdin', '-v', 'error', '-n']
    encode = common + ['-protocol_whitelist', 'file', '-i', 'source.wav',
        '-f', 'ffmetadata', '-protocol_whitelist', 'file', '-i', 'chapters.ffmeta',
        '-map', '0:a:0', '-map_metadata', '1', '-map_chapters', '1', '-vn',
        '-ac', '1', '-ar', str(SAMPLE_RATE), '-c:a', 'libmp3lame' if format == 'mp3' else 'aac',
        '-b:a', PRESETS[preset]]
    if format == 'mp3':
        encode += ['-id3v2_version', '3', '-write_xing', '1', '-f', 'mp3']
    else:
        encode += ['-movflags', '+faststart+use_metadata_tags', '-f', 'mp4']
    encode += ['listening.' + format]
    decode = common + ['-protocol_whitelist', 'file', '-i', 'listening.' + format,
        '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(SAMPLE_RATE), '-c:a', 'pcm_s16le', '-f', 'wav', 'decoded.wav']
    return encode, decode


def _decoded(path: Path) -> dict:
    with opened_file(path, MAX_MASTER_BYTES) as stream:
        raw_hash, size = hash_stream(stream, MAX_MASTER_BYTES)
        stream.seek(0)
        try:
            with wave.open(stream, 'rb') as reader:
                count = wav_parameters(reader)
                hasher = hashlib.sha256()
                remaining = count
                while remaining:
                    frames = reader.readframes(min(remaining, CHUNK_BYTES // 2))
                    if not frames or len(frames) % 2:
                        raise SpokenBriefError('Decoded WAV is truncated')
                    remaining -= len(frames) // 2
                    hasher.update(frames)
        except (EOFError, wave.Error) as exc:
            raise SpokenBriefError(f'Decoded listening export is not a valid WAV: {exc}') from exc
    return {'samples': count, 'sample_rate': SAMPLE_RATE, 'channels': 1, 'sample_width': 2,
            'pcm_sha256': hasher.hexdigest(), 'wav_sha256': raw_hash, 'wav_bytes': size,
            'duration_tolerance_samples': DECODE_TOLERANCE_SAMPLES}


def _reuse(directory: Path, request: dict) -> dict:
    receipt, _ = checked_json(directory / 'receipt.json')
    try:
        if (type(receipt['schema_version']) is not int or receipt['schema_version'] != EXPORT_VERSION or receipt['kind'] != 'spoken-brief-export'
                or canonical_digest(receipt['request']) != canonical_digest(request) or receipt['id'] != canonical_digest(request)
                or receipt['receipt_sha256'] != canonical_digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})):
            raise SpokenBriefError('Existing export identity or receipt is corrupt')
        format = request['format']
        expected = {'chapters.json', 'chapters.ffmeta'}
        if format != 'chapters':
            expected.add('listening.' + format)
            if (not isinstance(receipt['tool'], dict) or receipt['tool']['sha256'] != request['tool']['sha256']
                    or any(receipt['tool'].get(key) != value for key, value in request['tool'].items())
                    or not isinstance(receipt['tool']['version'], str)
                    or not receipt['tool']['version'].startswith('ffmpeg version')
                    or type(receipt['decoded']['samples']) is not int
                    or receipt['decoded']['samples'] <= 0
                    or abs(receipt['decoded']['samples'] - request['master']['samples']) > DECODE_TOLERANCE_SAMPLES):
                raise SpokenBriefError('Existing export has invalid tool or decode evidence')
        actual = set()
        with os.scandir(directory) as entries:
            for entry in entries:
                actual.add(entry.name)
                if len(actual) > len(expected) + 1:
                    raise SpokenBriefError('Unexpected files in immutable export')
        if actual != expected | {'receipt.json'} or set(receipt['files']) != expected:
            raise SpokenBriefError('Existing export is incomplete or contains unexpected files')
        if any(receipt['files'].get(name) != record for name, record in request['sidecar_files'].items()):
            raise SpokenBriefError('Retained sidecars no longer match the requested archive')
        for name in sorted(expected):
            maximum = MAX_DERIVATIVE_BYTES if name.startswith('listening.') else MAX_JSON_BYTES
            if file_record(directory / name, maximum) != receipt['files'][name]:
                raise SpokenBriefError('An immutable export artifact changed')
        return {'directory': str(directory), 'receipt': str(directory / 'receipt.json'), 'reused': True}
    except (KeyError, TypeError, AttributeError) as exc:
        raise SpokenBriefError('Malformed existing export receipt') from exc


def export_run(run_dir, *, format: str = 'chapters', preset: str = 'quick', ffmpeg=None, ffmpeg_sha256=None) -> dict:
    """Publish one complete immutable directory, or verify and reuse it read-only."""
    if not isinstance(format, str) or not isinstance(preset, str) or format not in ('chapters', 'mp3', 'm4b') or preset not in PRESETS:
        raise SpokenBriefError('Choose chapters/mp3/m4b and the quick/high listening preset')
    if format == 'chapters' and (ffmpeg is not None or ffmpeg_sha256 is not None):
        raise SpokenBriefError('Chapter sidecars need no executable')
    directory = checked_directory(run_dir)
    sidecar = inspect_run(directory)
    tool = None if format == 'chapters' else _tool(ffmpeg, ffmpeg_sha256)
    sidecar_files = {'chapters.json': _json_bytes(sidecar), 'chapters.ffmeta': ffmetadata(sidecar).encode('utf-8')}
    request = {'version': EXPORT_VERSION, 'manifest_sha256': sidecar['manifest_sha256'],
        'chapters_sha256': sidecar['chapters_sha256'], 'master': sidecar['master'],
        'format': format, 'preset': preset, 'tool': tool,
        'sidecar_files': {name: {'sha256': digest_bytes(raw), 'bytes': len(raw)} for name, raw in sidecar_files.items()}}
    if tool is not None:
        request['encode_argv'], request['decode_argv'] = _commands(tool, format, preset)
    parent = directory / 'exports'
    target = parent / canonical_digest(request)
    if os.path.lexists(target):
        return _reuse(checked_directory(target), request)
    stage = None
    try:
        with _claim(directory, sidecar['manifest_sha256']) as verify_claim:
            if inspect_run(directory) != sidecar:
                raise SpokenBriefError('Archive changed before acquiring export ownership')
            if os.path.lexists(parent):
                checked_directory(parent)
            else:
                parent.mkdir()
            parent_identity = _lineage(parent)
            with os.scandir(parent) as entries:
                for index, _ in enumerate(entries):
                    if index >= MAX_EXPORTS - 1:
                        raise SpokenBriefError('Export capacity reached; explicitly archive old exports or crash remnants')
            if os.path.lexists(target):
                return _reuse(checked_directory(target), request)
            stage = Path(tempfile.mkdtemp(prefix='.export-', dir=parent))
            for name, raw in sidecar_files.items():
                _new_file(stage / name, raw)
            receipt = {'schema_version': EXPORT_VERSION, 'kind': 'spoken-brief-export',
                       'id': canonical_digest(request), 'request': request, 'tool': None, 'decoded': None}
            if tool is not None:
                if _tool(ffmpeg, ffmpeg_sha256) != tool:
                    raise SpokenBriefError('FFmpeg changed before invocation')
                version = _run_pinned(tool, [tool['path'], '-version'], stage, timeout=15).strip()
                if not version.startswith('ffmpeg version'):
                    raise SpokenBriefError('The pinned executable did not identify itself as FFmpeg')
                receipt['tool'] = {**tool, 'version': version}
                with opened_file(directory / sidecar['master']['name'], MAX_MASTER_BYTES) as source:
                    with (stage / 'source.wav').open('xb') as sink:
                        copied_sha, _ = hash_stream(source, MAX_MASTER_BYTES, sink)
                        sink.flush()
                        os.fsync(sink.fileno())
                if copied_sha != sidecar['master']['sha256']:
                    raise SpokenBriefError('Master changed during export snapshot capture')
                _run_pinned(tool, request['encode_argv'], stage, outputs={'listening.' + format: MAX_DERIVATIVE_BYTES})
                _run_pinned(tool, request['decode_argv'], stage, outputs={'decoded.wav': MAX_MASTER_BYTES})
                receipt['decoded'] = _decoded(stage / 'decoded.wav')
                if abs(receipt['decoded']['samples'] - sidecar['master']['samples']) > DECODE_TOLERANCE_SAMPLES:
                    raise SpokenBriefError('Decoded duration falls outside the recorded codec tolerance')
                if _tool(ffmpeg, ffmpeg_sha256) != tool:
                    raise SpokenBriefError('FFmpeg changed during export')
                (stage / 'source.wav').unlink()
                (stage / 'decoded.wav').unlink()
            names = ['chapters.json', 'chapters.ffmeta'] + ([] if tool is None else ['listening.' + format])
            receipt['files'] = {name: file_record(stage / name,
                MAX_DERIVATIVE_BYTES if name.startswith('listening.') else MAX_JSON_BYTES) for name in names}
            receipt['receipt_sha256'] = canonical_digest(receipt)
            _new_file(stage / 'receipt.json', _json_bytes(receipt))
            for name in names:
                with (stage / name).open('r+b') as stream:
                    os.fsync(stream.fileno())
            _sync_parent(stage / 'receipt.json')
            if inspect_run(directory) != sidecar or _lineage(parent) != parent_identity:
                raise SpokenBriefError('Archive or export parent changed before publication')
            _reuse(stage, request)  # Revalidate exact staged bytes after all flushes.
            verify_claim()
            if os.path.lexists(target):
                raise SpokenBriefError('Export target appeared before publication; refusing replacement')
            os.rename(stage, target)
            stage = None
            _sync_parent(target)
            return {'directory': str(target), 'receipt': str(target / 'receipt.json'), 'reused': False}
    except OSError as exc:
        raise SpokenBriefError(f'Cannot publish listening export: {exc}') from exc
    finally:
        if stage is not None:
            shutil.rmtree(stage)


def _playback(sidecar: dict, sample, rate, loop) -> dict:
    total = sidecar['master']['samples']
    if (type(sample) is not int or not 0 <= sample <= total or type(rate) not in (int, float)
            or not math.isfinite(rate) or not 0.5 <= rate <= 3):
        raise SpokenBriefError('Playback sample must be in range and rate must be between 0.5 and 3')
    if loop is not None and (not isinstance(loop, list) or len(loop) != 2
            or any(type(x) is not int for x in loop) or not 0 <= loop[0] < loop[1] <= total):
        raise SpokenBriefError('Playback loop must contain increasing in-range sample offsets')
    return {'schema_version': 1, 'kind': 'spoken-brief-playback', 'manifest_sha256': sidecar['manifest_sha256'],
        'master_sha256': sidecar['master']['sha256'], 'sample': sample, 'rate': rate, 'loop': loop,
        'status': 'completed' if sample == total else ('unheard' if sample == 0 else 'in-progress')}


def _load_playback(directory: Path, sidecar: dict) -> tuple[dict, str | None]:
    path = directory / 'playback.json'
    if not os.path.lexists(path):
        return _playback(sidecar, 0, 1.0, None), None
    value, digest = checked_json(path)
    try:
        expected = _playback(sidecar, value['sample'], value['rate'], value['loop'])
        if canonical_digest(value) != canonical_digest(expected):
            raise SpokenBriefError('Playback state belongs to different audio or has an unsupported schema')
        return value, digest
    except (KeyError, TypeError) as exc:
        raise SpokenBriefError('Malformed playback state') from exc


def load_playback(run_dir) -> dict:
    directory = checked_directory(run_dir)
    return _load_playback(directory, inspect_run(directory))[0]


class PlaybackConflict(SpokenBriefError):
    """A newer saved position must not be overwritten by a stale reader."""


def save_playback(run_dir, *, sample: int, rate: float = 1.0, loop=None,
                  expected_playback_sha256: str | None = None,
                  expected_archive_sha256: str | None = None) -> dict:
    directory = checked_directory(run_dir)
    sidecar = inspect_run(directory)
    require_archive(sidecar, expected_archive_sha256)
    value = _playback(sidecar, sample, rate, loop)
    with _claim(directory, sidecar['manifest_sha256']) as verify_claim:
        current, previous = _load_playback(directory, sidecar)
        if expected_playback_sha256 is not None and canonical_digest(current) != expected_playback_sha256:
            raise PlaybackConflict('Playback state changed; inspect the newer bookmark before saving')
        if inspect_run(directory) != sidecar:
            raise SpokenBriefError('Audio changed before saving playback state')
        verify_claim()
        if _load_playback(directory, sidecar)[1] != previous:
            raise SpokenBriefError('Playback state changed outside the owned claim')
        descriptor, name = tempfile.mkstemp(prefix='.playback.json-', suffix='.tmp', dir=directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(_json_bytes(value))
                stream.flush()
                os.fsync(stream.fileno())
            verify_claim()
            if inspect_run(directory) != sidecar or _load_playback(directory, sidecar)[1] != previous:
                raise SpokenBriefError('Audio or playback state changed during persistence')
            os.replace(temporary, directory / 'playback.json')
            _sync_parent(directory / 'playback.json')
        finally:
            temporary.unlink(missing_ok=True)
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect')
    export = commands.add_parser('export')
    export.add_argument('--format', choices=('chapters', 'mp3', 'm4b'), default='chapters')
    export.add_argument('--preset', choices=tuple(PRESETS), default='quick')
    export.add_argument('--ffmpeg', type=Path)
    export.add_argument('--ffmpeg-sha256')
    progress = commands.add_parser('playback')
    progress.add_argument('--sample', type=int)
    progress.add_argument('--rate', type=float, default=1.0)
    progress.add_argument('--loop', nargs=2, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            result = inspect_run(args.run_dir)
        elif args.command == 'export':
            result = export_run(args.run_dir, format=args.format, preset=args.preset,
                                ffmpeg=args.ffmpeg, ffmpeg_sha256=args.ffmpeg_sha256)
        elif args.sample is None:
            if args.rate != 1.0 or args.loop is not None:
                raise SpokenBriefError('Provide --sample when updating rate or loop')
            result = load_playback(args.run_dir)
        else:
            result = save_playback(args.run_dir, sample=args.sample, rate=args.rate, loop=args.loop)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        print('spoken brief export: interrupted; inspect retained exports before retrying', file=sys.stderr)
        return 130
    except (SpokenBriefError, OSError) as exc:
        print('spoken brief export: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
