#!/usr/bin/env python3
"""Inspect, explicitly update, or reconcile a private narration profile registry."""
import argparse
import json
from pathlib import Path

import voice_profile as vp
import voice_profile_registry as registry
from strict_json import StrictJsonError, load_bounded_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True, type=Path)
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('inspect', help='Read current profiles, registry digest and durable receipts')
    update = commands.add_parser('update', help='Apply one explicit JSON command with expected identities')
    update.add_argument('--command', required=True, type=Path)
    update.add_argument('--lock-timeout', default=5.0, type=float)
    receipt = commands.add_parser('receipt', help='Read the durable receipt for an original request ID')
    receipt.add_argument('request_id')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'inspect': result = registry.inspect_registry(args.registry)
        elif args.operation == 'receipt': result = registry.get_receipt(args.registry, args.request_id)
        else:
            command = load_bounded_json(args.command, label='registry command', maximum_bytes=vp.MAX_PROFILE_JSON_BYTES)
            result = registry.update_registry(args.registry, command, lock_timeout=args.lock_timeout)
    except (vp.VoiceProfileError, StrictJsonError) as exc:
        unconfirmed = isinstance(exc, registry.RegistryUnconfirmed)
        print(json.dumps({'status': 'unconfirmed' if unconfirmed else 'refused', 'error': str(exc)}))
        return 3 if unconfirmed else 2
    print(json.dumps({'status': 'ok', 'result': result}, ensure_ascii=True))
    return 0


if __name__ == '__main__': raise SystemExit(main())
