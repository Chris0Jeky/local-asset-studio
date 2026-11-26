"""Read current Studio authority without initializing, migrating or mutating it.

A snapshot is evidence at this read, never a future submission capability. The
worker/importer must recheck it at their mutation boundary. Local-user rows are
declarations; this module does not authenticate humans or make art decisions.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pipeline as p


def _exact(value, fields, label):
    p.require(type(value) is dict and set(value) == set(fields), 'Invalid ' + label + ' fields')


def validate_binding(family, binding):
    p.validate_family(family); p.canonical_bytes(binding)
    _exact(binding, {'schema', 'family_id', 'workspace_id', 'character_card_id', 'card_revision',
                     'concept_asset_id', 'stages'}, 'Workspace binding')
    p.require(binding['schema'] == 'las.p36-workspace-binding/1', 'Unknown Workspace binding schema')
    p.require(binding['family_id'] == family['family_id'] and binding['workspace_id'] == family['workspace_id'],
              'Workspace binding scope differs')
    p.require(type(binding['character_card_id']) is str and p.ENTITY.fullmatch(binding['character_card_id']),
              'Character card ID required')
    p.require(type(binding['card_revision']) is int and 0 <= binding['card_revision'] < 2**53,
              'Exact nonnegative card revision required')
    p.require('concept' in family['heads'], 'An accepted concept receipt is required before live binding')
    p.require(type(binding['stages']) is dict and set(binding['stages']) == set(family['heads']),
              'Bind exactly the current family heads')
    for stage, head in family['heads'].items():
        item = binding['stages'][stage]
        _exact(item, {'receipt_id', 'artifacts', 'jobs'}, 'stage binding')
        p.require(item['receipt_id'] == head, 'Bound receipt is stale')
        artifacts = {a['key']: a for a in family['receipts'][head]['payload']['artifacts']}
        p.require(type(item['artifacts']) is dict and set(item['artifacts']) == set(artifacts),
                  'Bind every artifact exactly once')
        for key, artifact in artifacts.items():
            record = item['artifacts'][key]
            _exact(record, {'asset_id', 'sha256', 'acceptance_id', 'use'}, 'artifact authority')
            p.require(record['asset_id'] == artifact['asset_id'] and record['sha256'] == artifact['sha256'],
                      'Authority subject differs from immutable receipt')
            p.require(type(record['acceptance_id']) is str and p.ENTITY.fullmatch(record['acceptance_id']),
                      'Exact acceptance ID required')
            p.require(type(record['use']) is str and 0 < len(record['use']) <= 80
                      and record['use'] == ' '.join(record['use'].split()), 'Explicit normalized intended use required')
        p.require(type(item['jobs']) is dict and 0 < len(item['jobs']) <= 48, 'Exact retained job bindings required')
        for job_id, fingerprints in item['jobs'].items():
            p.require(type(job_id) is str and p.ENTITY.fullmatch(job_id), 'Unsafe job ID')
            p.safe_relative(job_id)
            _exact(fingerprints, {'state_sha256', 'workflow_sha256'}, 'retained job')
            p.require(all(type(v) is str and p.HEX64.fullmatch(v) for v in fingerprints.values()),
                      'Retained job digests must be SHA-256')
    concept = family['receipts'][family['heads']['concept']]['payload']['artifacts']
    p.require(any(a['asset_id'] == binding['concept_asset_id'] and a['media_type'].startswith('image/')
                  for a in concept), 'Bound canon is not a concept image')


def read_record(root, relative):
    """Bounded duplicate-key-safe stable read, without following links/junctions."""
    path = p.contained_file(root, relative); before = path.stat()
    p.require(before.st_size <= p.MAX_JSON, 'Retained record exceeds read bound')
    with path.open('rb') as handle: raw = handle.read(p.MAX_JSON + 1)
    after = path.stat()
    p.require((before.st_size, before.st_mtime_ns, before.st_ino) ==
              (after.st_size, after.st_mtime_ns, after.st_ino), 'Retained record changed during read')
    return p.decode_json(raw), hashlib.sha256(raw).hexdigest()


def job_is_settled(job):
    """Only complete known outputs; never grant retry from absence of a prompt."""
    if type(job) is not dict or job.get('status') != 'completed': return False
    if any(key in job for key in ('pending_submission', 'record_error', 'abandonment')): return False
    if job.get('tracking_disposition'): return False
    ids, submissions, outputs = (job.get(k) for k in ('prompt_ids', 'submissions', 'outputs'))
    if type(ids) is not list or type(submissions) is not list or type(outputs) is not list or not outputs: return False
    if not all(type(o) is dict for o in outputs): return False
    # Imports have completed evidence but never a ComfyUI submission receipt.
    if job.get('operation') == 'asset.import': return ids == [] and submissions == []
    # Other native operations need their own future, decoded native receipt adapter.
    if job.get('operation'): return False
    if not ids or not all(type(x) is str and x.strip() for x in ids) or len(ids) != len(set(ids)): return False
    if type(job.get('batch_count')) is not int or job['batch_count'] != len(ids): return False
    if len(submissions) != len(ids) or not all(type(s) is dict for s in submissions): return False
    return (all(s.get('prompt_id') == prompt_id and s.get('status') == 'completed'
                for s, prompt_id in zip(submissions, ids))
            and all(o.get('prompt_id') in ids for o in outputs))


def capture_authority(experiments, family, binding, *, stages=None):
    """Check the real Workspace tables, stable bytes and retained source jobs.

    Invalid caller contracts raise PipelineError. Missing/unreadable/revoked live
    evidence produces a failed report. No database or directory is created.
    """
    validate_binding(family, binding)
    selected = set(family['heads']) if stages is None else set(stages)
    p.require(selected and selected <= set(family['heads']), 'Invalid authority stage selection')
    experiments = Path(experiments).absolute(); root = experiments / 'workspace'
    blockers, snapshot = [], {'workspace_id': None, 'card': None, 'assets': {}, 'jobs': {}}

    def block(code, stage='', detail=''):
        blockers.append({'code': code, 'stage': stage, 'detail': detail})

    try:
        database = p.contained_file(root, 'assets.sqlite3')
        connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute('PRAGMA query_only=ON'); connection.execute('BEGIN')
            identity = connection.execute('SELECT id FROM workspace_identity WHERE singleton=1').fetchone()
            snapshot['workspace_id'] = identity['id'] if identity else None
            if snapshot['workspace_id'] != binding['workspace_id']: block('workspace_changed')
            card_row = connection.execute('SELECT * FROM cards WHERE id=?', (binding['character_card_id'],)).fetchone()
            card = dict(card_row) if card_row else None
            if not card or card['kind'] != 'character' or card['trashed_at'] is not None:
                block('card_unavailable')
            else:
                snapshot['card'] = {k: card[k] for k in ('id', 'kind', 'revision', 'lineage', 'body', 'trashed_at')}
                if card['revision'] != binding['card_revision']: block('card_changed')
                lineage = p.decode_json(card['lineage'])
                canon = [v for v in lineage if type(v) is dict and v.get('role') == 'canon'] if type(lineage) is list else []
                artifacts = family['receipts'][family['heads']['concept']]['payload']['artifacts']
                expected = next(a for a in artifacts if a['asset_id'] == binding['concept_asset_id'])
                if (len(canon) != 1 or canon[0].get('asset_id') != expected['asset_id']
                        or canon[0].get('sha256') != expected['sha256']): block('canon_changed')
            jobs_cache = {}
            for stage in p.STAGES:
                if stage not in selected: continue
                item = binding['stages'][stage]; used_jobs = set()
                payload = family['receipts'][family['heads'][stage]]['payload']
                for artifact in payload['artifacts']:
                    grant = item['artifacts'][artifact['key']]
                    found = connection.execute('SELECT * FROM assets WHERE id=?', (grant['asset_id'],)).fetchone()
                    row = dict(found) if found else None
                    if not row or row['privacy'] != 'regular' or row['trashed_at'] is not None:
                        block('asset_unavailable', stage, artifact['key']); continue
                    record = {k: row[k] for k in ('id', 'job_id', 'output_index', 'sha256', 'bytes', 'path',
                                                  'review', 'privacy', 'metadata_revision', 'trashed_at')}
                    snapshot['assets'][stage + '/' + artifact['key']] = record
                    if row['sha256'] != artifact['sha256'] or row['bytes'] != artifact['bytes']:
                        block('asset_subject_changed', stage, artifact['key'])
                    if row['review'] in ('rejected', 'needs_work'): block('asset_review_conflict', stage, artifact['key'])
                    try:
                        p.require(type(row['path']) is str and row['path'].startswith('media/'), 'Expected Workspace media')
                        p.verify_artifact(root, {'path': row['path'], 'sha256': artifact['sha256'], 'bytes': artifact['bytes']})
                    except (ValueError, OSError, TypeError): block('asset_bytes_changed', stage, artifact['key'])
                    acceptance_row = connection.execute('SELECT * FROM asset_acceptances WHERE id=?',
                                                        (grant['acceptance_id'],)).fetchone()
                    acceptance = dict(acceptance_row) if acceptance_row else None
                    if acceptance is None: block('acceptance_missing', stage, artifact['key'])
                    else:
                        record['acceptance'] = {k: acceptance[k] for k in ('id', 'asset_id', 'sha256', 'use', 'reviewer',
                                                                         'accepted_at', 'withdrawn_at', 'brief_id', 'slot', 'criteria')}
                        if acceptance['withdrawn_at'] is not None: block('acceptance_withdrawn', stage, artifact['key'])
                        if acceptance['asset_id'] != artifact['asset_id'] or acceptance['sha256'] != artifact['sha256']:
                            block('acceptance_subject_changed', stage, artifact['key'])
                        if acceptance['reviewer'] != 'local-user': block('acceptance_not_owner_declared', stage, artifact['key'])
                        if acceptance['use'] != grant['use']: block('acceptance_use_changed', stage, artifact['key'])
                        # Brief acceptance depends on a live brief/slot contract; do not flatten it into a generic use.
                        if any(acceptance[k] is not None for k in ('brief_id', 'slot', 'criteria')):
                            block('brief_acceptance_requires_adapter', stage, artifact['key'])
                    job_id = row['job_id']; used_jobs.add(job_id)
                    if job_id not in item['jobs']:
                        block('job_unbound', stage, artifact['key']); continue
                    if job_id not in jobs_cache:
                        try:
                            p.safe_relative(job_id)
                            job, state_hash = read_record(experiments, 'runs/' + job_id + '/state.json')
                            workflow, workflow_hash = read_record(experiments, 'runs/' + job_id + '/workflow.json')
                            p.require(type(job) is dict and job.get('id') == job_id and type(workflow) is dict,
                                      'Retained job identity differs')
                            p.require(job.get('privacy', 'regular') == 'regular', 'Retained source is private')
                            jobs_cache[job_id] = (job, state_hash, workflow_hash)
                        except (ValueError, OSError, TypeError): jobs_cache[job_id] = None
                    captured = jobs_cache[job_id]
                    if captured is None: block('job_record_unavailable', stage, job_id); continue
                    job, state_hash, workflow_hash = captured
                    snapshot['jobs'][job_id] = {'state_sha256': state_hash, 'workflow_sha256': workflow_hash,
                                                'status': job.get('status'), 'operation': job.get('operation'),
                                                'prompt_ids': job.get('prompt_ids')}
                    if not job_is_settled(job): block('job_unresolved', stage, job_id)
                    if item['jobs'][job_id] != {'state_sha256': state_hash, 'workflow_sha256': workflow_hash}:
                        block('job_record_changed', stage, job_id)
                    index = row['output_index']; outputs = job.get('outputs')
                    if (type(outputs) is not list or type(index) is not int or not 0 <= index < len(outputs)
                            or outputs[index] != p.decode_json(row['source'])):
                        block('job_output_unbound', stage, artifact['key'])
                if used_jobs != set(item['jobs']): block('job_inventory_changed', stage)
            # The read transaction keeps all authority rows in one consistent SQLite snapshot.
            connection.rollback()
        finally: connection.close()
    except (sqlite3.Error, ValueError, OSError, KeyError, TypeError) as exc:
        block('authority_unavailable', detail=type(exc).__name__)
    blockers = sorted({p.digest(b): b for b in blockers}.values(), key=lambda b: (b['stage'], b['code'], b['detail']))
    result = {'schema': 'las.p36-authority-capture/1', 'passed': not blockers, 'blockers': blockers,
              'family_sha256': p.digest(family), 'binding_sha256': p.digest(binding),
              'stages': [s for s in p.STAGES if s in selected], 'snapshot': snapshot,
              'evidence_state': 'implemented', 'generation_submitted': False,
              'reviewer_authenticated': False, 'licence_clearance_inferred': False,
              'validity': 'snapshot-only; recheck at the worker/importer mutation boundary'}
    result['capture_sha256'] = p.digest(result)
    return result
