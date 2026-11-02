"""Read-only recorded ComfyUI patch warnings; never apply patches or block startup."""
from __future__ import annotations

import argparse
import hashlib
from itertools import islice
import json
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
MAX_RECORDS = 32
MAX_RECORD_BYTES = 16 * 1024
MAX_TARGET_BYTES = 4 * 1024 * 1024


class ReadLimit(ValueError):
    pass


def _read(path, limit):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode): raise ValueError('Not a regular file')
    if info.st_size > limit: raise ReadLimit()
    with path.open('rb') as stream: data = stream.read(limit + 1)
    if len(data) > limit: raise ReadLimit()
    return data


def _observe_record(record, comfy_root):
    row = {'patch': record.name, 'target': None, 'status': 'invalid-record',
           'message': 'patch record is invalid or unreadable; patch status is unknown.'}
    try:
        if record.resolve().parent != record.parent.resolve(): return row
        saved = json.loads(_read(record, MAX_RECORD_BYTES))
        target = saved['file']; original = saved['original_sha256']; patched = saved['patched_sha256']
        if (not isinstance(target, str) or not re.fullmatch(r'[A-Za-z0-9_. /-]{1,240}', target)
                or any(part in ('', '.', '..') for part in target.split('/'))): return row
        if not all(isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value)
                   for value in (original, patched)): return row
        original = original.lower(); patched = patched.lower()
        if original == patched: return row
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return row
    row['target'] = target
    try:
        root = Path(comfy_root).resolve()
        path = (root / target).resolve()
        if not path.is_relative_to(root):
            return {**row, 'status': 'unreadable', 'message': 'target resolves outside the configured ComfyUI root; patch status is unknown.'}
        digest = hashlib.sha256(_read(path, MAX_TARGET_BYTES)).hexdigest()
    except FileNotFoundError:
        return {**row, 'status': 'missing', 'message': 'target is missing; patch status is unknown.'}
    except ReadLimit:
        return {**row, 'status': 'unreadable', 'message': 'target exceeds the source-file read limit; patch status is unknown.'}
    except (OSError, ValueError, RuntimeError):
        return {**row, 'status': 'unreadable', 'message': 'target is unreadable or is not a regular file; patch status is unknown.'}
    if digest == patched:
        status, message = 'applied', 'target matches the recorded patched SHA-256.'
    elif digest == original:
        status, message = 'unapplied', 'patch is not applied: target matches the recorded original SHA-256.'
    else:
        status, message = 'unexpected', 'target has an unexpected SHA-256; it matches neither recorded version.'
    return {**row, 'status': status, 'message': message, 'actual_sha256': digest}


def observe(root, comfy_root):
    """Inspect top-level patch records and bounded source bytes, without importing runtime code."""
    directory = Path(root) / 'runtime-patches'
    try:
        records = sorted(islice((p for p in directory.iterdir() if p.suffix == '.json'), MAX_RECORDS + 1))
    except OSError:
        return [{'patch': 'runtime-patches', 'target': None, 'status': 'records-unavailable',
                 'message': 'patch record directory is unavailable; patch status is unknown.'}]
    rows = [_observe_record(record, comfy_root) for record in records[:MAX_RECORDS]]
    if len(records) > MAX_RECORDS:
        rows.append({'patch': 'runtime-patches', 'target': None, 'status': 'record-limit',
                     'message': f'patch record limit ({MAX_RECORDS}) reached; remaining patches were not checked.'})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--comfy-root', type=Path, required=True)
    args = parser.parse_args(argv)
    for row in observe(args.root, args.comfy_root):
        if row['status'] == 'applied': continue
        # Only bounded names and authored messages are printed, never source bytes or exception text.
        name = json.dumps(row['patch'], ensure_ascii=True)
        target = ' (' + json.dumps(row['target'], ensure_ascii=True) + ')' if row['target'] else ''
        print(f"ComfyUI runtime patch {name}{target}: {row['message']} See runtime-patches/README.md.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
