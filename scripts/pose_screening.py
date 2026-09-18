#!/usr/bin/env python3
"""Validate or compile the bounded corrected-pose screen; never run a model."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio_workflow.pose_artifact import MAX_BYTES, loads
from studio_workflow.pose_screening import compile_plan, validate_plan


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def read(path):
    with Path(path).open('rb') as source:
        data = source.read(MAX_BYTES + 1)
    return loads(data)


def receipt(plan):
    return {
        'campaign_id': plan['campaign_id'],
        'plan_id': plan['plan_id'],
        'manifest_sha256': plan['manifest_sha256'],
        'candidate_count': plan['candidate_count'],
        'candidate_cap': plan['candidate_cap'],
        'additional_image_attempt_cap': plan['additional_image_attempt_cap'],
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
    }


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest='command', required=True)
        validate = commands.add_parser('validate', help='validate and summarize a manifest')
        validate.add_argument('manifest', type=Path)
        plan = commands.add_parser('plan', help='compile a new immutable plan file')
        plan.add_argument('manifest', type=Path)
        plan.add_argument('--out', type=Path, required=True)
        verify = commands.add_parser('validate-plan', help='verify a saved plan against its manifest')
        verify.add_argument('manifest', type=Path)
        verify.add_argument('plan', type=Path)
        args = parser.parse_args(argv)
        source = read(args.manifest)
        if args.command == 'validate':
            result = compile_plan(source)
        elif args.command == 'plan':
            result = compile_plan(source)
            with args.out.open('x', encoding='utf-8', newline='\n') as output:
                json.dump(result, output, sort_keys=True, indent=2, allow_nan=False)
                output.write('\n')
        else:
            result = validate_plan(read(args.plan), source)
        print(json.dumps(receipt(result), sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            'error': str(exc),
            'authority': 'none',
            'execution_authorized': False,
            'generation_submitted': False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
