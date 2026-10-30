"""Persistent asset organization and immutable local output snapshots.

Comfy outputs remain untouched. Trash is reversible metadata, shared by every
browser using this experiments directory. SQLite transactions make bulk edits
atomic; a content-addressed file store keeps media available between backends.
"""
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class WorkspaceError(ValueError):
    status = 400
    code = "invalid_asset_command"

    def __init__(self, message, *, status=None, code=None, **details):
        super().__init__(message)
        self.status = status or self.status
        self.code = code or self.code
        self.details = details

    def response(self):
        return {"error": str(self), "code": self.code, **self.details}


WAL_INITIALIZATION_TIMEOUT = 15
_INITIALIZATION_LOCK = threading.Lock()
MAX_REVISION = 2**53 - 1
# register() copies a job name (AV project names reach 1,000 characters) into the initial title; the
# edit limit is 200. Conflict projections in app/static/workspace.js accept up to this bound.
REGISTERED_TITLE_MAX = 1024
# The editor-conflict envelope: the editor, its conflict projection and the recovery shelf validate exactly these keys.
# run_label is not an editor field; it travels in the receipt's applied values and in every full asset read (#939).
METADATA_FIELDS = ("id", "title", "notes", "tags", "favorite", "review", "trashed_at", "archived_at", "metadata_revision")
# Additive, nullable asset columns: a Workspace created before them opens unchanged and its assets read as NULL (#939).
ADDITIVE_COLUMNS = ("run_label", "prompt_excerpt")
PROMPT_EXCERPT_CHARS = 60
RUN_LABEL_MAX = 80
# Quick review checks (#1203): one owner answer per check, stored as a `check:<name>=yes|no` tag so it saves with the
# asset's revisioned review. The page picks which checks a recipe route shows; absent means not checked (K14).
REVIEW_CHECKS = ("pose", "face", "outfit", "style", "clean", "anatomy", "composition", "silhouette", "hands", "depth", "palette")
CHECK_TAG = re.compile(r"check:(%s)=(yes|no)" % "|".join(REVIEW_CHECKS))
# Cards (#1221, #1205): named, revisioned Workspace records that are not pictures. `body` is the kind's JSON (a look's wording
# template and recipe, app/looks.py; a character's words, app/characters.py), `lineage` the pictures it came from.
CARD_KINDS = ("look", "character", "brief")
CARD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,127}")
CARD_BODY_MAX = 64 * 1024
CARD_LINEAGE_MAX = 20


def privacy_scope(value, *, creation=False):
    choices = ('regular', 'private') if creation else ('regular', 'private', 'all')
    if type(value) is not str or value not in choices:
        raise WorkspaceError('Choose a valid creation privacy' if creation else 'Choose a valid privacy scope', code='privacy_invalid')
    return value


def privacy_matches(value, scope):
    return type(value) is str and value in ('regular', 'private') and (scope == 'all' or value == scope)


def privacy_sql(scope, prefix=''):
    privacy_scope(scope)
    return (prefix+"privacy IN ('regular','private')", []) if scope == 'all' else (prefix+'privacy=?', [scope])


def clean_run_label(value):
    """A run label (#939): None, or trimmed printable text of 1-80 characters; ValueError otherwise.
    Shared by job submission (app/server.py) and the asset edit command, where None marks the asset as the operator's own."""
    if value is None: return None
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= RUN_LABEL_MAX or not value.strip().isprintable():
        raise ValueError(f"label must be printable text of 1 to {RUN_LABEL_MAX} characters")
    return value.strip()


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_excerpt(job, limit=PROMPT_EXCERPT_CHARS):
    """The start of a job's positive prompt, whitespace-collapsed and bounded, for a library subtitle; None when unknown. Never raises."""
    try:
        text = (job.get("controls") or {}).get("positive")
        if not isinstance(text, str):
            node, name = ((job.get("prompt_bindings") or {}).get("positive") or [(None, None)])[0]
            text = job["graph"][str(node)]["inputs"][str(name)]
    except (AttributeError, KeyError, TypeError, IndexError, ValueError): return None
    if not isinstance(text, str): return None
    text = " ".join(text.split())
    return (text if len(text) <= limit else text[:limit - 1].rstrip() + "…") or None


class AssetWorkspace:
    def __init__(self, experiments):
        self.root = (Path(experiments) / "workspace").resolve()
        # Retain the literal child name: resolving a pre-existing symlink here
        # would make later containment checks mistake a regular/outside path for private storage.
        self.private_root = Path(experiments).resolve() / "private"
        self.root.mkdir(parents=True, exist_ok=True)
        self.media = self.root / "media"
        self.media.mkdir(exist_ok=True)
        self.database = self.root / "assets.sqlite3"
        # One process must not race WAL activation against its own schema migration.
        # SQLite's bounded BUSY retry remains the cross-process coordination boundary.
        with _INITIALIZATION_LOCK:
            self._initialize_database()

    def _initialize_database(self):
        with self.connection() as db:
            self._enable_wal(db)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL, output_index INTEGER NOT NULL,
                    title TEXT NOT NULL, media_type TEXT NOT NULL, path TEXT NOT NULL,
                    filename TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL, preset_id TEXT, preset_name TEXT,
                    source TEXT NOT NULL, lineage TEXT NOT NULL DEFAULT '[]',
                    tags TEXT NOT NULL DEFAULT '[]', favorite INTEGER NOT NULL DEFAULT 0,
                    review TEXT NOT NULL DEFAULT 'unreviewed', notes TEXT NOT NULL DEFAULT '',
                    trashed_at REAL, UNIQUE(job_id, output_index));
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_assets (
                    collection_id TEXT REFERENCES collections(id) ON DELETE CASCADE,
                    asset_id TEXT REFERENCES assets(id) ON DELETE CASCADE,
                    PRIMARY KEY(collection_id, asset_id));
                CREATE TABLE IF NOT EXISTS asset_commands (
                    request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                    result TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS setups (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, recipe TEXT NOT NULL,
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                    body TEXT NOT NULL DEFAULT '{}', lineage TEXT NOT NULL DEFAULT '[]',
                    origin TEXT NOT NULL DEFAULT 'owner', revision INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL, trashed_at REAL);
            """)
            # Serialize migration discovery with the ALTER, including simultaneous clients.
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS workspace_identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), id TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO workspace_identity VALUES (1,?)", (uuid.uuid4().hex,))
            columns = {r["name"] for r in db.execute("PRAGMA table_info(assets)")}
            if "metadata_revision" not in columns:
                db.execute("ALTER TABLE assets ADD COLUMN metadata_revision INTEGER NOT NULL DEFAULT 0")
            for column in ADDITIVE_COLUMNS:
                if column not in columns: db.execute(f"ALTER TABLE assets ADD COLUMN {column} TEXT")
            if "archived_at" not in columns:
                db.execute("ALTER TABLE assets ADD COLUMN archived_at REAL")
            from studio_workflow.collection_commands import migrate
            migrate(db)
            for table in ('assets', 'collections', 'asset_commands', 'collection_commands_v1'):
                if 'privacy' not in {r['name'] for r in db.execute('PRAGMA table_info('+table+')')}:
                    db.execute("ALTER TABLE "+table+" ADD COLUMN privacy TEXT NOT NULL DEFAULT 'regular'")
            from studio_workflow.asset_reads import migrate as migrate_asset_reads
            migrate_asset_reads(db)

    @staticmethod
    def _enable_wal(db):
        # SQLite can return BUSY without invoking its busy handler when a lock
        # upgrade would deadlock. Retry only this pre-transaction mode change.
        deadline = time.monotonic() + WAL_INITIALIZATION_TIMEOUT
        original_timeout = db.execute("PRAGMA busy_timeout").fetchone()[0]
        while True:
            remaining = max(0, deadline - time.monotonic())
            db.execute(f"PRAGMA busy_timeout={min(100, int(remaining * 1000))}")
            try:
                mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            except sqlite3.OperationalError as exc:
                remaining = deadline - time.monotonic()
                if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_BUSY or remaining <= 0:
                    raise
                time.sleep(min(0.025, remaining))
            else:
                if mode != "wal":
                    raise WorkspaceError(f"Workspace requires WAL journaling; SQLite retained {mode!r}")
                db.execute(f"PRAGMA busy_timeout={original_timeout}")
                return

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        except sqlite3.IntegrityError as exc:
            if str(exc) == 'Asset catalogue read state unavailable':
                raise WorkspaceError('Asset catalogue read state is unavailable; nothing changed',
                                     status=503, code='asset_read_unavailable') from exc
            raise
        finally:
            db.close()

    def storage_root(self, privacy='regular'):
        if privacy_scope(privacy, creation=True) == 'regular': return self.root
        for path in (self.private_root, self.private_root / 'media'):
            if path.is_symlink() or path.resolve() != path:
                raise WorkspaceError('Private storage must use its dedicated directory without symlinks',
                                     code='privacy_storage_unavailable')
        if self.private_root == self.root or self.root in self.private_root.parents or self.private_root in self.root.parents:
            raise WorkspaceError('Private storage must be separate from the regular workspace', code='privacy_storage_unavailable')
        return self.private_root

    def snapshot_file(self, source, privacy='regular'):
        root = self.storage_root(privacy)
        media = root / 'media'; media.mkdir(parents=True, exist_ok=True)
        source = Path(source)
        temporary = media / (uuid.uuid4().hex + ".part")
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as src, temporary.open("xb") as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                dst.flush(); os.fsync(dst.fileno())
            if not size:
                raise WorkspaceError("The output file is empty")
            hexdigest = digest.hexdigest()
            suffix = source.suffix.lower()
            if len(suffix) > 12 or not suffix[1:].isalnum():
                suffix = ".data"
            destination = media / (hexdigest + suffix)
            if destination.exists():
                self._verify_snapshot(destination, hexdigest)
            else:
                # Link only our private copy, never the mutable Comfy output. A
                # competing name is checked, not overwritten by a rename fallback.
                try: os.link(temporary, destination)
                except FileExistsError: self._verify_snapshot(destination, hexdigest)
            # A verified existing/colliding link may belong to a publisher that has
            # not synced the directory yet. Every returning caller owns this barrier.
            if os.name != 'nt':
                fd = os.open(media, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                try: os.fsync(fd)
                finally: os.close(fd)
            return str(destination.relative_to(root)), hexdigest, size
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _verify_snapshot(path, expected):
        if path.is_symlink() or not path.is_file():
            raise WorkspaceError("An existing asset snapshot is not a regular file; original retained")
        if digest_file(path) != expected:
            raise WorkspaceError("An existing asset snapshot has changed; original retained")

    @staticmethod
    def asset_id(job, index): return uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:{job['id']}:{index}").hex

    def registered_ids(self):
        """{asset id: privacy} in one connection, so a restart need not look every known output up separately (#1761)."""
        with self.connection() as db: return {row['id']: row['privacy'] for row in db.execute("SELECT id,privacy FROM assets")}

    def register(self, job, index, source):
        privacy = privacy_scope(job.get('privacy', 'regular'), creation=True)
        asset_id = self.asset_id(job, index)
        with self.connection() as db:
            existing = db.execute("SELECT id,privacy FROM assets WHERE id=?", (asset_id,)).fetchone()
            if existing:
                if existing['privacy'] != privacy:
                    raise WorkspaceError('The existing output has a different privacy classification; nothing changed', status=409, code='asset_privacy_conflict')
                return asset_id
        if not Path(source).is_file():
            return None
        try: output = job["outputs"][index]
        except (IndexError, KeyError, TypeError): output = None
        if not isinstance(output, dict): raise WorkspaceError("That job output index is invalid; nothing was registered")
        path, digest, size = self.snapshot_file(source, privacy=privacy)
        label = job.get("label") if isinstance(job.get("label"), str) and job.get("label") else None
        with self.connection() as db:
            inserted = db.execute("""INSERT OR IGNORE INTO assets
                (id,job_id,output_index,title,media_type,path,filename,sha256,bytes,
                 created_at,preset_id,preset_name,source,lineage,run_label,prompt_excerpt,privacy)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                asset_id, job["id"], index, self.registered_title(job.get("preset_name", "Untitled"), index),
                output.get("media_type", "image"), path, output.get("filename", Path(source).name),
                digest, size, job.get("created_at", time.time()), job.get("preset_id"),
                job.get("preset_name"), json.dumps(output), json.dumps(job.get("parent_assets", [])),
                label[:80] if label else None, prompt_excerpt(job), privacy))
            if inserted.rowcount == 0:
                stored = db.execute("SELECT id,privacy FROM assets WHERE job_id=? AND output_index=?",
                                    (job["id"], index)).fetchone()
                if stored is None:
                    raise WorkspaceError("That job output is already registered; nothing changed",
                                         status=409, code="asset_register_conflict")
                if stored['privacy'] != privacy:
                    raise WorkspaceError('The existing output has a different privacy classification; nothing changed', status=409, code='asset_privacy_conflict')
                return stored["id"]
        return asset_id

    @staticmethod
    def registered_title(name, index):
        suffix = f" · {index + 1}"
        return name[:REGISTERED_TITLE_MAX - len(suffix)] + suffix

    def _asset(self, row):
        value = dict(row)
        for field in ("tags", "lineage", "source"):
            value[field] = json.loads(value[field])
        value["favorite"] = bool(value["favorite"])
        value["url"] = "/api/assets/" + value["id"] + "/file"
        if value.get('privacy') == 'private': value['url'] += '?privacy=private'
        return value

    def get(self, asset_id, privacy='regular'):
        if not isinstance(asset_id, str): raise WorkspaceError("Asset not found")  # caller JSON; SQLite would raise a non-ValueError
        clause, params = privacy_sql(privacy)
        with self.connection() as db:
            row = db.execute("SELECT * FROM assets WHERE id=? AND "+clause, [asset_id, *params]).fetchone()
        if row is None:
            raise WorkspaceError("Asset not found")
        return self._asset(row)

    def file(self, asset_id, privacy='regular'):
        return self.file_entry(asset_id, privacy=privacy)[0]

    def file_entry(self, asset_id, privacy='regular'):
        """(snapshot path, asset record): the contained media file and the row whose sha256 names its bytes."""
        asset = self.get(asset_id, privacy=privacy)
        root = self.storage_root(asset['privacy'])
        path = (root / asset["path"]).resolve()
        if (root / 'media').resolve() not in path.parents or not path.is_file():
            raise WorkspaceError("Asset snapshot is unavailable")
        return path, asset

    def snapshot(self, privacy='regular'):
        clause, params = privacy_sql(privacy)
        with self.connection() as db:
            db.execute("BEGIN")
            identity = self._workspace_id(db)
            assets = [dict(self._asset(r), workspace_id=identity) for r in db.execute("SELECT * FROM assets WHERE "+clause+" ORDER BY created_at DESC,id", params)]
            collections = [dict(r) for r in db.execute("SELECT * FROM collections WHERE "+clause+" ORDER BY name COLLATE NOCASE", params)]
            membership = list(db.execute("SELECT collection_id,asset_id FROM collection_assets"))
        by_id = {a["id"]: a for a in assets}
        collection_ids = {c['id'] for c in collections}
        for asset in assets:
            asset["collections"] = []
        counts = {}
        for row in membership:
            asset = by_id.get(row["asset_id"])
            if asset is not None and row['collection_id'] in collection_ids:
                collection_id = row["collection_id"]
                asset["collections"].append(collection_id)
                if not asset["trashed_at"]:
                    counts[collection_id] = counts.get(collection_id, 0) + 1
        for collection in collections:
            collection["count"] = counts.get(collection["id"], 0)
            if collection['privacy'] == 'regular': collection.pop('privacy')
        return {"assets": assets, "collections": collections, "workspace_id": identity}

    def asset_page(self, **query):
        from studio_workflow.asset_reads import AssetReads, AssetReadError
        try:
            return AssetReads(self).page(**query)
        except AssetReadError as exc:
            raise WorkspaceError(str(exc), status=exc.status, code=exc.code, **exc.details) from exc

    def asset_selection(self, ids, *, workspace_id, details=False, privacy='regular'):
        from studio_workflow.asset_reads import AssetReads, AssetReadError
        try:
            return AssetReads(self).selection(ids, workspace_id=workspace_id, details=details, privacy=privacy)
        except AssetReadError as exc:
            raise WorkspaceError(str(exc), status=exc.status, code=exc.code, **exc.details) from exc

    def _library_assets(self, db, summaries, identity, *, unavailable=None, privacy='regular'):
        """Opt-in bounded Library fields; never decode unbounded private JSON or read media."""
        from studio_workflow.asset_reads import _text_encoding, require
        if not summaries: return []
        # Bound SQL materialization without cutting an editor baseline. Thirty
        # 60-code-point tags can use 43,444 bytes as escaped JSON in UTF-16.
        bounds = {'title':4096,'filename':4096,'preset_name':4096,'notes':32000,'tags':43520,
                  'source':65536,'lineage':16384,'job_id':512,'run_label':320,'prompt_excerpt':1024}
        encoding = _text_encoding(db)
        columns = ','.join(f"CASE WHEN typeof({key})='text' AND length(CAST({key} AS BLOB))<={limit} THEN CAST({key} AS BLOB) END AS {key},"
                          f'{key} IS NULL AS {key}_null' for key,limit in bounds.items())
        marks = ','.join('?' for _ in summaries)
        rows = db.execute('SELECT id,output_index,'+columns+' FROM assets WHERE id IN ('+marks+')',
                          [a['id'] for a in summaries])
        found = {}
        for row in rows:
            try:
                # Decode inside this row's refusal boundary. SQLite's eager TEXT
                # decoding would otherwise abort the entire page for one bad byte.
                fields = {key:row[key].decode(encoding) if type(row[key]) is bytes else row[key] for key in bounds}
                require(all(type(value) is str or value is None and row[key+'_null']
                            and key in ('preset_name','run_label','prompt_excerpt') for key,value in fields.items()),
                        'Library metadata exceeds its bound or is invalid',code='asset_read_unavailable',status=503)
                for key,kind in (('tags',list),('source',dict),('lineage',list)):
                    fields[key] = json.loads(fields[key])
                    require(type(fields[key]) is kind, 'Invalid Library metadata',code='asset_read_unavailable',status=503)
                require(all(type(x) is str for x in fields['tags']+fields['lineage']),
                        'Invalid Library labels',code='asset_read_unavailable',status=503)
                json.dumps(fields,allow_nan=False)
                clause, params = privacy_sql(privacy, 'c.')
                memberships = db.execute('SELECT ca.collection_id FROM collection_assets ca JOIN collections c ON c.id=ca.collection_id WHERE ca.asset_id=? AND '+clause+' ORDER BY ca.collection_id LIMIT 201',
                                         [row['id'], *params]).fetchall()
                require(len(memberships)<=200, 'Library memberships exceed their bound',code='asset_read_unavailable',status=503)
                found[row['id']] = dict(fields,output_index=row['output_index'],collections=[r[0] for r in memberships],workspace_id=identity)
            except (ValueError,RecursionError) as exc:
                if unavailable is None:
                    raise WorkspaceError('Library metadata is unavailable',code='asset_read_unavailable',status=503) from exc
                unavailable.append({'id':row['id'],'code':'asset_read_unavailable',
                                    'error':'Library metadata is unavailable for this asset'})
        return [dict(a,**found[a['id']]) for a in summaries if a['id'] in found]

    def collection_page(self, *, workspace_id=None, limit=50, cursor=None, privacy='regular'):
        from studio_workflow.asset_reads import _integer, _state, require
        from studio_workflow.collection_http import collection_cursor
        require(_integer(limit,1,100), 'Page size must be an integer between 1 and 100')
        privacy_scope(privacy)
        position = collection_cursor(cursor) if cursor is not None else None
        if workspace_id is not None: self._validate_scope(workspace_id)
        if position is not None:
            require(position['limit']==limit and position.get('privacy','regular')==privacy, 'Collection cursor belongs to another privacy scope or page size; explicitly refresh',
                    code='collection_cursor_mismatch',status=409)
            require(workspace_id is None or position['workspace_id']==workspace_id, 'Collection cursor belongs to another Workspace',
                    code='asset_workspace_conflict',status=409)
            workspace_id = position['workspace_id']
        with self.connection() as db:
            db.execute('BEGIN')
            identity, stamp = self._check_scope(db,workspace_id), _state(db,privacy)
            return self._collection_page(db,identity,stamp,limit=limit,position=position,privacy=privacy)

    def _collection_page(self, db, identity, stamp, *, limit, position=None, privacy='regular'):
        """Existing bounded collection projection inside the caller's read snapshot."""
        from studio_workflow.asset_reads import _integer, ENTITY, require
        from studio_workflow.collection_http import encode_cursor
        require(position is None or position['catalogue']==stamp, 'Collection catalogue changed; explicitly refresh',
                code='collection_cursor_stale',status=409)
        clause, params = privacy_sql(privacy, 'c.')
        asset_clause, asset_params = privacy_sql(privacy, 'a.')
        where = ' WHERE '+clause
        if position: where += ' AND (c.name COLLATE NOCASE,c.id)>(?,?)'; params += position['last']
        rows = db.execute('''SELECT CASE WHEN length(CAST(c.id AS BLOB))<=512 THEN c.id END AS id,
            CASE WHEN length(CAST(c.name AS BLOB))<=400 THEN c.name END AS name,
            CASE WHEN length(CAST(c.description AS BLOB))<=4000 THEN c.description END AS description,
            c.revision,c.privacy,(SELECT COUNT(*) FROM collection_assets AS ca JOIN assets AS a ON a.id=ca.asset_id
                WHERE ca.collection_id=c.id AND a.trashed_at IS NULL AND '''+asset_clause+''') AS count
            FROM collections AS c'''+where+' ORDER BY c.name COLLATE NOCASE,c.id LIMIT ?',[*asset_params,*params,limit+1]).fetchall()
        items = [dict(row) for row in rows[:limit]]
        require(all(type(c['id']) is str and ENTITY.fullmatch(c['id']) and type(c['name']) is str
                    and 0<len(c['name'])<=100 and type(c['description']) is str and len(c['description'])<=1000
                    and _integer(c['revision'],1) and _integer(c['count']) for c in items),
                'Collection metadata is unavailable',code='collection_read_unavailable',status=503)
        for item in items:
            if item['privacy'] == 'regular': item.pop('privacy')
        next_cursor = encode_cursor({'format':'studio.collection-cursor/v1','workspace_id':identity,'catalogue':stamp,
                                     **({'privacy':privacy} if privacy!='regular' else {}),
                                     'limit':limit,'last':[items[-1]['name'],items[-1]['id']]}) if len(rows)>limit else None
        return {'format':'studio.collection-page/v1','workspace_id':identity,'catalogue':stamp,'limit':limit,
                'order':'name_nocase_asc_id_asc','collections':items,'next_cursor':next_cursor,'observation_only':True,
                'media_bytes_verified':False,'generation_submitted':False}

    @staticmethod
    def text(value, name, maximum):
        if not isinstance(value, str) or len(value) > maximum:
            raise WorkspaceError(f"{name} must be text up to {maximum} characters")
        return value.strip()

    def collection(self, payload, privacy='regular'):
        from studio_workflow.collection_commands import CollectionCommands, CollectionError
        try:
            service = CollectionCommands(self, privacy=privacy_scope(privacy))
            versioned = isinstance(payload, dict) and bool(set(payload) & {"format", "workspace_id", "request_id", "expected_revision"})
            return service.command(payload) if versioned else service.legacy(payload)
        except CollectionError as exc:
            result = exc.response()
            raise WorkspaceError(result.pop("error"), status=exc.status, code=result.pop("code"), **result) from exc

    def collection_status(self, request_id, expected_workspace_id, privacy='regular'):
        from studio_workflow.collection_commands import CollectionCommands, CollectionError
        try:
            return CollectionCommands(self, privacy=privacy_scope(privacy)).status(request_id, expected_workspace_id)
        except CollectionError as exc:
            result = exc.response()
            raise WorkspaceError(result.pop("error"), status=exc.status, code=result.pop("code"), **result) from exc

    @staticmethod
    def request_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value):
            raise WorkspaceError("A request ID of 16–128 letters, digits, underscores or hyphens is required")
        return value

    @staticmethod
    def _workspace_id(db):
        # Read within the caller's transaction, never cache identity across a replaced DB.
        row = db.execute("SELECT id FROM workspace_identity WHERE singleton=1").fetchone()
        if not row or not re.fullmatch(r"[0-9a-f]{32}", row["id"]):
            raise WorkspaceError("Workspace identity is unavailable", status=503, code="asset_workspace_unavailable")
        return row["id"]

    @staticmethod
    def _validate_scope(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
            raise WorkspaceError("Workspace identity must be 32 lowercase hexadecimal characters")
        return value

    def _check_scope(self, db, expected):
        identity = self._workspace_id(db)
        if expected is not None and self._validate_scope(expected) != identity:
            raise WorkspaceError("This recovery belongs to a different Workspace. Return to its original Workspace; nothing changed.",
                                 status=409, code="asset_workspace_conflict", workspace_id=identity)
        return identity

    def _metadata_row(self, row, identity):
        return dict({k: v for k, v in self._asset(row).items() if k in METADATA_FIELDS}, workspace_id=identity)

    def metadata(self, asset_id, expected_workspace_id=None, privacy='regular'):
        clause, params = privacy_sql(privacy)
        with self.connection() as db:
            db.execute("BEGIN")
            identity = self._check_scope(db, expected_workspace_id)
            row = db.execute("SELECT * FROM assets WHERE id=? AND "+clause, [asset_id, *params]).fetchone()
            if row is None:
                raise WorkspaceError("Asset not found")
            return self._metadata_row(row, identity)

    def _observe_receipt(self, db, receipt, expected_workspace_id, privacy='regular'):
        if expected_workspace_id is None:
            return receipt  # Preserve the historical unscoped API's exact receipt shape.
        identity = self._check_scope(db, expected_workspace_id)
        current = []
        clause, params = privacy_sql(privacy)
        # Observed metadata is separate from the immutable receipt and bounded like conflicts.
        for asset_id in receipt.get("updated", [])[:10]:
            row = db.execute("SELECT * FROM assets WHERE id=? AND "+clause, [asset_id, *params]).fetchone()
            if row is not None:
                current.append(self._metadata_row(row, identity))
        return dict(receipt, workspace_id=identity, current=current)

    def command_status(self, request_id, expected_workspace_id=None, privacy='regular'):
        request_id = self.request_id(request_id)
        clause, params = privacy_sql(privacy)
        with self.connection() as db:
            db.execute("BEGIN")
            self._check_scope(db, expected_workspace_id)
            row = db.execute("SELECT result FROM asset_commands WHERE request_id=? AND "+clause, [request_id, *params]).fetchone()
            # A missing receipt cannot prove that an in-flight command will not commit.
            receipt = json.loads(row["result"]) if row else {"request_id": request_id, "status": "unknown"}
            return self._observe_receipt(db, receipt, expected_workspace_id, privacy)

    def update(self, payload, privacy='regular'):
        clause, privacy_params = privacy_sql(privacy)
        if not isinstance(payload, dict):
            raise WorkspaceError("Asset command must be an object")
        ids = payload.get("ids", [])
        if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(not isinstance(i, str) or not 1 <= len(i) <= 128 for i in ids):
            raise WorkspaceError("Select between 1 and 200 assets")
        ids = list(dict.fromkeys(ids))
        if "request_id" not in payload or "expected_revisions" not in payload:
            raise WorkspaceError("Reload the asset metadata and supply expected_revisions and a new request_id; nothing changed",
                                 status=428, code="asset_precondition_required")
        request_id = self.request_id(payload["request_id"])
        expected = payload["expected_revisions"]
        if (not isinstance(expected, dict) or set(expected) != set(ids) or
                any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= MAX_REVISION for v in expected.values())):
            raise WorkspaceError("Supply one nonnegative safe integer revision for every selected asset")
        scope = self._validate_scope(payload["workspace_id"]) if "workspace_id" in payload else None
        allowed = {"workspace_id", "ids", "action", "request_id", "expected_revisions", "title", "notes", "tags", "favorite", "review", "run_label", "collection_id"}
        if set(payload) - allowed:
            raise WorkspaceError("Unknown asset command fields")
        try:
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as error:
            raise WorkspaceError("Asset command must contain finite JSON values") from error
        if len(raw.encode()) > 128 * 1024:
            raise WorkspaceError("Asset command exceeds 128 KiB")
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()
        action = payload.get("action")
        with self.connection() as db:
            # No read-check/write gap: competing clients serialize at this boundary.
            db.execute("BEGIN IMMEDIATE")
            identity = self._check_scope(db, scope)
            receipt = db.execute("SELECT fingerprint,result,privacy FROM asset_commands WHERE request_id=?", (request_id,)).fetchone()
            if receipt:
                if not privacy_matches(receipt['privacy'], privacy):
                    raise WorkspaceError('Asset command not found', status=404, code='asset_command_not_found')
                if receipt["fingerprint"] != fingerprint:
                    raise WorkspaceError("That request ID already identifies a different command; nothing changed",
                                         status=409, code="asset_request_reused", request_id=request_id)
                return self._observe_receipt(db, json.loads(receipt["result"]), scope, privacy)
            placeholders = ",".join("?" for _ in ids)
            rows = {r["id"]: r for r in db.execute(f"SELECT * FROM assets WHERE id IN ({placeholders}) AND "+clause, [*ids,*privacy_params])}
            missing = [i for i in ids if i not in rows]
            conflicts = [i for i in ids if i in rows and rows[i]["metadata_revision"] != expected[i]]
            if missing or conflicts:
                current = [self._metadata_row(rows[i], identity) for i in conflicts[:10]]
                raise WorkspaceError("Selected asset metadata changed or no longer exists; nothing changed in this batch",
                                     status=409, code="asset_revision_conflict", request_id=request_id,
                                     conflict_ids=conflicts, missing_ids=missing, current=current, workspace_id=identity)
            changed_ids = [i for i in ids if (not rows[i]["trashed_at"]) == (action == "trash")] if action in ("trash", "restore") else ids
            if action in ("archive", "unarchive"):
                changed_ids = [i for i in ids if (rows[i]["archived_at"] is None) == (action == "archive")]
            if any(rows[i]["metadata_revision"] >= MAX_REVISION for i in changed_ids):
                raise WorkspaceError("Asset revision limit reached; nothing changed")
            applied = {}
            if action in ("add_collection", "remove_collection"):
                collection_id = payload.get("collection_id")
                if not isinstance(collection_id, str) or not 1 <= len(collection_id) <= 128:
                    raise WorkspaceError("Choose an existing collection")
                collection = db.execute("SELECT id,privacy FROM collections WHERE id=? AND "+clause, [collection_id,*privacy_params]).fetchone()
                if not collection:
                    raise WorkspaceError("Choose an existing collection")
                if any(rows[i]['privacy'] != collection['privacy'] for i in ids):
                    raise WorkspaceError('Assets and collection must share one privacy classification; nothing changed', status=409, code='asset_collection_privacy_conflict')
                members = {r["asset_id"] for r in db.execute(f"SELECT asset_id FROM collection_assets WHERE collection_id=? AND asset_id IN ({placeholders})", [collection_id, *ids])}
                # Only rows whose membership flips are changes: a repeat add or a remove of a non-member burns no revision (#1405 pattern).
                changed_ids = [i for i in ids if (i not in members) == (action == "add_collection")]
                if action == "add_collection":
                    db.executemany("INSERT OR IGNORE INTO collection_assets VALUES (?,?)", [(collection_id, i) for i in ids])
                else:
                    db.executemany("DELETE FROM collection_assets WHERE collection_id=? AND asset_id=?", [(collection_id, i) for i in ids])
                applied = {"collection_id": collection_id}
                if changed_ids:
                    changed_placeholders = ",".join("?" for _ in changed_ids)
                    db.execute(f"UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id IN ({changed_placeholders})", changed_ids)
            else:
                changes = {}
                if action in ("trash", "restore"):
                    changes["trashed_at"] = time.time() if action == "trash" else None
                elif action in ("archive", "unarchive"):
                    changes["archived_at"] = time.time() if action == "archive" else None
                elif action == "edit":
                    for field, maximum in (("title", 200), ("notes", 8000)):
                        if field in payload:
                            changes[field] = self.text(payload[field], field, maximum)
                    if "favorite" in payload:
                        if not isinstance(payload["favorite"], bool):
                            raise WorkspaceError("Favorite must be true or false")
                        changes["favorite"] = int(payload["favorite"])
                    if "review" in payload:
                        if payload["review"] not in ("unreviewed", "selected", "needs_work", "rejected"):
                            raise WorkspaceError("Unknown review state")
                        changes["review"] = payload["review"]
                    if "tags" in payload:
                        tags = payload["tags"]
                        if not isinstance(tags, list) or len(tags) > 30:
                            raise WorkspaceError("Use up to 30 tags")
                        valid_tags = []
                        for tag in tags:
                            if isinstance(tag, str) and not tag.strip():
                                continue   # blank or whitespace-only entries are dropped, never stored as ''
                            valid_tags.append(self.text(tag, "Tag", 60))
                        if tags and not valid_tags:
                            raise WorkspaceError("Enter at least one non-blank tag, or send an empty list to clear the tags; nothing changed")
                        valid_tags = list(dict.fromkeys(valid_tags))
                        answered = [CHECK_TAG.fullmatch(t) for t in valid_tags if t[:6].lower() == "check:"]
                        if not all(answered) or len({m[1] for m in answered}) != len(answered):
                            raise WorkspaceError("Check tags read check:<" + "|".join(REVIEW_CHECKS) + ">=yes or =no, one answer per check; nothing changed")
                        changes["tags"] = json.dumps(valid_tags)
                    if "run_label" in payload:
                        # A label marks an agent run; null clears it (the operator's own). Reversible like every edit.
                        try: changes["run_label"] = clean_run_label(payload["run_label"])
                        except ValueError as error: raise WorkspaceError("Run label must be null or printable text of 1 to 80 characters") from error
                else:
                    raise WorkspaceError("Unknown asset action")
                if not changes:
                    raise WorkspaceError("No changes supplied")
                fields = ",".join(key + "=?" for key in changes)
                if changed_ids:
                    changed_placeholders = ",".join("?" for _ in changed_ids)
                    db.execute(f"UPDATE assets SET {fields},metadata_revision=metadata_revision+1 WHERE id IN ({changed_placeholders})", [*changes.values(), *changed_ids])
                applied = dict(changes) if changed_ids else {}
                if "tags" in applied: applied["tags"] = json.loads(applied["tags"])
                if "favorite" in applied: applied["favorite"] = bool(applied["favorite"])
            result = {"status": "applied", "request_id": request_id, "updated": ids, "action": action,
                      "revisions": {i: expected[i] + (i in changed_ids) for i in ids}, "applied": applied}
            if len(changed_ids) < len(ids): result["unchanged"] = [i for i in ids if i not in changed_ids]   # a repeat trash/restore keeps these as they were (#1405)
            if scope is not None:
                result["workspace_id"] = identity
            # Compact receipts retain changed fields and revisions, never N copies of media/notes.
            command_privacy = 'private' if any(row['privacy']=='private' for row in rows.values()) else 'regular'
            db.execute("INSERT INTO asset_commands (request_id,fingerprint,result,created_at,privacy) VALUES (?,?,?,?,?)", (request_id, fingerprint, json.dumps(result), time.time(), command_privacy))
            result = self._observe_receipt(db, result, scope, privacy)
        return result

    def setups(self):
        with self.connection() as db:
            return [dict(r, recipe=json.loads(r["recipe"])) for r in db.execute("SELECT * FROM setups ORDER BY created_at DESC")]

    def save_setup(self, payload):
        if not isinstance(payload, dict):
            raise WorkspaceError("Setup request must be an object")
        if 'privacy' in payload and payload['privacy'] != 'regular':
            raise WorkspaceError('Private saved setups are not supported', code='privacy_unsupported')
        if payload.get("action") == "delete" and "id" not in payload:
            raise WorkspaceError("Setup ID is required to delete a setup")
        if "id" in payload:
            identifier = payload["id"]
            if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
                raise WorkspaceError("Setup ID must be a non-empty string up to 128 characters")
        else:
            identifier = uuid.uuid4().hex
        with self.connection() as db:
            if payload.get("action") == "delete":
                db.execute("DELETE FROM setups WHERE id=?", (identifier,))
                return {"id": identifier, "deleted": True}
            name = self.text(payload.get("name"), "Setup name", 120)
            recipe = payload.get("recipe")
            if not name or not isinstance(recipe, dict):
                raise WorkspaceError("Name and recipe are required")
            try:
                raw = json.dumps(recipe, allow_nan=False)
            except (TypeError, ValueError, RecursionError) as error:
                raise WorkspaceError("Saved setup recipe must contain finite JSON values") from error
            if len(raw) > 128 * 1024:
                raise WorkspaceError("Saved setup is too large")
            self._regular_record_sources(db, raw)
            existing = db.execute("SELECT name,recipe FROM setups WHERE id=?", (identifier,)).fetchone()
            if existing:
                if existing["name"] != name or json.loads(existing["recipe"]) != recipe:
                    raise WorkspaceError("That setup ID already exists; the original was preserved. Save with a new ID.")
            else:
                inserted = db.execute("INSERT OR IGNORE INTO setups VALUES (?,?,?,?)", (identifier, name, raw, time.time()))
                if inserted.rowcount == 0:
                    winner = db.execute("SELECT name,recipe FROM setups WHERE id=?", (identifier,)).fetchone()
                    if winner is None:  # deleted between the ignored insert and this read: a conflict, not a TypeError
                        raise WorkspaceError("That setup changed while it was being saved; nothing was stored. Save again with a new ID.",
                                             status=409, code="setup_conflict")
                    if winner["name"] != name or json.loads(winner["recipe"]) != recipe:
                        raise WorkspaceError("That setup ID already exists; the original was preserved. Save with a new ID.")
        return {"id": identifier, "name": name}

    def asset_by_sha256(self, digest, privacy='regular'):
        """The oldest live asset whose snapshot has these bytes, or None: a card's lineage names pictures by content, not by row."""
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest): return None
        clause, params = privacy_sql(privacy)
        with self.connection() as db:
            row = db.execute("SELECT * FROM assets WHERE sha256=? AND trashed_at IS NULL AND "+clause+" ORDER BY created_at,id LIMIT 1", [digest,*params]).fetchone()
        return self._asset(row) if row else None

    @staticmethod
    def _card(row):
        value = dict(row); value["body"] = json.loads(value["body"]); value["lineage"] = json.loads(value["lineage"]); return value

    def cards(self, kind):
        with self.connection() as db:
            return [self._card(r) for r in db.execute("SELECT * FROM cards WHERE kind=? ORDER BY name COLLATE NOCASE,id", (kind,))]

    def card(self, card_id):
        if not isinstance(card_id, str): raise WorkspaceError("Card not found", status=404, code="card_not_found")
        with self.connection() as db: row = db.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if row is None: raise WorkspaceError("Card not found", status=404, code="card_not_found")
        return self._card(row)

    @staticmethod
    def _card_json(value, name, kind):
        if not isinstance(value, kind): raise WorkspaceError(f"Card {name} must be a JSON {'object' if kind is dict else 'list'}")
        try: raw = json.dumps(value, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError, RecursionError) as error: raise WorkspaceError(f"Card {name} must contain finite JSON values") from error
        if len(raw.encode()) > CARD_BODY_MAX: raise WorkspaceError(f"Card {name} exceeds {CARD_BODY_MAX // 1024} KiB")
        if kind is list and (len(value) > CARD_LINEAGE_MAX or not all(isinstance(entry, dict) for entry in value)):
            raise WorkspaceError(f"Card lineage is a list of up to {CARD_LINEAGE_MAX} objects")
        return json.dumps(value, allow_nan=False)

    def _card_fields(self, payload, required):
        fields = {}
        if "name" in payload or required:
            name = self.text(payload.get("name"), "Card name", 120)
            if not name: raise WorkspaceError("Card name is required")
            fields["name"] = name
        if "body" in payload or required: fields["body"] = self._card_json(payload.get("body"), "body", dict)
        if "lineage" in payload or required: fields["lineage"] = self._card_json(payload.get("lineage", []), "lineage", list)
        return fields

    @staticmethod
    def _regular_record_sources(db, raw):
        """Cards and legacy setups have no private store; known sources stay regular."""
        def asset(identifier):
            if type(identifier) is not str or not db.execute("SELECT 1 FROM assets WHERE id=? AND privacy='regular'", (identifier,)).fetchone():
                raise WorkspaceError('Source asset is unavailable', status=404, code='card_source_unavailable')
        pending = [json.loads(raw)]
        while pending:
            value = pending.pop()
            if isinstance(value, list): pending.extend(value)
            elif isinstance(value, dict):
                if 'privacy' in value and value['privacy'] != 'regular':
                    raise WorkspaceError('Private sources are not supported for this record', code='privacy_unsupported')
                for key in ('asset_id','parent_asset','source_asset_id','canon_asset_id','anchor_asset_id'):
                    if key in value: asset(value[key])
                if 'parent_assets' in value:
                    if not isinstance(value['parent_assets'],list): raise WorkspaceError('Invalid source asset list')
                    for identifier in value['parent_assets']: asset(identifier)
                if 'parent_by_input' in value:
                    if not isinstance(value['parent_by_input'],dict): raise WorkspaceError('Invalid source asset mapping')
                    for identifier in value['parent_by_input'].values(): asset(identifier)
                if 'job_id' in value:
                    identifier = value['job_id']
                    # Portable looks retain historical external job IDs as evidence.
                    # Known local jobs must have only regular output classifications.
                    if type(identifier) is not str or not identifier or db.execute("SELECT 1 FROM assets WHERE job_id=? AND (privacy IS NULL OR privacy!='regular') LIMIT 1", (identifier,)).fetchone():
                        raise WorkspaceError('Card source is unavailable', status=404, code='card_source_unavailable')
                pending.extend(value.values())

    def card_command(self, payload):
        """create (optional client id: the same id and content again is a no-op), edit, trash, restore. Every change after create
        names the revision it read; a stale one is a 409 carrying the current card and changes nothing (no lost update)."""
        if not isinstance(payload, dict): raise WorkspaceError("Card command must be an object")
        action = payload.get("action")
        allowed = {"create": {"action", "id", "kind", "name", "body", "lineage"}, "edit": {"action", "id", "expected_revision", "name", "body", "lineage"},
                   "trash": {"action", "id", "expected_revision"}, "restore": {"action", "id", "expected_revision"}}
        if not isinstance(action, str) or action not in allowed: raise WorkspaceError("Unknown card action")
        if set(payload) - allowed[action]: raise WorkspaceError("Unknown card command fields")
        now = time.time()
        if action == "create":
            if payload.get("kind") not in CARD_KINDS: raise WorkspaceError("Unknown card kind; known: " + ", ".join(CARD_KINDS))
            identifier = payload.get("id", uuid.uuid4().hex)
            if not isinstance(identifier, str) or not CARD_ID.fullmatch(identifier): raise WorkspaceError("Card ID must be 3-128 letters, digits, underscores or hyphens")
            fields = self._card_fields(payload, True)
            with self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                self._regular_record_sources(db, fields['lineage'])
                existing = db.execute("SELECT * FROM cards WHERE id=?", (identifier,)).fetchone()
                if existing:
                    same = existing["kind"] == payload["kind"] and existing["name"] == fields["name"] and json.loads(existing["body"]) == json.loads(fields["body"]) and json.loads(existing["lineage"]) == json.loads(fields["lineage"])
                    if not same: raise WorkspaceError("That card ID already names a different card; nothing changed", status=409, code="card_id_taken", current=self._card(existing))
                    return self._card(existing)
                if payload['kind'] == 'brief':
                    from scene_briefs import validate_write
                    validate_write(self, db, json.loads(fields['body']))
                db.execute("INSERT INTO cards (id,kind,name,body,lineage,origin,revision,created_at,updated_at) VALUES (?,?,?,?,?,'owner',0,?,?)",
                           (identifier, payload["kind"], fields["name"], fields["body"], fields["lineage"], now, now))
                return self._card(db.execute("SELECT * FROM cards WHERE id=?", (identifier,)).fetchone())
        if "expected_revision" not in payload:
            raise WorkspaceError("Reload the card and supply expected_revision; nothing changed", status=428, code="card_precondition_required")
        expected = payload["expected_revision"]
        if isinstance(expected, bool) or not isinstance(expected, int) or not 0 <= expected < MAX_REVISION: raise WorkspaceError("expected_revision must be a nonnegative safe integer")
        fields = self._card_fields(payload, False) if action == "edit" else {"trashed_at": now if action == "trash" else None}
        if not fields: raise WorkspaceError("No changes supplied")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if 'lineage' in fields: self._regular_record_sources(db, fields['lineage'])
            row = db.execute("SELECT * FROM cards WHERE id=?", (payload.get("id"),)).fetchone() if isinstance(payload.get("id"), str) else None
            if row is None: raise WorkspaceError("Card not found", status=404, code="card_not_found")
            if row['kind'] == 'brief':
                from scene_briefs import validate_write
                try: prior = json.loads(row['body'])
                except (ValueError, TypeError) as exc:
                    raise WorkspaceError('Brief data is unreadable; the original is preserved', code='brief_unreadable') from exc
                validate_write(self, db, json.loads(fields['body']) if 'body' in fields else prior, prior)
            if row["revision"] != expected:
                raise WorkspaceError("This card changed since you read it; nothing changed. Reload it and try again.", status=409, code="card_revision_conflict", current=self._card(row))
            if action in ("trash", "restore") and (not row["trashed_at"]) != (action == "trash"): return self._card(row)
            db.execute(f"UPDATE cards SET {','.join(k + '=?' for k in fields)},revision=revision+1,updated_at=? WHERE id=?", [*fields.values(), now, row["id"]])
            return self._card(db.execute("SELECT * FROM cards WHERE id=?", (row["id"],)).fetchone())

    @staticmethod
    def card_digest(card):
        """sha256 of a card's content (name, body, lineage) as canonical JSON: how a shipped card names the versions it replaces."""
        content = {"name": card["name"], "body": card["body"], "lineage": card.get("lineage", [])}
        return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()   # ASCII: a lone surrogate hashes, never raises

    def seed_cards(self, entries):
        """Insert shipped cards whose id is absent; never overwrite or resurrect one the owner edited or put away. Returns the new ids.
        An updated shipped card lists `supersedes`, the card_digest of each earlier shipped version. A stored seed card whose content
        still hashes to one of them has never been edited, so it takes the new version as a revision (a page that read the old one
        gets a 409) and keeps its put-away state. An edited card hashes to something else and keeps the owner's version."""
        added, now = [], time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for entry in entries:
                if entry.get("kind") not in CARD_KINDS or not CARD_ID.fullmatch(str(entry.get("id", ""))): raise WorkspaceError("Invalid seed card")
                supersedes = entry.get("supersedes", [])
                if not isinstance(supersedes, list) or len(supersedes) > 20 or not all(isinstance(d, str) and re.fullmatch(r"[0-9a-f]{64}", d) for d in supersedes):
                    raise WorkspaceError("A seed card's supersedes is a list of up to 20 sha256 digests")
                fields = self._card_fields(entry, True)
                inserted = db.execute("INSERT OR IGNORE INTO cards (id,kind,name,body,lineage,origin,revision,created_at,updated_at) VALUES (?,?,?,?,?,'seed',0,?,?)",
                                      (entry["id"], entry["kind"], fields["name"], fields["body"], fields["lineage"], now, now))
                if inserted.rowcount: added.append(entry["id"]); continue
                row = db.execute("SELECT * FROM cards WHERE id=?", (entry["id"],)).fetchone() if supersedes else None
                stored = self.card_digest(self._card(row)) if row is not None else None
                if row is None or row["origin"] != "seed" or row["kind"] != entry["kind"] or stored not in supersedes or stored == self.card_digest(entry): continue
                db.execute("UPDATE cards SET name=?,body=?,lineage=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?",
                           (fields["name"], fields["body"], fields["lineage"], now, row["id"], row["revision"]))
        return added
