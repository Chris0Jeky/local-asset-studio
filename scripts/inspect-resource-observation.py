#!/usr/bin/env python3
"""Verify one saved job-resource observation without contacting Studio or ComfyUI."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
from resource_receipts import EvidenceError, SCHEMA, inspect_observation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--expected-result-sha256')
    parser.add_argument('--expected-job-id')
    parser.add_argument('--output', type=Path, help='Create a new JSON report; default is stdout')
    args = parser.parse_args(argv)
    try:
        report = inspect_observation(args.directory, expected_result_sha256=args.expected_result_sha256,
                                     expected_job_id=args.expected_job_id)
    except EvidenceError as error:
        print(json.dumps({'schema': SCHEMA, 'integrity': 'incomplete' if error.incomplete else 'invalid',
                          'reason': error.code, 'qualified_benchmark': False, 'execution_authority': False}))
        return 2
    try:
        data = json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + '\n'
        if args.output is None: sys.stdout.write(data)
        else:
            with args.output.open('x', encoding='utf-8', newline='\n') as stream: stream.write(data)
        return 0
    except (OSError, ValueError):
        print('Inspection output unavailable; existing files were not overwritten.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
