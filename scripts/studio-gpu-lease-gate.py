"""Read-only desktop launch admission; never acquire, expire or rewrite a lease.

Exit 0 permits the ordinary launch path, 10 skips ComfyUI but permits Studio to
start under a held lease, and 20 blocks both starts until state is inspected.
This observation is not a cross-process reservation of the GPU.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from gpu_lease import GpuLease

MAX_STATE_BYTES = 64 * 1024


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Duplicate lease field')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Non-finite lease value')


def observe(root, now=None):
    """Return (exit code, JSON observation); uncertainty never permits launch."""
    path = Path(root) / '.runtime' / 'studio-gpu-lease.json'
    try:
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError('Linked lease state is not launch authority')
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            return 0, {'state': 'available', 'message': 'No retained Studio GPU lease.'}
        if not stat.S_ISREG(mode): raise ValueError('Lease state must be a regular file')
        with path.open('rb') as stream:
            raw = stream.read(MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES: raise ValueError('Lease state exceeds its read bound')
        saved = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
        if not isinstance(saved, dict) or 'record' not in saved:
            raise ValueError('Invalid lease envelope')
        record = saved['record']
        if record is None:
            return 0, {'state': 'available', 'message': 'The retained Studio GPU lease was released.'}
        if not GpuLease._valid_record(record): raise ValueError('Invalid lease holder or deadline')
        if record['expires_at'] <= (time.time() if now is None else now):
            return 0, {'state': 'available', 'message': 'The retained Studio GPU lease has expired.'}
        return 10, {'state': 'held', 'holder': record['holder'],
                    'message': f"GPU leased to {record['holder']}; ComfyUI launch skipped. Studio can start for lease release/status."}
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        return 20, {'state': 'unknown',
                    'message': 'GPU lease state is unavailable or invalid; no launch is authorized. Inspect .runtime/studio-gpu-lease.json. ' + str(exc)[:160]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    code, value = observe(args.root)
    print(json.dumps(value, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
