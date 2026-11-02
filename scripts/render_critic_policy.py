"""Offline, non-promoting review-floor hypotheses over retained render-critic receipts.

    python scripts/render_critic_policy.py replay receipt.json --fraction 0.004 --out new-decision.json

No image/model/Blender execution. The raw detector is never changed. A below-floor
result is not evidence of noise, artistic acceptance, or permission to ship an asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

SCHEMA = 'las.render-critic-review-hypothesis.v1'
MAX_RECEIPT_BYTES = 2 * 1024 * 1024
MAX_VIEWS = 256
MAX_SIDE = 65536


def _require(ok, message):
    if not ok: raise ValueError(message)


def _dimensions(value):
    _require(isinstance(value, list) and len(value) == 2
             and all(type(n) is int and 0 < n <= MAX_SIDE for n in value), 'invalid recorded dimensions')
    return value[0] * value[1]


def _observe(receipt):
    _require(isinstance(receipt, dict), 'receipt must be an object')
    _require('error' not in receipt and receipt.get('evidence_complete') is True, 'incomplete or failed pixel evidence')
    _require(type(receipt.get('changed')) is bool, 'missing raw changed boolean')
    policy = receipt.get('pixel_policy')
    _require(isinstance(policy, dict), 'missing pixel policy')
    _require(policy.get('channels') == 'decoded-RGBA8' and policy.get('colour_management') == 'none',
             'unsupported sample policy')
    level, minimum = policy.get('level'), policy.get('min_pixels')
    _require(type(level) is int and 0 <= level <= 255 and type(minimum) is int and minimum > 0,
             'invalid recorded pixel gate')
    pixels, sizes = receipt.get('pixel_diff'), receipt.get('view_sizes')
    _require(isinstance(pixels, dict) and isinstance(sizes, dict)
             and 0 < len(pixels) <= MAX_VIEWS and pixels.keys() == sizes.keys(), 'missing or mismatched per-view evidence')
    out = {}
    for label, observation in pixels.items():
        _require(isinstance(label, str) and label and isinstance(observation, dict)
                 and isinstance(sizes[label], dict), 'invalid view entry')
        dimensions = sizes[label]
        candidate, reference = dimensions.get('candidate'), dimensions.get('reference')
        area = _dimensions(candidate); _dimensions(reference)
        count = observation.get('changed_px')
        _require(type(count) is int and 0 <= count <= area, 'invalid changed-pixel count')
        mismatch = candidate != reference
        _require((mismatch and observation.get('size_mismatch') == [candidate, reference] and count == area)
                 or (not mismatch and 'size_mismatch' not in observation), 'inconsistent size-mismatch evidence')
        out[label] = {'changed_px': count, 'total_px': area, 'changed_fraction': count / area,
                      'size_mismatch': mismatch}
    expected = sum(v['changed_px'] for v in out.values()) >= minimum or any(v['size_mismatch'] for v in out.values())
    _require(receipt['changed'] == expected, 'raw changed boolean contradicts observations')
    return out


def decide(receipt, min_fraction):
    """Pure hypothetical policy; malformed evidence always requires review, never defaults to a resolution.

    Keep the recorded aggregate raw pixel gate. If it fired, require *any one view*
    to exceed the proposed fraction, so extra unchanged views cannot dilute it.
    Dimension mismatches always require review, even with a fraction of 1.
    """
    _require(type(min_fraction) in (int, float) and math.isfinite(min_fraction) and 0 <= min_fraction <= 1,
             'fraction must be finite and between 0 and 1')
    raw = receipt.get('changed') if isinstance(receipt, dict) and type(receipt.get('changed')) is bool else None
    result = {'schema': SCHEMA, 'experimental': True, 'min_fraction': min_fraction, 'raw_changed': raw}
    try:
        views = _observe(receipt)
    except ValueError as exc:
        return dict(result, status='incomplete', requires_review=True, error=str(exc), views={})
    triggering = [label for label, v in views.items()
                  if v['size_mismatch'] or (raw and v['changed_fraction'] > min_fraction)]
    status = 'changed' if triggering else 'below_floor' if raw else 'raw_gate_quiet'
    return dict(result, status=status, requires_review=bool(triggering), views=views, triggering_views=triggering)


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out: raise ValueError(f'duplicate JSON key: {key}')
        out[key] = value
    return out


def _no_constant(value):
    raise ValueError(f'non-finite JSON constant: {value}')


def replay(receipt_path, out_path, min_fraction):
    """Read a bounded receipt, record its byte identity and create a new decision file exclusively."""
    with Path(receipt_path).open('rb') as stream: data = stream.read(MAX_RECEIPT_BYTES + 1)
    _require(len(data) <= MAX_RECEIPT_BYTES, 'receipt exceeds 2 MiB')
    receipt = json.loads(data, object_pairs_hook=_unique_object, parse_constant=_no_constant)
    result = dict(decide(receipt, min_fraction), receipt_sha256=hashlib.sha256(data).hexdigest())
    with Path(out_path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    replay_parser = commands.add_parser('replay')
    replay_parser.add_argument('receipt'); replay_parser.add_argument('--fraction', type=float, required=True)
    replay_parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        result = replay(args.receipt, args.out, args.fraction)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr); return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result['status'] == 'incomplete' else 1 if result['requires_review'] else 0


if __name__ == '__main__': raise SystemExit(main())
