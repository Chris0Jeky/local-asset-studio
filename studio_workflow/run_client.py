"""Client-only saved-run operations. No database, model call or execution method."""
from __future__ import annotations
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlencode

from .client import ClientError
from .commands import identifier
from .core import MAX_BYTES, canonical, decode, digest, need

PREFIX = '/api/workflow-studio/document-runs'


def key(value):
    identifier(value)
    need(value not in ('.', '..'), 'Invalid saved-run identifier')
    return value


def bounded(value, maximum, label):
    need(type(value) is int and 1 <= value <= maximum, 'Invalid ' + label)
    return value


def record_result(result, expected=None, job_id=None):
    """Validate a recovered report before exposing/exporting its ticket.

    Hashes catch damaged responses, not an attacker rewriting the entire local
    database. The server still validates the ticket again at explicit execution.
    """
    try:
        record = result['record']
        record = decode(canonical(record))
        need(record['format'] == 'studio.document-run/v1' and digest(record) == result['record_sha256'],
             'Saved-run record integrity mismatch')
        value, report = record['request'], record['report']
        need(isinstance(value, dict) and isinstance(report, dict), 'Malformed saved-run report')
        for field, wanted in (expected or {}).items():
            need(type(value.get(field)) is type(wanted) and value[field] == wanted, 'Saved-run response belongs to another ' + field)
        ticket = report['ticket']
        need(ticket['format'] == 'studio.run-ticket/v1' and digest(ticket) == report['ticket_sha256'],
             'Saved-run ticket integrity mismatch')
        need(canonical(ticket['recipe']) == canonical(report['recipe'])
             and report['recipe']['preset_id'] == value['preset_id']
             and report['prepared_graph_sha256'] == ticket['pins']['graph_sha256'], 'Saved-run projection mismatch')
        if job_id is not None: need(report['job_id'] == job_id, 'Saved-run response belongs to another job')
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError('Studio returned an invalid saved-run record') from exc
    return result


class SavedRuns:
    """Namespace shared by SDK, CLI and MCP; transport is the ordinary Client."""
    def __init__(self, request): self.request = request

    def _call(self, path, body=None):
        try:
            result = self.request(path, body)
        except HTTPError as exc:
            status = exc.code
            try:
                with exc: raw = exc.read(MAX_BYTES + 1)
                data = decode(raw)
            except (ValueError, OSError, HTTPException): data = {}
            if not isinstance(data, dict): data = {}
            raise ClientError(status, data) from exc
        need(isinstance(result, dict), 'Studio returned a non-object saved-run result')
        need(len(canonical(result)) <= 2 * MAX_BYTES, 'Saved-run response exceeds 2 MiB')
        return result

    def prepare(self, document_id: str, *, expected_revision: int, preset_id: str, request_id: str) -> dict:
        value = {'document_id': key(document_id), 'expected_revision': bounded(expected_revision, 1024, 'revision'),
                 'preset_id': key(preset_id), 'request_id': key(request_id)}
        return record_result(self._call(PREFIX, value), value)

    def get(self, request_id: str) -> dict:
        return record_result(self._call(PREFIX + '/' + key(request_id)), {'request_id': request_id})

    def by_job(self, job_id: str) -> dict:
        return record_result(self._call(PREFIX + '/by-job/' + key(job_id)), job_id=job_id)

    def list(self, document_id: str, *, before: int | None = None, limit: int = 25) -> dict:
        query = {'document_id': key(document_id), 'limit': bounded(limit, 100, 'page limit')}
        if before is not None: query['before'] = bounded(before, 2**53 - 1, 'page cursor')
        result = self._call(PREFIX + '?' + urlencode(query))
        need(result.get('document_id') == document_id and isinstance(result.get('runs'), list), 'Invalid saved-run page')
        rows = result['runs']; need(len(rows) <= limit, 'Saved-run page exceeds requested limit')
        previous = before or 2**53
        for row in rows:
            need(isinstance(row, dict) and row.get('document_id') == document_id, 'Run page contains another document')
            sequence = bounded(row.get('sequence'), 2**53 - 1, 'returned sequence')
            need(sequence < previous, 'Run page is not descending'); previous = sequence
        cursor = result.get('next_before')
        need(cursor is None or bool(rows) and type(cursor) is int and cursor == rows[-1]['sequence'], 'Invalid next run cursor')
        return result

    def observe(self, request_id: str) -> dict:
        result = self._call(PREFIX + '/' + key(request_id) + '/observe')
        need(result.get('request_id') == request_id and isinstance(result.get('observation'), dict), 'Invalid run observation')
        observation = result['observation']
        need(observation.get('state') in ('observed', 'not_observed', 'workspace_changed', 'evidence_mismatch'), 'Unknown observation state')
        if observation['state'] == 'observed':
            job = observation.get('job')
            need(isinstance(job, dict) and isinstance(job.get('id'), str) and job['id'] == observation.get('job_id')
                 and isinstance(job.get('status'), str), 'Invalid observed job')
        return result
