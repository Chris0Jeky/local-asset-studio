"""Restore the pinned character-research kit into a NEW local evidence directory.

No network, executable import, model installation or generation. The archive lock
is an integrity record, not a signature. Use the reviewed repository lock.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_study import SHA, file_sha, integer, keys, read_json, relative, require, sha, write_json

MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024


def import_bundle(archive: Path, lock: dict, output: Path) -> dict:
    keys(lock, {'schema_version', 'kind', 'archive', 'max_uncompressed_bytes', 'members', 'policy'})
    require(type(lock['schema_version']) is int and lock['schema_version'] == 1
            and lock['kind'] == 'character_research_archive_lock', 'Unsupported archive lock')
    keys(lock['archive'], {'filename', 'bytes', 'sha256'})
    integer(lock['archive']['bytes'], 1, MAX_ARCHIVE, 'archive bytes')
    integer(lock['max_uncompressed_bytes'], 1, MAX_EXPANDED, 'expanded bytes')
    require(isinstance(lock['members'], dict) and 1 <= len(lock['members']) <= 128, 'Expected 1..128 pinned members')
    folded = set(); total = 0
    for name, entry in lock['members'].items():
        relative(name)
        require(name.startswith('character-consistency-kit/'), 'Unexpected member root')
        require(name.casefold() not in folded, 'Case-colliding member names'); folded.add(name.casefold())
        keys(entry, {'bytes', 'sha256'}); integer(entry['bytes'], 1, MAX_EXPANDED, 'member bytes')
        require(isinstance(entry['sha256'], str) and bool(SHA.fullmatch(entry['sha256'])), 'Invalid member digest')
        total += entry['bytes']
    require(total == lock['max_uncompressed_bytes'], 'Expanded-size total disagrees with lock')
    require(isinstance(lock['archive']['sha256'], str) and bool(SHA.fullmatch(lock['archive']['sha256'])), 'Invalid archive digest')
    output = Path(output)
    if output.exists() or output.is_symlink(): raise FileExistsError('Choose a new evidence directory')
    stage = None
    try:
        with Path(archive).open('rb') as stream:
            h = hashlib.sha256(); size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(chunk); require(size <= MAX_ARCHIVE, 'Archive exceeds limit'); h.update(chunk)
            require(size == lock['archive']['bytes'] and h.hexdigest() == lock['archive']['sha256'], 'Archive digest/size mismatch')
            stream.seek(0)
            with zipfile.ZipFile(stream) as source:
                infos = source.infolist(); names = [i.filename for i in infos]
                require(len(names) == len(set(names)) and set(names) == set(lock['members']), 'Archive member set differs from lock')
                for info in infos:
                    mode = info.external_attr >> 16
                    require(not info.is_dir() and not (info.flag_bits & 1), 'Directory/encrypted members are unsupported')
                    require(stat.S_IFMT(mode) in {0, stat.S_IFREG}, 'Special/symlink member rejected')
                    require(info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}, 'Unsupported compression')
                    require(info.file_size == lock['members'][info.filename]['bytes'], 'Member size differs from lock')
                output.parent.mkdir(parents=True, exist_ok=True)
                stage = Path(tempfile.mkdtemp(prefix='.character-import-', dir=output.parent))
                for info in infos:
                    destination = stage / info.filename; destination.parent.mkdir(parents=True, exist_ok=True)
                    h = hashlib.sha256(); written = 0
                    with source.open(info) as src, destination.open('xb') as dst:
                        for chunk in iter(lambda: src.read(1024 * 1024), b''):
                            written += len(chunk); require(written <= info.file_size, 'Member exceeds declared size')
                            h.update(chunk); dst.write(chunk)
                    entry = lock['members'][info.filename]
                    require(written == entry['bytes'] and h.hexdigest() == entry['sha256'], 'Member digest mismatch')
        receipt = {'schema_version': 1, 'kind': 'character_research_import', 'archive_sha256': lock['archive']['sha256'],
                   'lock_sha256': sha(lock), 'members_verified': len(lock['members']), 'bytes_verified': total,
                   'generation_submitted': False, 'code_executed_from_archive': False,
                   'art_accepted': False, 'licence_cleared': False}
        write_json(stage / 'IMPORT-RECEIPT.json', receipt)
        if output.exists() or output.is_symlink(): raise FileExistsError('Output appeared during import')
        # Repository contract: one trusted writer; this is not a hostile filesystem sandbox.
        stage.rename(output); stage = None
        return receipt
    finally:
        if stage is not None: shutil.rmtree(stage, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--lock', type=Path, default=ROOT / 'research/character-consistency/archive-lock.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = import_bundle(args.archive, read_json(args.lock), args.out)
        print(json.dumps(result, indent=2)); return 0
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
        parser.exit(2, f'character-archive: {exc}\n')


if __name__ == '__main__': raise SystemExit(main())
