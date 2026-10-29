"""Six-slot scene briefs in Workspace's existing revisioned card store.

Preparation reads records and composes an existing owner handoff. It never
creates a job, changes asset review, or grants art/licence/export acceptance.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlencode

from workspace import WorkspaceError, MAX_REVISION

FORMAT = 'studio.scene-brief/v1'
SLOTS = {'background':'image', 'sprite':'image', 'icon':'image',
         'video':'video', 'audio':'audio', 'mesh':'3d'}


def need(condition, message, **details):
    if not condition: raise WorkspaceError(message, **details)


def regular(scope):
    need(scope == 'regular', 'Scene briefs are available in Regular scope only. Private brief storage is not supported.',
         status=400, code='privacy_unsupported')


def shape(body):
    """Validate stored and incoming envelopes alike; never repair unknown data."""
    need(isinstance(body, dict) and set(body) == {'format','workspace_id','collection_id','direction','slots'}, 'Unsupported brief fields')
    need(body['format'] == FORMAT, 'Unsupported brief version; the original is preserved')
    need(isinstance(body['workspace_id'], str) and re.fullmatch('[a-f0-9]{32}', body['workspace_id']), 'Invalid brief Workspace identity')
    need(body['collection_id'] is None or isinstance(body['collection_id'], str) and 1 <= len(body['collection_id']) <= 128, 'Invalid collection identity')
    need(isinstance(body['direction'], str) and len(body['direction']) <= 4000, 'Shared direction must be at most 4,000 characters')
    need(isinstance(body['slots'], dict) and set(body['slots']) == set(SLOTS), 'A brief needs exactly six typed slots')
    for slot in body['slots'].values():
        need(isinstance(slot, dict) and set(slot) == {'intent','criteria','selected','previous'}, 'Unsupported slot fields')
        for field in ('intent','criteria'):
            need(isinstance(slot[field], str) and len(slot[field]) <= 2000, 'Slot wording must be at most 2,000 characters')
        for field in ('selected','previous'):
            ref = slot[field]
            if ref is None: continue
            need(isinstance(ref, dict) and set(ref) == {'asset_id','sha256','metadata_revision'}, 'Invalid candidate snapshot')
            need(isinstance(ref['asset_id'], str) and 1 <= len(ref['asset_id']) <= 128, 'Invalid asset identity')
            need(isinstance(ref['sha256'], str) and re.fullmatch('[a-f0-9]{64}', ref['sha256']), 'Invalid candidate hash')
            need(type(ref['metadata_revision']) is int and 0 <= ref['metadata_revision'] < MAX_REVISION, 'Invalid candidate revision')
    return body


def source(db, ref, kind, collection):
    row = db.execute("SELECT * FROM assets WHERE id=? AND privacy='regular'", (ref['asset_id'],)).fetchone()
    need(row is not None, 'Candidate is unavailable in this Workspace', status=409, code='brief_source_unavailable')
    need(row['media_type'] == kind and row['sha256'] == ref['sha256'] and row['metadata_revision'] == ref['metadata_revision']
         and row['trashed_at'] is None and row['archived_at'] is None,
         'Candidate changed or is unavailable; choose its current record again', status=409, code='brief_source_stale')
    if collection:
        need(db.execute('SELECT 1 FROM collection_assets WHERE collection_id=? AND asset_id=?', (collection,ref['asset_id'])).fetchone(),
             'Candidate is no longer in the brief collection', status=409, code='brief_source_stale')
    return dict(row)


def validate_write(store, db, body, prior=None):
    """Runs inside card_command's write transaction, including source checks."""
    shape(body)
    if prior is not None:
        shape(prior)
        store._check_scope(db, prior['workspace_id'])
    store._check_scope(db, body['workspace_id'])
    collection = body['collection_id']
    if collection and (prior is None or collection != prior['collection_id']):
        need(db.execute("SELECT 1 FROM collections WHERE id=? AND privacy='regular'", (collection,)).fetchone(), 'Collection is unavailable')
    for key, kind in SLOTS.items():
        old = prior['slots'][key] if prior else {}
        for field in ('selected','previous'):
            ref = body['slots'][key][field]
            # An unchanged old snapshot can remain while the owner edits words.
            # Moving it into another slot, restoring it, or changing collection
            # must resolve the current record again.
            unchanged = prior and (field == 'previous' or collection == prior['collection_id']) and ref == old.get(field)
            rotated = field == 'previous' and prior and ref == old['selected']
            if ref is not None and not (unchanged or rotated): source(db, ref, kind, collection)


def read(store, identifier):
    try: card = store.card(identifier)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, WorkspaceError): raise
        raise WorkspaceError('Brief data is unreadable; the original is preserved', code='brief_unreadable') from exc
    need(card['kind'] == 'brief', 'Brief not found', status=404, code='brief_not_found')
    shape(card['body'])
    with store.connection() as db: store._check_scope(db, card['body']['workspace_id'])
    return card


def inspect(studio, identifier, scope='regular'):
    regular(scope); store = studio.assets; card = read(store, identifier)
    states = {}
    with store.connection() as db:
        collection = card['body']['collection_id']
        collection_ok = not collection or bool(db.execute("SELECT 1 FROM collections WHERE id=? AND privacy='regular'", (collection,)).fetchone())
        for key, slot in card['body']['slots'].items():
            ref = slot['selected']
            if ref is None: states[key] = {'state':'empty'}; continue
            try:
                need(collection_ok, 'The brief collection is unavailable')
                asset = source(db, ref, SLOTS[key], collection)
                store.file_entry(asset['id'], privacy='regular')
                states[key] = {'state':'selected', 'title':asset['title'] or asset['filename'], 'filename':asset['filename']}
            except (WorkspaceError, OSError):
                states[key] = {'state':'unavailable', 'reason':'The saved candidate changed or is unavailable. Its snapshot is retained.'}
    return {'card':card, 'candidates':states, 'collection_available':collection_ok}


def listing(studio, scope='regular'):
    regular(scope); entries = []
    with studio.assets.connection() as db:
        workspace_id = studio.assets._workspace_id(db)
        for row in db.execute("SELECT id,name,body,revision,trashed_at FROM cards WHERE kind='brief' ORDER BY updated_at DESC,id"):
            if row['trashed_at']: continue
            try:
                body = shape(json.loads(row['body']))
                available = body['workspace_id'] == workspace_id
            except (ValueError, TypeError): available = False
            entries.append({'id':row['id'], 'name':row['name'], 'revision':row['revision'], 'available':available})
    return {'workspace_id':workspace_id, 'briefs':entries}


def command(studio, payload, scope='regular'):
    regular(scope)
    need(isinstance(payload, dict), 'Brief command must be an object')
    if payload.get('action') == 'create':
        need(payload.get('kind') == 'brief', 'Use a brief card')
    else: read(studio.assets, payload.get('id'))
    return studio.assets.card_command(payload)


def pack_sources(store, card, db):
    """Revalidate the saved snapshot, including immediately before ZIP publication."""
    row = db.execute('SELECT * FROM cards WHERE id=?', (card['id'],)).fetchone()
    need(row is not None and store._card(row) == card and not card['trashed_at'],
         'The brief changed. Reload and download the saved revision again.', status=409, code='card_revision_conflict')
    body = shape(card['body']); store._check_scope(db, body['workspace_id'])
    collection = body['collection_id']
    if collection:
        need(db.execute("SELECT 1 FROM collections WHERE id=? AND privacy='regular'", (collection,)).fetchone(),
             'The brief collection is unavailable. Choose a current collection and save again.', status=409, code='brief_source_unavailable')
    assets = {}
    for key, kind in SLOTS.items():
        ref = body['slots'][key]['selected']
        if ref is None: continue
        asset = source(db, ref, kind, collection)
        literal = store.root / asset['path']
        try: resolved = literal.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise WorkspaceError('A selected source file is unavailable; working pack stopped', status=409, code='brief_source_unavailable') from exc
        need(resolved == literal and not literal.is_symlink() and store.media in resolved.parents,
             'Selected source files must remain inside Workspace media without links', status=409, code='brief_source_unavailable')
        store.file_entry(asset['id'], privacy='regular')
        assets[asset['id']] = store._asset(asset)
    return list(assets.values())


def working_pack(studio, payload, scope='regular'):
    regular(scope)
    need(isinstance(payload, dict) and set(payload) == {'id','expected_revision','workspace_id'}, 'Supply the saved brief, revision and Workspace')
    with studio.assets.connection() as db: studio.assets._check_scope(db, studio.assets._validate_scope(payload['workspace_id']))
    card = read(studio.assets, payload['id'])
    need(type(payload['expected_revision']) is int and payload['expected_revision'] == card['revision'] and not card['trashed_at'],
         'The brief changed. Reload and download the saved revision again.', status=409, code='card_revision_conflict')
    return studio.export_assets({}, privacy='regular', brief=card)


def prepare(studio, payload, scope='regular'):
    regular(scope)
    need(isinstance(payload, dict) and not set(payload) - {'id','slot','expected_revision','look_id','look_revision'}, 'Unsupported preparation fields')
    card = read(studio.assets, payload.get('id'))
    need(not card['trashed_at'], 'Restore this brief before preparing')
    need(type(payload.get('expected_revision')) is int and payload['expected_revision'] == card['revision'],
         'The brief changed. Reload and prepare the saved revision again.', status=409, code='card_revision_conflict')
    key = payload.get('slot'); need(isinstance(key, str) and key in SLOTS, 'Choose a brief slot')
    body = card['body']; slot = body['slots'][key]
    context = {'workspace_id':body['workspace_id'], 'id':card['id'], 'revision':card['revision'], 'slot':key}
    if key in ('background','icon'):
        import looks
        need(type(payload.get('look_revision')) is int, 'Choose a current look')
        scene = '\n'.join(text.strip() for text in (body['direction'],slot['intent'],slot['criteria']) if text.strip())
        result = looks.prepare(studio, {'id':payload.get('look_id'), 'expected_revision':payload['look_revision'], 'scene':scene})
        return {'target':'create', 'prepared':result, 'context':context, 'generation_submitted':False}
    if key == 'video':
        ids = []
        with studio.assets.connection() as db:
            for source_key in ('background','video','audio'):
                ref = body['slots'][source_key]['selected']
                if ref is None: continue
                asset = source(db, ref, SLOTS[source_key], body['collection_id'])
                expected_suffix = {'image':'.png','video':'.mp4','audio':'.wav'}[asset['media_type']]
                need(Path(asset['filename']).suffix.lower() == expected_suffix, 'Scenes need PNG, MP4 and 48 kHz PCM WAV sources; convert other formats explicitly')
                studio.assets.file_entry(asset['id'], privacy='regular')
                ids.append(asset['id'])
        need(body['slots']['background']['selected'] or slot['selected'], 'Choose a background PNG or an MP4 candidate before preparing a scene')
        return {'target':'scene', 'url':'/av.html?'+urlencode({'asset_ids':','.join(dict.fromkeys(ids))}),
                'context':context, 'generation_submitted':False,
                'notice':'Sources will be selected in Scenes. Create scene and Render remain separate actions; media and tool checks belong to Scenes.'}
    reason = {'sprite':'Directional sprite-sheet preparation is not supported. You can choose an existing image candidate.',
              'audio':'Ambience generation is not supported here. Voice requires its own speaker, lines and pinned bundle; choose an existing audio candidate.',
              'mesh':'3D preparation needs a suitable reference and a supported recipe. Choose an existing 3D candidate or use Full editor explicitly.'}[key]
    raise WorkspaceError(reason, code='brief_preparation_unsupported')
