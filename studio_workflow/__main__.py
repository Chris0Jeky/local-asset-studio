"""Headless client. Start the ordinary Studio server; no browser or second worker."""
from __future__ import annotations
import argparse
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from .core import decode, canonical, need
from .client import Client, ClientError, NoRedirect
from . import document_cli, run_cli

PREFIX = '/api/workflow-studio'


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://127.0.0.1:8191')
    p.add_argument('--http-timeout', type=float, default=30)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('capabilities', 'guides', 'nodes', 'catalog'):
        sub.add_parser(name)
    document_cli.add_parser(sub)
    run_cli.add_parser(sub)
    for name, field in (('prepare', 'recipe'), ('run', 'ticket'), ('compile', 'document'), ('import', 'graph')):
        q = sub.add_parser(name)
        q.add_argument('--' + field, required=True, type=Path)
        q.add_argument('--out', type=Path)
        if name == 'run': q.add_argument('--approve', action='store_true')
    q = sub.add_parser('prepare-document', help='Project supported builder edits into a registered recipe ticket')
    q.add_argument('--document', required=True, type=Path)
    q.add_argument('--preset', required=True)
    q.add_argument('--out', type=Path, help='Write only the run ticket; stdout contains the full source report')
    for name in ('status', 'wait'):
        q = sub.add_parser(name)
        q.add_argument('job_id')
        if name == 'wait':
            q.add_argument('--seconds', type=float, default=600)
            q.add_argument('--interval', type=float, default=3)
    return p


def _emit_ascii_diagnostic(value):
    try: text = json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n'
    except (TypeError, ValueError): text = '{"status":"diagnostic_encoding_error","code":"diagnostic_encoding_error"}\n'
    try: sys.stdout.write(text)
    except (OSError, UnicodeError, ValueError): pass


def _received_encoding_diagnostic(command, received, exc):
    return {'status': 'received_response_encoding_error', 'code': 'received_result_nonfinite', 'command': command,
            'error': str(exc), 'response_received': True,
            'received_result': {'encoding': 'json-with-nonfinite-tokens',
                                'text': json.dumps(received, ensure_ascii=False, indent=2, allow_nan=True)},
            'recovery': 'The Studio response was received once but contains non-finite values. Preserve received_result.text and the original request or ticket ID; do not repeat the operation. No output file was created.'}


def _wait_for_job(client, path, seconds, interval):
    """Bound polling starts and each socket wait; this never cancels remote work."""
    deadline = time.monotonic() + seconds
    original_timeout, last = client.timeout, None
    def expired():
        return {'status': 'observation_timeout', 'job': last,
                'message': 'Observation stopped; the job was not cancelled.'}
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: return expired()
            client.timeout = min(original_timeout, remaining)
            try:
                last = client.request(path)
            except (TimeoutError, URLError) as exc:
                timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, 'reason', None), TimeoutError)
                if timed_out and time.monotonic() >= deadline: return expired()
                raise
            if last.get('status') not in ('queued', 'waiting', 'submitting', 'running'):
                return last
            remaining = deadline - time.monotonic()
            if remaining <= 0: return expired()
            time.sleep(min(interval, remaining))
    finally:
        client.timeout = original_timeout


def main(argv=None):
    args = parser().parse_args(argv)
    command = args.command
    if command == 'runs': return run_cli.execute(args)
    result = None
    output_preflight = exporting = False
    try:
        target = getattr(args, 'out', None)
        if target:
            output_preflight = True
            need(not os.path.lexists(target), 'Output already exists; nothing was requested')
            need(target.parent.is_dir(), 'Output directory is missing; nothing was requested')
            output_preflight = False
        client = Client(args.url, args.http_timeout)
        if command == 'documents':
            result = document_cli.execute(args)
        elif command in ('capabilities', 'guides', 'nodes', 'catalog'):
            result = client.request('/api/catalog' if command == 'catalog' else PREFIX + '/' + command)
        elif command == 'prepare-document':
            result = client.request(PREFIX + '/prepare-document',
                                    {'document': decode(args.document.read_bytes()), 'preset_id': args.preset})
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
                result = _wait_for_job(client, path, args.seconds, args.interval)
            else:
                result = client.request(path)
        try: encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        except ValueError as exc:
            _emit_ascii_diagnostic(_received_encoding_diagnostic(command, result, exc))
            return 2
        if target:
            exporting = True
            # Refuse overwrite: tickets are durable request identities, not scratch files.
            with args.out.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(result['ticket'], ensure_ascii=False, indent=2, allow_nan=False) + '\n'
                             if command == 'prepare-document' else encoded)
        print(encoded, end='')
        if result.get('valid') is False: return 2
        state = result.get('status') or result.get('job', {}).get('status')
        if state in ('uncertain', 'reconciliation_required'): return 3
        if state == 'observation_timeout': return 4
        if state in ('failed', 'partial', 'cancelled'): return 5
        return 0
    except (ValueError, OSError, HTTPError, URLError, TimeoutError, HTTPException, UnicodeError) as exc:
        received = result
        result = {'error': str(exc), 'command': command}
        if isinstance(exc, ClientError): result.update(exc.result, http_status=exc.status, code=exc.code)
        if output_preflight:
            result.update(code='output_unavailable', request_sent=False, recovery='Choose a new output path in an existing directory. No request was sent.')
        elif exporting:
            result.update(code='local_output_error', response_received=True, result=received,
                          recovery='The Studio response was received but local export failed. Retain the returned result and original ticket or request ID; do not create replacement work. The output path was not overwritten and may contain an incomplete file.')
        elif received is not None:
            result.update(status='received_response_output_error', code='stdout_unavailable', response_received=True, result=received,
                          recovery='The Studio response was received but local stdout failed. Retain the returned result and original ticket or request ID; do not repeat the operation.')
        elif command == 'run': result['recovery'] = 'Outcome may be unknown. Retain the same ticket and inspect it; never prepare a replacement ticket to retry.'
        elif command == 'documents': result['recovery'] = 'Retain the same request ID and content. Inspect the current revision; do not silently rebase a conflicting edit.'
        _emit_ascii_diagnostic(result)
        if output_preflight or exporting: return 2
        if isinstance(exc, ClientError) and exc.status == 409: return 6
        return 3 if command == 'run' else 2


if __name__ == '__main__':
    sys.exit(main())
