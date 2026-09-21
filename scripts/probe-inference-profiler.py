#!/usr/bin/env python3
"""Run one fixed profiler arithmetic probe in a selected Python environment."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from profiler_probe import run_probe


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--python', type=Path, default=Path(sys.executable), help='Trusted Python executable, not a shell command')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu', help='cuda is also the PyTorch HIP interface')
    parser.add_argument('--allow-device-probe', action='store_true', help='Explicitly permit the small device workload')
    parser.add_argument('--timeout', type=float, default=30, help='Worker deadline in seconds, 5–120')
    args = parser.parse_args()
    report = run_probe(args.python, device=args.device, timeout=args.timeout, allow_device=args.allow_device_probe)
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    return 0 if report['status'] in ('cpu_observed', 'device_observed') else 2


if __name__ == '__main__': raise SystemExit(main())
