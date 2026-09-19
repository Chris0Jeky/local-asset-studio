#!/usr/bin/env python3
"""Turn one Markdown handoff into durable LAS voice batches and one PCM WAV."""
from __future__ import annotations

import argparse
import json
import sys

from spoken_brief_compile import *
from spoken_brief_transport import *
from spoken_brief_runtime import *


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description='Compile a Markdown handoff and render one LAS narration WAV.')
    commands = result.add_subparsers(dest='command', required=True)
    for name in ('plan', 'run'):
        command = commands.add_parser(name)
        command.add_argument('pack', help='Pack directory, COMPRESSED.md, or INDEX.md')
        command.add_argument('--profile-id', default=DEFAULT_PROFILE_ID)
        command.add_argument('--delivery-id', default=DEFAULT_DELIVERY_ID)
        command.add_argument('--profile-registry')
        command.add_argument(
            '--speaker-id',
            default=None,
            help='Optional metadata-only speaker ID override; this does not design or clone a voice.',
        )
        if name == 'run':
            command.add_argument('--base-url', default='http://127.0.0.1:8191')
            command.add_argument('--poll-seconds', type=float, default=1.0)
            command.add_argument('--deadline-minutes', type=float, default=60.0)
    return result


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        common = {
            'profile_id': arguments.profile_id,
            'delivery_id': arguments.delivery_id,
            'profile_registry': arguments.profile_registry,
            'speaker_id': arguments.speaker_id,
        }
        if arguments.command == 'plan':
            value = plan(arguments.pack, **common)
        else:
            value = run(
                arguments.pack,
                base_url=arguments.base_url,
                poll_seconds=arguments.poll_seconds,
                deadline_seconds=arguments.deadline_minutes * 60,
                **common,
            )
        print(json.dumps(value, indent=2, ensure_ascii=False)); return 0
    except (SpokenBriefError, OSError) as exc:
        print('spoken brief: ' + str(exc), file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
