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
METADATA_FIELDS = ("id", "title", "notes", "tags", "favorite", "review", "trashed_at", "run_label", "metadata_revision")
# Additive, nullable asset columns: a Workspace created before them opens unchanged and its assets read as NULL (#939).
ADDITIVE_COLUMNS = ("run_label", "prompt_excerpt")
PROMPT_EXCERPT_CHARS = 60
RUN_LABEL_MAX = 80


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
            from studio_workflow.collection_commands import migrate
            migrate(db)
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

    def snapshot_file(self, source):
        source = Path(source)
        temporary = self.media / (uuid.uuid4().hex + ".part")
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as src, temporary.open("xb") as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if not size:
                raise WorkspaceError("The output file is empty")
            hexdigest = digest.hexdigest()
            suffix = source.suffix.lower()
            if len(suffix) > 12 or not suffix[1:].isalnum():
                suffix = ".data"
            destination = self.media / (hexdigest + suffix)
            if destination.exists():
                self._verify_snapshot(destination, hexdigest)
            else:
                # Link only our private copy, never the mutable Comfy output. A
                # competing name is checked, not overwritten by a rename fallback.
                try: os.link(temporary, destination)
                except FileExistsError: self._verify_snapshot(destination, hexdigest)
            return str(destination.relative_to(self.root)), hexdigest, size
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _verify_snapshot(path, expected):
        if path.is_symlink() or not path.is_file():
            raise WorkspaceError("An existing asset snapshot is not a regular file; original retained")
        if digest_file(path) != expected:
            raise WorkspaceError("An existing asset snapshot has changed; original retained")

    def register(self, job, index, source):
        asset_id = uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:{job['id']}:{index}").hex
        with self.connection() as db:
            if db.execute("SELECT id FROM assets WHERE id=?", (asset_id,)).fetchone():
                return asset_id
        if not Path(source).is_file():
            return None
        path, digest, size = self.snapshot_file(source)
        output = job["outputs"][index]
        label = job.get("label") if isinstance(job.get("label"), str) and job.get("label") else None
        with self.connection() as db:
            db.execute("""INSERT OR IGNORE INTO assets
                (id,job_id,output_index,title,media_type,path,filename,sha256,bytes,
                 created_at,preset_id,preset_name,source,lineage,run_label,prompt_excerpt)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                asset_id, job["id"], index, self.registered_title(job.get("preset_name", "Untitled"), index),
                output.get("media_type", "image"), path, output.get("filename", Path(source).name),
                digest, size, job.get("created_at", time.time()), job.get("preset_id"),
                job.get("preset_name"), json.dumps(output), json.dumps(job.get("parent_assets", [])),
                label[:80] if label else None, prompt_excerpt(job)))
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
        return value

    def get(self, asset_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None:
            raise WorkspaceError("Asset not found")
        return self._asset(row)

    def file(self, asset_id):
        asset = self.get(asset_id)
        path = (self.root / asset["path"]).resolve()
        if self.media.resolve() not in path.parents or not path.is_file():
            raise WorkspaceError("Asset snapshot is unavailable")
        return path

    def snapshot(self):
        with self.connection() as db:
            db.execute("BEGIN")
            identity = self._workspace_id(db)
            assets = [dict(self._asset(r), workspace_id=identity) for r in db.execute("SELECT * FROM assets ORDER BY created_at DESC,id")]
            collections = [dict(r) for r in db.execute("SELECT * FROM collections ORDER BY name COLLATE NOCASE")]
            membership = list(db.execute("SELECT collection_id,asset_id FROM collection_assets"))
        by_id = {a["id"]: a for a in assets}
        for asset in assets:
            asset["collections"] = []
        counts = {}
        for row in membership:
            asset = by_id.get(row["asset_id"])
            if asset is not None:
                collection_id = row["collection_id"]
                asset["collections"].append(collection_id)
                if not asset["trashed_at"]:
                    counts[collection_id] = counts.get(collection_id, 0) + 1
        for collection in collections:
            collection["count"] = counts.get(collection["id"], 0)
        return {"assets": assets, "collections": collections, "workspace_id": identity}

    def asset_page(self, **query):
        from studio_workflow.asset_reads import AssetReads, AssetReadError
        try:
            return AssetReads(self).page(**query)
        except AssetReadError as exc:
            raise WorkspaceError(str(exc), status=exc.status, code=exc.code, **exc.details) from exc

    def asset_selection(self, ids, *, workspace_id):
        from studio_workflow.asset_reads import AssetReads, AssetReadError
        try:
            return AssetReads(self).selection(ids, workspace_id=workspace_id)
        except AssetReadError as exc:
            raise WorkspaceError(str(exc), status=exc.status, code=exc.code, **exc.details) from exc

    @staticmethod
    def text(value, name, maximum):
        if not isinstance(value, str) or len(value) > maximum:
            raise WorkspaceError(f"{name} must be text up to {maximum} characters")
        return value.strip()

    def collection(self, payload):
        from studio_workflow.collection_commands import CollectionCommands, CollectionError
        try:
            service = CollectionCommands(self)
            versioned = isinstance(payload, dict) and bool(set(payload) & {"format", "workspace_id", "request_id", "expected_revision"})
            return service.command(payload) if versioned else service.legacy(payload)
        except CollectionError as exc:
            result = exc.response()
            raise WorkspaceError(result.pop("error"), status=exc.status, code=result.pop("code"), **result) from exc

    def collection_status(self, request_id, expected_workspace_id):
        from studio_workflow.collection_commands import CollectionCommands, CollectionError
        try:
            return CollectionCommands(self).status(request_id, expected_workspace_id)
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

    def metadata(self, asset_id, expected_workspace_id=None):
        with self.connection() as db:
            db.execute("BEGIN")
            identity = self._check_scope(db, expected_workspace_id)
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
            if row is None:
                raise WorkspaceError("Asset not found")
            return self._metadata_row(row, identity)

    def _observe_receipt(self, db, receipt, expected_workspace_id):
        if expected_workspace_id is None:
            return receipt  # Preserve the historical unscoped API's exact receipt shape.
        identity = self._check_scope(db, expected_workspace_id)
        current = []
        # Observed metadata is separate from the immutable receipt and bounded like conflicts.
        for asset_id in receipt.get("updated", [])[:10]:
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
            if row is not None:
                current.append(self._metadata_row(row, identity))
        return dict(receipt, workspace_id=identity, current=current)

    def command_status(self, request_id, expected_workspace_id=None):
        request_id = self.request_id(request_id)
        with self.connection() as db:
            db.execute("BEGIN")
            self._check_scope(db, expected_workspace_id)
            row = db.execute("SELECT result FROM asset_commands WHERE request_id=?", (request_id,)).fetchone()
            # A missing receipt cannot prove that an in-flight command will not commit.
            receipt = json.loads(row["result"]) if row else {"request_id": request_id, "status": "unknown"}
            return self._observe_receipt(db, receipt, expected_workspace_id)

    def update(self, payload):
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
            receipt = db.execute("SELECT fingerprint,result FROM asset_commands WHERE request_id=?", (request_id,)).fetchone()
            if receipt:
                if receipt["fingerprint"] != fingerprint:
                    raise WorkspaceError("That request ID already identifies a different command; nothing changed",
                                         status=409, code="asset_request_reused", request_id=request_id)
                return self._observe_receipt(db, json.loads(receipt["result"]), scope)
            placeholders = ",".join("?" for _ in ids)
            rows = {r["id"]: r for r in db.execute(f"SELECT * FROM assets WHERE id IN ({placeholders})", ids)}
            missing = [i for i in ids if i not in rows]
            conflicts = [i for i in ids if i in rows and rows[i]["metadata_revision"] != expected[i]]
            if missing or conflicts:
                current = [self._metadata_row(rows[i], identity) for i in conflicts[:10]]
                raise WorkspaceError("Selected asset metadata changed or no longer exists; nothing changed in this batch",
                                     status=409, code="asset_revision_conflict", request_id=request_id,
                                     conflict_ids=conflicts, missing_ids=missing, current=current, workspace_id=identity)
            if any(rows[i]["metadata_revision"] >= MAX_REVISION for i in ids):
                raise WorkspaceError("Asset revision limit reached; nothing changed")
            applied = {}
            if action in ("add_collection", "remove_collection"):
                collection_id = payload.get("collection_id")
                if not isinstance(collection_id, str) or not 1 <= len(collection_id) <= 128:
                    raise WorkspaceError("Choose an existing collection")
                if not db.execute("SELECT id FROM collections WHERE id=?", (collection_id,)).fetchone():
                    raise WorkspaceError("Choose an existing collection")
                if action == "add_collection":
                    db.executemany("INSERT OR IGNORE INTO collection_assets VALUES (?,?)", [(collection_id, i) for i in ids])
                else:
                    db.executemany("DELETE FROM collection_assets WHERE collection_id=? AND asset_id=?", [(collection_id, i) for i in ids])
                applied = {"collection_id": collection_id}
                db.execute(f"UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id IN ({placeholders})", ids)
            else:
                changes = {}
                if action in ("trash", "restore"):
                    changes["trashed_at"] = time.time() if action == "trash" else None
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
                        changes["tags"] = json.dumps(list(dict.fromkeys(self.text(t, "Tag", 60) for t in tags if t)))
                    if "run_label" in payload:
                        # A label marks an agent run; null clears it (the operator's own). Reversible like every edit.
                        try: changes["run_label"] = clean_run_label(payload["run_label"])
                        except ValueError as error: raise WorkspaceError("Run label must be null or printable text of 1 to 80 characters") from error
                else:
                    raise WorkspaceError("Unknown asset action")
                if not changes:
                    raise WorkspaceError("No changes supplied")
                fields = ",".join(key + "=?" for key in changes)
                db.execute(f"UPDATE assets SET {fields},metadata_revision=metadata_revision+1 WHERE id IN ({placeholders})", [*changes.values(), *ids])
                applied = dict(changes)
                if "tags" in applied: applied["tags"] = json.loads(applied["tags"])
                if "favorite" in applied: applied["favorite"] = bool(applied["favorite"])
            result = {"status": "applied", "request_id": request_id, "updated": ids, "action": action,
                      "revisions": {i: expected[i] + 1 for i in ids}, "applied": applied}
            if scope is not None:
                result["workspace_id"] = identity
            # Compact receipts retain changed fields and revisions, never N copies of media/notes.
            db.execute("INSERT INTO asset_commands VALUES (?,?,?,?)", (request_id, fingerprint, json.dumps(result), time.time()))
            result = self._observe_receipt(db, result, scope)
        return result

    def setups(self):
        with self.connection() as db:
            return [dict(r, recipe=json.loads(r["recipe"])) for r in db.execute("SELECT * FROM setups ORDER BY created_at DESC")]

    def save_setup(self, payload):
        if not isinstance(payload, dict):
            raise WorkspaceError("Setup request must be an object")
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
            raw = json.dumps(recipe)
            if len(raw) > 128 * 1024:
                raise WorkspaceError("Saved setup is too large")
            existing = db.execute("SELECT name,recipe FROM setups WHERE id=?", (identifier,)).fetchone()
            if existing:
                if existing["name"] != name or json.loads(existing["recipe"]) != recipe:
                    raise WorkspaceError("That setup ID already exists; the original was preserved. Save with a new ID.")
            else:
                inserted = db.execute("INSERT OR IGNORE INTO setups VALUES (?,?,?,?)", (identifier, name, raw, time.time()))
                if inserted.rowcount == 0:
                    winner = db.execute("SELECT name,recipe FROM setups WHERE id=?", (identifier,)).fetchone()
                    if winner["name"] != name or json.loads(winner["recipe"]) != recipe:
                        raise WorkspaceError("That setup ID already exists; the original was preserved. Save with a new ID.")
        return {"id": identifier, "name": name}
