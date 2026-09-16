"""Append-only workflow revisions in the existing AssetWorkspace SQLite database.

No network/schema discovery, media writes, model calls or queue ownership. All
writes and request receipts share one transaction with an expected-revision check.
"""
from __future__ import annotations
import time
import uuid
from .core import document, decode, need
from .revision_consistency import (RequestState, byte_budget, canonical_sha256,
                                   canonical_value, classify_request, compare_head, stored_value)
from .commands import apply_commands, changes, execution_inputs_sha256, identifier, fields

MAX_DOCUMENTS = 256
MAX_REVISIONS = 1024
MAX_HISTORY_BYTES = 128 * 1024 * 1024
NAMESPACE = uuid.UUID('0943b1d3-3a9c-4de4-a1b7-b59b8d7fa86d')


class DocumentError(ValueError):
    def __init__(self, code, message, status=400, **details):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details
    def result(self):
        return {'error': str(self), 'code': self.code, **self.details, 'generation_submitted': False}


class WorkflowDocuments:
    def __init__(self, workspace):
        self.workspace = workspace
        # The existing connection helper owns commit/rollback/close. This only
        # creates namespaced tables; it never changes other Workspace schemas.
        with workspace.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workflow_documents_v1 (
                    id TEXT PRIMARY KEY, head INTEGER NOT NULL, origin TEXT NOT NULL, name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_revisions_v1 (
                    document_id TEXT NOT NULL REFERENCES workflow_documents_v1(id),
                    revision INTEGER NOT NULL, document TEXT NOT NULL, sha256 TEXT NOT NULL,
                    created_at REAL NOT NULL, bytes INTEGER NOT NULL, PRIMARY KEY(document_id,revision));
                CREATE TABLE IF NOT EXISTS workflow_requests_v1 (
                    request_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
                    document_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    kind TEXT NOT NULL, summary TEXT NOT NULL,
                    FOREIGN KEY(document_id,revision) REFERENCES workflow_revisions_v1(document_id,revision));
            ''')

    def _read(self, db, key, revision=None):
        identifier(key)
        if revision is not None: self._revision(revision)
        row = db.execute('''SELECT r.*, d.head, d.origin FROM workflow_documents_v1 d
            JOIN workflow_revisions_v1 r ON d.id=r.document_id AND r.revision=COALESCE(?,d.head)
            WHERE d.id=?''', (revision, key)).fetchone()
        if row is None: raise DocumentError('not_found', 'Workflow or revision not found', 404)
        try:
            stored = stored_value(row['document'], row['sha256'])
            need(stored.matches, 'Stored workflow integrity check failed')
            doc = document(stored.value)
            origin = decode(row['origin']); need(isinstance(origin, dict), 'Invalid stored workflow origin')
        except (ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
            raise DocumentError('storage_unavailable', 'Stored workflow integrity check failed', 503,
                                recovery='Retain the same request and inspect the stored evidence.') from exc
        return {'id': key, 'revision': row['revision'], 'head_revision': row['head'],
                'document': doc, 'document_sha256': row['sha256'],
                'execution_inputs_sha256': execution_inputs_sha256(doc),
                'origin': origin, 'generation_submitted': False}

    @staticmethod
    def _revision(value):
        need(type(value) is int and 1 <= value <= MAX_REVISIONS, 'Invalid server revision')

    def get(self, key, revision=None):
        with self.workspace.connection() as db: return self._read(db, key, revision)

    def list(self):
        with self.workspace.connection() as db:
            rows = db.execute('''SELECT d.id,d.head,d.name,r.sha256,r.created_at FROM workflow_documents_v1 d
                JOIN workflow_revisions_v1 r ON d.id=r.document_id AND d.head=r.revision ORDER BY d.id''').fetchall()
        return {'documents': [{'id': r['id'], 'revision': r['head'], 'name': r['name'],
                               'document_sha256': r['sha256'], 'updated_at': r['created_at']} for r in rows],
                'limits': {'documents': MAX_DOCUMENTS, 'revisions_per_document': MAX_REVISIONS,
                           'history_bytes': MAX_HISTORY_BYTES}, 'generation_submitted': False}

    def history(self, key):
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            current = self._read(db, key)
            rows = db.execute('''SELECT r.revision,r.sha256,r.created_at,q.request_id,q.kind,q.summary
                FROM workflow_revisions_v1 r JOIN workflow_requests_v1 q
                ON q.document_id=r.document_id AND q.revision=r.revision
                WHERE r.document_id=? ORDER BY r.revision DESC''', (key,)).fetchall()
        return {'id': key, 'head_revision': current['head_revision'], 'generation_submitted': False,
                'revisions': [{**dict(r), 'summary': history_summary(r['summary'])} for r in rows]}

    def _replay(self, db, request_id, sha):
        previous = db.execute('SELECT * FROM workflow_requests_v1 WHERE request_id=?', (request_id,)).fetchone()
        state = classify_request(None if previous is None else previous['sha256'], sha)
        if state is RequestState.ABSENT: return None
        if state is RequestState.CONFLICT:
            raise DocumentError('request_conflict', 'Request ID was already used for different content', 409)
        return {**self._read(db, previous['document_id'], previous['revision']), 'replayed': True}

    @staticmethod
    def _request(value, required):
        fields(value, required)
        identifier(value['request_id'])
        return canonical_value(value).value

    def _append(self, db, key, revision, doc, request_id, request_sha, kind, summary):
        need(revision <= MAX_REVISIONS, 'Workflow revision limit reached; export before archiving or forking')
        doc = document({**doc, 'revision': revision}); bound = canonical_value(doc)
        used = db.execute('SELECT COALESCE(SUM(bytes),0) FROM workflow_revisions_v1').fetchone()[0]
        need(byte_budget(used, bound.bytes, MAX_HISTORY_BYTES).fits,
             'Workflow history storage budget reached; no history was removed')
        db.execute('INSERT INTO workflow_revisions_v1 VALUES (?,?,?,?,?,?)',
                   (key, revision, bound.raw.decode('utf-8'), bound.sha256, time.time(), bound.bytes))
        db.execute('INSERT INTO workflow_requests_v1 VALUES (?,?,?,?,?,?)',
                   (request_id, request_sha, key, revision, kind,
                    canonical_value(summary).raw.decode('utf-8')))
        db.execute('UPDATE workflow_documents_v1 SET head=?,name=? WHERE id=?', (revision, doc['name'], key))
        return {**self._read(db, key), 'replayed': False}

    def create(self, value):
        value = self._request(value, ('request_id', 'document'))
        doc = document(value['document']); sha = canonical_sha256({'action': 'create', **value})
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            repeated = self._replay(db, value['request_id'], sha)
            if repeated: return repeated
            return self._create(db, doc, value['request_id'], sha, {})

    def _create(self, db, doc, request_id, sha, origin):
        count = db.execute('SELECT COUNT(*) FROM workflow_documents_v1').fetchone()[0]
        need(count < MAX_DOCUMENTS, 'Workflow count limit reached; no document was removed')
        key = str(uuid.uuid5(NAMESPACE, request_id))
        db.execute('INSERT INTO workflow_documents_v1 VALUES (?,?,?,?)',
                   (key, 1, canonical_value(origin).raw.decode('utf-8'), doc['name']))
        return self._append(db, key, 1, doc, request_id, sha, 'fork' if origin else 'create', {})

    def fork(self, key, value):
        identifier(key); value = self._request(value, ('request_id', 'revision', 'name'))
        self._revision(value['revision']); sha = canonical_sha256({'action': 'fork', 'id': key, **value})
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            repeated = self._replay(db, value['request_id'], sha)
            if repeated: return repeated
            source = self._read(db, key, value['revision'])
            doc = {**source['document'], 'name': value['name']}
            origin = {k: source[k] for k in ('id', 'revision', 'document_sha256')}
            return self._create(db, doc, value['request_id'], sha, origin)

    def _current(self, db, key, expected):
        self._revision(expected); current = self._read(db, key)
        comparison = compare_head(expected, current['revision'], current['document_sha256'])
        if not comparison.matches:
            raise DocumentError('revision_conflict', 'Workflow changed; inspect the current revision before applying', 409,
                                id=key, expected_revision=comparison.expected, current_revision=comparison.current,
                                current_sha256=comparison.current_sha256)
        return current

    def command(self, key, value, restore=False):
        identifier(key); field = 'revision' if restore else 'commands'
        value = self._request(value, ('request_id', 'expected_revision', field))
        sha = canonical_sha256({'action': 'restore' if restore else 'command', 'id': key, **value})
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            repeated = self._replay(db, value['request_id'], sha)
            if repeated: return repeated
            current = self._current(db, key, value['expected_revision'])
            next_doc = (self._read(db, key, value['revision'])['document'] if restore
                        else apply_commands(current['document'], value['commands']))
            summary = changes(current['document'], next_doc)
            if restore: summary['restored_revision'] = value['revision']
            return self._append(db, key, current['revision'] + 1, next_doc, value['request_id'], sha,
                                'restore' if restore else 'command', summary)

    def preview(self, key, value):
        fields(value, ('expected_revision', 'commands'))
        with self.workspace.connection() as db:
            current = self._current(db, key, value['expected_revision'])
        doc = apply_commands(current['document'], value['commands'])
        doc['revision'] = current['revision'] + 1
        return {'id': key, 'expected_revision': current['revision'], 'document': doc,
                'document_sha256': canonical_value(doc).sha256, 'changes': changes(current['document'], doc),
                'committed': False, 'generation_submitted': False}


def history_summary(raw):
    """Bound all 1,024 history summaries below the client's 16 MiB limit.

    Only the preview lists are shortened. Full revision documents and stored
    summaries remain intact; counts and truncation are explicit in each response.
    """
    try:
        summary = decode(raw)
        need(isinstance(summary, dict), 'Invalid stored summary')
        allowed = {'added_nodes', 'removed_nodes', 'changed_nodes', 'changed_fields',
                   'execution_inputs_changed', 'restored_revision'}
        need(set(summary) <= allowed, 'Unknown stored summary fields')
        result = dict(summary)
        for key in ('added_nodes', 'removed_nodes', 'changed_nodes', 'changed_fields'):
            if key not in result: continue
            values = result[key]
            need(isinstance(values, list) and len(values) <= 256, 'Invalid stored change list')
            for value in values: identifier(value)
            result[key + '_count'] = len(values)
            result[key] = values[:16]
        if 'execution_inputs_changed' in summary:
            need(type(summary['execution_inputs_changed']) is bool, 'Invalid stored change flag')
        if 'restored_revision' in summary: WorkflowDocuments._revision(summary['restored_revision'])
        result['truncated'] = any(len(summary.get(key, [])) > 16 for key in ('added_nodes', 'removed_nodes', 'changed_nodes', 'changed_fields'))
        return result
    except (ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
        raise DocumentError('storage_unavailable', 'Stored workflow history integrity check failed', 503,
                            recovery='Retain the same request and inspect the stored evidence.') from exc
