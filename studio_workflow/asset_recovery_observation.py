"""Bounded read projection, using the existing Workspace connection and scope owner.

No journal, metadata writer, media reads, migration or background activity lives here.
"""
import json
import math
import time

FORMAT = 'studio.asset-recovery-observation/v1'
MAX_TARGETS = 200
MAX_COLLECTIONS = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _identifier(value):
    return isinstance(value, str) and 1 <= len(value) <= 128


def _text(value, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError('Stored recovery summary exceeds its field bound; observation unavailable')
    return value


def observe(workspace, ids, workspace_id, collection_id=None):
    """Return every selected target, including missing ones, in one scoped snapshot."""
    if (not isinstance(ids, list) or not 1 <= len(ids) <= MAX_TARGETS or
            any(not _identifier(i) for i in ids) or len(set(ids)) != len(ids)):
        raise ValueError('Supply 1–200 distinct bounded target IDs')
    workspace._validate_scope(workspace_id)  # Unlike the legacy snapshot, scope is mandatory.
    if collection_id is not None and not _identifier(collection_id):
        raise ValueError('Supply a bounded collection identity')
    with workspace.connection() as db:
        db.execute('BEGIN')
        identity = workspace._check_scope(db, workspace_id)
        collection = None
        if collection_id is not None:
            row = db.execute('SELECT id,name FROM collections WHERE id=?', (collection_id,)).fetchone()
            collection = {'id': collection_id, 'exists': row is not None}
            if row is not None: collection['name'] = _text(row['name'], 100)
        targets = []
        for identifier in ids:
            row = db.execute('SELECT id,title,metadata_revision,trashed_at FROM assets WHERE id=?', (identifier,)).fetchone()
            if row is None:
                targets.append({'id': identifier, 'state': 'missing'})
                continue
            timestamp = row['trashed_at']
            if timestamp is not None and (type(timestamp) not in (int, float) or
                    not math.isfinite(timestamp) or timestamp < 0):
                raise ValueError('Stored lifecycle state is unavailable')
            revision = row['metadata_revision']
            if type(revision) is not int or not 0 <= revision <= 2**53 - 1:
                raise ValueError('Stored metadata revision is unavailable')
            count = db.execute('SELECT count(*) FROM collection_assets ca JOIN collections c ON c.id=ca.collection_id WHERE ca.asset_id=?', (identifier,)).fetchone()[0]
            memberships = db.execute('SELECT c.id,c.name FROM collection_assets ca JOIN collections c ON c.id=ca.collection_id WHERE ca.asset_id=? ORDER BY c.name,c.id LIMIT ?', (identifier, MAX_COLLECTIONS)).fetchall()
            target = {'id': identifier, 'state': 'active' if row['trashed_at'] is None else 'trashed',
                      'title': _text(row['title'], 200), 'metadata_revision': revision,
                      'collection_count': count, 'collections_limited': count > MAX_COLLECTIONS,
                      'collections': [{'id': _text(c['id'], 128), 'name': _text(c['name'], 100)} for c in memberships]}
            if collection is not None:
                target['in_collection'] = bool(collection['exists'] and db.execute('SELECT 1 FROM collection_assets WHERE asset_id=? AND collection_id=?', (identifier, collection_id)).fetchone())
            targets.append(target)
        result = {'format': FORMAT, 'workspace_id': identity, 'observed_at': time.time(),
                  'targets': targets, 'collection': collection, 'generation_submitted': False}
        # Match Handler._json, including ASCII escapes for non-ASCII code points.
        if len(json.dumps(result, allow_nan=False).encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise ValueError('Recovery observation exceeds 2 MiB; no partial result was returned')
        return result
