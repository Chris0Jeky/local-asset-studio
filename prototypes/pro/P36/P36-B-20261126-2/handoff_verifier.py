"""Offline integrity/claim verifier for P36 staged drafts; never native admission.

Unkeyed hashes are not signatures. Captured rows and semantic annotations remain
declarations. Current checks require caller-supplied Studio paths; bundle paths
never select authority. Even a live pass authorizes no dispatch or native import.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

if __name__ == '__main__': sys.dont_write_bytecode = True

import admission
import attempt_ledger
from export_guard import build_guarded_manifest
import pipeline as p
import sheet_identity
import studio_authority as authority

DOCUMENTS = {'family': 'family.json', 'binding': 'binding.json', 'metadata': 'character-metadata.json',
             'semantic_policy': 'semantic-policy.json', 'annotations': 'annotations.json',
             'pack': 'pack.json', 'captured': 'current-authority.json', 'ready': 'READY.json'}
ROOT_FIELDS = ('experiments_root_sha256', 'asset_root_sha256', 'ledger_path_sha256')
MAX_TOTAL_BYTES = 64 * 1024**3


def _exact(value, fields, label):
    p.require(type(value) is dict and set(value) == set(fields), 'Unsupported ' + label + ' fields', 'unsupported_claim')


def _same(actual, expected, label):
    p.require(p.canonical_bytes(actual) == p.canonical_bytes(expected), label + ' differs from reconstructed facts',
              'claim_mismatch')


def _hash_field(value):
    p.require(type(value) is str and p.HEX64.fullmatch(value), 'SHA-256 field required', 'invalid_digest')


def _sealed(value, field):
    copied = dict(value); claimed = copied.pop(field)
    _hash_field(claimed); _same(claimed, p.digest(copied), field)


def _strict_family(family):
    _exact(family, ('schema', 'family_id', 'workspace_id', 'character_id', 'mode', 'policy',
                    'policy_sha256', 'receipts', 'heads'), 'family')
    p.validate_family(family)
    _same(sorted(family['heads']), sorted(p.STAGES), 'complete stage inventory')
    for receipt in family['receipts'].values():
        _exact(receipt, ('id', 'payload', 'generation', 'inspection', 'acceptance', 'licence'), 'receipt')
        _exact(receipt['payload'], ('family_id', 'workspace_id', 'character_id', 'mode', 'policy_sha256',
            'stage', 'parents', 'concept_id', 'artifacts', 'recipe', 'references', 'identity', 'quality'), 'receipt payload')


def _stream_files(bundle, pack):
    """Read at most the declared bytes plus one, with bounded 1 MiB buffers."""
    p.require(type(pack.get('files')) is dict and 0 < len(pack['files']) <= 384, 'Bounded file inventory required')
    seen, total = set(), 0
    for record in pack['files'].values():
        p.require(type(record) is dict and type(record.get('bytes')) is int and
                  0 < record['bytes'] <= 8 * 1024**3, 'Invalid artifact byte bound')
        p.safe_relative(record.get('path')); _hash_field(record.get('sha256'))
        folded = record['path'].casefold()
        p.require(folded not in seen, 'Repeated or case-colliding manifest paths'); seen.add(folded)
        total += record['bytes']; p.require(total <= MAX_TOTAL_BYTES, 'Bundle exceeds 64 GiB verification bound')
        relative = f"assets/packs/{pack['id']}/{record['path']}"
        path = p.contained_file(bundle, relative); before = path.stat()
        p.require(before.st_size == record['bytes'], 'Copied artifact byte count changed', 'asset_bytes_changed')
        h, count = hashlib.sha256(), 0
        with path.open('rb') as handle:
            while True:
                chunk = handle.read(min(1024 * 1024, record['bytes'] - count + 1))
                if not chunk: break
                count += len(chunk)
                p.require(count <= record['bytes'], 'Copied artifact grew during read', 'asset_bytes_changed')
                h.update(chunk)
        after = path.stat()
        p.require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                  (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and
                  count == record['bytes'] and h.hexdigest() == record['sha256'],
                  'Copied artifact changed or digest differs', 'asset_bytes_changed')
    return total


def _file_references(node, files):
    if type(node) is dict:
        for key, value in node.items():
            if key == 'file':
                p.require(type(value) is str and value in files, 'Invalid or dangling recursive file reference',
                          'file_reference_invalid')
            else: _file_references(value, files)
    elif type(node) is list:
        for value in node: _file_references(value, files)


def _captured_authority(captured, family, binding, concept):
    _exact(captured, ('schema', 'passed', 'blockers', 'family_sha256', 'binding_sha256', 'stages', 'snapshot',
        'evidence_state', 'generation_submitted', 'reviewer_authenticated', 'licence_clearance_inferred',
        'validity', 'capture_sha256'), 'authority capture')
    _sealed(captured, 'capture_sha256')
    snapshot = captured['snapshot']; _exact(snapshot, ('workspace_id', 'card', 'assets', 'jobs'), 'authority snapshot')
    _same(snapshot['workspace_id'], family['workspace_id'], 'captured Workspace')
    card = snapshot['card']; _exact(card, ('id', 'kind', 'revision', 'lineage', 'body', 'trashed_at'), 'captured card')
    _same({k: card[k] for k in ('id', 'kind', 'revision', 'trashed_at')},
          {'id': binding['character_card_id'], 'kind': 'character', 'revision': binding['card_revision'],
           'trashed_at': None}, 'captured card subject')
    p.require(type(card['lineage']) is str and type(card['body']) is str, 'Encoded card fields required')
    lineage = p.decode_json(card['lineage']); authority.validate_character_body(p.decode_json(card['body']))
    p.require(type(lineage) is list, 'Card lineage must be a list')
    canon = [row for row in lineage if type(row) is dict and row.get('role') == 'canon']
    p.require(len(canon) == 1 and canon[0].get('asset_id') == concept['asset_id']
              and canon[0].get('sha256') == concept['media_sha256'], 'Captured canon differs', 'captured_subject_mismatch')
    expected_assets, expected_jobs = set(), {}
    p.require(type(snapshot['assets']) is dict and type(snapshot['jobs']) is dict, 'Captured inventories required')
    for stage in p.STAGES:
        bound = binding['stages'][stage]; used_jobs = set()
        for artifact in family['receipts'][family['heads'][stage]]['payload']['artifacts']:
            key = stage + '/' + artifact['key']; expected_assets.add(key)
            row = snapshot['assets'][key]; grant = bound['artifacts'][artifact['key']]
            _exact(row, ('id', 'job_id', 'output_index', 'sha256', 'bytes', 'path', 'review', 'privacy',
                         'metadata_revision', 'trashed_at', 'acceptance'), 'captured asset')
            _same({k: row[k] for k in ('id', 'sha256', 'bytes', 'privacy', 'trashed_at')},
                  {'id': artifact['asset_id'], 'sha256': artifact['sha256'], 'bytes': artifact['bytes'],
                   'privacy': 'regular', 'trashed_at': None}, 'captured artifact subject')
            p.require(type(row['output_index']) is int and 0 <= row['output_index'] < 2**53 and
                      type(row['metadata_revision']) is int and 0 <= row['metadata_revision'] < 2**53 and
                      row['review'] in ('unreviewed', 'selected'), 'Invalid captured asset state')
            p.safe_relative(row['path']); p.require(row['path'].startswith('media/'), 'Expected captured Workspace media')
            accepted = row['acceptance']
            _exact(accepted, ('id', 'asset_id', 'sha256', 'use', 'reviewer', 'accepted_at', 'withdrawn_at',
                              'brief_id', 'slot', 'criteria'), 'captured acceptance')
            p.require(type(accepted['accepted_at']) in (int, float) and accepted['accepted_at'] >= 0,
                      'Invalid captured acceptance time')
            _same(accepted, {'id': grant['acceptance_id'], 'asset_id': artifact['asset_id'],
                'sha256': artifact['sha256'], 'use': grant['use'], 'reviewer': 'local-user',
                'accepted_at': accepted['accepted_at'], 'withdrawn_at': None, 'brief_id': None,
                'slot': None, 'criteria': None}, 'captured acceptance subject')
            job_id = row['job_id']; p.require(type(job_id) is str and job_id in bound['jobs'], 'Unbound captured job')
            p.require(row['id'] == authority.AssetWorkspace.asset_id({'id': job_id}, row['output_index']),
                      'Captured asset ID differs from job/output index', 'captured_subject_mismatch')
            used_jobs.add(job_id); job = snapshot['jobs'][job_id]
            _exact(job, ('state_sha256', 'workflow_sha256', 'status', 'operation', 'prompt_ids'), 'captured job')
            _same({k: job[k] for k in ('state_sha256', 'workflow_sha256')}, bound['jobs'][job_id], 'captured job digests')
            p.require(job['status'] == 'completed' and type(job['prompt_ids']) is list, 'Captured job is not settled')
            ids = job['prompt_ids']
            p.require((job['operation'] == 'asset.import' and ids == []) or
                      (job['operation'] is None and ids and all(type(x) is str and x.strip() for x in ids)
                       and len(ids) == len(set(ids))), 'Unsupported captured job declaration')
            if job_id in expected_jobs: _same(expected_jobs[job_id], job, 'reused captured job')
            expected_jobs[job_id] = job
        _same(sorted(used_jobs), sorted(bound['jobs']), 'captured stage job inventory')
    _same(sorted(snapshot['assets']), sorted(expected_assets), 'captured asset inventory')
    _same(snapshot['jobs'], expected_jobs, 'captured job inventory')
    expected = {'schema': 'las.p36-authority-capture/1', 'passed': True, 'blockers': [],
        'family_sha256': p.digest(family), 'binding_sha256': p.digest(binding), 'stages': list(p.STAGES),
        'snapshot': snapshot, 'evidence_state': 'implemented', 'generation_submitted': False,
        'reviewer_authenticated': False, 'licence_clearance_inferred': False,
        'validity': 'snapshot-only; recheck at the worker/importer mutation boundary'}
    expected['capture_sha256'] = p.digest(expected); _same(captured, expected, 'authority capture')


def _captured_ledger(captured, family):
    _exact(captured, ('schema', 'passed', 'blockers', 'family_id', 'stages', 'attempts', 'generation_submitted',
                      'submission_authority', 'scope', 'snapshot_sha256'), 'attempt capture')
    _sealed(captured, 'snapshot_sha256')
    rows = captured['attempts']; p.require(type(rows) is list and len(rows) <= 4096, 'Bounded attempt list required')
    seen, jobs, sources = set(), set(), set()
    for row in rows:
        _exact(row, (*attempt_ledger.IDENTITY_FIELDS, 'attempt_id', 'state', 'observation_sha256', 'revision'), 'attempt')
        attempt_ledger._validate_row(row)
        p.require(row['family_id'] == family['family_id'] and row['workspace_id'] == family['workspace_id'] and
                  row['state'] in ('completed', 'failed'), 'Captured attempt is unresolved or outside scope')
        key = row['request_id']; p.require(key not in seen and row['job_id'] not in jobs, 'Duplicate captured attempt')
        seen.add(key); jobs.add(row['job_id'])
        sources.add(row['source_root_sha256'])
    p.require(len(sources) <= 1, 'Retained attempts name inconsistent source roots', 'captured_source_mismatch')
    _same(rows, sorted(rows, key=lambda row: (row['stage'], row['request_id'])), 'captured attempt order')
    expected = {'schema': 'las.p36-attempt-capture/1', 'passed': True, 'blockers': [],
        'family_id': family['family_id'], 'stages': sorted(p.STAGES), 'attempts': rows,
        'generation_submitted': False, 'submission_authority': False,
        'scope': 'Only attempts reserved in this ledger; worker integration must reserve every attempt'}
    expected['snapshot_sha256'] = p.digest(expected); _same(captured, expected, 'attempt capture')


def _reconstruct_admission(docs, store):
    family, binding, policy, annotations = (docs[k] for k in ('family', 'binding', 'semantic_policy', 'annotations'))
    captured = docs['captured']; authority.validate_binding(family, binding)
    _same(sorted(annotations), sorted(p.STAGES), 'annotation stage inventory')
    root = family['receipts'][family['heads']['concept']]['payload']
    asset = next(a for a in root['artifacts'] if a['asset_id'] == binding['concept_asset_id'])
    concept = {'asset_id': asset['asset_id'], 'media_sha256': asset['sha256'], 'receipt_digest': family['heads']['concept']}
    policy_hash = sheet_identity.semantic_policy_digest(policy); _same(policy['concept'], concept, 'semantic concept')
    semantic = {}; metric = {k: family['policy'][k] for k in ('version', 'features', 'required')}
    for stage in p.STAGES:
        p.require(family['mode'] != 'production' or not admission._fixture_semantics(annotations[stage]),
                  'Synthetic semantic annotations cannot qualify production', 'synthetic_semantic_provenance')
        payload = family['receipts'][family['heads'][stage]]['payload']
        scored = sheet_identity.score_sheet_identity(root['identity']['anchor_features'], payload['identity']['sheet'],
            metric, stage, semantic_policy=policy, annotations=annotations[stage], concept=concept)
        p.require(scored['passed'] is True, 'Recomputed semantic identity refused: ' + stage, 'semantic_identity_failed')
        semantic[stage] = scored
    _captured_authority(captured['authority'], family, binding, concept)
    _captured_ledger(captured['ledger'], family)
    fingerprints = {'family_sha256': p.digest(family), 'binding_sha256': p.digest(binding),
        'semantic_policy_sha256': policy_hash, 'annotations_sha256': p.digest(annotations), 'concept_sha256': p.digest(concept)}
    for name in ROOT_FIELDS:
        value = captured['input_fingerprints'][name]; _hash_field(value); fingerprints[name] = value
    expected = {'schema': 'las.p36-transition-admission/1', 'evidence_state': 'implemented', 'stage': 'unreal',
        'include_target': True, 'passed': True, 'blockers': [], 'action': 'prepare-only',
        'generation_submitted': False, 'submission_authority': False, 'native_import_performed': False,
        'perceptual_identity_verified': False, 'reviewer_authenticated': False, 'licence_clearance_inferred': False,
        'selected_stages': list(p.STAGES), 'ledger_stages': list(p.STAGES), 'input_fingerprints': fingerprints,
        'capture_fingerprints': {'authority_sha256': captured['authority']['capture_sha256'],
            'ledger_sha256': captured['ledger']['snapshot_sha256'], 'semantic_sha256': p.digest(semantic)},
        'next_gate': p.next_gate(family, 'unreal', asset_root=store), 'target_gate': p.assess(family, 'unreal'),
        'semantic': semantic, 'authority': captured['authority'], 'ledger': captured['ledger'], 'media_bytes_verified': True,
        'validity': 'snapshot-only; recheck before dispatch, export promotion or native import'}
    p.require(expected['next_gate']['passed'] and expected['target_gate']['passed'], 'Recomputed family gate refused')
    expected['report_sha256'] = p.digest(expected); _same(captured, expected, 'complete admission report')
    return expected


def verify_handoff(bundle, *, experiments=None, ledger_path=None, require_current=False,
                   allow_synthetic=False, expected_pack_id=None):
    """Return a bounded hashed report; neither offline nor live pass grants import."""
    result = {'schema': 'las.p36-handoff-verification/1', 'evidence_state': 'implemented',
        'action': 'verify-handoff-only', 'passed': False, 'blockers': [], 'integrity_verified': False,
        'require_current': require_current is True, 'allow_synthetic': allow_synthetic is True,
        'synthetic': None, 'current_authority_checked': False, 'current_authority_matches': False,
        'native_import_allowed': False, 'native_import_performed': False, 'generation_submitted': False,
        'production_promoted': False, 'owner_authenticated': False, 'acceptance_inferred': False,
        'licence_clearance_inferred': False, 'perceptual_identity_verified': False,
        'input_fingerprints': {}, 'artifact_count': 0, 'artifact_bytes': 0,
        'current_report_sha256': None, 'retained_admission_sha256': None,
        'validity': 'optimistic integrity snapshot; hashes are not signatures; consumer must rehash and revalidate'}
    try:
        p.require(type(require_current) is bool and type(allow_synthetic) is bool, 'Verifier flags must be booleans')
        p.require(expected_pack_id is None or type(expected_pack_id) is str and p.CHARACTER.fullmatch(expected_pack_id),
                  'Expected pack ID is invalid')
        p.require(not require_current or experiments is not None and ledger_path is not None,
                  'Current verification needs explicit owner experiments and ledger paths', 'current_context_required')
        p.require(require_current or experiments is None and ledger_path is None,
                  'Supply owner paths only with require_current', 'ambiguous_current_context')
        bundle = Path(bundle).absolute()
        relative = list(DOCUMENTS.values())
        for name in ('PARTIAL.json', 'READY.pending.json'):
            if (bundle / name).exists() or p.linked(bundle / name): relative.append(name)
        before = admission._destination_observation(bundle, relative)
        loaded = {name: authority.read_record(bundle, path) for name, path in DOCUMENTS.items()}
        docs = {name: record[0] for name, record in loaded.items()}
        family, pack, ready = (docs[k] for k in ('family', 'pack', 'ready'))
        _strict_family(family); p.require(type(pack) is dict and pack.get('id') == family['character_id'], 'Pack subject differs')
        p.require(expected_pack_id is None or pack['id'] == expected_pack_id, 'Expected pack ID differs', 'pack_id_mismatch')
        result['synthetic'] = family['mode'] == 'synthetic'
        p.require(allow_synthetic or not result['synthetic'], 'Synthetic bundle needs explicit permission', 'synthetic_refused')
        p.require(pack.get('schema') == 'lumenfold.pack/1' and pack.get('status') == 'draft', 'Only supported draft packs are verified')
        store = bundle / 'assets' / 'packs' / pack['id']
        result['artifact_bytes'] = _stream_files(bundle, pack); result['artifact_count'] = len(pack['files'])
        asset_paths = [f"assets/packs/{pack['id']}/{record['path']}" for record in pack['files'].values()]
        observed_assets = admission._destination_observation(bundle, asset_paths)
        extension = pack['x-studio-character-pipeline']; release = extension['release_clearance_checked']
        intended = extension['intended_use']
        p.require(type(release) is bool and (intended is None or type(intended) is str and intended), 'Invalid release declarations')
        expected_pack = build_guarded_manifest(family, store, docs['metadata'], release=release, intended_use=intended)
        reconstructed = _reconstruct_admission(docs, store)
        ext = expected_pack['x-studio-character-pipeline']; ext['handoff_sidecar'] = 'READY.json'
        ext['consumer_admission'].update(authority_sidecar='current-authority.json', admission_sha256=reconstructed['report_sha256'])
        _file_references(pack, pack['files'])
        _same(pack, expected_pack, 'guarded pack manifest including file references')
        inputs = {key: p.digest(docs[key]) for key in ('family', 'binding', 'metadata', 'semantic_policy', 'annotations')}
        expected_ready = {'schema': 'las.p36-ready-handoff/1', 'family_sha256': inputs['family'],
            'pack_sha256': p.digest(pack), 'authority_sha256': p.digest(reconstructed), 'input_fingerprints': inputs,
            'admission_sha256': reconstructed['report_sha256'], 'concept_receipt': family['heads']['concept'],
            'mode': family['mode'], 'evidence_state': 'implemented', 'generation_submitted': False,
            'asset_copy_performed': True, 'assets_verified_at_export': True, 'revalidate_at_import': True,
            'current_direct_import_allowed': False, 'native_import_performed': False, 'unreal_import': 'planned'}
        _same(ready, expected_ready, 'completion marker')
        if 'PARTIAL.json' in relative:
            partial, _ = authority.read_record(bundle, 'PARTIAL.json')
            _same(partial, {'schema': 'las.p36-export-staging/1', 'phase': 'staging', 'family_sha256': inputs['family'],
                'pack_sha256': p.digest(pack), 'generation_submitted': False, 'native_import_performed': False,
                'completion_marker': 'READY.json', 'retry_allowed': False}, 'retained staging marker')
        if 'READY.pending.json' in relative:
            pending, raw_hash = authority.read_record(bundle, 'READY.pending.json')
            _same(pending, ready, 'pending marker'); _same(raw_hash, loaded['ready'][1], 'pending marker bytes')
        result['input_fingerprints'] = {name: p.digest(value) for name, value in docs.items()}
        result['retained_admission_sha256'] = reconstructed['report_sha256']
        admission._check_destination_observation(bundle, {**before, **observed_assets})
        result['integrity_verified'] = True
        if require_current:
            original = reconstructed['input_fingerprints']
            _same(p.digest(str(Path(experiments).absolute())), original['experiments_root_sha256'], 'explicit experiments root')
            _same(p.digest(str(Path(ledger_path).absolute())), original['ledger_path_sha256'], 'explicit ledger path')
            current = admission.check_transition(experiments, family, docs['binding'], 'unreal', asset_root=store,
                semantic_policy=docs['semantic_policy'], annotations=docs['annotations'], ledger_path=ledger_path, include_target=True)
            result['current_authority_checked'] = True; result['current_report_sha256'] = current['report_sha256']
            p.require(current['passed'] is True, 'Current source admission refused', 'current_authority_refused')
            # The copied asset root differs by transport; all source authority,
            # ledger, annotations and other input facts must remain identical.
            projected = dict(current); projected.pop('report_sha256')
            projected['input_fingerprints'] = dict(current['input_fingerprints'])
            projected['input_fingerprints']['asset_root_sha256'] = original['asset_root_sha256']
            projected['report_sha256'] = p.digest(projected)
            _same(projected, reconstructed, 'current source capture with copied asset-root projection')
            result['current_authority_matches'] = True
        admission._check_destination_observation(bundle, {**before, **observed_assets})
        result['passed'] = True
    except Exception as error:
        if result['integrity_verified']:
            try: admission._check_destination_observation(bundle, {**before, **observed_assets})
            except Exception: result['integrity_verified'] = False
        result['blockers'].append({'code': admission._diagnostic(getattr(error, 'code', 'verification_failed'), 128),
                                  'detail': admission._diagnostic(type(error).__name__ + ': ' + str(error), 400)})
    result['report_sha256'] = p.digest(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    verify = commands.add_parser('verify'); verify.add_argument('--bundle', required=True)
    verify.add_argument('--allow-synthetic', action='store_true'); verify.add_argument('--require-current', action='store_true')
    verify.add_argument('--experiments'); verify.add_argument('--ledger'); verify.add_argument('--expected-pack-id')
    args = parser.parse_args(argv)
    result = verify_handoff(args.bundle, experiments=args.experiments, ledger_path=args.ledger,
        require_current=args.require_current, allow_synthetic=args.allow_synthetic, expected_pack_id=args.expected_pack_id)
    sys.stdout.buffer.write(p.canonical_bytes(result))
    return 0 if result['passed'] else 2


if __name__ == '__main__': raise SystemExit(main())
