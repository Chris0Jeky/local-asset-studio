"""Bounded, read-only projections of the existing reviewed-setup revision tables.

No migration, live file verification, staging or command authority is granted by
these reads. The normal SetupDrafts command owner remains unchanged.
"""
from contextlib import contextmanager
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
READ_ACTIONS = {'history', 'compare', 'export'}


def _integer(value, maximum=MAX_REVISIONS):
    need(type(value) is int and 1 <= value <= maximum, 'Invalid bounded history integer')
    return value


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _bounded_reply(value):
    # Handler._json uses ensure_ascii=True with default separators, not canonical.
    need(len(json.dumps(value, allow_nan=False).encode('utf-8')) <= MAX_READ_BYTES,
         'History response exceeds its byte bound; no partial result was returned')
    return value


def _preview(value):
    raw = canonical(value)
    decoded = raw.decode('utf-8')
    return {'sha256': digest(value), 'bytes': len(raw),
            'preview': decoded[:MAX_PREVIEW], 'truncated': len(decoded) > MAX_PREVIEW}


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
    }


class SetupHistory:
    """Use an existing AssetWorkspace; never initialize another store or table."""
    def __init__(self, workspace):
        self.workspace = workspace

    @contextmanager
    def _snapshot(self, key, workspace_id):
        identifier(key)
        self.workspace._validate_scope(workspace_id)
        with self.workspace.connection() as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db, workspace_id)
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('setup_drafts_v1','setup_versions_v1')").fetchall()
            if len(tables) != 2:
                raise SetupError('setup_not_found', 'Reviewed setup history is not initialized', 404)
            row = db.execute("SELECT CASE WHEN typeof(head)='integer' THEN head END AS head FROM setup_drafts_v1 WHERE id=?", (key,)).fetchone()
            if row is None:
                raise SetupError('setup_not_found', 'Reviewed setup line not found', 404)
            head = row['head']
            need(type(head) is int and 1 <= head <= MAX_REVISIONS, 'Stored setup head failed its integrity bound')
            stats = db.execute('''SELECT count(*) AS count,
                min(CASE WHEN typeof(revision)='integer' THEN revision END) AS first,
                max(CASE WHEN typeof(revision)='integer' THEN revision END) AS last,
                sum(CASE WHEN typeof(revision)='integer' AND revision BETWEEN 1 AND ? THEN 0 ELSE 1 END) AS invalid
                FROM setup_versions_v1 WHERE draft_id=?''', (MAX_REVISIONS, key)).fetchone()
            need(stats['count'] == head and stats['first'] == 1 and stats['last'] == head and stats['invalid'] == 0,
                 'Stored setup history is not contiguous; retained rows were not changed')
            yield db, scope, head

    @staticmethod
    def _read(db, key, revision):
        # Bound both text and scalar columns before Python materializes a corrupt row.
        row = db.execute('''SELECT
            CASE WHEN typeof(record)='text' AND length(CAST(record AS BLOB))<=? THEN record END AS record,
            CASE WHEN typeof(sha256)='text' AND length(CAST(sha256 AS BLOB))=64 THEN sha256 END AS sha256,
            CASE WHEN typeof(bytes)='integer' AND bytes BETWEEN 1 AND ? THEN bytes END AS bytes
            FROM setup_versions_v1 WHERE draft_id=? AND revision=?''', (MAX_COMMAND, MAX_COMMAND, key, revision)).fetchone()
        if row is None:
            raise SetupError('setup_not_found', 'Reviewed setup revision not found', 404)
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
             all(type(runtime[k]) is str for k in runtime) and 1 <= len(runtime['backend_id']) <= 128,
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

    def page(self, key, *, workspace_id, limit=MAX_PAGE, before_revision=None, expected_head=None):
        _integer(limit, MAX_PAGE)
        if expected_head is not None: _integer(expected_head)
        if before_revision is not None:
            _integer(before_revision)
            need(expected_head is not None, 'A continuation requires the observed expected head')
        with self._snapshot(key, workspace_id) as (db, scope, head):
            if expected_head is not None and expected_head != head:
                raise SetupError('setup_history_head_changed', 'Reviewed setup head changed; explicitly restart history inspection')
            need(before_revision is None or before_revision <= head, 'Continuation is outside the observed head')
            rows = db.execute('SELECT revision FROM setup_versions_v1 WHERE draft_id=? AND revision<? ORDER BY revision DESC LIMIT ?',
                              (key, before_revision if before_revision is not None else head+1, limit+1)).fetchall()
            summaries = [self._read(db, key, r['revision'])[1] for r in rows[:limit]]
            return _bounded_reply({'format': 'studio.setup-history-page/v1', 'workspace_id': scope, 'draft_id': key,
                                   'head_revision': head, 'revisions': summaries,
                                   'next_before_revision': summaries[-1]['revision'] if len(rows) > limit else None,
                                   'generation_submitted': False})

    def compare(self, key, left, right, *, workspace_id):
        _integer(left); _integer(right)
        with self._snapshot(key, workspace_id) as (db, scope, head):
            a, sa = self._read(db, key, left); b, sb = self._read(db, key, right)
            lhs, rhs = _sections(a), _sections(b)
            sections = [{'section': name, 'changed': canonical(lhs[name]) != canonical(rhs[name]),
                         'left': _preview(lhs[name]), 'right': _preview(rhs[name])} for name in lhs]
            return _bounded_reply({'format': 'studio.setup-history-compare/v1', 'workspace_id': scope, 'draft_id': key,
                                   'head_revision': head, 'left_revision': left, 'right_revision': right,
                                   'left_record_sha256': sa['record_sha256'], 'right_record_sha256': sb['record_sha256'],
                                   'sections': sections, 'generation_submitted': False})

    def export_revision(self, key, revision, *, workspace_id):
        _integer(revision)
        with self._snapshot(key, workspace_id) as (db, scope, head):
            record, summary = self._read(db, key, revision)
            value = {'format': 'studio.setup-revision-inspection/v1', 'workspace_id': scope,
                     'draft_id': key, 'revision': revision, 'source_record_sha256': summary['record_sha256'],
                     'draft': record['draft'], 'draft_sha256': summary['draft_sha256'], 'inputs': record['inputs'],
                     'backend_id': summary['backend_id'], 'graph_sha256': summary['graph_sha256'],
                     'authority': 'none'}
            return _bounded_reply({'format': 'studio.setup-history-export/v1', 'workspace_id': scope, 'draft_id': key,
                                   'head_revision': head, 'export': value, 'export_json': canonical(value).decode('utf-8'),
                                   'export_sha256': digest(value), 'generation_submitted': False})


def read_route(path, workspace):
    need(type(path) is str and len(path.encode('utf-8')) <= 4096, 'History query exceeds its byte bound')
    parsed = urlsplit(path)
    need(not parsed.scheme and not parsed.netloc and not parsed.fragment and parsed.path.startswith(PREFIX+'/'), 'Relative history route required')
    parts = parsed.path[len(PREFIX)+1:].split('/')
    need(len(parts) == 2 and parts[1] in READ_ACTIONS, 'Unknown setup history read')
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=4, errors='strict')
    values = dict(pairs)
    required = {'workspace_id'} | ({'left', 'right'} if parts[1] == 'compare' else {'revision'} if parts[1] == 'export' else set())
    allowed = required | ({'limit', 'before_revision', 'expected_head'} if parts[1] == 'history' else set())
    need(len(values) == len(pairs) and required <= set(values) <= allowed, 'Invalid or duplicate history query fields')
    for name in values.keys() - {'workspace_id'}:
        need(re.fullmatch('[1-9][0-9]{0,2}', values[name]) is not None, 'History integers require canonical decimal notation')
        values[name] = int(values[name])
    history = SetupHistory(workspace)
    method = {'history': history.page, 'compare': history.compare, 'export': history.export_revision}[parts[1]]
    return method(identifier(parts[0]), **values)
