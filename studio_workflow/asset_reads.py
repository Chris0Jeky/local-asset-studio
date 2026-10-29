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
MAX_CURSOR = 12288  # 1,024 title characters, six-byte JSON escapes, envelope and base64.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ORDER = 'created_at_desc_id_desc'
SORTS = {'newest':('a.created_at','DESC','<',ORDER),
         'oldest':('a.created_at','ASC','>','created_at_asc_id_asc'),
         'title':('a.title COLLATE NOCASE','ASC','>','title_nocase_asc_id_asc')}
ENTITY = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
HEX32 = re.compile(r'[0-9a-f]{32}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
DEFAULT_FILTERS = {'visibility':'active', 'media_type':None, 'review':None,
                   'favorite':None, 'collection_id':None}
FILTER_KEYS = (*DEFAULT_FILTERS, 'source', 'job_id', 'privacy', 'archive')
REVIEWS = ('unreviewed','selected','needs_work','rejected')
DISPLAY_LIMITS = {'title':200, 'filename':256, 'preset_name':200}
EPOCH_VALID = "typeof(epoch)='text' AND length(epoch)=32 AND instr(epoch,char(0))=0 AND epoch NOT GLOB '*[^0-9a-f]*'"


def _text_encoding(db):
    # CAST(TEXT AS BLOB) uses the database encoding, not Python's UTF-8 text
    # representation. Keep bounds and decoding local to this connection.
    encoding = {'UTF-8':'utf-8', 'UTF-16le':'utf-16-le', 'UTF-16be':'utf-16-be'}.get(
        db.execute('PRAGMA encoding').fetchone()[0])
    require(encoding is not None, 'Unsupported asset catalogue text encoding',
            code='asset_read_unavailable', status=503)
    return encoding


def _projection(db):
    encoding = _text_encoding(db)
    width = 1 if encoding == 'utf-8' else 2
    # SQL bounds strings before they reach Python; no private JSON is decoded.
    return ','.join([
    f"'{encoding}' AS _text_encoding",
    *[f"CASE WHEN typeof(a.{key})='text' AND length(CAST(a.{key} AS BLOB))<={limit*width} "
      f"THEN CAST(a.{key} AS BLOB) END AS {key}" for key,limit in
      {'id':128,'sha256':64,'media_type':32,'review':32,'preset_id':128,'privacy':7}.items()],
    # SQLite's TEXT substr stops at NUL. Byte prefixes preserve labels and must
    # never silently turn a corrupt identity into another valid identity.
    *[f"CASE WHEN typeof(a.{key})='text' THEN coalesce(substr(CAST(a.{key} AS BLOB),1,{4*(limit+1)}),X'') END AS {key},"
      f"length(CAST(a.{key} AS BLOB)) AS {key}_bytes" for key,limit in DISPLAY_LIMITS.items()],
    *[f"CASE WHEN typeof(a.{key})='integer' THEN a.{key} END AS {key}"
      for key in ('bytes','metadata_revision','favorite')],
    *[f"CASE WHEN typeof(a.{key}) IN ('integer','real') THEN a.{key} END AS {key}"
      for key in ('created_at','trashed_at','archived_at')],
    'a.preset_id IS NULL AS preset_id_null','a.trashed_at IS NULL AS trashed_at_null',
    'a.archived_at IS NULL AS archived_at_null',
    ])


class AssetReadError(ValueError):
    def __init__(self, message, *, code='asset_read_invalid', status=400, **details):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details


def require(condition, message, **error):
    if not condition: raise AssetReadError(message, **error)


def privacy_scope(value):
    require(type(value) is str and value in ('regular','private','all'), 'Invalid privacy scope', code='privacy_invalid')
    return value


def privacy_matches(value, scope):
    return type(value) is str and value in ('regular','private') and (scope == 'all' or value == scope)


def privacy_sql(scope, prefix=''):
    privacy_scope(scope)
    return (prefix+"privacy IN ('regular','private')", []) if scope == 'all' else (prefix+'privacy=?', [scope])


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _is_media_type(value):
    # One reader/writer contract for legacy stored values: the bounded read
    # projection lists decoded text of 1..32 characters, so the exact filter
    # must accept that same value space instead of a narrower legacy pattern.
    # Control characters stay refused on both sides; they cannot be selected
    # and a stored one keeps the documented asset_read_unavailable refusal.
    return type(value) is str and 1 <= len(value) <= 32 and value.isprintable()


def _integer(value, minimum=0, maximum=MAX_REVISION):
    return type(value) is int and minimum <= value <= maximum


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def _state(db, privacy='regular'):
    privacy_scope(privacy)
    column = 'revision' if privacy == 'all' else privacy+'_revision'
    try:
        rows = db.execute(f"""SELECT singleton,
            CASE WHEN typeof(version)='integer' THEN version END AS version,
            CASE WHEN {EPOCH_VALID} THEN epoch END AS epoch,
            CASE WHEN typeof(revision)='integer' THEN revision END AS all_revision,
            CASE WHEN typeof({column})='integer' THEN {column} END AS revision
            FROM asset_read_state_v1 LIMIT 2""").fetchall()
        row = rows[0] if len(rows) == 1 and rows[0]['singleton'] == 1 else None
    except sqlite3.DatabaseError as exc:
        raise AssetReadError('Asset catalogue read state is unavailable', code='asset_read_unavailable', status=503) from exc
    require(row is not None and row['version'] == 1 and _matches(HEX32,row['epoch'])
            and _integer(row['all_revision']) and _integer(row['revision']), 'Asset catalogue read state is invalid or unsupported',
            code='asset_read_unavailable', status=503)
    # Scope epochs invalidate legacy global cursors once, without exposing old
    # global mutation counts. Replacing the base epoch still expires every scope.
    epoch = row['epoch'] if privacy == 'all' else hashlib.sha256((row['epoch']+':'+privacy).encode()).hexdigest()[:32]
    return {'epoch':epoch, 'revision':row['revision']}


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
    _state(db, 'all')  # Never reset an existing invalid/unknown state or reuse old cursors.
    columns = {row['name'] for row in db.execute('PRAGMA table_info(asset_read_state_v1)')}
    for privacy in ('regular','private'):
        column = privacy+'_revision'
        if column not in columns:
            db.execute(f'''ALTER TABLE asset_read_state_v1 ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0
                CHECK(typeof({column})='integer' AND {column} BETWEEN 0 AND 9007199254740991)''')
        _state(db, privacy)
    db.execute('CREATE INDEX IF NOT EXISTS asset_read_order_v1 ON assets(created_at DESC,id DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS asset_read_active_v1 ON assets(created_at DESC,id DESC) WHERE trashed_at IS NULL')
    db.execute('CREATE INDEX IF NOT EXISTS asset_read_job_v1 ON assets(job_id,created_at DESC,id DESC)')
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
            # The global stamp remains available only in explicit All reads.
            # Memberships affect a scoped view only when both endpoints are in
            # that scope. Parent deletes already invalidate their own scope,
            # including cascades whose parent is absent from this AFTER trigger.
            records = ('NEW',) if action == 'INSERT' else ('OLD',) if action == 'DELETE' else ('OLD','NEW')
            for privacy in ('regular','private'):
                if table == 'collection_assets':
                    predicate = ' OR '.join(f'''EXISTS(SELECT 1 FROM assets a JOIN collections c
                        ON c.id={record}.collection_id WHERE a.id={record}.asset_id
                        AND a.privacy='{privacy}' AND c.privacy='{privacy}')''' for record in records)
                else:
                    predicate = ' OR '.join(f"{record}.privacy='{privacy}'" for record in records)
                column = privacy+'_revision'
                db.execute(f'''CREATE TRIGGER IF NOT EXISTS asset_read_{table}_{action.lower()}_{privacy}_v1
                    AFTER {action} ON {table} WHEN {predicate} BEGIN
                    UPDATE asset_read_state_v1 SET {column}={column}+1
                    WHERE singleton=1 AND version=1 AND typeof({column})='integer'
                    AND {column} BETWEEN 0 AND 9007199254740990 AND {EPOCH_VALID};
                    SELECT CASE WHEN changes()!=1 THEN RAISE(ABORT,'Asset catalogue read state unavailable') END;
                    END''')


def normalize_filters(value=None):
    require(value is None or type(value) is dict, 'Asset filters must be an object')
    value = {} if value is None else value
    require(set(value) <= set(FILTER_KEYS), 'Unsupported asset filter')
    result = dict(DEFAULT_FILTERS, **value)
    archive = result.pop('archive', 'active')
    require(type(archive) is str and archive in ('active','archived','all'), 'Invalid archive filter')
    # Unarchived legacy pages keep their query shape. Explicit alternatives bind cursors.
    if archive != 'active': result['archive'] = archive
    source = result.pop('source', 'all')
    require(type(source) is str and source in ('all', 'mine', 'agent'), 'Invalid source filter')
    # Omitted/All keeps the original response shape and cursor identity.
    if source != 'all': result['source'] = source
    privacy = privacy_scope(result.pop('privacy', 'regular'))
    # Keep regular legacy query/cursor identity; non-default scopes remain bound.
    if privacy != 'regular': result['privacy'] = privacy
    job = result.pop('job_id', None)
    require(job is None or type(job) is str and 1 <= len(job) <= 128 and job.isprintable(), 'Invalid job filter')
    if job is not None: result['job_id'] = job
    require(type(result['visibility']) is str and result['visibility'] in ('active','trash','all'), 'Invalid visibility filter')
    kind = result['media_type']
    require(kind is None or _is_media_type(kind), 'Invalid media type filter')
    review = result['review']
    require(review is None or type(review) is str and review in REVIEWS, 'Invalid review filter')
    require(result['favorite'] is None or type(result['favorite']) is bool, 'Favorite filter must be boolean')
    require(result['collection_id'] is None or _matches(ENTITY,result['collection_id']), 'Invalid collection filter')
    return result


def page_options(q, sort):
    require(q is None or type(q) is str and 1 <= len(q) <= 200 and q.strip() and '\0' not in q,
            'Search must be nonempty text of at most 200 characters without NUL')
    require(type(sort) is str and sort in SORTS, 'Sort must be newest, oldest or title')
    if q is not None:
        try: q.encode('utf-8')
        except UnicodeError as exc: raise AssetReadError('Invalid search text encoding') from exc


def page_query_hash(filters, q, sort):
    # Preserve the original default query identity for existing read-only clients.
    query = dict(filters)
    if q is not None: query['q'] = q
    if sort != 'newest': query['sort'] = sort
    return hashlib.sha256(canonical(query)).hexdigest()


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
                and type(last) is list and len(last) == 2
                and (_finite(last[0]) or type(last[0]) is str and len(last[0]) <= 4096) and _matches(ENTITY,last[1]),
                'Invalid asset cursor values', **error)
        return body
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        if isinstance(exc,AssetReadError): raise
        raise AssetReadError('Invalid asset cursor encoding', **error) from exc


def _encode_cursor(scope, stamp, query_hash, limit, asset, key=None):
    body = {'format':'studio.asset-cursor/v1', 'workspace_id':scope, 'catalogue':stamp,
            'query_sha256':query_hash, 'limit':limit, 'last':[asset['created_at'] if key is None else key,asset['id']]}
    envelope = {'position':body,'sha256':hashlib.sha256(canonical(body)).hexdigest()}
    cursor = base64.urlsafe_b64encode(canonical(envelope)).decode('ascii').rstrip('=')
    require(len(cursor) <= MAX_CURSOR, 'Asset sort key exceeds its cursor bound',code='asset_read_unavailable',status=503)
    return cursor


def _summary(row):
    value = dict(row)
    encoding = value.pop('_text_encoding')
    preset_null, trashed_null = value.pop('preset_id_null'), value.pop('trashed_at_null')
    archived_null = value.pop('archived_at_null')
    error = {'code':'asset_read_unavailable','status':503}
    # Decode bounded scalar bytes here, not in SQLite's implicit TEXT converter.
    # Corrupt stored text must become the same typed refusal as other bad metadata.
    for key in ('id','sha256','media_type','review','preset_id','privacy'):
        raw = value[key]
        if raw is None: continue
        require(type(raw) is bytes, 'An asset scalar is not text', **error)
        try:
            value[key] = raw.decode(encoding)
        except UnicodeError as exc:
            raise AssetReadError('An asset scalar has invalid text encoding', **error) from exc
    require(_matches(ENTITY,value['id']) and _matches(HEX64,value['sha256']) and value['privacy'] in ('regular','private')
            and _is_media_type(value['media_type'])
            and value['review'] in REVIEWS and value['favorite'] in (0,1)
            and _finite(value['created_at']) and _integer(value['bytes'])
            and _integer(value['metadata_revision'])
            and ((value['trashed_at'] is None and trashed_null == 1) or _finite(value['trashed_at']))
            and ((value['archived_at'] is None and archived_null == 1) or _finite(value['archived_at']) and value['archived_at'] >= 0)
            and ((value['preset_id'] is None and preset_null == 1) or _matches(ENTITY,value['preset_id'])),
            'An asset summary has invalid identity or scalar metadata', **error)
    if value['archived_at'] is None: value.pop('archived_at')
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
    if value['privacy'] == 'private': value['url'] += '?privacy=private'
    else: value.pop('privacy')  # Additive private label; retain existing regular summary shape.
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

    def page(self, *, workspace_id=None, limit=50, cursor=None, filters=None, details=False, q=None, sort='newest',
             include_collections=False, reanchor=False):
        require(type(details) is bool, 'Details must be boolean')
        require(type(include_collections) is bool and type(reanchor) is bool, 'Page options must be boolean')
        require(_integer(limit,1,MAX_PAGE),'Page size must be an integer between 1 and 100')
        query = normalize_filters(filters)
        page_options(q,sort)
        query_hash = page_query_hash(query,q,sort)
        sort_key, direction, comparison, order = SORTS[sort]
        position = _cursor(cursor) if cursor is not None else None
        if workspace_id is not None: self.workspace._validate_scope(workspace_id)
        if position is not None:
            require(position['limit'] == limit and position['query_sha256'] == query_hash,
                    'Cursor belongs to different filters, search, sort or page size; explicitly refresh',
                    code='asset_cursor_mismatch',status=409)
            if workspace_id is not None:
                require(position['workspace_id'] == workspace_id, 'Cursor belongs to another Workspace',
                        code='asset_workspace_conflict',status=409)
            workspace_id = position['workspace_id']
            require(type(position['last'][0]) is str if sort == 'title' else _finite(position['last'][0]),
                    'Invalid cursor sort key',code='asset_cursor_invalid')
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db,workspace_id)
            privacy = query.get('privacy', 'regular')
            stamp = _state(db, privacy)
            if position is not None:
                compatible = position['catalogue'] == stamp or reanchor and position['catalogue']['epoch'] == stamp['epoch'] \
                    and position['catalogue']['revision'] <= stamp['revision']
                require(compatible, 'Asset catalogue changed; explicitly refresh this query',
                        code='asset_cursor_stale',status=409)
            privacy_clause, params = privacy_sql(privacy, 'a.')
            clauses = [privacy_clause]
            archive = query.get('archive', 'active')
            if archive != 'all':
                clauses.append('a.archived_at IS ' + ('NULL' if archive == 'active' else 'NOT NULL'))
            if query.get('source') in ('mine', 'agent'):
                # Match assetIsAgentRun exactly: Make labels are the owner's runs.
                # substr equality stays case-sensitive, unlike SQLite's default LIKE.
                agent = "(typeof(a.run_label)='text' AND a.run_label<>'' AND substr(a.run_label,1,7)<>'Make · ')"
                clauses.append(agent if query['source'] == 'agent' else 'NOT ' + agent)
            if query['visibility'] != 'all':
                clauses.append('a.trashed_at IS ' + ('NULL' if query['visibility']=='active' else 'NOT NULL'))
            for key in ('media_type','review','favorite'):
                if query[key] is not None: clauses.append('a.'+key+'=?'); params.append(query[key])
            if 'job_id' in query: clauses.append('a.job_id=?'); params.append(query['job_id'])
            if query['collection_id'] is not None:
                collection_clause, collection_params = privacy_sql(privacy)
                require(db.execute('SELECT 1 FROM collections WHERE id=? AND '+collection_clause,[query['collection_id'],*collection_params]).fetchone() is not None,
                        'The selected collection no longer exists',code='asset_collection_unavailable',status=409)
                clauses.append('EXISTS (SELECT 1 FROM collection_assets AS ca WHERE ca.collection_id=? AND ca.asset_id=a.id)')
                params.append(query['collection_id'])
            if q is not None:
                # LIKE metacharacters are literal search text; all values stay bound.
                pattern = '%' + q.lower().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
                db.create_function('asset_search_text',1,lambda value: value.lower() if type(value) is str else '',deterministic=True)
                fields = ('title','filename','preset_name','notes','run_label','prompt_excerpt')
                matches = ["asset_search_text(a."+field+") LIKE ? ESCAPE '\\'" for field in fields]
                matches.append("EXISTS (SELECT 1 FROM json_each(CASE WHEN json_valid(a.tags) THEN a.tags ELSE '[]' END) AS tag "
                               "WHERE tag.type='text' AND asset_search_text(tag.value) LIKE ? ESCAPE '\\')")
                clauses.append('('+' OR '.join(matches)+')');params.extend([pattern]*len(matches))
            if position is not None:
                clauses.append('('+sort_key+',a.id)'+comparison+'(?,?)'); params.extend(position['last'])
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            projection = _projection(db)
            if sort == 'title': projection += ',CASE WHEN length(CAST(a.title AS BLOB))<=4096 THEN CAST(a.title AS BLOB) END AS _sort_title'
            rows = db.execute('SELECT '+projection+' FROM assets AS a'+where+
                              ' ORDER BY '+sort_key+' '+direction+',a.id '+direction+' LIMIT ?',[*params,limit+1]).fetchall()
            summaries, keys = [], []
            for row in rows[:limit]:
                value = dict(row)
                last_key = None
                if sort == 'title':
                    raw = value.pop('_sort_title')
                    require(type(raw) is bytes, 'Asset title sort key is invalid or exceeds its bound',code='asset_read_unavailable',status=503)
                    try: last_key = raw.decode(value['_text_encoding'])
                    except UnicodeError as exc: raise AssetReadError('Invalid title sort key encoding',code='asset_read_unavailable',status=503) from exc
                summaries.append(_summary(value)); keys.append(last_key)
            extra = {}
            if details or include_collections or reanchor:
                extra['cursor'] = _encode_cursor(scope,stamp,query_hash,limit,
                    {'id':position['last'][1],'created_at':position['last'][0]},position['last'][0]) if position else None
            if include_collections:
                extra['collection_page'] = self.workspace._collection_page(db,scope,stamp,limit=100,privacy=privacy)
            count = len(summaries)
            if details:
                unavailable = []
                projected = self.workspace._library_assets(db,summaries,scope,unavailable=unavailable,privacy=privacy)
                by_id = {a['id']:a for a in projected}; errors = {e['id']:e for e in unavailable}
                items, extra['unavailable_assets'], count = [], [], 0
                # Preserve a prefix of observed rows, including unavailable IDs.
                # Reserve the maximum next-cursor size; full editor fields are never cut.
                empty = _result('page',scope,stamp,filters=query,order=order,limit=limit,assets=[],next_cursor=None,**extra)
                used = len(json.dumps(empty,allow_nan=False).encode('utf-8')) + MAX_CURSOR + 8
                for summary in summaries:
                    identifier = summary['id']; item = by_id.get(identifier,errors.get(identifier))
                    size = len(json.dumps(item,allow_nan=False).encode('utf-8')) + 2
                    if used + size > MAX_RESPONSE_BYTES: break
                    (items if identifier in by_id else extra['unavailable_assets']).append(item)
                    used += size; count += 1
                require(not summaries or count > 0, 'An asset observation exceeds its response bound',
                        code='asset_read_unavailable',status=503)
            else: items = summaries
            next_cursor = _encode_cursor(scope,stamp,query_hash,limit,summaries[count-1],keys[count-1]) if len(rows)>count else None
            return _result('page',scope,stamp,filters=query,order=order,limit=limit,assets=items,next_cursor=next_cursor,**extra)

    def selection(self, ids, *, workspace_id, details=False, privacy='regular'):
        require(type(details) is bool, 'Details must be boolean')
        clause, params = privacy_sql(privacy, 'a.')
        ids = selection_ids(ids)
        self.workspace._validate_scope(workspace_id)
        with self.workspace.connection() as db:
            db.execute('BEGIN')
            scope = self.workspace._check_scope(db,workspace_id)
            stamp = _state(db, privacy)
            marks = ','.join('?' for _ in ids)
            rows = db.execute('SELECT '+_projection(db)+' FROM assets AS a WHERE a.id IN ('+marks+') AND '+clause,[*ids,*params])
            found = {item['id']:item for item in map(_summary,rows)}
            if details: found = {item['id']:item for item in self.workspace._library_assets(db,list(found.values()),scope,privacy=privacy)}
            items = []
            for key in ids:
                asset = found.get(key)
                state = 'missing' if asset is None else 'active' if asset['trashed_at'] is None else 'trashed'
                items.append({'id':key,'state':state,'asset':asset})
            return _result('selection',scope,stamp,items=items)
