#!/usr/bin/env python3
"""Summarise one existing resource-profile receipt; never contact a runtime."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from performance_history import summarize_resource_profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('input', type=Path, help='Existing finite profiler JSONL receipt')
    parser.add_argument('--output', type=Path, help='New JSON summary file; default is stdout')
    args = parser.parse_args(argv)
    try:
        # NONBLOCK prevents a nominated FIFO from hanging before fstat can refuse it.
        flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
        descriptor = os.open(args.input, flags)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError('Input must be a regular file')
            stream = os.fdopen(descriptor, 'rb')
            descriptor = None
            with stream:
                result = summarize_resource_profile(stream)
        finally:
            if descriptor is not None:
                os.close(descriptor)
        rendered = json.dumps(result, indent=2, allow_nan=False) + '\n'
        # Parsing finishes before output creation. Exclusive creation also protects
        # the source when input/output designate the same file or an existing link.
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            with args.output.open('x', encoding='utf-8', newline='\n') as output:
                output.write(rendered)
        return 0
    except (OSError, ValueError):
        print('Resource summary failed: invalid receipt or unavailable file; existing files were not overwritten.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
