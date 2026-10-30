"""Read-only plan for moving complete retained runs between Regular and Private (#1678, first slice).

It resolves each run's closure (run folder, every output sibling, snapshots, thumbnails, upload copies,
collections, lineage children, receipts, external ComfyUI copies), reports blockers and binds the result
with a plan hash. plan() never writes: no journal, metadata, thumbnail render or file move.
Visibility follows the request's privacy scope exactly; anything outside it is neither listed nor counted.

apply() moves a re-planned closure with no blockers in either direction (Regular -> Private, and Private -> Regular
since #1678's last slice) through one direction-parametrised path and a durable journal under private/migrations/:
staging -> verified -> published -> cleanup-needed/complete, or rolled-back. The workspace commit marker (run_migrations_v1) is the publication point; recover() runs at
Studio start before job discovery and rolls an interrupted journal back or forward from that truth.
"""
import errno
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import creation_privacy
import project_storage
from workspace import WorkspaceError, digest_file, privacy_matches, privacy_scope, privacy_sql

MAX_IDS = 50
MAX_RUN_FILES = 500
MAX_ITEMS = 5000
MAX_RECEIPTS = 50
IDENTITY = re.compile(r'[A-Za-z0-9_-]{1,128}')
SETTLED = ('completed', 'failed', 'cancelled', 'abandoned')
COPIED = ('run_file', 'asset', 'upload', 'thumbnail')
OUTSIDE = ('external_copy', 'scene_copy', 'production_plan')  # Bytes that stay where they are; the receipt lists them.
FIELDS = {'workspace_id', 'destination', 'asset_ids', 'job_ids'}
SCOPE_PARTIAL = ('Related items in another privacy classification are not inspected under this scope. '
                 'Plan again with privacy=all before any apply.')
REMAINING = ('Scene project input copies and production plans that name these runs or assets are listed in the plan and stay regular. '
             'ComfyUI history, earlier exports, browser downloads and backups may keep further copies; migration neither finds nor erases them.')


def _ids(payload, field):
    value = payload.get(field, [])
    if type(value) is not list or not all(type(i) is str and IDENTITY.fullmatch(i) for i in value) or len(set(value)) != len(value):
        raise WorkspaceError(field+' must be a list of unique IDs')
    return value


def _validate(payload):
    if type(payload) is not dict or not set(payload) <= FIELDS or 'workspace_id' not in payload or 'destination' not in payload:
        raise WorkspaceError('Supply workspace_id, destination and asset_ids and/or job_ids only')
    if type(payload['workspace_id']) is not str: raise WorkspaceError('Workspace identity must be 32 lowercase hexadecimal characters')
    if payload['destination'] not in ('regular', 'private'):
        raise WorkspaceError('Destination must be regular or private', code='privacy_invalid')
    asset_ids, job_ids = _ids(payload, 'asset_ids'), _ids(payload, 'job_ids')
    if not 1 <= len(asset_ids)+len(job_ids) <= MAX_IDS:
        raise WorkspaceError(f'Name 1 to {MAX_IDS} asset or job IDs')
    return asset_ids, job_ids


def _file(item_kind, path, label, classification, **extra):
    extra.pop('guard')()
    stat = path.stat()
    return dict(kind=item_kind, id=label, classification=classification, bytes=stat.st_size, sha256=digest_file(path), **extra)


def plan(studio, payload, scope):
    privacy_scope(scope)
    asset_ids, job_ids = _validate(payload)
    destination, assets, experiments = payload['destination'], studio.assets, studio.experiments
    items, blockers = {}, []
    def guard():  # Refuse as soon as the bound is reached, before hashing another file.
        if len(items) >= MAX_ITEMS: raise WorkspaceError(f'The migration closure exceeds {MAX_ITEMS} items; choose fewer runs', status=413, code='plan_too_large')
    def add(item):
        if (item['kind'], item['id']) not in items: guard()
        items[(item['kind'], item['id'])] = item
    def block(code, message, **detail):
        if (entry := dict(code=code, message=message, **detail)) not in blockers: blockers.append(entry)
    def rel(path): return path.relative_to(experiments).as_posix()
    with studio.lock:  # One consistent view of the visible jobs; nothing in them is changed.
        visible = {k: json.loads(json.dumps({f: v.get(f) for f in ('id', 'privacy', 'status', 'outputs', 'references', 'parent_assets', 'operation', 'comfy_root', 'controls')}
                                            | {'pending': 'pending_submission' in v, 'record_error': 'record_error' in v}, default=str))
                   for k, v in studio.jobs.items() if privacy_matches(v.get('privacy', 'regular'), scope)}
        loaded = set(studio.jobs)
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
                try: directory = studio._job_directory(run_id, classification)
                except ValueError: directory = None; block('run_storage_alias', 'The run folder redirects through a filesystem alias', run_id=run_id)
                state = directory/'state.json' if directory else None
                readable = bool(state and state.is_file() and not state.is_symlink())
                if readable: guard()
                add(dict(kind='run', id=run_id, classification=classification, status=job['status'], revision=digest_file(state) if readable else None))
                if str(job['operation'] or '').startswith('native.'):
                    block('unsupported_operation', 'Native project runs keep their originals under projects/; their migration is not supported', run_id=run_id, operation=job['operation'])
                if job['status'] not in SETTLED or job['pending'] or job['record_error']:
                    block('run_not_settled', 'Queued, running, partial, uncertain or unresolved submissions own their state; nothing is cancelled or cleared', run_id=run_id, status=job['status'])
                if classification == destination: block('already_in_destination', 'This run is already '+destination, run_id=run_id)
                if directory is None: pass
                elif _alias(directory) or not directory.is_dir():
                    block('missing_run_record', 'The run folder is missing or redirected', run_id=run_id)
                else:
                    count = 0
                    for folder, names, files in os.walk(directory):
                        for name in [n for n in names if _alias(Path(folder)/n)]:  # Never descend through a link or junction.
                            names.remove(name); block('run_storage_alias', 'A run folder entry redirects through a filesystem alias', run_id=run_id, path=rel(Path(folder)/name))
                        for name in sorted(files):
                            path = Path(folder)/name; count += 1
                            if count > MAX_RUN_FILES: break
                            if path.is_symlink(): block('run_storage_alias', 'A run file redirects through a filesystem alias', run_id=run_id, path=rel(path)); continue
                            add(_file('run_file', path, rel(path), classification, run_id=run_id, guard=guard))
                        if count > MAX_RUN_FILES: block('run_too_large', f'The run folder holds more than {MAX_RUN_FILES} files', run_id=run_id); break
                    for name in ('recipe.json', 'state.json', 'workflow.json'):
                        if directory is not None and ('run_file', rel(directory/name)) not in items: block('missing_run_record', 'A run record file is missing', run_id=run_id, path=rel(directory/name))
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
                    for name in references: _upload(studio, add, block, guard, rel, run_id, name, classification)
                staged = [r['file'] for r in job['references'] or [] if isinstance(r, dict) and isinstance(r.get('file'), str)]
                controls = job['controls'] if isinstance(job['controls'], dict) else {}  # Studio.prepare binds these uploads apart from references.
                staged += [controls[k] for k in ('reference', 'last_reference') if isinstance(controls.get(k), str)]
                for name in dict.fromkeys(staged): _upload(studio, add, block, guard, rel, run_id, name, classification)
            for row in rows:
                closure.add(row['id'])
                if classification and row['privacy'] != classification: block('privacy_mismatch', 'An asset and its run disagree on classification', asset_id=row['id'], run_id=run_id)
                root = assets.storage_root(row['privacy'])
                media = root/row['path']
                item = dict(kind='asset', id=row['id'], classification=row['privacy'], bytes=row['bytes'], sha256=row['sha256'],
                            revision=row['metadata_revision'], run_id=run_id, output_index=row['output_index'], path=rel(media),
                            trashed=row['trashed_at'] is not None, archived=row['archived_at'] is not None)
                if media.is_symlink() or not media.is_file(): block('missing_snapshot', 'An asset snapshot is missing', asset_id=row['id'])
                elif guard() or digest_file(media) != row['sha256']: block('snapshot_changed', 'An asset snapshot no longer matches its hash', asset_id=row['id'])
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
                found = db.execute('SELECT request_id,privacy FROM '+table+' WHERE '+column+' LIKE ? AND '+clause+' ORDER BY request_id LIMIT ?', [pattern, *params, MAX_RECEIPTS+1]).fetchall()
                if len(found) > MAX_RECEIPTS: block('receipts_overflow', f'More than {MAX_RECEIPTS} historical receipts name this asset; they are not all listed', asset_id=asset_id, table=table)
                for row in found[:MAX_RECEIPTS]:
                    add(dict(kind='receipt', id=table+'/'+row['request_id'], request_id=row['request_id'], classification=row['privacy'], table=table,
                             consequence='Immutable receipt keeps its classification and original target IDs'))
    if privacy_matches('regular', scope): _production_refs(studio, add, block, items, run_ids, closure, loaded)  # Projects are always regular.
    for job in visible.values():
        parents = job['parent_assets'] if isinstance(job['parent_assets'], list) else []
        if job['id'] not in run_ids and closure.intersection(p for p in parents if isinstance(p, str)):
            add(dict(kind='lineage_child', id=job['id'], classification=job['privacy'] or 'regular', status=job['status'],
                     consequence='Stays where it is; its recipe keeps naming this parent'))
    if scope != 'all': block('scope_partial', SCOPE_PARTIAL)
    ordered = [items[key] for key in sorted(items)]
    bound = {'version': 1, 'workspace_id': identity, 'scope': scope, 'destination': destination, 'asset_ids': sorted(asset_ids), 'job_ids': sorted(job_ids),
             'items': [{k: item.get(k) for k in ('kind', 'id', 'classification', 'bytes', 'sha256', 'revision', 'status')} for item in ordered]}
    digest = hashlib.sha256(json.dumps(bound, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return {'workspace_id': identity, 'scope': scope, 'destination': destination, 'asset_ids': asset_ids, 'job_ids': job_ids,
            'items': ordered, 'item_count': len(ordered), 'blockers': blockers, 'applicable': not blockers,
            'byte_estimate': sum(item['bytes'] for item in ordered if item['kind'] in COPIED),
            'remaining_copies': REMAINING, 'plan_sha256': digest, 'apply_available': True, 'writes': False}


def _production(studio):
    """(plans [(project id, plan JSON)], scene documents [(project id, document JSON)]) read-only from the Production database, or None when they cannot all be read:
    callers fail closed. Production itself does not exist yet when recover() runs, and its state column (attempts, artifacts) is never loaded."""
    path = studio.experiments/'projects'/'projects.sqlite3'
    if not path.is_file(): return [], []
    try:
        db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=15)
        try:
            projects = db.execute('SELECT id,plan FROM projects LIMIT ?', (MAX_SCANNED_RUNS+1,)).fetchall()
            scenes = db.execute('SELECT project_id,document FROM av_documents LIMIT ?', (MAX_SCANNED_RUNS+1,)).fetchall() if db.execute("SELECT 1 FROM sqlite_master WHERE name='av_documents'").fetchone() else []
        finally: db.close()
    except sqlite3.Error: return None
    return None if max(len(projects), len(scenes)) > MAX_SCANNED_RUNS else (projects, scenes)


def _stages(projects):
    """(project id, plan, stage index, stage request) for every stage of every comparison plan; ValueError when a plan is not shaped as Production writes it."""
    for pid, text in projects:
        try:
            plan = json.loads(text)
            if plan.get('kind') != 'comparison': continue
            for index, stage in enumerate(plan['stages']):
                if type(stage['request']) is not dict: raise TypeError('stage request')
                yield pid, plan, index, stage['request']
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc: raise ValueError(str(exc) or type(exc).__name__) from exc


def _pending_uploads(studio, have, read=None):
    """(project id, upload name) for each upload a comparison stage names whose run is not in `have` (not started, so no run record holds its uploads yet), or None when unreadable."""
    read = read or _production(studio)
    try: return None if read is None else [(pid, name) for pid, _, index, request in _stages(read[0]) if project_storage.stage_job_id(pid, index) not in have for name in sorted(_upload_names(request))]
    except (ValueError, TypeError): return None  # TypeError: a stage whose references are not iterable.


def _production_refs(studio, add, block, items, run_ids, closure, loaded):
    """Regular copies outside the closure that this move cannot move: scene inputs and production plans stay (listed), a stage yet to start would need a planned upload (blocked)."""
    unreadable = ('production_unreadable', 'Scene projects or production plans could not all be read, so the copies they keep of these runs and assets are unknown')
    read = _production(studio)
    if read is None: return block(*unreadable)
    try:
        for pid, text in read[1]:
            document = json.loads(text)
            for source in document['sources']:
                if source['asset_id'] in closure:
                    add(dict(kind='scene_copy', id='projects/'+pid+'/'+document['project']['assets'][source['key']]['path'], classification=None, bytes=source['bytes'], sha256=source['sha256'],
                             asset_id=source['asset_id'], project_id=pid, consequence='A scene project copied this asset into its own inputs folder; the copy stays regular'))
        stages = {}
        for pid, plan, index, request in _stages(read[0]):
            if (job_id := project_storage.stage_job_id(pid, index)) in run_ids: stages.setdefault(pid, (plan, []))[1].append(job_id)
        for pid, (plan, runs) in stages.items():
            add(dict(kind='production_plan', id='projects/'+pid+'/plan.json', classification=None, bytes=len(json.dumps(plan, sort_keys=True).encode()), sha256=plan.get('sha256'),
                     project_id=pid, run_ids=sorted(runs), consequence='The project plan keeps these runs recipes (prompt, upload names), and any contact sheet or review stays regular'))
    except WorkspaceError: raise  # plan_too_large stays the documented 413, not a production_unreadable blocker.
    except (ValueError, KeyError, TypeError, RecursionError): return block(*unreadable)
    moving = {_upload_base(i['id']) for i in items.values() if i['kind'] == 'upload' and i['classification'] == 'regular'}
    if (pending := _pending_uploads(studio, loaded, read)) is None: return block(*unreadable)
    for pid, name in pending:
        if name in moving: block('pending_stage_upload', 'A production comparison stage that has not started needs this upload, which must stay regular for it', project_id=pid, file=name)


def _alias(path):
    return path.is_symlink() or path.is_junction()


def _upload(studio, add, block, guard, rel, run_id, name, classification):
    try: path = studio._upload_path(name, classification, allow_regular=True)
    except ValueError: return block('missing_reference', 'A staged reference copy is unavailable', run_id=run_id, file=name)
    owner = 'private' if path.parent == studio._private_directory('uploads').resolve() else 'regular'
    add(_file('upload', path, rel(path), owner, run_id=run_id, guard=guard))
    sidecar = path.with_name(path.name+'.json')
    if sidecar.is_file() and not sidecar.is_symlink(): add(_file('upload', sidecar, rel(sidecar), owner, run_id=run_id, guard=guard))
    original = studio.comfy_root/'input'/name
    if original.is_file() and not original.is_symlink():
        add(dict(kind='external_copy', id='comfyui/input/'+name, classification=None, bytes=original.stat().st_size, run_id=run_id,
                 consequence='ComfyUI input copy; it remains in place'))


# ---- Apply: both directions through one path (#1678). The journal names source and destination; one without `source` predates
# Private -> Regular and means Regular -> Private. ----
APPLY_FIELDS = FIELDS | {'plan_sha256', 'request_id'}
FORMAT = 'studio.run-migration/v1'
MARKER_TABLE = 'CREATE TABLE IF NOT EXISTS run_migrations_v1 (request_id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL, job_ids TEXT NOT NULL, targets TEXT NOT NULL, created_at REAL NOT NULL)'
REQUEST_ID = re.compile(r'[A-Za-z0-9_-]{16,128}')
SETTLED_STAGES = ('complete', 'rolled-back', 'cleanup-needed')  # Published or undone; anything else awaits recovery.
MAX_SCANNED_RUNS = 20000
ROOTS = {'regular': {'run_file': ('runs',), 'upload': ('uploads',), 'asset': ('workspace', 'media'), 'thumbnail': ('workspace', 'thumbs')},
         'private': {'run_file': ('private', 'runs'), 'upload': ('private', 'uploads'), 'asset': ('private', 'media'), 'thumbnail': ('private', 'thumbs')}}  # experiments/ folder per kind
OTHER = {'regular': 'private', 'private': 'regular'}
ASSET_ROOT = {'regular': 'workspace/', 'private': 'private/'}  # Asset rows hold media/<file> under these storage roots.
_LOCK = threading.Lock()  # ponytail: one migration at a time Studio-wide; per-run locks if overlapping migrations ever matter


def _checkpoint(stage):
    """A journal boundary. Tests replace this to simulate a crash (a BaseException skips every rollback)."""


def _journal_path(studio, request_id): return studio._private_directory('migrations')/(request_id+'.json')


def _journal_file(request_id): return 'private/migrations/'+request_id+'.json'


def _stage_root(studio, request_id): return studio._private_directory('migrations')/request_id


def _write(studio, journal, stage, **fields):
    journal.update(fields, stage=stage, updated_at=time.time())
    path = _journal_path(studio, journal['request_id']); path.parent.mkdir(parents=True, exist_ok=True)
    studio._write_observation_state(path, journal)


def _at(studio, rel):
    """A journal path, contained in experiments; a journal never names anything outside it."""
    path = studio.experiments/rel
    if type(rel) is not str or Path(rel).is_absolute() or '..' in Path(rel).parts or studio.experiments not in path.resolve().parents:
        raise WorkspaceError('A migration journal path escapes the experiments folder', status=500, code='migration_journal_invalid')
    return path


def _under(kind, rel, classification):
    """rel's parts below the root `kind` keeps in `classification`; ValueError when it is not strictly inside that root."""
    parts, root = Path(rel).parts if type(rel) is str else (), ROOTS[classification][kind]
    if len(parts) <= len(root) or parts[:len(root)] != root or '..' in parts or Path(rel).is_absolute(): raise ValueError('Journal names a '+kind+' path outside its '+classification+' root')
    return parts[len(root):]


def _target(kind, rel, source, destination): return '/'.join(ROOTS[destination][kind] + _under(kind, rel, source))


def _upload_names(job):
    names = [r.get('file') for r in job.get('references') or [] if isinstance(r, dict)]
    controls = job.get('controls') if isinstance(job.get('controls'), dict) else {}
    names += [controls.get(k) for k in ('reference', 'last_reference')]
    names += [o.get('uploaded_file') for o in job.get('outputs') or [] if isinstance(o, dict)]
    return {n for n in names if isinstance(n, str)}


def _upload_base(source):
    name = Path(source).name
    return name[:-5] if name.endswith('.json') else name  # A sidecar follows its upload.


def _others(studio, runs, source='regular'):
    """Upload names that runs outside `runs` able to read the `source` uploads root still reference, or None (keep every upload) when any run could not be
    read: its controls are unknown. Every run (and every pending stage, all regular) reads Regular uploads; only Private runs read Private ones."""
    with studio.lock:
        others = [j for k, j in studio.jobs.items() if k not in runs]
        loaded = set(studio.jobs)
    if any('record_error' in j for j in others): return None
    if source == 'private': return set().union(*(_upload_names(j) for j in others if j.get('privacy') == 'private'))
    pending = _pending_uploads(studio, loaded)  # Stages not yet started have no run: their plans name their uploads.
    return None if pending is None else set().union(*(_upload_names(j) for j in others), (n for _, n in pending))


def _outcome(journal):
    """The receipt for this request identity: the same answer after a lost acknowledgement, with the current stage."""
    recovery = {'recovery': journal['recovery']} if journal.get('recovery') else {}
    common = dict(request_id=journal['request_id'], plan_sha256=journal['plan_sha256'], destination=journal['destination'], stage=journal['stage'], **recovery)
    if journal['stage'] == 'rolled-back':
        failure = journal['failure']
        return failure['status'], dict(common, error=failure['error'], code=failure['code'], failed_stage=failure['failed_stage'], published=False)
    if journal['stage'] not in ('complete', 'cleanup-needed'):
        return 409, dict(common, error='This migration has not finished; restart the Studio to recover it. If recovery still reports '+_journal_file(journal['request_id'])+' as invalid or unmarked, inspect it and move it out of private/migrations/. Nothing is retried automatically.', code='migration_in_progress', published=None)
    return 200, dict(common, published=True, job_ids=journal['job_ids'], asset_ids=journal['asset_ids'], collection_ids=journal['collection_ids'],
                     cleanup_remaining=journal['remaining'], external_copies=journal['external_copies'], remaining_copies=REMAINING)


def apply(studio, payload, scope):
    """(status, body). Refusals before the journal exists change nothing and leave no receipt; afterwards every outcome is a receipt."""
    if type(payload) is not dict or not set(payload) <= APPLY_FIELDS or 'plan_sha256' not in payload or 'request_id' not in payload:
        raise WorkspaceError('Supply workspace_id, destination, plan_sha256, request_id and asset_ids and/or job_ids only')
    request_id = studio.assets.request_id(payload['request_id'])
    if type(payload['plan_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', payload['plan_sha256']):
        raise WorkspaceError('plan_sha256 must be 64 lowercase hexadecimal characters')
    request = {k: v for k, v in payload.items() if k in FIELDS}
    asset_ids, job_ids = _validate(request)
    if privacy_scope(scope) != 'all':
        raise WorkspaceError('Apply plans again under the all privacy scope; send X-Studio-Privacy: all. Nothing changed', code='migration_scope_required')
    fingerprint = hashlib.sha256(json.dumps({'workspace_id': request['workspace_id'], 'destination': request['destination'], 'plan_sha256': payload['plan_sha256'],
                                             'asset_ids': sorted(asset_ids), 'job_ids': sorted(job_ids)}, sort_keys=True).encode()).hexdigest()
    if not _LOCK.acquire(blocking=False): raise WorkspaceError('Another migration is running; nothing changed', status=409, code='migration_busy')
    try:
        path = _journal_path(studio, request_id)
        if path.exists():
            journal = json.loads(path.read_text(encoding='utf-8'))
            if journal.get('fingerprint') != fingerprint:
                raise WorkspaceError('This request ID already names a different migration; nothing changed', status=409, code='migration_request_conflict')
            return _outcome(journal)
        if pending := _pending(studio):  # Recovery of an unfinished journal could otherwise undo files this request publishes.
            raise WorkspaceError('An earlier migration has not finished ('+', '.join(map(_journal_file, pending[:3]))+'); restart the Studio to recover it. If recovery still reports a journal as invalid or unmarked, inspect that file and move it out of private/migrations/. Nothing changed', status=409, code='migration_recovery_pending', request_ids=pending[:10])
        return _apply(studio, request, request_id, payload['plan_sha256'], fingerprint)
    finally: _LOCK.release()


def _apply(studio, request, request_id, plan_sha256, fingerprint):
    current = plan(studio, request, 'all')
    if current['blockers']:
        raise WorkspaceError('The migration is blocked; nothing changed', status=409, code='migration_blocked', blockers=current['blockers'])
    if current['plan_sha256'] != plan_sha256:
        raise WorkspaceError('The plan is stale: something in it changed. Review a fresh plan; nothing changed', status=409, code='migration_stale')
    items, destination = current['items'], current['destination']; origin = OTHER[destination]
    runs = {i['id']: i['revision'] for i in items if i['kind'] == 'run'}
    for run_id in runs:
        if studio._job_directory(run_id, destination).exists():
            raise WorkspaceError('A '+destination+' run folder with this ID already exists; nothing changed', status=409, code='migration_destination_occupied', run_id=run_id)
    copies = {}
    for item in items:  # A Private run may name a Regular upload: it stays where it is, and the run still reads it once Regular.
        if item['kind'] in ('run_file', 'upload') and item['classification'] == origin: source = item['id']
        elif item['kind'] == 'asset': source = item['path']
        else: continue
        target = _target(item['kind'], source, origin, destination)
        copies[target] = dict(kind=item['kind'], source=source, target=target, sha256=item['sha256'], bytes=item['bytes'])
    others = _others(studio, runs, origin)  # Uploads still named by a run outside this closure that reads the source root stay where they are.
    journal = dict(format=FORMAT, request_id=request_id, fingerprint=fingerprint, plan_sha256=plan_sha256, workspace_id=current['workspace_id'],
                   source=origin, destination=destination, job_ids=sorted(runs), asset_ids=sorted(i['id'] for i in items if i['kind'] == 'asset'),
                   collection_ids=sorted(i['id'] for i in items if i['kind'] == 'collection'),
                   asset_revisions={i['id']: [i['revision'], i['sha256'], i['path']] for i in items if i['kind'] == 'asset'},
                   collection_revisions={i['id']: i['revision'] for i in items if i['kind'] == 'collection'},
                   copies=sorted(copies.values(), key=lambda c: c['target']), thumbnails=sorted(i['id'] for i in items if i['kind'] == 'thumbnail'),
                   keep_uploads='all' if others is None else sorted(c['source'] for c in copies.values() if c['kind'] == 'upload' and _upload_base(c['source']) in others),
                   external_copies=sorted(i['id'] for i in items if i['kind'] in OUTSIDE), placements=None, remaining=[], created_at=time.time())
    stage, committed, staging = 'staging', False, _stage_root(studio, request_id)
    try:
        with studio.lock: studio.migrating.update(runs)  # Studio._save refuses these runs until the finally below.
        _write(studio, journal, 'staging')
        for copy in journal['copies']:
            if copy['kind'] != 'run_file' and _at(studio, copy['target']).exists(): continue  # The destination already holds this blob; verified below.
            staged = staging/copy['target']; staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_at(studio, copy['source']), staged); _durable(studio, staged)
        _checkpoint('staging')
        placements = []
        for copy in journal['copies']:
            staged = staging/copy['target']; existing = copy['kind'] != 'run_file' and not staged.exists()
            checked = _at(studio, copy['target']) if existing else staged
            if checked.is_symlink() or not checked.is_file() or checked.stat().st_size != copy['bytes'] or digest_file(checked) != copy['sha256']:
                raise WorkspaceError('A copied file did not match its planned SHA-256; nothing was published', status=409, code='migration_verify_failed', file=copy['source'])
            if copy['kind'] != 'run_file': placements.append(dict(target=copy['target'], created=not existing))
        stage = 'verified'; _write(studio, journal, 'verified', placements=placements)
        _checkpoint('verified')
        with studio.lock:
            for run_id, revision in runs.items():  # Job writes for these runs are refused now; this catches one that landed before.
                if digest_file(studio._job_directory(run_id, origin)/'state.json') != revision:
                    raise WorkspaceError('A run changed while it was being copied; nothing was published', status=409, code='migration_stale', run_id=run_id)
            for run_id in runs:  # Only the classification changes; every other run file stays byte-identical.
                folder = staging.joinpath(*ROOTS[destination]['run_file'], run_id)
                state = json.loads((folder/'state.json').read_text(encoding='utf-8')); state['privacy'] = destination
                recipe = json.loads((folder/'recipe.json').read_text(encoding='utf-8')); recipe.pop('privacy', None)
                if destination == 'private': recipe['privacy'] = 'private'  # As Studio._save writes it: only a private recipe names its classification.
                studio._write_observation_state(folder/'recipe.json', recipe); studio._write_observation_state(folder/'state.json', state)
                _durable(studio, folder/'recipe.json'); _durable(studio, folder/'state.json')
                folder.rename(studio._job_directory(run_id, destination)); studio._sync_parent_directory(studio._job_directory(run_id, destination).parent)
            for placement in placements:
                if placement['created']:
                    final = _at(studio, placement['target']); final.parent.mkdir(parents=True, exist_ok=True); os.replace(staging/placement['target'], final)
                    studio._sync_parent_directory(final.parent)
            _checkpoint('placed')
            _publish(studio, journal)
            committed = True
            _checkpoint('committed')
            for run_id in runs: studio.jobs[run_id]['privacy'] = destination
            getattr(studio, 'bump_jobs_view', bool)()  # in-place classification change: the cached /api/jobs scopes are now wrong (#1767)
            stage = 'published'; _write(studio, journal, 'published')
        _checkpoint('published')
        _cleanup(studio, journal, live=True)
        return _outcome(journal)
    except Exception as exc:
        if committed: raise  # Published is never rolled back; the commit marker lets recovery finish the cleanup.
        if isinstance(exc, WorkspaceError): status, code, message = exc.status, exc.code, str(exc)
        elif isinstance(exc, OSError) and exc.errno == errno.ENOSPC: status, code, message = 507, 'migration_storage_full', 'The disk is full; nothing was published and the copies were removed'
        else: status, code, message = 500, 'migration_failed', 'The migration failed before publication; nothing was published ('+(str(exc) or type(exc).__name__)[:200]+')'
        _rollback(studio, journal)
        _write(studio, journal, 'rolled-back', failure=dict(status=status, code=code, error=message, failed_stage=stage))
        return _outcome(journal)
    finally:
        with studio.lock: studio.migrating.difference_update(runs)


def _publish(studio, journal):
    """The one publication step: every asset and collection changes classification with the commit marker, or nothing does."""
    asset_ids, collection_ids, destination = journal['asset_ids'], journal['collection_ids'], journal['destination']; origin = OTHER[destination]
    with studio.assets.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        studio.assets._check_scope(db, journal['workspace_id'])
        db.execute(MARKER_TABLE)
        marks = ','.join('?'*len(journal['job_ids']))
        rows = {r['id']: r for r in db.execute('SELECT id,privacy,metadata_revision,sha256,path FROM assets WHERE job_id IN ('+marks+')', journal['job_ids'])}
        if set(rows) != set(asset_ids) or any(r['privacy'] != origin or [r['metadata_revision'], r['sha256'], ASSET_ROOT[origin]+Path(r['path']).as_posix()] != journal['asset_revisions'][k] for k, r in rows.items()):
            raise WorkspaceError('An asset in this plan changed; nothing was published', status=409, code='migration_stale')
        for key, revision in journal['collection_revisions'].items():
            row = db.execute('SELECT privacy,revision FROM collections WHERE id=?', (key,)).fetchone()
            members = {r[0] for r in db.execute('SELECT asset_id FROM collection_assets WHERE collection_id=?', (key,))}  # Adding a member bumps only that asset.
            if row is None or row['privacy'] != origin or row['revision'] != revision or not members <= set(asset_ids):
                raise WorkspaceError('A collection in this plan changed; nothing was published', status=409, code='migration_stale')
        db.executemany("UPDATE assets SET privacy=?,metadata_revision=metadata_revision+1 WHERE id=?", [(destination, k) for k in asset_ids])
        db.executemany("UPDATE collections SET privacy=?,revision=revision+1 WHERE id=?", [(destination, k) for k in collection_ids])
        db.execute('INSERT INTO run_migrations_v1 VALUES (?,?,?,?,?)', (journal['request_id'], journal['plan_sha256'], json.dumps(journal['job_ids']),
                                                                      json.dumps([p['target'] for p in journal['placements']]), time.time()))


def _committed(studio, request_id):
    with studio.assets.connection() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_migrations_v1'").fetchone(): return False
        return db.execute('SELECT 1 FROM run_migrations_v1 WHERE request_id=?', (request_id,)).fetchone() is not None


def _rollback(studio, journal):
    """Before publication only: remove what this journal placed or staged. Source originals were never touched."""
    if journal.get('placements') is not None:  # Placement starts only after 'verified'; the occupied check proved these folders absent.
        destination = journal['destination']
        owned_runs, owned_targets = _owned(studio, journal)  # Never undo what another, later committed request published.
        for run_id in journal['job_ids']:
            folder = studio._job_directory(run_id, destination)
            if folder.exists() and run_id not in owned_runs: shutil.rmtree(folder)
        with studio.assets.connection() as db: used = {Path(r[0]).as_posix() for r in db.execute('SELECT path FROM assets WHERE privacy=?', (destination,))}  # Windows rows hold media\x
        for placement in journal['placements']:
            if placement['created'] and placement['target'] not in owned_targets and placement['target'].removeprefix(ASSET_ROOT[destination]) not in used:
                _at(studio, placement['target']).unlink(missing_ok=True)
    staging = _stage_root(studio, journal['request_id'])
    if staging.exists(): shutil.rmtree(staging)


def _cleanup(studio, journal, live):
    """After publication: retire the source originals nothing left in the source classification uses. A failure stays listed (cleanup-needed)
    and is retried at the next start."""
    remaining, staging, origin = [], _stage_root(studio, journal['request_id']), _origin(journal)
    copied = {c['source'] for c in journal['copies']}
    for run_id in journal['job_ids']:
        base = '/'.join(ROOTS[origin]['run_file'])+'/'+run_id
        original, retired = studio.experiments/base, staging/'retired'/run_id
        try:
            if original.exists(): retired.parent.mkdir(parents=True, exist_ok=True); original.rename(retired)  # Atomic: the source view never shows a partial run.
            if retired.exists():
                for path in sorted(retired.rglob('*'), reverse=True):
                    tail = path.relative_to(retired).as_posix()
                    if path.is_dir() and not path.is_symlink():
                        if not any(path.iterdir()): path.rmdir()
                    elif base+'/'+tail in copied: path.unlink()
                    else: remaining.append('private/migrations/'+journal['request_id']+'/retired/'+run_id+'/'+tail)  # Appeared after planning: kept for inspection.
                if not any(retired.iterdir()): retired.rmdir()
        except OSError: remaining.append(base)
    _checkpoint('cleanup')
    with studio.assets.connection() as db:
        source_paths = {Path(r[0]).as_posix() for r in db.execute('SELECT path FROM assets WHERE privacy=?', (origin,))}
        source_shas = {r[0] for r in db.execute('SELECT sha256 FROM assets WHERE privacy=?', (origin,))}
    others = _others(studio, journal['job_ids'], origin) if live else _disk_consumers(studio, journal['job_ids'], origin)  # At start no job is loaded: read run records.
    retire = [c['source'] for c in journal['copies'] if c['kind'] == 'asset' and c['source'].removeprefix(ASSET_ROOT[origin]) not in source_paths]
    keep = journal['keep_uploads']  # 'all': apply could not read every record, so nothing is retired until a start can; that start settles it below.
    if keep == 'all' and not live and others is not None: keep = journal['keep_uploads'] = sorted(c['source'] for c in journal['copies'] if c['kind'] == 'upload' and _upload_base(c['source']) in others)  # Every record reads now: the usual keep set.
    uploads = [c['source'] for c in journal['copies'] if c['kind'] == 'upload' and (keep == 'all' or c['source'] not in keep)]
    retire += [u for u in uploads if keep != 'all' and others is not None and _upload_base(u) not in others]
    if others is None or keep == 'all': remaining += uploads  # Who else uses them is unknown: kept and listed, and re-checked at every start until one can read every record.
    retire += [t for t in journal['thumbnails'] if Path(t).name.split('-', 1)[0] not in source_shas]  # A regenerable cache; the destination renders its own.
    for rel in dict.fromkeys(retire):
        try: _at(studio, rel).unlink(missing_ok=True)
        except OSError: remaining.append(rel)
    if not remaining and staging.exists():
        try: shutil.rmtree(staging)
        except OSError: remaining.append('private/migrations/'+journal['request_id'])
    _write(studio, journal, 'cleanup-needed' if remaining else 'complete', remaining=remaining)


def recover(studio):
    """At Studio start, before job discovery: finish or undo each interrupted journal. One report per journal acted on."""
    reports, folder = [], studio._private_directory('migrations')
    if not folder.is_dir(): return reports
    for path in sorted(folder.glob('*.json')):
        try:
            journal = json.loads(path.read_text(encoding='utf-8')); stage = journal['stage']
            if stage in ('complete', 'rolled-back'): continue
            _check_journal(studio, journal, path)
            committed = _committed(studio, journal['request_id'])
            if stage not in ('staging', 'verified') and not committed: raise ValueError('A published stage without its commit marker; left untouched')
            if stage in ('staging', 'verified') and not committed:
                _rollback(studio, journal)
                journal.update(stage='rolled-back', failure=dict(status=500, code='migration_interrupted', failed_stage=stage,
                                                                 error='The Studio stopped before publication; the run stayed '+_origin(journal)+' and nothing was published'))
            else: _cleanup(studio, journal, live=False)  # Published: the commit marker proves it even when the journal missed that write.
            _write(studio, journal, journal['stage'], recovery=dict(from_stage=stage, stage=journal['stage'], at=time.time()))
            reports.append(dict(request_id=journal['request_id'], from_stage=stage, stage=journal['stage']))
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:  # Left as found; job discovery still keeps duplicate run IDs private.
            reports.append(dict(request_id=path.stem, error=(str(exc) or type(exc).__name__)[:200]))
    return reports


def _check_journal(studio, journal, path):
    """A journal acts on nothing until its identity and run IDs are the ones its file name and format promise."""
    if journal.get('format') != FORMAT or journal.get('request_id') != path.stem or not REQUEST_ID.fullmatch(path.stem): raise ValueError('Journal identity does not match its file')
    if (journal.get('source', 'regular'), journal.get('destination')) not in (('regular', 'private'), ('private', 'regular')): raise ValueError('Journal direction is invalid')
    if type(journal.get('created_at')) not in (int, float): raise ValueError('Journal created_at is invalid')
    runs, origin, destination = journal.get('job_ids'), _origin(journal), journal['destination']
    if type(runs) is not list or not runs or not all(type(r) is str and IDENTITY.fullmatch(r) for r in runs): raise ValueError('Journal run IDs are invalid')
    for run_id in runs: studio._job_directory(run_id, destination); studio._job_directory(run_id, origin)
    copies = journal.get('copies') or []
    for entry in copies:  # Cleanup unlinks each source and rollback each target: a source sits under its kind's source root and the target is derived from it.
        kind = entry.get('kind') if type(entry) is dict else None
        if kind not in ('run_file', 'upload', 'asset'): raise ValueError('Journal names an unknown copy kind')
        tail = _under(kind, entry.get('source'), origin)
        if (kind == 'run_file' and tail[0] not in runs) or entry.get('target') != _target(kind, entry['source'], origin, destination): raise ValueError('Journal names a copy outside its run or its destination root')
    targets = {c['target'] for c in copies if c['kind'] != 'run_file'}
    if any(type(p) is not dict or p.get('target') not in targets for p in journal.get('placements') or []): raise ValueError('Journal names a placement that is not one of its copies')
    thumbnails = journal.get('thumbnails')
    if type(thumbnails) is not list or any(len(_under('thumbnail', t, origin)) != 1 or not t.endswith('.webp') for t in thumbnails): raise ValueError('Journal names a thumbnail outside its source thumbs/')
    if journal.get('keep_uploads') != 'all' and (type(journal.get('keep_uploads')) is not list or not all(type(u) is str for u in journal['keep_uploads'])): raise ValueError('Journal keep_uploads is invalid')


def _pending(studio):
    folder = studio._private_directory('migrations')
    if not folder.is_dir(): return []
    pending = []
    for path in sorted(folder.glob('*.json')):
        try: stage = json.loads(path.read_text(encoding='utf-8')).get('stage')
        except (OSError, ValueError, AttributeError): stage = None  # Unreadable counts as unfinished.
        if stage not in SETTLED_STAGES: pending.append(path.stem)
    return pending


def _origin(journal): return journal.get('source', 'regular')  # A journal written before both directions existed moved Regular -> Private.


def _owned(studio, journal):
    """(run IDs, placement targets) published by every other request committed after this journal began. An earlier one cannot own what this
    request placed (the occupied check saw nothing there), and a run moved there and back again must not shield this request's placement."""
    runs, targets = set(), set()
    with studio.assets.connection() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_migrations_v1'").fetchone(): return runs, targets
        for row in db.execute('SELECT job_ids,targets FROM run_migrations_v1 WHERE request_id<>? AND created_at>=?', (journal['request_id'], journal['created_at'])):
            runs.update(json.loads(row[0])); targets.update(json.loads(row[1]))
    return runs, targets


def _disk_consumers(studio, exclude, source='regular'):
    """Upload names that retained run records outside `exclude` able to read the `source` uploads root reference, or None when that cannot be
    established (keep them all). Every record is still read: one unreadable record in either root keeps everything."""
    names, count, have = set(), 0, set()
    for classification, root in (('regular', studio.runs), ('private', studio._private_directory('runs'))):
        for state in root.glob('*/state.json'):
            name = state.parent.name
            if name in have and name not in exclude: return None  # The loader marks a duplicate ID unreadable.
            have.add(name)
            if name in exclude: continue
            count += 1
            if count > MAX_SCANNED_RUNS: return None
            try:  # As strict as the loader: a record it would mark record_error says nothing about which uploads it uses.
                record = studio._read_job_record(state); studio._validate_job_record(record); studio._read_job_record(state.parent/'workflow.json')
                if state.is_symlink() or state.parent.is_symlink() or record.get('id') != name or creation_privacy.normalize(record.get('privacy', 'regular')) != classification: return None
                if source == 'regular' or classification == 'private': names |= _upload_names(record)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError): return None
    if source == 'private': return names  # Production stages are always regular: they never read a Private upload.
    pending = _pending_uploads(studio, have)
    return None if pending is None else names | {n for _, n in pending}


def _durable(studio, path):
    """Flush one staged file (and, where supported, its folder) before anything depends on it, as snapshot_file does."""
    with open(path, 'r+b') as stream: os.fsync(stream.fileno())
    studio._sync_parent_directory(path.parent)
