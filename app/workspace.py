"""Persistent asset organization and immutable local output snapshots.

Comfy outputs remain untouched. Trash is reversible metadata, shared by every
browser using this experiments directory. SQLite transactions make bulk edits
atomic; a content-addressed file store keeps media available between backends.
"""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class WorkspaceError(ValueError):
    pass


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AssetWorkspace:
    def __init__(self, experiments):
        self.root = (Path(experiments) / "workspace").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.media = self.root / "media"
        self.media.mkdir(exist_ok=True)
        self.database = self.root / "assets.sqlite3"
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
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
                CREATE TABLE IF NOT EXISTS setups (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, recipe TEXT NOT NULL,
                    created_at REAL NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
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
                if digest_file(destination) != hexdigest:
                    raise WorkspaceError("An existing asset snapshot has changed; original retained")
            else:
                temporary.replace(destination)
            return str(destination.relative_to(self.root)), hexdigest, size
        finally:
            temporary.unlink(missing_ok=True)

    def register(self, job, index, source):
        asset_id = uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:{job['id']}:{index}").hex
        with self.connection() as db:
            if db.execute("SELECT id FROM assets WHERE id=?", (asset_id,)).fetchone():
                return asset_id
        if not Path(source).is_file():
            return None
        path, digest, size = self.snapshot_file(source)
        output = job["outputs"][index]
        with self.connection() as db:
            db.execute("""INSERT OR IGNORE INTO assets
                (id,job_id,output_index,title,media_type,path,filename,sha256,bytes,
                 created_at,preset_id,preset_name,source,lineage)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                asset_id, job["id"], index, job.get("preset_name", "Untitled") + f" · {index + 1}",
                output.get("media_type", "image"), path, output.get("filename", Path(source).name),
                digest, size, job.get("created_at", time.time()), job.get("preset_id"),
                job.get("preset_name"), json.dumps(output), json.dumps(job.get("parent_assets", []))))
        return asset_id

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
            assets = [self._asset(r) for r in db.execute("SELECT * FROM assets ORDER BY created_at DESC,id")]
            collections = [dict(r) for r in db.execute("SELECT * FROM collections ORDER BY name COLLATE NOCASE")]
            membership = list(db.execute("SELECT collection_id,asset_id FROM collection_assets"))
        by_id = {a["id"]: a for a in assets}
        for asset in assets:
            asset["collections"] = []
        for row in membership:
            if row["asset_id"] in by_id:
                by_id[row["asset_id"]]["collections"].append(row["collection_id"])
        for collection in collections:
            collection["count"] = sum(collection["id"] in a["collections"] and not a["trashed_at"] for a in assets)
        return {"assets": assets, "collections": collections}

    @staticmethod
    def text(value, name, maximum):
        if not isinstance(value, str) or len(value) > maximum:
            raise WorkspaceError(f"{name} must be text up to {maximum} characters")
        return value.strip()

    def collection(self, payload):
        action = payload.get("action", "create")
        identifier = payload.get("id")
        with self.connection() as db:
            if action in ("rename", "delete"):
                if not db.execute("SELECT id FROM collections WHERE id=?", (identifier,)).fetchone():
                    raise WorkspaceError("Collection not found")
                if action == "delete":
                    db.execute("DELETE FROM collections WHERE id=?", (identifier,))
                    return {"id": identifier, "deleted": True}
            elif action == "create":
                identifier = uuid.uuid4().hex
            else:
                raise WorkspaceError("Unknown collection action")
            name = self.text(payload.get("name"), "Collection name", 100)
            if not name:
                raise WorkspaceError("Give the collection a name")
            description = self.text(payload.get("description", ""), "Description", 1000)
            if action == "create":
                db.execute("INSERT INTO collections VALUES (?,?,?,?)", (identifier, name, description, time.time()))
            else:
                db.execute("UPDATE collections SET name=?,description=? WHERE id=?", (name, description, identifier))
        return {"id": identifier, "name": name, "description": description}

    def update(self, payload):
        ids = payload.get("ids", [])
        if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(not isinstance(i, str) for i in ids):
            raise WorkspaceError("Select between 1 and 200 assets")
        ids = list(dict.fromkeys(ids))
        action = payload.get("action")
        with self.connection() as db:
            placeholders = ",".join("?" for _ in ids)
            existing = db.execute(f"SELECT id FROM assets WHERE id IN ({placeholders})", ids).fetchall()
            if len(existing) != len(ids):
                raise WorkspaceError("One of the selected assets no longer exists; nothing changed")
            if action in ("add_collection", "remove_collection"):
                collection_id = payload.get("collection_id")
                if not db.execute("SELECT id FROM collections WHERE id=?", (collection_id,)).fetchone():
                    raise WorkspaceError("Choose an existing collection")
                if action == "add_collection":
                    db.executemany("INSERT OR IGNORE INTO collection_assets VALUES (?,?)", [(collection_id, i) for i in ids])
                else:
                    db.executemany("DELETE FROM collection_assets WHERE collection_id=? AND asset_id=?", [(collection_id, i) for i in ids])
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
                else:
                    raise WorkspaceError("Unknown asset action")
                if not changes:
                    raise WorkspaceError("No changes supplied")
                fields = ",".join(key + "=?" for key in changes)
                db.execute(f"UPDATE assets SET {fields} WHERE id IN ({placeholders})", [*changes.values(), *ids])
        return {"updated": ids, "action": action}

    def setups(self):
        with self.connection() as db:
            return [dict(r, recipe=json.loads(r["recipe"])) for r in db.execute("SELECT * FROM setups ORDER BY created_at DESC")]

    def save_setup(self, payload):
        identifier = payload.get("id") or uuid.uuid4().hex
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
                db.execute("INSERT INTO setups VALUES (?,?,?,?)", (identifier, name, raw, time.time()))
        return {"id": identifier, "name": name}
