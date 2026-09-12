"""Headless client. Start the ordinary Studio server; no browser or second worker."""
from __future__ import annotations
import argparse
from http.client import HTTPException
import json
import math
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError
from .core import decode, canonical, need

PREFIX = '/api/workflow-studio'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused; use the actual loopback Studio address')


class Client:
    def __init__(self, base='http://127.0.0.1:8191', timeout=30):
        parsed = urlsplit(base)
        need(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', '::1')
             and not parsed.username and not parsed.password and parsed.path in ('', '/')
             and not parsed.query and not parsed.fragment, 'Use a literal loopback HTTP Studio origin')
        need(math.isfinite(timeout) and 0 < timeout <= 120, 'HTTP timeout must be 0–120 seconds')
        self.base, self.timeout = base.rstrip('/'), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, body=None):
        need(path.startswith('/api/') and not path.startswith('//'), 'Studio API path required')
        raw = canonical(body) if body is not None else None
        request = Request(self.base + path, data=raw,
                          headers={'Origin': self.base, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        with self.opener.open(request, timeout=self.timeout) as response:
            data = response.read(16 * 1024 * 1024 + 1)
            need(len(data) <= 16 * 1024 * 1024, 'Response exceeds 16 MiB')
            result = json.loads(data)
            need(isinstance(result, dict), "Studio returned a non-object response")
            return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://127.0.0.1:8191')
    p.add_argument('--http-timeout', type=float, default=30)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('capabilities', 'guides', 'nodes', 'catalog'):
        sub.add_parser(name)
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
        if command in ('capabilities', 'guides', 'nodes', 'catalog'):
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
        if command == 'run': result['recovery'] = 'Outcome may be unknown. Retain the same ticket and inspect it; never prepare a replacement ticket to retry.'
        print(json.dumps(result, ensure_ascii=False))
        return 3 if command == 'run' else 2


if __name__ == '__main__':
    sys.exit(main())
