#!/usr/bin/env python3
"""Read one saved, bounded inference trace; stdout only, no runtime contact."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'app'))
from inference_trace import MAX_BYTES, TraceError, summarize_trace
from resource_receipts import EvidenceError, read_evidence_file


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--sha256', help='Expected hash of the exact saved trace bytes')
    args = parser.parse_args()
    try:
        raw = read_evidence_file(args.trace, MAX_BYTES)
        result = summarize_trace(raw, expected_sha256=args.sha256)
    except (TraceError, EvidenceError) as exc:
        result = {'schema': 'studio.inference-trace-error/v1', 'code': exc.code,
                  'incomplete': bool(getattr(exc, 'incomplete', False))}
        print(json.dumps(result, sort_keys=True)); return 2
    print(json.dumps(result, sort_keys=True, indent=2)); return 0


if __name__ == '__main__': raise SystemExit(main())
