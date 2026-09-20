"""Bounded, read-only projections of the existing reviewed-setup revision tables.

No migration, live file verification, staging or command authority is granted by
these reads. The normal SetupDrafts command owner remains unchanged.
"""
from contextlib import contextmanager
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlsplit

from .commands import identifier
from .core import canonical, digest, need
from .revision_consistency import stored_value
from .setup_drafts import MAX_COMMAND, MAX_REVISIONS, PREFIX, SetupError
from .setup_proposal import validate_draft

MAX_PAGE = 20
MAX_PREVIEW = 1024
MAX_READ_BYTES = 1024 * 1024
MAX_EXPORT_BYTES = 1024 * 1024
FLAGS = {'observation_only': True, 'dependencies_checked': False,
         'generation_submitted': False, 'staging_performed': False}
READ_ACTIONS = {'history', 'compare', 'export'}


class HistoryReadError(SetupError):
    """Read failures must not suggest recovery of a write that never occurred."""
    def result(self):
        return {'error': str(self), 'code': self.code, **FLAGS,
                'recovery': 'Read-only inspection failed. Evidence was retained; no write was retried.'}


def _corrupt(condition, message):
    if not condition:
        raise HistoryReadError('setup_history_corrupt', message, 503)


def _integer(value, maximum=MAX_REVISIONS):
    need(type(value) is int and 1 <= value <= maximum, 'Invalid bounded history integer')
    return value


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _bounded_reply(value):
    # Handler._json uses ensure_ascii=True with default separators, not canonical.
    if len(json.dumps(value, allow_nan=False).encode('utf-8')) > MAX_READ_BYTES:
        raise HistoryReadError('setup_history_response_too_large',
                               'History response exceeds its byte bound; no partial result was returned', 413)
    return value


def _preview(value, *, redacted=False):
    raw = canonical(value)
    text = raw.decode('utf-8')[:MAX_PREVIEW] if not redacted else None
    omitted = len(raw) - (len(text.encode('utf-8')) if text is not None else 0)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'preview': text, 'truncated': not redacted and omitted > 0,
            'omitted_bytes': omitted, 'redacted': redacted}


def _sections(record):
    draft = record['draft']; recipe = draft['recipe']; controls = recipe['controls']
    return {
        'recipe_graph': {'preset': recipe['preset'], 'templateHash': draft['templateHash'],
                         'graph_sha256': record['graph_sha256'], 'backend_id': record['runtime']['backend_id']},
        'wording': {k: controls[k] for k in ('positive', 'negative') if k in controls},
        'references': {'board': recipe['references'], 'inputs': record['inputs'],
                       'named': {k: controls[k] for k in ('reference', 'last_reference') if k in controls}},
        'controls': {k: v for k, v in controls.items() if k not in ('positive', 'negative', 'reference', 'last_reference')},
        'lineage': {k: recipe[k] for k in ('parent_assets', 'parent_by_input', 'continuation') if k in recipe},
        'batch': recipe['batch'], 'pending_inputs': draft['pendingInputs'],
        'authoring': {'updatedAt': draft['updatedAt']},
        'runtime': record['runtime'],
    }


class SetupHistory:
    """Use an existing AssetWorkspace; never initialize another store or table."""
    def __init__(self, workspace):
        self.workspace = workspace

    @contextmanager
    def _snapshot(self, key, workspace_id, expected_head=None):
        identifier(key)
        self.workspace._validate_scope(workspace_id)
        if expected_head is not None: _integer(expected_head)
        with self.workspace.connection() as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db, workspace_id)
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('setup_drafts_v1','setup_versions_v1')").fetchall()
            if len(tables) != 2:
                raise HistoryReadError('setup_not_found', 'Reviewed setup history is not initialized', 404)
            row = db.execute("SELECT CASE WHEN typeof(head)='integer' THEN head END AS head FROM setup_drafts_v1 WHERE id=?", (key,)).fetchone()
            if row is None:
                raise HistoryReadError('setup_not_found', 'Reviewed setup line not found', 404)
            head = row['head']
            _corrupt(type(head) is int and 1 <= head <= MAX_REVISIONS, 'Stored setup head failed its integrity bound')
            if expected_head is not None and expected_head != head:
                raise HistoryReadError('setup_history_head_changed', 'Reviewed setup head changed; explicitly restart history inspection')
            # At most 257 scalar rows, including one excess-row sentinel. The
            # primary key supplies order; no unbounded aggregate is materialized.
            revisions = db.execute('''SELECT CASE WHEN typeof(revision)='integer' THEN revision END AS revision
                FROM setup_versions_v1 WHERE draft_id=? ORDER BY setup_versions_v1.revision DESC LIMIT ?''',
                (key, MAX_REVISIONS + 1)).fetchall()
            _corrupt([row['revision'] for row in revisions] == list(range(head, 0, -1)),
                     'Stored setup history is not contiguous; retained rows were not changed')
            current = self._read(db, key, head)
            context = {'workspace_id': scope, 'draft_id': key, 'head_revision': head,
                       'head_record_sha256': current[1]['record_sha256']}
            yield db, context, current

    @staticmethod
    def _read(db, key, revision):
        # Bound both text and scalar columns before Python materializes a corrupt row.
        row = db.execute('''SELECT
            CASE WHEN typeof(record)='text' AND length(CAST(record AS BLOB))<=? THEN record END AS record,
            CASE WHEN typeof(sha256)='text' AND length(CAST(sha256 AS BLOB))=64 THEN sha256 END AS sha256,
            CASE WHEN typeof(bytes)='integer' AND bytes BETWEEN 1 AND ? THEN bytes END AS bytes
            FROM setup_versions_v1 WHERE draft_id=? AND revision=?''', (MAX_COMMAND, MAX_COMMAND, key, revision)).fetchone()
        if row is None:
            raise HistoryReadError('setup_not_found', 'Reviewed setup revision not found', 404)
        try:
            need(row['record'] is not None and _sha(row['sha256']) and row['bytes'] is not None,
                 'Stored setup revision exceeds its integrity bound')
            raw = row['record'].encode('utf-8')
            need(len(raw) == row['bytes'], 'Stored setup revision bytes failed their integrity check')
            stored = stored_value(row['record'], row['sha256'])
            need(stored.matches and canonical(stored.value) == raw, 'Stored setup revision failed its canonical integrity check')
            record = stored.value
            need(type(record) is dict and set(record) == {'draft', 'inputs', 'runtime', 'graph_sha256'},
                 'Unsupported stored setup record fields')
            validate_draft(record['draft'])
            need(_sha(record['graph_sha256']), 'Invalid stored graph identity')
            runtime = record['runtime']
            need(type(runtime) is dict and set(runtime) == {'backend_id', 'root', 'endpoint'} and
                 all(type(runtime[k]) is str and len(runtime[k]) <= 4096 for k in runtime) and 1 <= len(runtime['backend_id']) <= 128,
                 'Invalid stored runtime identity')
            inputs = record['inputs']
            need(type(inputs) is list and len(inputs) <= 10, 'Stored input count exceeds its bound')
            names = set()
            for item in inputs:
                need(type(item) is dict and set(item) == {'file', 'sha256', 'bytes', 'width', 'height'}, 'Invalid stored input fields')
                name = item['file']
                need(type(name) is str and 1 <= len(name) <= 255 and name not in ('.', '..') and
                     not any(c in name for c in ('/', '\\', '\x00')) and name not in names and _sha(item['sha256']),
                     'Invalid stored input identity')
                names.add(name)
                need(all(type(item[k]) is int and 1 <= item[k] <= 2**53-1 for k in ('bytes', 'width', 'height')), 'Invalid stored input dimensions or bytes')
            return record, {'revision': revision, 'record_sha256': row['sha256'], 'record_bytes': row['bytes'],
                            'draft_sha256': digest(record['draft']), 'preset_id': record['draft']['recipe']['preset'],
                            'backend_id': runtime['backend_id'], 'graph_sha256': record['graph_sha256'], 'input_count': len(inputs)}
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
            if isinstance(exc, SetupError): raise
            raise HistoryReadError('setup_history_corrupt',
                                   'Stored setup history failed integrity validation: ' + str(exc)[:256], 503) from exc

    @staticmethod
    def _reply(kind, context, **values):
        return _bounded_reply({'format': 'studio.setup-history-' + kind + '/v2',
                               **context, **values, **FLAGS})

    def page(self, key, *, workspace_id, limit=MAX_PAGE, before_revision=None, expected_head=None):
        _integer(limit, MAX_PAGE)
        if before_revision is not None:
            _integer(before_revision)
            need(expected_head is not None, 'A continuation requires the observed expected head')
        with self._snapshot(key, workspace_id, expected_head) as (db, context, current):
            head = context['head_revision']
            need(before_revision is None or before_revision <= head, 'Continuation is outside the observed head')
            rows = db.execute('SELECT revision FROM setup_versions_v1 WHERE draft_id=? AND revision<? ORDER BY revision DESC LIMIT ?',
                              (key, before_revision if before_revision is not None else head+1, limit+1)).fetchall()
            summaries = [(current if r['revision'] == head else self._read(db, key, r['revision']))[1]
                         for r in rows[:limit]]
            return self._reply('page', context, limit=limit, revisions=summaries,
                               next_before_revision=summaries[-1]['revision'] if len(rows) > limit else None)

    def compare(self, key, left, right, *, workspace_id, expected_head=None):
        _integer(left); _integer(right)
        with self._snapshot(key, workspace_id, expected_head) as (db, context, current):
            head = context['head_revision']
            a, sa = current if left == head else self._read(db, key, left)
            b, sb = (a, sa) if right == left else current if right == head else self._read(db, key, right)
            lhs, rhs = _sections(a), _sections(b)
            sections = [{'section': name, 'changed': canonical(lhs[name]) != canonical(rhs[name]),
                         'left': _preview(lhs[name], redacted=name == 'runtime'),
                         'right': _preview(rhs[name], redacted=name == 'runtime')} for name in lhs]
            return self._reply('compare', context, left_revision=left, right_revision=right,
                               left_record_sha256=sa['record_sha256'], right_record_sha256=sb['record_sha256'],
                               sections=sections)

    def export_revision(self, key, revision, *, workspace_id, expected_head=None):
        _integer(revision)
        with self._snapshot(key, workspace_id, expected_head) as (db, context, current):
            record, summary = current if revision == context['head_revision'] else self._read(db, key, revision)
            # Head observation stays outside the immutable export document.
            # This projection deliberately excludes runtime root/endpoint, not
            # arbitrary sensitive text the user may have authored in the draft.
            value = {'format': 'studio.setup-revision-inspection/v2', 'workspace_id': context['workspace_id'],
                     'draft_id': key, 'revision': revision, 'source_record_sha256': summary['record_sha256'],
                     'source_record_bytes': summary['record_bytes'],
                     'draft': record['draft'], 'draft_sha256': summary['draft_sha256'], 'inputs': record['inputs'],
                     'backend_id': summary['backend_id'], 'graph_sha256': summary['graph_sha256'],
                     'authority': 'none', **FLAGS}
            raw = canonical(value)
            if len(raw) > MAX_EXPORT_BYTES:
                raise HistoryReadError('setup_history_export_too_large', 'Setup inspection export exceeds its byte bound', 413)
            return self._reply('export', context, export=value, export_json=raw.decode('utf-8'),
                               export_sha256=hashlib.sha256(raw).hexdigest(), export_bytes=len(raw))


def read_route(path, workspace):
    need(type(path) is str and len(path.encode('utf-8')) <= 4096, 'History query exceeds its byte bound')
    parsed = urlsplit(path)
    need(not parsed.scheme and not parsed.netloc and not parsed.fragment and parsed.path.startswith(PREFIX+'/'), 'Relative history route required')
    parts = parsed.path[len(PREFIX)+1:].split('/')
    need(len(parts) == 2 and parts[1] in READ_ACTIONS, 'Unknown setup history read')
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=4, errors='strict')
    values = dict(pairs)
    required = {'workspace_id'} | ({'left', 'right'} if parts[1] == 'compare' else {'revision'} if parts[1] == 'export' else set())
    allowed = required | {'expected_head'} | ({'limit', 'before_revision'} if parts[1] == 'history' else set())
    need(len(values) == len(pairs) and required <= set(values) <= allowed, 'Invalid or duplicate history query fields')
    for name in values.keys() - {'workspace_id'}:
        need(re.fullmatch('[1-9][0-9]{0,2}', values[name]) is not None, 'History integers require canonical decimal notation')
        values[name] = int(values[name])
    history = SetupHistory(workspace)
    method = {'history': history.page, 'compare': history.compare, 'export': history.export_revision}[parts[1]]
    return method(identifier(parts[0]), **values)
