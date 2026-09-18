#!/usr/bin/env python3
"""Compile or validate one zero-authority pose-source/native-route binding."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow.pose_artifact import MAX_BYTES as MAX_JSON_BYTES, loads
from studio_workflow.pose_route_binding import MAX_SOURCE_BYTES, compile_binding, validate_binding


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def read_json(path: Path):
    with path.open('rb') as source:
        data = source.read(MAX_JSON_BYTES + 1)
    return loads(data)


def read_source(path: Path) -> bytes:
    with path.open('rb') as source:
        data = source.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError('source image exceeds 20 MiB')
    return data


def receipt(binding):
    return {
        'binding_id': binding['binding_id'],
        'binding_name': binding['binding_name'],
        'route_id': binding['route']['id'],
        'source_sha256': binding['source']['sha256'],
        'request_sha256': binding['request_sha256'],
        'ready_for_execution': False,
        'execution_authorized': False,
        'generation_submitted': False,
    }


def build_parser():
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    compile_cmd = commands.add_parser('compile', help='compile one immutable binding file')
    compile_cmd.add_argument('request', type=Path)
    compile_cmd.add_argument('--source', type=Path, required=True)
    compile_cmd.add_argument('--artifact', type=Path)
    compile_cmd.add_argument('--out', type=Path, required=True)
    validate_cmd = commands.add_parser('validate-binding', help='recompute and validate a saved binding')
    validate_cmd.add_argument('request', type=Path)
    validate_cmd.add_argument('binding', type=Path)
    validate_cmd.add_argument('--source', type=Path, required=True)
    validate_cmd.add_argument('--artifact', type=Path)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        request = read_json(args.request)
        source = read_source(args.source)
        artifact = read_json(args.artifact) if args.artifact else None
        if args.command == 'compile':
            result = compile_binding(request, source, artifact=artifact)
            with args.out.open('x', encoding='utf-8', newline='\n') as output:
                json.dump(result, output, sort_keys=True, indent=2, allow_nan=False)
                output.write('\n')
        else:
            result = validate_binding(read_json(args.binding), request, source, artifact=artifact)
        print(json.dumps(receipt(result), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({
            'error': str(exc),
            'ready_for_execution': False,
            'execution_authorized': False,
            'generation_submitted': False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
