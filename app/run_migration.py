"""Read-only plan for moving complete retained runs between Regular and Private (#1678, first slice).

It resolves each run's closure (run folder, every output sibling, snapshots, thumbnails, upload copies,
collections, lineage children, receipts, external ComfyUI copies), reports blockers and binds the result
with a plan hash. It never writes: no journal, metadata, thumbnail render or file move. Apply is not built.
Visibility follows the request's privacy scope exactly; anything outside it is neither listed nor counted.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from workspace import WorkspaceError, digest_file, privacy_matches, privacy_scope, privacy_sql

MAX_IDS = 50
MAX_RUN_FILES = 500
MAX_ITEMS = 5000
MAX_RECEIPTS = 50
IDENTITY = re.compile(r'[A-Za-z0-9_-]{1,128}')
SETTLED = ('completed', 'failed', 'cancelled', 'abandoned')
COPIED = ('run_file', 'asset', 'upload', 'thumbnail')
FIELDS = {'workspace_id', 'destination', 'asset_ids', 'job_ids'}
SCOPE_PARTIAL = ('Related items in another privacy classification are not inspected under this scope. '
                 'Plan again with privacy=all before any apply.')
REMAINING = ('ComfyUI history, earlier exports, browser downloads and backups may keep further copies; '
             'migration neither finds nor erases them.')


def _ids(payload, field):
    value = payload.get(field, [])
    if type(value) is not list or not all(type(i) is str and IDENTITY.fullmatch(i) for i in value) or len(set(value)) != len(value):
        raise WorkspaceError(field+' must be a list of unique IDs')
    return value


def _validate(payload):
    if type(payload) is not dict or not set(payload) <= FIELDS or 'workspace_id' not in payload or 'destination' not in payload:
        raise WorkspaceError('Supply workspace_id, destination and asset_ids and/or job_ids only')
    if payload['destination'] not in ('regular', 'private'):
        raise WorkspaceError('Destination must be regular or private', code='privacy_invalid')
    asset_ids, job_ids = _ids(payload, 'asset_ids'), _ids(payload, 'job_ids')
    if not 1 <= len(asset_ids)+len(job_ids) <= MAX_IDS:
        raise WorkspaceError(f'Name 1 to {MAX_IDS} asset or job IDs')
    return asset_ids, job_ids


def _file(item_kind, path, label, classification, **extra):
    stat = path.stat()
    return dict(kind=item_kind, id=label, classification=classification, bytes=stat.st_size, sha256=digest_file(path), **extra)


def plan(studio, payload, scope):
    privacy_scope(scope)
    asset_ids, job_ids = _validate(payload)
    destination, assets, experiments = payload['destination'], studio.assets, studio.experiments
    items, blockers = {}, []
    def add(item): items[(item['kind'], item['id'])] = item
    def block(code, message, **detail):
        if (entry := dict(code=code, message=message, **detail)) not in blockers: blockers.append(entry)
    def rel(path): return path.relative_to(experiments).as_posix()
    with studio.lock:  # One consistent view of the visible jobs; nothing in them is changed.
        visible = {k: json.loads(json.dumps({f: v.get(f) for f in ('id', 'privacy', 'status', 'outputs', 'references', 'parent_assets', 'operation', 'comfy_root')}
                                            | {'pending': 'pending_submission' in v, 'record_error': 'record_error' in v}, default=str))
                   for k, v in studio.jobs.items() if privacy_matches(v.get('privacy', 'regular'), scope)}
    clause, params = privacy_sql(scope)
    with assets.connection() as db:
        db.execute('BEGIN')
        identity = assets._check_scope(db, payload['workspace_id'])
        run_ids = list(dict.fromkeys(job_ids))
        for identifier in job_ids:  # Same absence as GET /api/jobs/<id> for unknown or out-of-scope runs.
            if identifier not in visible: raise WorkspaceError('Unknown job', status=404, code='not_found')
        for identifier in asset_ids:
            row = db.execute('SELECT job_id FROM assets WHERE id=? AND '+clause, [identifier, *params]).fetchone()
            if row is None: raise WorkspaceError('Asset not found')
            if row['job_id'] not in run_ids: run_ids.append(row['job_id'])
        closure = set()
        for run_id in run_ids:
            job = visible.get(run_id)
            rows = db.execute('SELECT * FROM assets WHERE job_id=? AND '+clause+' ORDER BY output_index', [run_id, *params]).fetchall()
            if job is None:
                block('missing_run', 'An asset names a run whose record is unavailable in this scope', run_id=run_id); classification = None
            else:
                classification = job['privacy'] or 'regular'
                directory = studio._job_directory(run_id, classification)
                state = directory/'state.json'
                add(dict(kind='run', id=run_id, classification=classification, status=job['status'],
                         revision=digest_file(state) if state.is_file() and not state.is_symlink() else None))
                if job['status'] not in SETTLED or job['pending'] or job['record_error']:
                    block('run_not_settled', 'Queued, running, partial, uncertain or unresolved submissions own their state; nothing is cancelled or cleared', run_id=run_id, status=job['status'])
                if classification == destination: block('already_in_destination', 'This run is already '+destination, run_id=run_id)
                if directory.is_symlink() or not directory.is_dir():
                    block('missing_run_record', 'The run folder is missing or redirected', run_id=run_id)
                else:
                    count = 0
                    for folder, names, files in os.walk(directory):
                        for name in sorted(files):
                            path = Path(folder)/name; count += 1
                            if count > MAX_RUN_FILES: break
                            if path.is_symlink(): block('run_storage_alias', 'A run file redirects through a filesystem alias', run_id=run_id, path=rel(path)); continue
                            add(_file('run_file', path, rel(path), classification, run_id=run_id))
                        if count > MAX_RUN_FILES: block('run_too_large', f'The run folder holds more than {MAX_RUN_FILES} files', run_id=run_id); break
                    for name in ('recipe.json', 'state.json', 'workflow.json'):
                        if ('run_file', rel(directory/name)) not in items: block('missing_run_record', 'A run record file is missing', run_id=run_id, path=rel(directory/name))
                indexed = {row['output_index'] for row in rows}
                for index, output in enumerate(job['outputs'] or []):
                    if index not in indexed: block('missing_sibling', 'An output has no retained asset; the run cannot move whole', run_id=run_id, output_index=index)
                    if not isinstance(output, dict): continue
                    if job['operation'] == 'asset.import' and isinstance(output.get('uploaded_file'), str): references = [output['uploaded_file']]
                    else: references = []
                    if not job['operation'] and output.get('filename'):
                        try: original = studio.output_path(output, dict(job, comfy_root=job['comfy_root'] or str(studio.comfy_root)))
                        except (ValueError, OSError): original = None
                        if original is not None and original.is_file():
                            add(dict(kind='external_copy', id='comfyui/'+original.relative_to(Path(job['comfy_root'] or studio.comfy_root).resolve()).as_posix(),
                                     classification=None, bytes=original.stat().st_size, run_id=run_id, consequence='ComfyUI owns this original; it remains in place'))
                    for name in references: _upload(studio, add, block, rel, run_id, name, classification)
                for reference in job['references'] or []:
                    if isinstance(reference, dict) and isinstance(reference.get('file'), str): _upload(studio, add, block, rel, run_id, reference['file'], classification)
            for row in rows:
                closure.add(row['id'])
                if classification and row['privacy'] != classification: block('privacy_mismatch', 'An asset and its run disagree on classification', asset_id=row['id'], run_id=run_id)
                root = assets.storage_root(row['privacy'])
                media = root/row['path']
                item = dict(kind='asset', id=row['id'], classification=row['privacy'], bytes=row['bytes'], sha256=row['sha256'],
                            revision=row['metadata_revision'], run_id=run_id, output_index=row['output_index'], path=rel(media),
                            trashed=row['trashed_at'] is not None, archived=row['archived_at'] is not None)
                if media.is_symlink() or not media.is_file(): block('missing_snapshot', 'An asset snapshot is missing', asset_id=row['id'])
                elif digest_file(media) != row['sha256']: block('snapshot_changed', 'An asset snapshot no longer matches its hash', asset_id=row['id'])
                shared = db.execute('SELECT COUNT(*) FROM assets WHERE sha256=? AND privacy=? AND job_id<>?', (row['sha256'], row['privacy'], run_id)).fetchone()[0]
                if shared: item['consequence'] = 'Other assets in this classification share the snapshot; the source copy stays'
                add(item)
                folder = root/'thumbs'
                if folder.is_dir() and not folder.is_symlink():
                    for thumb in sorted(folder.glob(row['sha256']+'-*.webp')):
                        if thumb.is_file() and not thumb.is_symlink():
                            add(dict(kind='thumbnail', id=rel(thumb), classification=row['privacy'], bytes=thumb.stat().st_size, asset_id=row['id'],
                                     consequence='A regenerable cache; the destination renders its own'))
        for asset_id in sorted(closure):
            for row in db.execute('SELECT c.id,c.name,c.privacy,c.revision FROM collections c JOIN collection_assets m ON m.collection_id=c.id WHERE m.asset_id=? AND c.'+clause, [asset_id, *params]):
                members = {m[0] for m in db.execute('SELECT m.asset_id FROM collection_assets m JOIN assets a ON a.id=m.asset_id WHERE m.collection_id=? AND a.'+clause, [row['id'], *params])}
                if members - closure: block('collection_mixed', 'A collection also holds assets outside this plan; one collection keeps one classification', collection_id=row['id'])
                add(dict(kind='collection', id=row['id'], classification=row['privacy'], revision=row['revision'], name=row['name']))
            pattern = '%"'+asset_id+'"%'
            for row in db.execute('SELECT id,job_id,privacy,metadata_revision FROM assets WHERE lineage LIKE ? AND '+clause, [pattern, *params]):
                if row['id'] not in closure:
                    add(dict(kind='lineage_child', id=row['id'], classification=row['privacy'], revision=row['metadata_revision'], parent=asset_id,
                             consequence='Stays where it is; its lineage keeps naming this parent'))
            for table, column in (('asset_commands', 'result'), ('collection_commands_v1', 'receipt')):
                for row in db.execute('SELECT request_id,privacy FROM '+table+' WHERE '+column+' LIKE ? AND '+clause+' ORDER BY request_id LIMIT ?', [pattern, *params, MAX_RECEIPTS]):
                    add(dict(kind='receipt', id=row['request_id'], classification=row['privacy'], table=table,
                             consequence='Immutable receipt keeps its classification and original target IDs'))
    for job in visible.values():
        parents = job['parent_assets'] if isinstance(job['parent_assets'], list) else []
        if job['id'] not in run_ids and closure.intersection(p for p in parents if isinstance(p, str)):
            add(dict(kind='lineage_child', id=job['id'], classification=job['privacy'] or 'regular', status=job['status'],
                     consequence='Stays where it is; its recipe keeps naming this parent'))
    if len(items) > MAX_ITEMS: raise WorkspaceError(f'The migration closure exceeds {MAX_ITEMS} items; choose fewer runs', status=413, code='plan_too_large')
    if scope != 'all': block('scope_partial', SCOPE_PARTIAL)
    ordered = [items[key] for key in sorted(items)]
    bound = {'version': 1, 'workspace_id': identity, 'scope': scope, 'destination': destination, 'asset_ids': sorted(asset_ids), 'job_ids': sorted(job_ids),
             'items': [{k: item.get(k) for k in ('kind', 'id', 'classification', 'bytes', 'sha256', 'revision', 'status')} for item in ordered]}
    digest = hashlib.sha256(json.dumps(bound, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return {'workspace_id': identity, 'scope': scope, 'destination': destination, 'asset_ids': asset_ids, 'job_ids': job_ids,
            'items': ordered, 'item_count': len(ordered), 'blockers': blockers, 'applicable': not blockers,
            'byte_estimate': sum(item['bytes'] for item in ordered if item['kind'] in COPIED),
            'remaining_copies': REMAINING, 'plan_sha256': digest, 'apply_available': False, 'writes': False}


def _upload(studio, add, block, rel, run_id, name, classification):
    try: path = studio._upload_path(name, classification, allow_regular=True)
    except ValueError: return block('missing_reference', 'A staged reference copy is unavailable', run_id=run_id, file=name)
    owner = 'private' if path.parent == studio._private_directory('uploads').resolve() else 'regular'
    add(_file('upload', path, rel(path), owner, run_id=run_id))
    sidecar = path.with_name(path.name+'.json')
    if sidecar.is_file() and not sidecar.is_symlink(): add(_file('upload', sidecar, rel(sidecar), owner, run_id=run_id))
    original = studio.comfy_root/'input'/name
    if original.is_file() and not original.is_symlink():
        add(dict(kind='external_copy', id='comfyui/input/'+name, classification=None, bytes=original.stat().st_size, run_id=run_id,
                 consequence='ComfyUI input copy; it remains in place'))
