#!/usr/bin/env python3
"""Compare explicitly paired, pinned job-resource observations without running jobs."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
from resource_comparison import EvidenceError, SCHEMA, compare_observations, encode_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, help='Create a new report; default is stdout')
    args = parser.parse_args(argv)
    try: report = compare_observations(args.manifest)
    except EvidenceError as error:
        state = ('report_unavailable' if error.code == 'report_too_large'
                 else 'incomplete' if error.incomplete else 'invalid_plan')
        print(json.dumps({'schema': SCHEMA, 'reason': error.code, 'state': state,
                          'qualified_benchmark': False, 'execution_authority': False},
                         ensure_ascii=True, allow_nan=False, separators=(',', ':')))
        return 2
    try:
        data = encode_report(report).decode('ascii')
        if args.output is None: sys.stdout.write(data)
        else:
            with args.output.open('x', encoding='utf-8', newline='\n') as stream: stream.write(data)
        return 0 if report['evidence_complete'] and not report['counts']['withheld_pairs'] else 2
    except (OSError, ValueError):
        print('Comparison output unavailable; existing files were not overwritten.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
