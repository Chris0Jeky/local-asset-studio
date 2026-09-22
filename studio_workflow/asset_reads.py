"""Bounded catalogue observations in AssetWorkspace; no media or command authority.

Cursors bind one query to a catalogue revision. They are checksummed, not signed:
read positions are not credentials. Mutations expire continuation instead of
pretending that independent HTTP reads hold a historical SQLite snapshot.
"""
from __future__ import annotations

import base64
import codecs
import hashlib
import json
import math
import re
import sqlite3
import uuid

from .core import canonical, decode

MAX_REVISION = 2**53 - 1
MAX_PAGE = 100
MAX_SELECTION = 200
MAX_CURSOR = 2048
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ORDER = 'created_at_desc_id_desc'
ENTITY = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
HEX32 = re.compile(r'[0-9a-f]{32}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
DEFAULT_FILTERS = {'visibility':'active', 'media_type':None, 'review':None,
                   'favorite':None, 'collection_id':None}
REVIEWS = ('unreviewed','selected','needs_work','rejected')
DISPLAY_LIMITS = {'title':200, 'filename':256, 'preset_name':200}
EPOCH_VALID = "typeof(epoch)='text' AND length(epoch)=32 AND instr(epoch,char(0))=0 AND epoch NOT GLOB '*[^0-9a-f]*'"


def _projection(db):
    # CAST(TEXT AS BLOB) uses the database encoding, not Python's UTF-8 text
    # representation. Keep bounds and decoding local to this connection.
    encoding = {'UTF-8':'utf-8', 'UTF-16le':'utf-16-le', 'UTF-16be':'utf-16-be'}.get(
        db.execute('PRAGMA encoding').fetchone()[0])
    require(encoding is not None, 'Unsupported asset catalogue text encoding',
            code='asset_read_unavailable', status=503)
    width = 1 if encoding == 'utf-8' else 2
    # SQL bounds strings before they reach Python; no private JSON is decoded.
    return ','.join([
    f"'{encoding}' AS _text_encoding",
    *[f"CASE WHEN typeof(a.{key})='text' AND length(CAST(a.{key} AS BLOB))<={limit*width} "
      f"THEN a.{key} END AS {key}" for key,limit in
      {'id':128,'sha256':64,'media_type':32,'review':32,'preset_id':128}.items()],
    # SQLite's TEXT substr stops at NUL. Byte prefixes preserve labels and must
    # never silently turn a corrupt identity into another valid identity.
    *[f"CASE WHEN typeof(a.{key})='text' THEN substr(CAST(a.{key} AS BLOB),1,{4*(limit+1)}) END AS {key},"
      f"length(CAST(a.{key} AS BLOB)) AS {key}_bytes" for key,limit in DISPLAY_LIMITS.items()],
    *[f"CASE WHEN typeof(a.{key})='integer' THEN a.{key} END AS {key}"
      for key in ('bytes','metadata_revision','favorite')],
    *[f"CASE WHEN typeof(a.{key}) IN ('integer','real') THEN a.{key} END AS {key}"
      for key in ('created_at','trashed_at')],
    'a.preset_id IS NULL AS preset_id_null','a.trashed_at IS NULL AS trashed_at_null',
    ])


class AssetReadError(ValueError):
    def __init__(self, message, *, code='asset_read_invalid', status=400, **details):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details


def require(condition, message, **error):
    if not condition: raise AssetReadError(message, **error)


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _integer(value, minimum=0, maximum=MAX_REVISION):
    return type(value) is int and minimum <= value <= maximum


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def _state(db):
    try:
        rows = db.execute(f"""SELECT singleton,
            CASE WHEN typeof(version)='integer' THEN version END AS version,
            CASE WHEN {EPOCH_VALID} THEN epoch END AS epoch,
            CASE WHEN typeof(revision)='integer' THEN revision END AS revision
            FROM asset_read_state_v1 LIMIT 2""").fetchall()
        row = rows[0] if len(rows) == 1 and rows[0]['singleton'] == 1 else None
    except sqlite3.DatabaseError as exc:
        raise AssetReadError('Asset catalogue read state is unavailable', code='asset_read_unavailable', status=503) from exc
    require(row is not None and row['version'] == 1 and _matches(HEX32,row['epoch'])
            and _integer(row['revision']), 'Asset catalogue read state is invalid or unsupported',
            code='asset_read_unavailable', status=503)
    return {'epoch':row['epoch'], 'revision':row['revision']}


def migrate(db):
    """Called only inside AssetWorkspace's initialization writer transaction.

    This small change stamp owns no assets or receipts. Trigger increments roll
    back with their mutations and cover legacy SQL writers, including cascades.
    Its value is not a count of user commands (one command can touch many rows).
    """
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='asset_read_state_v1'").fetchone()
    if not exists:
        db.execute('''CREATE TABLE asset_read_state_v1 (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL,
            epoch TEXT NOT NULL, revision INTEGER NOT NULL
            CHECK(typeof(revision)='integer' AND revision BETWEEN 0 AND 9007199254740991))''')
        db.execute('INSERT INTO asset_read_state_v1 VALUES (1,1,?,0)', (uuid.uuid4().hex,))
    _state(db)  # Never reset an existing invalid/unknown state or reuse old cursors.
    db.execute('CREATE INDEX IF NOT EXISTS asset_read_order_v1 ON assets(created_at DESC,id DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS asset_read_active_v1 ON assets(created_at DESC,id DESC) WHERE trashed_at IS NULL')
    for table in ('assets','collections','collection_assets'):
        for action in ('INSERT','UPDATE','DELETE'):
            # Names come solely from the fixed schema above, never request input.
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS asset_read_{table}_{action.lower()}_v1
                AFTER {action} ON {table} BEGIN
                UPDATE asset_read_state_v1 SET revision=revision+1
                WHERE singleton=1 AND version=1 AND typeof(revision)='integer'
                AND revision BETWEEN 0 AND 9007199254740990
                AND {EPOCH_VALID};
                SELECT CASE WHEN changes()!=1 THEN RAISE(ABORT,'Asset catalogue read state unavailable') END;
                END''')


def normalize_filters(value=None):
    require(value is None or type(value) is dict, 'Asset filters must be an object')
    value = {} if value is None else value
    require(set(value) <= set(DEFAULT_FILTERS), 'Unsupported asset filter')
    result = dict(DEFAULT_FILTERS, **value)
    require(type(result['visibility']) is str and result['visibility'] in ('active','trash','all'), 'Invalid visibility filter')
    kind = result['media_type']
    require(kind is None or type(kind) is str and re.fullmatch(r'[a-z][a-z0-9_-]{0,31}',kind), 'Invalid media type filter')
    review = result['review']
    require(review is None or type(review) is str and review in REVIEWS, 'Invalid review filter')
    require(result['favorite'] is None or type(result['favorite']) is bool, 'Favorite filter must be boolean')
    require(result['collection_id'] is None or _matches(ENTITY,result['collection_id']), 'Invalid collection filter')
    return result


def selection_ids(value):
    require(type(value) is list and 1 <= len(value) <= MAX_SELECTION,
            'Supply between 1 and 200 selected asset IDs')
    require(all(_matches(ENTITY,item) for item in value), 'Invalid selected asset ID')
    require(len(set(value)) == len(value), 'Selected asset IDs must be unique; none were silently removed')
    return list(value)


def _cursor(value):
    error = {'code':'asset_cursor_invalid', 'status':400}
    require(type(value) is str and 0 < len(value) <= MAX_CURSOR
            and re.fullmatch(r'[A-Za-z0-9_-]+',value), 'Invalid asset cursor', **error)
    try:
        raw = base64.b64decode(value + '='*((-len(value))%4), altchars=b'-_', validate=True)
        envelope = decode(raw.decode('utf-8'))
        require(type(envelope) is dict and set(envelope) == {'position','sha256'}, 'Invalid asset cursor', **error)
        body = envelope['position']
        require(type(body) is dict and set(body) == {'format','workspace_id','catalogue','query_sha256','limit','last'},
                'Invalid asset cursor position', **error)
        require(canonical(envelope) == raw and envelope['sha256'] == hashlib.sha256(canonical(body)).hexdigest(),
                'Asset cursor checksum mismatch', **error)
        stamp, last = body['catalogue'], body['last']
        require(body['format'] == 'studio.asset-cursor/v1' and _matches(HEX32,body['workspace_id'])
                and _matches(HEX64,body['query_sha256']) and _integer(body['limit'],1,MAX_PAGE)
                and type(stamp) is dict and set(stamp) == {'epoch','revision'}
                and _matches(HEX32,stamp['epoch']) and _integer(stamp['revision'])
                and type(last) is list and len(last) == 2 and _finite(last[0]) and _matches(ENTITY,last[1]),
                'Invalid asset cursor values', **error)
        return body
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        if isinstance(exc,AssetReadError): raise
        raise AssetReadError('Invalid asset cursor encoding', **error) from exc


def _encode_cursor(scope, stamp, query_hash, limit, asset):
    body = {'format':'studio.asset-cursor/v1', 'workspace_id':scope, 'catalogue':stamp,
            'query_sha256':query_hash, 'limit':limit, 'last':[asset['created_at'],asset['id']]}
    envelope = {'position':body,'sha256':hashlib.sha256(canonical(body)).hexdigest()}
    return base64.urlsafe_b64encode(canonical(envelope)).decode('ascii').rstrip('=')


def _summary(row):
    value = dict(row)
    encoding = value.pop('_text_encoding')
    preset_null, trashed_null = value.pop('preset_id_null'), value.pop('trashed_at_null')
    error = {'code':'asset_read_unavailable','status':503}
    require(_matches(ENTITY,value['id']) and _matches(HEX64,value['sha256'])
            and type(value['media_type']) is str and 1 <= len(value['media_type']) <= 32
            and value['review'] in REVIEWS and value['favorite'] in (0,1)
            and _finite(value['created_at']) and _integer(value['bytes'])
            and _integer(value['metadata_revision'])
            and ((value['trashed_at'] is None and trashed_null == 1) or _finite(value['trashed_at']))
            and ((value['preset_id'] is None and preset_null == 1) or _matches(ENTITY,value['preset_id'])),
            'An asset summary has invalid identity or scalar metadata', **error)
    value['truncated_fields'] = []
    for key,limit in DISPLAY_LIMITS.items():
        raw, size = value[key], value.pop(key+'_bytes')
        if key == 'preset_name' and raw is None and size is None: continue
        require(type(raw) is bytes and _integer(size) and size >= len(raw),
                'An asset display label is invalid', **error)
        try:
            # A bounded prefix may end within a valid Unicode scalar. A complete
            # value must decode completely; only a genuinely cut tail is pending.
            text = codecs.getincrementaldecoder(encoding)().decode(raw,final=size==len(raw))
        except UnicodeError as exc:
            raise AssetReadError('An asset display label has invalid text encoding', **error) from exc
        if len(text) > limit or size > len(raw): value['truncated_fields'].append(key)
        value[key] = text[:limit]
    value['favorite'] = bool(value['favorite'])
    value['url'] = '/api/assets/' + value['id'] + '/file'
    return value


def _result(kind, scope, stamp, **value):
    result = {'format':'studio.asset-'+kind+'/v1','workspace_id':scope,'catalogue':stamp,
              **value,'observation_only':True,'media_bytes_verified':False,'generation_submitted':False}
    # Match the existing Handler's default JSON escaping, not a smaller hypothetical encoding.
    require(len(json.dumps(result,allow_nan=False).encode('utf-8')) <= MAX_RESPONSE_BYTES,
            'Asset observation exceeds its response bound', code='asset_read_unavailable',status=503)
    return result


class AssetReads:
    def __init__(self, workspace):
        self.workspace = workspace

    def page(self, *, workspace_id=None, limit=50, cursor=None, filters=None):
        require(_integer(limit,1,MAX_PAGE),'Page size must be an integer between 1 and 100')
        query = normalize_filters(filters)
        query_hash = hashlib.sha256(canonical(query)).hexdigest()
        position = _cursor(cursor) if cursor is not None else None
        if workspace_id is not None: self.workspace._validate_scope(workspace_id)
        if position is not None:
            require(position['limit'] == limit and position['query_sha256'] == query_hash,
                    'Cursor belongs to different filters or page size; explicitly refresh',
                    code='asset_cursor_mismatch',status=409)
            if workspace_id is not None:
                require(position['workspace_id'] == workspace_id, 'Cursor belongs to another Workspace',
                        code='asset_workspace_conflict',status=409)
            workspace_id = position['workspace_id']
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db,workspace_id)
            stamp = _state(db)
            if position is not None:
                require(position['catalogue'] == stamp, 'Asset catalogue changed; explicitly refresh this query',
                        code='asset_cursor_stale',status=409)
            clauses, params = [], []
            if query['visibility'] != 'all':
                clauses.append('a.trashed_at IS ' + ('NULL' if query['visibility']=='active' else 'NOT NULL'))
            for key in ('media_type','review','favorite'):
                if query[key] is not None: clauses.append('a.'+key+'=?'); params.append(query[key])
            if query['collection_id'] is not None:
                require(db.execute('SELECT 1 FROM collections WHERE id=?',(query['collection_id'],)).fetchone() is not None,
                        'The selected collection no longer exists',code='asset_collection_unavailable',status=409)
                clauses.append('EXISTS (SELECT 1 FROM collection_assets AS ca WHERE ca.collection_id=? AND ca.asset_id=a.id)')
                params.append(query['collection_id'])
            if position is not None:
                clauses.append('(a.created_at,a.id)<(?,?)'); params.extend(position['last'])
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            rows = db.execute('SELECT '+_projection(db)+' FROM assets AS a'+where+
                              ' ORDER BY a.created_at DESC,a.id DESC LIMIT ?',[*params,limit+1]).fetchall()
            items = [_summary(row) for row in rows[:limit]]
            next_cursor = _encode_cursor(scope,stamp,query_hash,limit,items[-1]) if len(rows)>limit else None
            return _result('page',scope,stamp,filters=query,order=ORDER,limit=limit,assets=items,next_cursor=next_cursor)

    def selection(self, ids, *, workspace_id):
        ids = selection_ids(ids)
        self.workspace._validate_scope(workspace_id)
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db,workspace_id)
            stamp = _state(db)
            marks = ','.join('?' for _ in ids)
            rows = db.execute('SELECT '+_projection(db)+' FROM assets AS a WHERE a.id IN ('+marks+')',ids)
            found = {row['id']:_summary(row) for row in rows}
            items = []
            for key in ids:
                asset = found.get(key)
                state = 'missing' if asset is None else 'active' if asset['trashed_at'] is None else 'trashed'
                items.append({'id':key,'state':state,'asset':asset})
            return _result('selection',scope,stamp,items=items)
