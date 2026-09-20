"""Bounded read-only projections of SetupDrafts' existing immutable records.

No schema, command, receipt, staging, backend, or media ownership lives here.
Construct with SetupHistory(existing_setup_drafts); instantiate the owner's store
before entering a query-only connection. A historical record is not current
runtime compatibility or permission to execute it.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import re

from .commands import identifier
from .core import canonical, need
from .revision_consistency import exact_stored_value
from .setup_drafts import MAX_REVISIONS, SetupError
from .setup_proposal import validate_draft

MAX_PAGE = 25
MAX_RECORD_BYTES = 1024 * 1024
MAX_SECTION_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_EXPORT_BYTES = 1024 * 1024
HASH = re.compile(r'[0-9a-f]{64}\Z')
FLAGS = {'observation_only': True, 'dependencies_checked': False,
         'generation_submitted': False, 'staging_performed': False}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _revision(value):
    need(type(value) is int and 1 <= value <= MAX_REVISIONS, 'Invalid setup history revision')


def _corrupt(condition):
    if not condition:
        raise SetupError('setup_history_corrupt', 'Stored setup history is invalid; no evidence was repaired or removed', 503)


def _sections(record):
    draft = record['draft']
    recipe = draft['recipe']
    controls = recipe['controls']
    return {
        'recipe_graph': {'preset': recipe['preset'], 'template_sha256': draft['templateHash'],
                         'graph_sha256': record['graph_sha256']},
        'wording': {key: value for key, value in controls.items() if key in ('positive', 'negative')},
        'controls': {key: value for key, value in controls.items()
                     if key not in ('positive', 'negative', 'reference', 'last_reference')},
        'references': {'slots': recipe['references'], 'staged_inputs': record['inputs'],
                       'bindings': {key: value for key, value in controls.items()
                                    if key in ('reference', 'last_reference')}},
        'lineage': {'parent_assets': recipe['parent_assets'], 'parent_by_input': recipe['parent_by_input'],
                    'continuation': recipe.get('continuation')},
        'batch_pending': {'batch': recipe['batch'], 'pending_inputs': draft['pendingInputs']},
        'runtime': record['runtime'],
    }


class SetupHistory:
    """Read adapter over the existing setup owner; never initializes another store."""

    def __init__(self, setups):
        self.setups = setups
        self.workspace = setups.workspace

    def _record(self, db, key, revision):
        # Bound allocation in SQLite, before either JSON decoder sees the row.
        row = db.execute('''SELECT
            CASE WHEN typeof(record)='text' AND length(CAST(record AS BLOB))<=? THEN record END AS record,
            CASE WHEN typeof(sha256)='text' AND length(CAST(sha256 AS BLOB))=64 THEN sha256 END AS sha256,
            CASE WHEN typeof(bytes)='integer' THEN bytes END AS bytes
            FROM setup_versions_v1 WHERE draft_id=? AND revision=?''',
            (MAX_RECORD_BYTES, key, revision)).fetchone()
        _corrupt(row is not None and type(row['record']) is str
                 and type(row['sha256']) is str and HASH.fullmatch(row['sha256']) is not None
                 and type(row['bytes']) is int and 0 < row['bytes'] <= MAX_RECORD_BYTES)
        try:
            bound = exact_stored_value(row['record'], row['sha256'], max_bytes=MAX_RECORD_BYTES)
            _corrupt(bound.matches and bound.bytes == row['bytes'] and canonical(bound.value) == bound.raw)
            record = bound.value
            _corrupt(type(record) is dict and set(record) == {'draft', 'inputs', 'runtime', 'graph_sha256'})
            validate_draft(record['draft'])
            _corrupt(type(record['graph_sha256']) is str and HASH.fullmatch(record['graph_sha256']) is not None)
            _corrupt(type(record['inputs']) is list and len(record['inputs']) <= 10
                     and all(type(item) is dict for item in record['inputs']))
            runtime = record['runtime']
            _corrupt(type(runtime) is dict and set(runtime) == {'backend_id', 'endpoint', 'root'}
                     and all(type(value) is str and len(value) <= 4096 for value in runtime.values()))
            return bound
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
            if isinstance(exc, SetupError):
                raise
            raise SetupError('setup_history_corrupt', 'Stored setup history failed validation; evidence was retained', 503) from exc

    @contextmanager
    def _view(self, key, workspace_id, expected_head=None):
        identifier(key)
        self.workspace._validate_scope(workspace_id)
        if expected_head is not None:
            _revision(expected_head)
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db, workspace_id)
            row = db.execute("SELECT CASE WHEN typeof(head)='integer' THEN head END AS head FROM setup_drafts_v1 WHERE id=?", (key,)).fetchone()
            if row is None:
                raise SetupError('setup_not_found', 'Setup draft not found', 404)
            head = row['head']
            _corrupt(type(head) is int and 1 <= head <= MAX_REVISIONS)
            if expected_head is not None and expected_head != head:
                raise SetupError('setup_revision_conflict', 'Setup head changed; explicitly refresh history')
            # At most 257 small scalars; refuse holes/future rows rather than
            # turning damaged retained evidence into a successful empty page.
            revisions = db.execute('''SELECT CASE WHEN typeof(revision)='integer' THEN revision END AS revision
                FROM setup_versions_v1 WHERE draft_id=? ORDER BY revision DESC LIMIT ?''',
                (key, MAX_REVISIONS + 1)).fetchall()
            _corrupt([row['revision'] for row in revisions] == list(range(head, 0, -1)))
            current = self._record(db, key, head)
            context = {'workspace_id': scope, 'draft_id': key, 'head_revision': head,
                       'head_record_sha256': current.stored_sha256}
            yield db, context, current

    @staticmethod
    def _summary(revision, bound):
        record = bound.value
        return {'revision': revision, 'record_sha256': bound.stored_sha256, 'record_bytes': bound.bytes,
                'draft_sha256': _hash(canonical(record['draft'])), 'graph_sha256': record['graph_sha256'],
                'input_count': len(record['inputs']), 'backend_id': record['runtime']['backend_id']}

    @staticmethod
    def _reply(kind, context, **values):
        result = {'format': 'studio.setup-history-' + kind + '/v1', **context, **values, **FLAGS}
        need(len(canonical(result)) <= MAX_RESPONSE_BYTES, 'Setup history response exceeds its byte limit')
        return result

    def page(self, key, *, workspace_id, limit=20, before_revision=None, expected_head=None):
        need(type(limit) is int and 1 <= limit <= MAX_PAGE, 'History page size must be 1..25')
        if before_revision is not None:
            _revision(before_revision)
            need(expected_head is not None, 'History continuation requires its observed head')
        with self._view(key, workspace_id, expected_head) as (db, context, current):
            head = context['head_revision']
            need(before_revision is None or before_revision <= head, 'History boundary exceeds observed head')
            start = head if before_revision is None else before_revision - 1
            end = max(0, start - limit)
            summaries = [self._summary(revision, current if revision == head else self._record(db, key, revision))
                         for revision in range(start, end, -1)]
            return self._reply('page', context, revisions=summaries, limit=limit,
                               next_before_revision=end + 1 if end else None)

    def compare(self, key, left, right, *, workspace_id, expected_head=None):
        _revision(left)
        _revision(right)
        with self._view(key, workspace_id, expected_head) as (db, context, current):
            need(max(left, right) <= context['head_revision'], 'Requested revision exceeds the setup head')
            before = current if left == context['head_revision'] else self._record(db, key, left)
            after = current if right == context['head_revision'] else self._record(db, key, right)
            old, new = _sections(before.value), _sections(after.value)
            sections = []
            for name in old:
                a, b = canonical(old[name]), canonical(new[name])
                section = {'section': name, 'changed': a != b, 'before_sha256': _hash(a),
                           'after_sha256': _hash(b), 'before_bytes': len(a), 'after_bytes': len(b),
                           'omitted': len(a) + len(b) > MAX_SECTION_BYTES}
                if not section['omitted']:
                    section.update(before=old[name], after=new[name])
                sections.append(section)
            return self._reply('diff', context, left=self._summary(left, before),
                               right=self._summary(right, after), sections=sections)

    def export_revision(self, key, revision, *, workspace_id, expected_head=None):
        _revision(revision)
        with self._view(key, workspace_id, expected_head) as (db, context, current):
            need(revision <= context['head_revision'], 'Requested revision exceeds the setup head')
            bound = current if revision == context['head_revision'] else self._record(db, key, revision)
            # Current head is observation metadata, not part of immutable export
            # identity: exporting revision 1 after an append produces the same file.
            document = {'format': 'studio.setup-revision/v1',
                        'origin': {'workspace_id': context['workspace_id'], 'draft_id': key, 'revision': revision},
                        'record': bound.value, 'record_sha256': bound.stored_sha256,
                        'record_bytes': bound.bytes, **FLAGS}
            raw = canonical(document)
            need(len(raw) <= MAX_EXPORT_BYTES, 'Setup revision export exceeds its byte limit; no history was removed')
            return self._reply('export', context, revision=revision, export_json=raw.decode('utf-8'),
                               export_sha256=_hash(raw), export_bytes=len(raw))
