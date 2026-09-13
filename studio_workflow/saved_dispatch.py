"""Hash-bound execution of a retained run. The original ticket stays server-side.

This is an adapter to execution.run_ticket, not a second dispatch journal or
executor. Reading a review packet never creates or replays a preparation.
"""
from __future__ import annotations

from pathlib import Path
import re

from .commands import fields, identifier
from .core import canonical, need
from .documents import DocumentError


def source_identity(result):
    record = result['record']; report = record['report']; request = record['request']
    return {'request_id': request['request_id'], 'document_id': request['document_id'],
            'revision': request['expected_revision'], 'preset_id': request['preset_id'],
            'document_sha256': report['document_sha256'], 'record_sha256': result['record_sha256'],
            'ticket_sha256': report['ticket_sha256'], 'job_id': report['job_id']}


def review_saved(records, request_id):
    """Exact JSON text avoids Python/JavaScript numeric representation changes."""
    result = records.get(identifier(request_id))
    record = result['record']; report = record['report']
    return {'source': source_identity(result), 'head_revision': result['head_revision'],
            'source_is_current': result['source_is_current'],
            'record_json': canonical(record).decode('utf-8'),
            'ticket_json': canonical(report['ticket']).decode('utf-8'),
            'controls_json': canonical(report['recipe']['controls']).decode('utf-8'),
            'backend_id': report['ticket']['pins']['backend_id'],
            'prepared_graph_sha256': report['prepared_graph_sha256'],
            'dispatch_attempted': False}


def run_saved(studio, records, request_id, value):
    """Resolve and approve an existing immutable record, then use its exact ticket.

    The caller approves both hashes. A later source revision does not silently
    replace this original attempt. No missing record triggers preparation.
    """
    identifier(request_id)
    need(request_id not in ('.', '..'), 'Invalid preparation identity')
    fields(value, ('approved', 'record_sha256', 'ticket_sha256'))
    need(value['approved'] is True, 'Explicit approval is required')
    for key in ('record_sha256', 'ticket_sha256'):
        need(isinstance(value[key], str) and re.fullmatch(r'[0-9a-f]{64}', value[key]), 'Invalid ' + key)
    with studio.lock:
        result = records.get(request_id)
        source = source_identity(result); record = result['record']
        if source['record_sha256'] != value['record_sha256'] or source['ticket_sha256'] != value['ticket_sha256']:
            raise DocumentError('approval_conflict', 'Approval does not match the retained record and ticket', 409)
        need(records.workspace is studio.assets
             and record['document_store'] == str(Path(studio.assets.database).resolve()),
             'Document workspace changed; inspect the original workspace')
        # The existing service pins runs/experiments and validates the recipe;
        # it fsyncs dispatch intent before creating the one shared-worker job.
        from .execution import run_ticket
        try:
            dispatch = run_ticket(studio, record['report']['ticket'], approved=True)
            need(isinstance(dispatch, dict), 'Invalid retained-ticket dispatch result')
        except Exception as exc:
            # Includes failures before dispatch whose exact phase we cannot know
            # here. Never infer "not submitted" after entering the dispatch seam.
            dispatch = {'status': 'reconciliation_required', 'job_id': source['job_id'],
                        'dispatch_attempted': None, 'error_type': type(exc).__name__,
                        'message': 'Outcome requires inspection. Keep this saved run and its original ticket.'}
    return {'source': source, 'dispatch': dispatch}
