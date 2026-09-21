#!/usr/bin/env python3
"""Erase explicit rectangles from an existing depth PNG; no Studio connection."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio_workflow.depth_erasure import MAX_IMAGE_BYTES, erase_png
from studio_workflow.pose_artifact import MAX_BYTES, loads


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def read(path, limit):
    with Path(path).open('rb') as source:
        return source.read(limit + 1)


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('source', type=Path)
        parser.add_argument('--expected-sha256', required=True)
        parser.add_argument('--rectangles', type=Path, required=True)
        parser.add_argument('--out', type=Path, required=True)
        args = parser.parse_args(argv)
        output, receipt = erase_png(read(args.source, MAX_IMAGE_BYTES), args.expected_sha256,
                                    loads(read(args.rectangles, MAX_BYTES)))
        with args.out.open('xb') as dest:
            dest.write(output)
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps(dict(error=str(exc), authority='none', generation_submitted=False)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
