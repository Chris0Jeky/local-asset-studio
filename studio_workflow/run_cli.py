"""Saved run CLI: preparation, review, recovery and explicitly approved dispatch."""
from __future__ import annotations
from http.client import HTTPException
import json
import os
from pathlib import Path

from .client import ClientError
from .core import canonical, need
from .sdk import WorkflowClient


def add_parser(sub):
    p = sub.add_parser('runs', help='Prepare and recover tickets linked to saved workflow revisions')
    actions = p.add_subparsers(dest='run_action', required=True)
    prepare = actions.add_parser('prepare')
    prepare.add_argument('document_id')
    prepare.add_argument('--expected-revision', type=int, required=True)
    prepare.add_argument('--preset', required=True)
    prepare.add_argument('--request-id', required=True, help='Retain this preparation identity with the exact arguments')
    prepare.add_argument('--ticket-out', type=Path)
    get = actions.add_parser('get'); get.add_argument('request_id'); get.add_argument('--ticket-out', type=Path)
    jobs = actions.add_parser('by-job'); jobs.add_argument('job_id'); jobs.add_argument('--ticket-out', type=Path)
    observe = actions.add_parser('observe'); observe.add_argument('request_id')
    review = actions.add_parser('review'); review.add_argument('request_id')
    run = actions.add_parser('run'); run.add_argument('request_id')
    run.add_argument('--record-sha256', required=True); run.add_argument('--ticket-sha256', required=True)
    run.add_argument('--approve', action='store_true')
    listing = actions.add_parser('list'); listing.add_argument('document_id')
    listing.add_argument('--before', type=int); listing.add_argument('--limit', type=int, default=25)


def execute(args):
    action = args.run_action
    context = {k: getattr(args, k) for k in ('request_id', 'document_id', 'expected_revision', 'job_id', 'preset', 'record_sha256', 'ticket_sha256') if hasattr(args, k)}
    result = None
    try:
        target = getattr(args, 'ticket_out', None)
        if target:
            # Also reject broken symlinks. Recheck atomically with 'x' on write.
            need(not os.path.lexists(target), 'Ticket output already exists; nothing was requested')
            need(target.parent.is_dir(), 'Ticket output directory is missing; nothing was requested')
        runs = WorkflowClient(args.url, args.http_timeout).saved_runs
        if action == 'prepare':
            result = runs.prepare(args.document_id, expected_revision=args.expected_revision,
                                  preset_id=args.preset, request_id=args.request_id)
        elif action == 'get': result = runs.get(args.request_id)
        elif action == 'by-job': result = runs.by_job(args.job_id)
        elif action == 'observe': result = runs.observe(args.request_id)
        elif action == 'review': result = runs.review(args.request_id)
        elif action == 'run':
            result = runs.run(args.request_id, record_sha256=args.record_sha256,
                              ticket_sha256=args.ticket_sha256, approved=args.approve)
        else: result = runs.list(args.document_id, before=args.before, limit=args.limit)
        if target:
            # The SDK already verified the report and ticket hashes. Export keeps
            # wide integers exact and preserves the normal run-ticket wire format.
            raw = canonical(result['record']['report']['ticket']) + b'\n'
            with target.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        if action == 'run':
            dispatch = result['dispatch']; status = dispatch.get('status') or (dispatch.get('job') or {}).get('status')
            if status in ('uncertain', 'reconciliation_required'): return 3
            if status in ('failed', 'partial', 'cancelled'): return 5
        if action == 'observe':
            observation = result['observation']
            if observation['state'] != 'observed': return 3
            status = observation['job']['status']
            if status in ('uncertain', 'reconciliation_required'): return 3
            if status in ('failed', 'partial', 'cancelled'): return 5
        return 0
    except (ValueError, OSError, HTTPException, KeyError, TypeError, UnicodeError, RecursionError) as exc:
        error = {'error': str(exc), 'command': 'runs', 'operation': action, 'context': context,
                 'dispatch_attempted': None if action == 'run' else False,
                 'recovery': 'Inspect runs get with the original preparation request ID. Never invent a replacement to recover uncertain work.'}
        if isinstance(exc, ClientError): error.update(http_status=exc.status, code=exc.code, details=exc.result)
        if result is not None:
            error['result'] = result
            error['recovery'] = 'The response was received but local export failed. Inspect the retained original record; do not prepare a replacement.'
        print(json.dumps(error, ensure_ascii=False, allow_nan=False))
        return 6 if isinstance(exc, ClientError) and exc.status == 409 else 3 if action == 'run' else 2
