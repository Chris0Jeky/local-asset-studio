"""Typed collection transactions in AssetWorkspace's database, not an event bus.

Receipts are immutable historical evidence. Current observations are separate;
unknown status neither cancels nor rules out an in-flight commit. No media I/O.
"""
from __future__ import annotations
import re
import time
import uuid
from .revision_consistency import (RequestState, byte_budget, canonical_value,
                                   classify_request, compare_head, exact_stored_value)

COMMAND_FORMAT = 'studio.collection-command/v1'
RECEIPT_FORMAT = 'studio.collection-receipt/v1'
RESULT_FORMAT = 'studio.collection-result/v1'
MAX_REVISION = 2**53 - 1
MAX_COMMAND_BYTES = 16 * 1024
MAX_RECEIPT_BYTES = 16 * 1024
MAX_RECEIPTS = 4096
MAX_JOURNAL_BYTES = 32 * 1024 * 1024
TOKEN = re.compile(r'[A-Za-z0-9_-]{16,128}\Z')
ENTITY = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
SCOPE = re.compile(r'[0-9a-f]{32}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
RECOVERY = 'Retain the original request ID and exact content. Inspect status in the original Workspace; do not allocate a replacement request.'


class CollectionError(ValueError):
    def __init__(self, message, *, code='collection_invalid_command', status=400, **details):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details

    def response(self):
        return {'format': 'studio.collection-error/v1', 'error': str(self), 'code': self.code,
                **self.details, 'generation_submitted': False}


def require(condition, message, **error):
    if not condition: raise CollectionError(message, **error)


def _fields(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields), 'Supply exactly the typed collection fields')


def _text(value, maximum, name):
    require(isinstance(value, str) and len(value) <= maximum, name + ' exceeds its text limit')
    return value.strip()


def _match(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def bind_command(value):
    require(isinstance(value, dict), 'Collection command must be an object')
    required = {'format', 'workspace_id', 'request_id', 'action'}
    if value.get('action') in ('rename', 'delete'): required |= {'id', 'expected_revision'}
    require(required <= set(value), 'Supply the collection format, Workspace, request ID and revision preconditions',
            status=428, code='collection_precondition_required')
    require(value['format'] == COMMAND_FORMAT, 'Unsupported collection command format')
    action = value['action']; require(action in ('create', 'rename', 'delete'), 'Unknown collection action')
    _fields(value, required | ({'name', 'description'} if action != 'delete' else set()))
    require(_match(SCOPE, value['workspace_id']), 'Workspace identity must be 32 lowercase hexadecimal characters')
    require(_match(TOKEN, value['request_id']), 'Request ID must contain 16–128 letters, digits, underscores or hyphens')
    if action != 'create':
        require(_match(ENTITY, value['id']), 'Invalid collection ID')
        require(type(value['expected_revision']) is int and 1 <= value['expected_revision'] <= MAX_REVISION,
                'Expected revision must be a positive safe integer')
    if action != 'delete':
        require(bool(_text(value['name'], 100, 'Collection name')), 'Give the collection a name')
        _text(value['description'], 1000, 'Description')
    bound = canonical_value(value)
    require(bound.bytes <= MAX_COMMAND_BYTES, 'Collection command exceeds 16 KiB')
    return bound


def _schema(db):
    rows = db.execute('SELECT singleton,version FROM collection_command_schema').fetchall()
    require(len(rows) == 1 and rows[0]['singleton'] == 1 and type(rows[0]['version']) is int and rows[0]['version'] == 1,
            'Collection schema is unsupported; no evidence was migrated or repaired',
            code='collection_schema_unsupported', status=503, recovery=RECOVERY)


def migrate(db):
    """Caller owns BEGIN IMMEDIATE and commit. DDL and marker are atomic."""
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    columns = {row['name'] for row in db.execute('PRAGMA table_info(collections)')}
    if 'collection_command_schema' in tables:
        _schema(db)
        require('revision' in columns and 'collection_commands_v1' in tables, 'Collection schema is incomplete',
                code='collection_storage_corrupt', status=503, recovery=RECOVERY)
        return
    require('revision' not in columns and 'collection_commands_v1' not in tables,
            'Unversioned collection evidence already exists; explicit recovery is required',
            code='collection_storage_corrupt', status=503, recovery=RECOVERY)
    db.execute('ALTER TABLE collections ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
    db.execute('''CREATE TABLE collection_commands_v1 (
        request_id TEXT PRIMARY KEY NOT NULL, version INTEGER NOT NULL, workspace_id TEXT NOT NULL,
        collection_id TEXT NOT NULL, command TEXT NOT NULL, command_sha256 TEXT NOT NULL,
        receipt TEXT NOT NULL, receipt_sha256 TEXT NOT NULL, bytes INTEGER NOT NULL)''')
    db.execute('CREATE TABLE collection_command_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)')
    db.execute('INSERT INTO collection_command_schema VALUES (1,1)')


class CollectionCommands:
    def __init__(self, workspace):
        self.workspace = workspace  # No migration, cached identity, read or write here.

    def _scope(self, db, expected):
        _schema(db)
        try: current = self.workspace._workspace_id(db)
        except ValueError as exc:
            raise CollectionError('Workspace identity is unavailable', code='collection_storage_corrupt',
                                  status=503, recovery=RECOVERY) from exc
        require(expected is None or expected == current, 'This command belongs to a different Workspace; nothing changed',
                code='collection_workspace_conflict', status=409, workspace_id=current)
        return current

    @staticmethod
    def _current(db, key):
        row = db.execute('SELECT id,name,description,revision FROM collections WHERE id=?', (key,)).fetchone()
        if row is None: return None
        try:
            require(_match(ENTITY, row['id']), 'Invalid stored collection ID')
            require(type(row['revision']) is int and 1 <= row['revision'] <= MAX_REVISION, 'Invalid stored collection revision')
            require(bool(_text(row['name'], 100, 'Stored name')), 'Invalid stored collection name')
            _text(row['description'], 1000, 'Stored description')
            return dict(row)
        except (ValueError, TypeError, KeyError) as exc:
            raise CollectionError('Stored collection state is invalid; no repair was attempted',
                                  code='collection_storage_corrupt', status=503, recovery=RECOVERY) from exc

    def _receipt(self, db, request_id, scope):
        # Refuse oversized rows before loading their text into Python. This and
        # the subsequent content read share the caller's transaction snapshot.
        row = db.execute('''SELECT request_id,version,workspace_id,collection_id,command_sha256,receipt_sha256,bytes,
            length(CAST(command AS BLOB)) AS command_bytes,length(CAST(receipt AS BLOB)) AS receipt_bytes
            FROM collection_commands_v1 WHERE request_id=?''', (request_id,)).fetchone()
        if row is None: return None
        try:
            require(type(row['version']) is int and row['version'] == 1, 'Unknown stored receipt version')
            require(row['workspace_id'] == scope and row['request_id'] == request_id, 'Stored scope/request differs')
            require(_match(ENTITY, row['collection_id']) and _match(SHA, row['command_sha256']) and _match(SHA, row['receipt_sha256']), 'Invalid stored identity')
            require(0 < row['command_bytes'] <= MAX_COMMAND_BYTES and 0 < row['receipt_bytes'] <= MAX_RECEIPT_BYTES, 'Stored evidence exceeds its bound')
            require(type(row['bytes']) is int and row['bytes'] == row['command_bytes'] + row['receipt_bytes'], 'Stored byte accounting differs')
            data = db.execute('SELECT command,receipt FROM collection_commands_v1 WHERE request_id=?', (request_id,)).fetchone()
            request = exact_stored_value(data['command'], row['command_sha256'], max_bytes=MAX_COMMAND_BYTES)
            receipt = exact_stored_value(data['receipt'], row['receipt_sha256'], max_bytes=MAX_RECEIPT_BYTES)
            require(request.matches and receipt.matches, 'Stored evidence digest differs')
            bound = bind_command(request.value)
            require(bound.raw == request.raw and canonical_value(receipt.value).raw == receipt.raw, 'Stored evidence is not canonical')
            require(request.value['workspace_id'] == scope and request.value['request_id'] == request_id, 'Stored command differs')
            self._validate_receipt(receipt.value, request.value, row['command_sha256'], row['collection_id'])
            return {'command': request, 'receipt': receipt}
        except (ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
            raise CollectionError('Stored collection command evidence is invalid; retain it for inspection',
                                  code='collection_storage_corrupt', status=503, recovery=RECOVERY) from exc

    @staticmethod
    def _validate_receipt(receipt, command, request_sha, collection_id):
        _fields(receipt, ('format', 'workspace_id', 'request_id', 'request_sha256', 'action', 'status', 'result', 'affected_asset_count'))
        require(receipt['format'] == RECEIPT_FORMAT and receipt['status'] == 'committed', 'Invalid receipt type/status')
        require(receipt['request_sha256'] == request_sha and all(receipt[k] == command[k] for k in ('workspace_id', 'request_id', 'action')), 'Receipt command binding differs')
        result = receipt['result']; _fields(result, ('id', 'name', 'description', 'revision', 'deleted'))
        require(result['id'] == collection_id and (command['action'] == 'create' or result['id'] == command['id']), 'Receipt collection differs')
        revision = 1 if command['action'] == 'create' else command['expected_revision'] + 1
        require(type(result['revision']) is int and result['revision'] == revision and revision <= MAX_REVISION, 'Receipt revision differs')
        require(type(result['deleted']) is bool and result['deleted'] == (command['action'] == 'delete'), 'Receipt deletion differs')
        require(bool(_text(result['name'], 100, 'Receipt name')), 'Receipt name is empty')
        _text(result['description'], 1000, 'Receipt description')
        if command['action'] != 'delete':
            require(result['name'] == command['name'].strip() and result['description'] == command['description'].strip(), 'Receipt result differs from command')
        count = receipt['affected_asset_count']
        require(type(count) is int and 0 <= count <= MAX_REVISION and (command['action'] == 'delete' or count == 0), 'Invalid affected asset count')

    @staticmethod
    def _budget(db, added):
        row = db.execute('''SELECT COUNT(*) AS count,
            COALESCE(SUM(length(CAST(command AS BLOB))+length(CAST(receipt AS BLOB))),0) AS used,
            COALESCE(SUM(CASE WHEN typeof(bytes)!='integer' OR bytes!=length(CAST(command AS BLOB))+length(CAST(receipt AS BLOB))
                OR version!=1 OR length(CAST(command AS BLOB))>? OR length(CAST(receipt AS BLOB))>? THEN 1 ELSE 0 END),0) AS invalid
            FROM collection_commands_v1''', (MAX_COMMAND_BYTES, MAX_RECEIPT_BYTES)).fetchone()
        require(not row['invalid'], 'Collection journal accounting/version is invalid',
                code='collection_storage_corrupt', status=503, recovery=RECOVERY)
        require(row['count'] < MAX_RECEIPTS and byte_budget(row['used'], added, MAX_JOURNAL_BYTES).fits,
                'Collection journal is full; no receipts were pruned and no new command committed',
                code='collection_journal_full', status=507, recovery=RECOVERY)

    def _mutate(self, db, value, *, legacy=False):
        action = value['action']
        if action == 'create':
            key, revision = uuid.uuid4().hex, 1
            name, description = value['name'].strip(), value['description'].strip()
            db.execute('INSERT INTO collections (id,name,description,created_at,revision) VALUES (?,?,?,?,?)',
                       (key, name, description, time.time(), revision))
            affected = 0
        else:
            key = value['id']; current = self._current(db, key)
            require(current is not None, 'Collection not found', code='collection_not_found', status=404)
            if not legacy:
                head = compare_head(value['expected_revision'], current['revision'])
                require(head.matches, 'Collection changed; inspect current metadata before applying',
                        code='collection_revision_conflict', status=409, expected_revision=head.expected,
                        current_revision=head.current, current=current)
            require(current['revision'] < MAX_REVISION, 'Collection revision limit reached; nothing changed',
                    code='collection_revision_limit', status=409)
            revision = current['revision'] + 1; affected = 0
            name, description = current['name'], current['description']
            if action == 'rename':
                name, description = value['name'].strip(), value['description'].strip()
                db.execute('UPDATE collections SET name=?,description=?,revision=? WHERE id=?', (name, description, revision, key))
            else:
                counts = db.execute('''SELECT COUNT(*) AS members,COUNT(a.id) AS assets,
                    COALESCE(SUM(CASE WHEN typeof(a.metadata_revision)!='integer' OR a.metadata_revision<0 THEN 1 ELSE 0 END),0) AS invalid,
                    COALESCE(SUM(CASE WHEN a.metadata_revision>=? THEN 1 ELSE 0 END),0) AS overflow
                    FROM collection_assets m LEFT JOIN assets a ON m.asset_id=a.id WHERE m.collection_id=?''', (MAX_REVISION, key)).fetchone()
                require(counts['members'] == counts['assets'] and not counts['invalid'], 'Member asset revision/state is invalid',
                        code='collection_storage_corrupt', status=503, recovery=RECOVERY)
                require(not counts['overflow'], 'Asset revision limit reached; collection was preserved',
                        code='collection_asset_revision_limit', status=409)
                affected = counts['members']
                db.execute('UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id IN (SELECT asset_id FROM collection_assets WHERE collection_id=?)', (key,))
                db.execute('DELETE FROM collections WHERE id=?', (key,))
        return {'id': key, 'name': name, 'description': description, 'revision': revision, 'deleted': action == 'delete'}, affected

    def _result(self, db, stored, *, replayed):
        receipt = stored['receipt']; value = receipt.value
        observation = {}
        try: current = self._current(db, value['result']['id'])
        except CollectionError as exc:
            # A valid historical commit is not erased by a failed current read.
            current = None; observation['current_error'] = exc.response()
        return {'format': RESULT_FORMAT, 'workspace_id': value['workspace_id'], 'request_id': value['request_id'],
                'status': 'committed', 'receipt': value, 'receipt_json': receipt.raw.decode('utf-8'),
                'receipt_sha256': receipt.observed_sha256, 'replayed': replayed, 'current': current,
                **observation, 'generation_submitted': False}

    def command(self, value):
        bound = bind_command(value); value = bound.value
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            scope = self._scope(db, value['workspace_id'])
            previous = self._receipt(db, value['request_id'], scope)
            state = classify_request(None if previous is None else previous['command'].observed_sha256, bound.sha256)
            require(state is not RequestState.CONFLICT, 'Request ID already identifies different collection bytes',
                    code='collection_request_conflict', status=409, request_id=value['request_id'])
            if state is RequestState.REPLAY:
                require(previous['command'].raw == bound.raw, 'Request bytes differ', code='collection_request_conflict', status=409)
                return self._result(db, previous, replayed=True)
            result, affected = self._mutate(db, value)
            receipt = canonical_value({'format': RECEIPT_FORMAT, 'workspace_id': scope, 'request_id': value['request_id'],
                'request_sha256': bound.sha256, 'action': value['action'], 'status': 'committed',
                'result': result, 'affected_asset_count': affected})
            require(receipt.bytes <= MAX_RECEIPT_BYTES, 'Collection receipt exceeds its bound')
            self._budget(db, bound.bytes + receipt.bytes)
            db.execute('INSERT INTO collection_commands_v1 VALUES (?,?,?,?,?,?,?,?,?)',
                       (value['request_id'], 1, scope, result['id'], bound.raw.decode('utf-8'), bound.sha256,
                        receipt.raw.decode('utf-8'), receipt.sha256, bound.bytes + receipt.bytes))
            return self._result(db, self._receipt(db, value['request_id'], scope), replayed=False)

    def status(self, request_id, workspace_id):
        require(_match(TOKEN, request_id), 'Invalid collection request ID')
        require(_match(SCOPE, workspace_id), 'Workspace identity is required', code='collection_precondition_required', status=428)
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            scope = self._scope(db, workspace_id)
            stored = self._receipt(db, request_id, scope)
            if stored is not None: return self._result(db, stored, replayed=True)
            return {'format': RESULT_FORMAT, 'workspace_id': scope, 'request_id': request_id,
                    'status': 'unknown', 'receipt': None, 'receipt_json': None, 'receipt_sha256': None,
                    'current': None, 'generation_submitted': False,
                    'recovery': 'No receipt is visible in this read snapshot. An in-flight write may still commit. ' + RECOVERY}

    def legacy(self, value):
        """Explicit unscoped v0 compatibility, no idempotency/CAS guarantee."""
        require(isinstance(value, dict), 'Collection command must be an object')
        action = value.get('action', 'create')
        require(action in ('create', 'rename', 'delete'), 'Unknown collection action')
        command = {'action': action}
        if action != 'create':
            require(_match(ENTITY, value.get('id')), 'Invalid collection ID'); command['id'] = value['id']
        if action != 'delete':
            command['name'] = _text(value.get('name'), 100, 'Collection name')
            require(bool(command['name']), 'Give the collection a name')
            command['description'] = _text(value.get('description', ''), 1000, 'Description')
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE'); self._scope(db, None)
            result, _ = self._mutate(db, command, legacy=True)
        return ({'id': result['id'], 'deleted': True} if action == 'delete' else
                {key: result[key] for key in ('id', 'name', 'description')})
