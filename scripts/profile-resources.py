"""Run a finite resource observation without loading Studio or model runtimes."""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Portable Python also exposes ComfyUI's unrelated regular `app` package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from resource_probe import ResourceSampler, write_samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', action='append', type=int, default=[], help='Explicit PID to observe (repeatable, maximum 16); no ownership is inferred')
    parser.add_argument('--include-self', action='store_true', help='Also observe this short-lived sampler process to measure its overhead')
    parser.add_argument('--comfy-url', help='Optional http://127.0.0.1:<port>; reads only /system_stats')
    parser.add_argument('--samples', type=int, default=6, help='1-120 samples, default 6')
    parser.add_argument('--interval', type=float, default=5.0, help='Seconds after each completed sample, 1-60, default 5')
    parser.add_argument('--output', type=Path, help='New JSONL receipt; existing files are never overwritten')
    args = parser.parse_args()
    if not 1 <= args.samples <= 120: parser.error('--samples must be between 1 and 120')
    if not 1 <= args.interval <= 60: parser.error('--interval must be between 1 and 60')
    try: sampler = ResourceSampler(args.pid + ([os.getpid()] if args.include_self else []), args.comfy_url)
    except ValueError as error: parser.error(str(error))
    output = args.output or Path('.runtime') / ('resource-profile-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid4().hex[:8] + '.jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open('x', encoding='utf-8') as stream:
            write_samples(stream, sampler, args.samples, args.interval)
    except FileExistsError: parser.error('Output already exists; choose a new receipt path')
    except KeyboardInterrupt:
        print('Stopped; completed observations preserved in ' + str(output.resolve()))
        return 130
    print('Saved ' + str(args.samples) + ' read-only observations to ' + str(output.resolve()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
