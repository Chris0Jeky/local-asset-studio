"""Headless client. Start the ordinary Studio server; no browser or second worker."""
from __future__ import annotations
import argparse
from http.client import HTTPException
import json
import math
from pathlib import Path
import sys
import time
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from .core import decode, canonical, need
from .client import Client, ClientError, NoRedirect
from . import document_cli

PREFIX = '/api/workflow-studio'


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://127.0.0.1:8191')
    p.add_argument('--http-timeout', type=float, default=30)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('capabilities', 'guides', 'nodes', 'catalog'):
        sub.add_parser(name)
    document_cli.add_parser(sub)
    for name, field in (('prepare', 'recipe'), ('run', 'ticket'), ('compile', 'document'), ('import', 'graph')):
        q = sub.add_parser(name)
        q.add_argument('--' + field, required=True, type=Path)
        q.add_argument('--out', type=Path)
        if name == 'run': q.add_argument('--approve', action='store_true')
    for name in ('status', 'wait'):
        q = sub.add_parser(name)
        q.add_argument('job_id')
        if name == 'wait':
            q.add_argument('--seconds', type=float, default=600)
            q.add_argument('--interval', type=float, default=3)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    command = args.command
    try:
        client = Client(args.url, args.http_timeout)
        if command == 'documents':
            result = document_cli.execute(args)
        elif command in ('capabilities', 'guides', 'nodes', 'catalog'):
            result = client.request('/api/catalog' if command == 'catalog' else PREFIX + '/' + command)
        elif command in ('prepare', 'run', 'compile', 'import'):
            key = {'prepare': 'recipe', 'run': 'ticket', 'compile': 'document', 'import': 'graph'}[command]
            value = decode(getattr(args, key).read_bytes())
            body = {key: value}
            if command == 'run':
                need(args.approve, 'run requires --approve; preparation never approves execution')
                body['approved'] = True
            result = client.request(PREFIX + '/' + command, body)
        else:
            path = '/api/jobs/' + quote(args.job_id, safe='')
            if command == 'wait':
                need(math.isfinite(args.seconds) and 0 < args.seconds <= 86400, 'Wait budget must be 0–86400 seconds')
                need(math.isfinite(args.interval) and 0.1 <= args.interval <= 60, 'Polling interval must be 0.1–60 seconds')
                deadline = time.monotonic() + args.seconds
            while True:
                result = client.request(path)
                if command == 'status' or result.get('status') not in ('queued', 'waiting', 'submitting', 'running'):
                    break
                if time.monotonic() >= deadline:
                    result = {'status': 'observation_timeout', 'job': result, 'message': 'Observation stopped; the job was not cancelled.'}
                    break
                time.sleep(min(args.interval, max(0, deadline - time.monotonic())))
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if getattr(args, 'out', None):
            # Refuse overwrite: tickets are durable request identities, not scratch files.
            with args.out.open('x', encoding='utf-8') as stream: stream.write(encoded)
        print(encoded, end='')
        if result.get('valid') is False: return 2
        state = result.get('status') or result.get('job', {}).get('status')
        if state in ('uncertain', 'reconciliation_required'): return 3
        if state == 'observation_timeout': return 4
        if state in ('failed', 'partial', 'cancelled'): return 5
        return 0
    except (ValueError, OSError, HTTPError, URLError, TimeoutError, HTTPException, UnicodeError) as exc:
        result = {'error': str(exc), 'command': command}
        if isinstance(exc, ClientError): result.update(exc.result, http_status=exc.status, code=exc.code)
        if command == 'run': result['recovery'] = 'Outcome may be unknown. Retain the same ticket and inspect it; never prepare a replacement ticket to retry.'
        elif command == 'documents': result['recovery'] = 'Retain the same request ID and content. Inspect the current revision; do not silently rebase a conflicting edit.'
        print(json.dumps(result, ensure_ascii=False))
        if isinstance(exc, ClientError) and exc.status == 409: return 6
        return 3 if command == 'run' else 2


if __name__ == '__main__':
    sys.exit(main())
