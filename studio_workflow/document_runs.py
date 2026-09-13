"""Durable saved-revision -> recipe-ticket links; never dispatches a job.

The existing document database owns these records. The existing run-ticket
journal still exclusively owns dispatch. Read/recovery operations do not call
ComfyUI, and an absent local job is not evidence that a ticket was never run.
"""
from __future__ import annotations

from pathlib import Path
import math
import re
import time
import uuid

from .commands import fields, identifier
from .core import MAX_BYTES, canonical, decode, digest, need
from .documents import DocumentError, WorkflowDocuments

VERSION = 'studio.document-run/v1'
MAX_RECORDS = 4096
MAX_STORAGE_BYTES = 128 * 1024 * 1024
MAX_PAGE = 100


def request_value(value):
    fields(value, ('request_id', 'document_id', 'expected_revision', 'preset_id'))
    value = decode(canonical(value))
    for key in ('request_id', 'document_id', 'preset_id'):
        identifier(value[key])
        need(value[key] not in ('.', '..'), 'Invalid ' + key)
    WorkflowDocuments._revision(value['expected_revision'])
    return value


class DocumentRuns:
    """Append-only preparation receipts, sharing AssetWorkspace's transactions."""

    def __init__(self, documents: WorkflowDocuments):
        self.documents, self.workspace = documents, documents.workspace
        with self.workspace.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workflow_document_runs_v1 (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    request_sha256 TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    job_id TEXT NOT NULL UNIQUE,
                    record TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    summary_sha256 TEXT NOT NULL,
                    bytes INTEGER NOT NULL,
                    FOREIGN KEY(document_id,revision)
                        REFERENCES workflow_revisions_v1(document_id,revision));
                CREATE INDEX IF NOT EXISTS workflow_document_runs_source_v1
                    ON workflow_document_runs_v1(document_id,sequence);
            ''')

    def _read(self, db, row):
        if row is None:
            raise DocumentError('not_found', 'Prepared workflow run not found', 404)
        try:
            record = decode(row['record'])
            need(digest(record) == row['record_sha256'], 'Run record hash mismatch')
            need(record['format'] == VERSION, 'Unknown run record format')
            value = request_value(record['request'])
            need(digest(value) == row['request_sha256'] and value['request_id'] == row['request_id']
                 and value['document_id'] == row['document_id']
                 and value['expected_revision'] == row['revision'], 'Run source identity mismatch')
            report = record['report']
            from .execution import NAMESPACE
            ticket = report['ticket']
            need(report['ticket_sha256'] == digest(ticket)
                 and report['job_id'] == row['job_id'] == str(uuid.uuid5(NAMESPACE, ticket['request_id']))
                 and report['recipe'] == ticket['recipe']
                 and report['recipe']['preset_id'] == value['preset_id']
                 and report['prepared_graph_sha256'] == ticket['pins']['graph_sha256'],
                 'Run ticket identity mismatch')
            source = self.documents._read(db, row['document_id'], row['revision'])
            need(report['document_sha256'] == source['document_sha256'], 'Run document hash mismatch')
            need(isinstance(record['document_store'], str), 'Run document store is missing')
            need(self._summary(record) == self._read_summary(row), 'Run summary identity mismatch')
        except DocumentError as exc:
            if exc.status == 503: raise
            raise DocumentError('storage_unavailable', 'Saved run source is unavailable', 503) from exc
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError) as exc:
            raise DocumentError('storage_unavailable', 'Saved run integrity check failed', 503,
                                recovery='Retain the original request and inspect stored evidence.') from exc
        return {'record': record, 'record_sha256': row['record_sha256'], 'sequence': row['sequence'],
                'head_revision': source['head_revision'],
                'source_is_current': source['head_revision'] == row['revision'], 'dispatch_attempted': False}

    @staticmethod
    def _summary(record):
        value, report = record['request'], record['report']
        return {'request_id': value['request_id'], 'document_id': value['document_id'],
                'revision': value['expected_revision'], 'preset_id': value['preset_id'],
                'job_id': report['job_id'], 'created_at': record['created_at'],
                'document_sha256': report['document_sha256'], 'record_sha256': digest(record)}

    @staticmethod
    def _read_summary(row):
        try:
            need(len(row['summary'].encode('utf-8')) <= 2048, 'Run summary exceeds limit')
            value = decode(row['summary'])
            fields(value, ('request_id', 'document_id', 'revision', 'preset_id', 'job_id',
                           'created_at', 'document_sha256', 'record_sha256'))
            need(digest(value) == row['summary_sha256'], 'Run summary hash mismatch')
            for key in ('request_id', 'document_id', 'preset_id', 'job_id'): identifier(value[key])
            WorkflowDocuments._revision(value['revision'])
            for key in ('document_sha256', 'record_sha256'):
                need(isinstance(value[key], str) and re.fullmatch(r'[0-9a-f]{64}', value[key]), 'Invalid run hash')
            need(type(value['created_at']) in (int, float) and math.isfinite(value['created_at']), 'Invalid run time')
            return value
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError, OverflowError) as exc:
            raise DocumentError('storage_unavailable', 'Saved run summary integrity check failed', 503) from exc

    def _find(self, db, key):
        return db.execute('SELECT * FROM workflow_document_runs_v1 WHERE request_id=?', (key,)).fetchone()

    def _replay(self, db, value):
        row = self._find(db, value['request_id'])
        if row is None: return None
        result = self._read(db, row)
        if row['request_sha256'] != digest(value):
            raise DocumentError('request_conflict', 'Preparation request ID belongs to different content', 409)
        return {**result, 'replayed': True}

    def prepare(self, studio, value):
        """Two revision checks; no SQLite write transaction during schema I/O.

        Uncommitted tickets are never returned or dispatched. Concurrent callers
        may project twice, but only the committed ticket is exposed to either.
        """
        value = request_value(value)
        with studio.lock:
            need(self.workspace is studio.assets, 'Document workspace changed; reopen the service')
            document_store = str(Path(self.workspace.database).resolve())
            with self.workspace.connection() as db:
                db.execute('BEGIN')
                repeated = self._replay(db, value)
                if repeated: return repeated
                source = self.documents._current(db, value['document_id'], value['expected_revision'])
            from .preset_adapter import prepare_document
            report = prepare_document(studio, source['document'], value['preset_id'])
            need(self.workspace is studio.assets and document_store == str(Path(self.workspace.database).resolve()),
                 'Document workspace changed during preparation; no record was committed')
            record = {'format': VERSION, 'request': value, 'report': report,
                      'document_store': document_store, 'created_at': time.time()}
            raw = canonical(record)
            summary = self._summary(record); summary_raw = canonical(summary)
            size = len(raw) + len(summary_raw)
            need(len(raw) <= MAX_BYTES, 'Saved run report exceeds 1 MiB; no record was committed')
            # Validate the full JSON contract before obtaining the write lock.
            decode(raw)
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                repeated = self._replay(db, value)
                if repeated: return repeated
                current = self.documents._current(db, value['document_id'], value['expected_revision'])
                need(current['document_sha256'] == source['document_sha256'], 'Source revision changed')
                count, used = db.execute('SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM workflow_document_runs_v1').fetchone()
                need(count < MAX_RECORDS and used + size <= MAX_STORAGE_BYTES,
                     'Saved run record budget reached; no history was removed')
                db.execute('''INSERT INTO workflow_document_runs_v1
                    (request_id,request_sha256,document_id,revision,job_id,record,record_sha256,summary,summary_sha256,bytes)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (value['request_id'], digest(value), value['document_id'], value['expected_revision'],
                     report['job_id'], raw.decode('utf-8'), digest(record), summary_raw.decode('utf-8'), digest(summary), size))
                result = self._read(db, self._find(db, value['request_id']))
            # The connection helper must commit successfully before returning.
            return {**result, 'replayed': False}

    def get(self, request_id):
        identifier(request_id)
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            return self._read(db, self._find(db, request_id))

    def by_job(self, job_id):
        identifier(job_id)
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            row = db.execute('SELECT * FROM workflow_document_runs_v1 WHERE job_id=?', (job_id,)).fetchone()
            return self._read(db, row)

    def list(self, document_id, *, before=None, limit=25):
        identifier(document_id)
        need(type(limit) is int and 1 <= limit <= MAX_PAGE, 'Page limit must be 1–100')
        need(before is None or type(before) is int and 1 <= before <= 2**53 - 1, 'Invalid page cursor')
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            source = self.documents._read(db, document_id)
            # Query summaries only: page cost cannot grow with embedded tickets.
            rows = db.execute('''SELECT sequence,summary,summary_sha256 FROM workflow_document_runs_v1
                WHERE document_id=? AND (? IS NULL OR sequence<?)
                ORDER BY sequence DESC LIMIT ?''', (document_id, before, before, limit + 1)).fetchall()
            summaries = []
            for row in rows[:limit]:
                item = self._read_summary(row)
                if item['document_id'] != document_id:
                    raise DocumentError('storage_unavailable', 'Run index points to another document', 503)
                summaries.append({**item, 'sequence': row['sequence']})
        return {'document_id': document_id, 'head_revision': source['head_revision'], 'runs': summaries,
                'next_before': rows[limit - 1]['sequence'] if len(rows) > limit else None,
                'dispatch_attempted': False}

    def observe(self, studio, request_id):
        """Join existing local job evidence. Never probe Comfy or read/replay intents."""
        result = self.get(request_id)
        record = result['record']; report = record['report']; pins = report['ticket']['pins']
        with studio.lock:
            matches = (self.workspace is studio.assets
                and record['document_store'] == str(Path(studio.assets.database).resolve())
                and pins.get('workspace') == str(studio.root)
                and pins.get('experiments_root') == str(studio.experiments.resolve())
                and pins.get('runs_root') == str(studio.runs.resolve()))
            observation = {'state': 'not_observed', 'job_id': report['job_id'],
                           'message': 'No local job is available. This does not prove the ticket was never dispatched.'}
            if not matches:
                observation.update(state='workspace_changed', message='Inspect the original workspace; no job was joined.')
            else:
                job = studio.jobs.get(report['job_id'])
                if job is not None:
                    try:
                        valid = (isinstance(job, dict) and job.get('id') == report['job_id']
                            and job.get('preset_id') == report['recipe']['preset_id']
                            and job.get('comfy_url') == pins.get('backend_url')
                            and isinstance(job.get('graph'), dict)
                            and digest(job['graph']) == report['prepared_graph_sha256'])
                    except (ValueError, TypeError, RecursionError): valid = False
                    if not valid:
                        observation.update(state='evidence_mismatch', message='Local job identity or graph differs; inspect evidence.')
                    else:
                        observation = {'state': 'observed', 'job_id': job['id'], 'job': studio.public(job)}
        return {'request_id': request_id, 'document_id': record['request']['document_id'],
                'revision': record['request']['expected_revision'], 'document_sha256': report['document_sha256'],
                'record_sha256': result['record_sha256'], 'head_revision': result['head_revision'],
                'observation': observation, 'dispatch_attempted': False}
