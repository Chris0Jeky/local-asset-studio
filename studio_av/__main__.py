"""Offline AV tools plus a small explicit client for a running local Studio."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from .client import StudioClient, StudioClientError


def payload(path):
    try:
        raw=Path(path).read_bytes()
        if len(raw)>1024*1024:raise StudioClientError('Payload file is too large')
        value=json.loads(raw.decode('utf-8'))
    except (OSError,UnicodeDecodeError,json.JSONDecodeError) as exc:raise StudioClientError('Payload file must contain UTF-8 JSON') from exc
    if not isinstance(value,dict):raise StudioClientError('Payload file must contain a JSON object')
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='tool',required=True)
    studio=commands.add_parser('studio',help='Call the running loopback Scene editor API')
    studio.add_argument('--url',default='http://127.0.0.1:8191',help='loopback Studio origin')
    action=studio.add_subparsers(dest='action',required=True)
    action.add_parser('list',help='list persisted scenes')
    inspect=action.add_parser('inspect',help='inspect one scene');inspect.add_argument('id')
    action.add_parser('workspace',help='list registered Workspace source assets')
    create=action.add_parser('create',help='create from a JSON request file');create.add_argument('payload_json')
    command=action.add_parser('command',help='send one scene command from a JSON request file');command.add_argument('id');command.add_argument('payload_json')
    args=parser.parse_args(argv)
    try:
        client=StudioClient(args.url)
        if args.action=='list':result=client.list()
        elif args.action=='inspect':result=client.inspect(args.id)
        elif args.action=='workspace':result=client.workspace()
        elif args.action=='create':result=client.create(payload(args.payload_json),'cli')
        else:result=client.command(args.id,payload(args.payload_json),'cli')
    except StudioClientError as exc:parser.error(str(exc))
    print(json.dumps(result,indent=2,sort_keys=True));return 0


if __name__=='__main__':main()
