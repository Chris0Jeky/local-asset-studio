"""Prepare-only Studio admission and isolated draft handoff staging.

This combines fresh receipt/media checks, supplied semantic declarations, live
Workspace authority and the durable attempt ledger. It never dispatches a job,
reserves a retry, imports an engine asset, grants a licence, or accepts art.

Semantic policy is explicit operator-owned configuration. It is never obtained
from a candidate score/report. Hashes bind its supplied contents; they cannot
authenticate its author or prove that matching annotations describe the images.

READY.json means only that this draft passed the recorded staging checks. The
current Lumenfold importer does not enforce this marker or extension; a future
adapter must revalidate authority and bytes at its own mutation boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True

import attempt_ledger
from export_guard import build_guarded_manifest
from pack_export import verify_family_media
import pipeline as p
import sheet_identity
import studio_authority


CONSUMER_VALIDATOR_SHA256 = '268588d7d01d09f9c597dce7c7dfafe050066586702676cfe633bad941af4de7'
CONSUMER_SCHEMA_SHA256 = '9892f716abfff35a85088c5b5c798a8ae38ddbff50f1e67845f799c7af16a28a'


def _closure(stage):
    selected = set()
    def visit(node):
        for parent in p.PARENTS[node]:
            if parent not in selected:
                selected.add(parent)
                visit(parent)
    visit(stage)
    return selected


def _diagnostic(value, limit):
    # Even malformed JSON strings containing lone surrogates must yield a
    # serializable failure. Diagnostics are bounded text, never authority.
    return str(value)[:limit].encode('utf-8', errors='backslashreplace').decode('utf-8')[:limit]


def _block(result, code, *, stage='', detail='', source='admission'):
    result['blockers'].append({'code': _diagnostic(code, 128), 'stage': _diagnostic(stage, 64),
                               'detail': _diagnostic(detail, 400), 'source': _diagnostic(source, 64)})


def _finish(result):
    result['blockers'] = sorted({p.digest(item): item for item in result['blockers']}.values(),
                                key=lambda item: (item['stage'], item['source'], item['code'], item['detail']))
    result['passed'] = not result['blockers']
    result['report_sha256'] = p.digest(result)
    return result


def _merge_blockers(result, report, source):
    for item in report.get('blockers', []):
        if type(item) is dict:
            _block(result, item.get('code', 'failed_check'), stage=item.get('stage', ''),
                   detail=item.get('detail', ''), source=source)
        else:
            _block(result, str(item), source=source)
    if not report.get('passed') and not report.get('blockers'):
        _block(result, 'failed_check', source=source)


def _fixture_semantics(annotation):
    if type(annotation) is not dict or type(annotation.get('views')) is not list:
        return False
    return any(type(view) is dict and type(view.get('anchors')) is dict and
               any(type(record) is dict and record.get('provenance') == 'fixture_truth'
                   for record in view['anchors'].values()) for view in annotation['views'])


def check_transition(experiments, family, binding, stage, *, asset_root, semantic_policy,
                     annotations, ledger_path, include_target=False):
    """Recompute the requested transition; ordinary malformed input returns failure.

Annotations must cover exactly the active stage inventory. Only the selected
ancestor closure is eligible to authorize a new preparation. Export also checks
the target receipt. Ledger scope always includes the requested target, including
when an uncertain attempt has produced no artifact or target receipt.
"""
    result = {'schema': 'las.p36-transition-admission/1', 'evidence_state': 'implemented',
              'stage': stage if type(stage) is str and stage in p.STAGES else None,
              'include_target': include_target is True,
              'passed': False, 'blockers': [], 'action': 'prepare-only',
              'generation_submitted': False, 'submission_authority': False,
              'native_import_performed': False, 'perceptual_identity_verified': False,
              'reviewer_authenticated': False, 'licence_clearance_inferred': False,
              'selected_stages': [], 'ledger_stages': [], 'input_fingerprints': {},
              'capture_fingerprints': {}, 'next_gate': None, 'target_gate': None,
              'semantic': {}, 'authority': None, 'ledger': None, 'media_bytes_verified': False,
              'validity': 'snapshot-only; recheck before dispatch, export promotion or native import'}
    try:
        p.require(type(stage) is str and stage in p.STAGES, 'Unsupported transition stage')
        p.require(type(include_target) is bool, 'include_target must be boolean')
        p.require(asset_root is not None and ledger_path is not None, 'Explicit media root and attempt ledger required')
        studio_authority.validate_binding(family, binding)
        p.require(type(annotations) is dict and set(annotations) == set(family['heads']),
                  'Annotations must cover exactly the active stage inventory')
        policy_hash = sheet_identity.semantic_policy_digest(semantic_policy)
        root_payload = family['receipts'][family['heads']['concept']]['payload']
        root_asset = next(a for a in root_payload['artifacts'] if a['asset_id'] == binding['concept_asset_id'])
        concept = {'asset_id': root_asset['asset_id'], 'media_sha256': root_asset['sha256'],
                   'receipt_digest': family['heads']['concept']}
        p.require(semantic_policy['concept'] == concept, 'Semantic policy names a stale or different root concept')
        selected = _closure(stage)
        if include_target:
            selected.add(stage)
        # A replacement-concept preparation still binds/checks the existing canon.
        selected.add('concept')
        p.require(selected <= set(family['heads']), 'Required ancestor or target receipt is missing')
        result['selected_stages'] = [name for name in p.STAGES if name in selected]
        result['ledger_stages'] = [name for name in p.STAGES if name in selected | {stage}]
        result['input_fingerprints'] = {
            'family_sha256': p.digest(family), 'binding_sha256': p.digest(binding),
            'semantic_policy_sha256': policy_hash, 'annotations_sha256': p.digest(annotations),
            'concept_sha256': p.digest(concept),
            'experiments_root_sha256': p.digest(str(Path(experiments).absolute())),
            'asset_root_sha256': p.digest(str(Path(asset_root).absolute())),
            'ledger_path_sha256': p.digest(str(Path(ledger_path).absolute())),
        }
        result['next_gate'] = p.next_gate(family, stage, asset_root=asset_root)
        _merge_blockers(result, result['next_gate'], 'receipt')
        if include_target:
            result['target_gate'] = p.assess(family, stage)
            _merge_blockers(result, result['target_gate'], 'receipt')
        try:
            verify_family_media(family, asset_root, stages=selected)
            result['media_bytes_verified'] = True
        except (ValueError, OSError, KeyError, TypeError) as error:
            _block(result, 'media_verification_failed', stage=stage, detail=error, source='media')
        metric_policy = {key: family['policy'][key] for key in ('version', 'features', 'required')}
        anchor = root_payload['identity']['anchor_features']
        for name in result['selected_stages']:
            if family['mode'] == 'production' and _fixture_semantics(annotations[name]):
                _block(result, 'synthetic_semantic_provenance', stage=name, source='semantic')
            payload = family['receipts'][family['heads'][name]]['payload']
            scored = sheet_identity.score_sheet_identity(anchor, payload['identity']['sheet'], metric_policy, name,
                        semantic_policy=semantic_policy, annotations=annotations[name], concept=concept)
            result['semantic'][name] = scored
            if not scored['passed']:
                _block(result, 'semantic_identity_failed', stage=name,
                       detail=', '.join(scored['blockers']), source='semantic')
        result['authority'] = studio_authority.capture_authority(experiments, family, binding, stages=selected)
        _merge_blockers(result, result['authority'], 'authority')
        result['capture_fingerprints']['authority_sha256'] = result['authority']['capture_sha256']
        try:
            ledger = attempt_ledger.inspect(ledger_path, family_id=family['family_id'],
                                             stages=result['ledger_stages'], experiments=experiments)
            p.require(type(ledger) is dict and type(ledger.get('passed')) is bool
                      and type(ledger.get('snapshot_sha256')) is str
                      and p.HEX64.fullmatch(ledger['snapshot_sha256']), 'Invalid attempt ledger capture')
            result['ledger'] = ledger
            _merge_blockers(result, ledger, 'attempt-ledger')
            result['capture_fingerprints']['ledger_sha256'] = ledger['snapshot_sha256']
        except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
            _block(result, 'attempt_ledger_unavailable', stage=stage, detail=error, source='attempt-ledger')
        result['capture_fingerprints']['semantic_sha256'] = p.digest(result['semantic'])
    except (ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError, StopIteration, sqlite3.Error) as error:
        _block(result, 'invalid_contract', stage=stage if type(stage) is str else '',
               detail=str(error) or type(error).__name__)
    return _finish(result)


def _output_path(out):
    path = Path(out).absolute()
    runtime = p.REPO_ROOT / '.runtime'
    p.require(path.resolve().is_relative_to(runtime.resolve()) and path != runtime,
              'Export destination must be a new directory under repository .runtime/', 'unsafe_destination')
    p.safe_relative(path.relative_to(runtime).as_posix())
    p.require(not any(p.linked(part) for part in (path, *path.parents)),
              'Linked export destination refused', 'unsafe_destination')
    p.require(not path.exists(), 'Export destination exists; inspect retained evidence before another explicit export',
              'destination_exists')
    return path


def _write_new(path, value):
    p.require(not any(p.linked(part) for part in (path, *path.parents)), 'Linked output file refused')
    raw = p.canonical_bytes(value)
    with path.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(raw).hexdigest()


def _copy_asset(asset_root, record, output_store):
    """Copy one verified file exclusively, then validate its exact copied bytes."""
    source = p.verify_artifact(asset_root, record)
    target = output_store / record['path']
    p.require(target.resolve().is_relative_to(output_store.resolve()), 'Copied path escaped its asset store')
    p.require(not any(p.linked(part) for part in (target, *target.parents)), 'Linked copy destination refused')
    target.parent.mkdir(parents=True, exist_ok=True)
    observed = hashlib.sha256()
    count = 0
    with source.open('rb') as reader, target.open('xb') as writer:
        before = os.fstat(reader.fileno())
        for chunk in iter(lambda: reader.read(1024 * 1024), b''):
            count += len(chunk)
            p.require(count <= record['bytes'], 'Source grew during copy', 'source_changed_during_copy')
            observed.update(chunk)
            writer.write(chunk)
        after = os.fstat(reader.fileno())
        p.require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                  (after.st_ino, after.st_size, after.st_mtime_ns),
                  'Source changed during copy', 'source_changed_during_copy')
        p.require(count == record['bytes'] and observed.hexdigest() == record['sha256'],
                  'Copied bytes differ from receipt', 'source_changed_during_copy')
        writer.flush()
        os.fsync(writer.fileno())
    p.verify_artifact(output_store, record)


def _inputs(family, binding, metadata, semantic_policy, annotations):
    return {name: p.digest(value) for name, value in
            [('family', family), ('binding', binding), ('metadata', metadata),
             ('semantic_policy', semantic_policy), ('annotations', annotations)]}


def _verify_copied(pack, store):
    for record in pack['files'].values():
        p.verify_artifact(store, record)


def _consumer_check(lumenfold_root, pack, assets):
    """Execute only the inspected pure validator, never a native importer."""
    root = Path(lumenfold_root)
    validator = p.contained_file(root, 'pipelines/characters/validate_pack.py')
    schema_path = p.contained_file(root, 'packs/pack.schema.json')
    p.require(validator.stat().st_size <= 128 * 1024 and schema_path.stat().st_size <= 128 * 1024,
              'Supplied consumer source exceeds the inspected bounds', 'consumer_source_changed')
    raw, schema_raw = validator.read_bytes(), schema_path.read_bytes()
    p.require(hashlib.sha256(raw).hexdigest() == CONSUMER_VALIDATOR_SHA256,
              'Supplied Lumenfold validator differs from the inspected source', 'consumer_source_changed')
    p.require(hashlib.sha256(schema_raw).hexdigest() == CONSUMER_SCHEMA_SHA256,
              'Supplied Lumenfold schema differs from the inspected source', 'consumer_source_changed')
    namespace = {'__name__': 'p36_pinned_consumer_validator', '__file__': str(validator)}
    exec(compile(raw, str(validator), 'exec'), namespace)
    namespace['SCHEMA'] = p.decode_json(schema_raw)
    namespace['ROOT'] = assets
    errors = namespace['validate_doc'](pack, pack['id'], False, check_files=True)
    p.require(not errors, 'Pinned consumer validator refused staged bytes: ' + '; '.join(errors),
              'consumer_validation_failed')
    return {'passed': True, 'validator_sha256': CONSUMER_VALIDATOR_SHA256,
            'schema_sha256': CONSUMER_SCHEMA_SHA256, 'native_import_performed': False}


def _check_input_files(input_files, initial):
    if input_files is None:
        return
    p.require(type(input_files) is dict and set(input_files) == set(initial), 'Explicit input-file inventory differs')
    for name, path in input_files.items():
        current = _read_input(path)
        p.require(p.digest(current) == initial[name], 'Input file changed while staging: ' + name, 'inputs_changed')


def export_verified_bundle(experiments, family, binding, metadata, out, *, asset_root, semantic_policy,
                           annotations, ledger_path, release=False, intended_use=None,
                           lumenfold_root=None, _input_files=None):
    """Stage an exclusive bundle; failure retains every partial file and no READY.

The optional consumer root must contain the exact inspected schema/validator.
This API does not initialize the ledger, reserve attempts or import native files.
CLI inputs are reopened before completion; in-memory callers' whole inputs are
fingerprinted again, including metadata and policy/annotations.
"""
    report = {'schema': 'las.p36-staged-export/1', 'evidence_state': 'implemented',
              'passed': False, 'ready': False, 'blockers': [], 'action': 'stage-draft-only',
              'generation_submitted': False, 'submission_authority': False,
              'native_import_performed': False, 'partial_retained': False, 'output': None,
              'input_fingerprints': {}, 'initial_admission_sha256': None,
              'final_admission_sha256': None, 'consumer_validation': None}
    created = False
    output = None
    try:
        output = _output_path(out)
        report['output'] = str(output)
        initial_inputs = _inputs(family, binding, metadata, semantic_policy, annotations)
        report['input_fingerprints'] = initial_inputs
        _check_input_files(_input_files, initial_inputs)
        first = check_transition(experiments, family, binding, 'unreal', asset_root=asset_root,
                    semantic_policy=semantic_policy, annotations=annotations, ledger_path=ledger_path, include_target=True)
        report['initial_admission_sha256'] = first['report_sha256']
        if not first['passed']:
            _merge_blockers(report, first, 'admission')
            return _finish(report)
        pack = build_guarded_manifest(family, asset_root, metadata, release=release, intended_use=intended_use)
        # These files are bundle metadata, not entries in the binary asset store.
        extension = pack['x-studio-character-pipeline']
        extension['handoff_sidecar'] = 'READY.json'
        extension['consumer_admission']['authority_sidecar'] = 'current-authority.json'
        extension['consumer_admission']['admission_sha256'] = first['report_sha256']
        pack_hash = p.digest(pack)
        output.mkdir(parents=True, exist_ok=False)
        created = True
        report['partial_retained'] = True
        _write_new(output / 'PARTIAL.json', {'schema': 'las.p36-export-staging/1', 'phase': 'staging',
            'family_sha256': initial_inputs['family'], 'pack_sha256': pack_hash,
            'generation_submitted': False, 'native_import_performed': False,
            'completion_marker': 'READY.json', 'retry_allowed': False})
        store = output / 'assets' / 'packs' / pack['id']
        store.mkdir(parents=True, exist_ok=False)
        for key in sorted(pack['files']):
            _copy_asset(asset_root, pack['files'][key], store)
        _write_new(output / 'family.json', family)
        _write_new(output / 'pack.json', pack)
        _write_new(output / 'current-authority.json', first)
        _write_new(output / 'binding.json', binding)
        _write_new(output / 'semantic-policy.json', semantic_policy)
        _write_new(output / 'annotations.json', annotations)
        _write_new(output / 'character-metadata.json', metadata)
        _verify_copied(pack, store)
        if lumenfold_root is not None:
            report['consumer_validation'] = _consumer_check(lumenfold_root, pack, output / 'assets')
        p.require(_inputs(family, binding, metadata, semantic_policy, annotations) == initial_inputs,
                  'An export input changed during staging', 'inputs_changed')
        _check_input_files(_input_files, initial_inputs)
        _verify_copied(pack, store)
        for filename, expected in [('family.json', initial_inputs['family']), ('pack.json', pack_hash),
                                   ('current-authority.json', p.digest(first)), ('binding.json', initial_inputs['binding']),
                                   ('semantic-policy.json', initial_inputs['semantic_policy']),
                                   ('annotations.json', initial_inputs['annotations']),
                                   ('character-metadata.json', initial_inputs['metadata'])]:
            p.require(p.digest(_read_input(output / filename)) == expected,
                      'A staged metadata file changed: ' + filename, 'staged_metadata_changed')
        # Finish potentially long copied-byte and metadata checks before the last
        # live authority/attempt capture. A withdrawal during those checks must
        # not be followed by a ready marker based on an older capture.
        _check_input_files(_input_files, initial_inputs)
        fresh = check_transition(experiments, family, binding, 'unreal', asset_root=asset_root,
                    semantic_policy=semantic_policy, annotations=annotations, ledger_path=ledger_path, include_target=True)
        report['final_admission_sha256'] = fresh['report_sha256']
        if not fresh['passed']:
            _merge_blockers(report, fresh, 'admission')
            raise p.PipelineError('Fresh admission failed after staging', 'admission_changed')
        p.require(fresh['report_sha256'] == first['report_sha256'],
                  'Current authority, ledger or admission inputs changed during staging', 'admission_changed')
        p.require(_inputs(family, binding, metadata, semantic_policy, annotations) == initial_inputs,
                  'An export input changed at final admission', 'inputs_changed')
        _check_input_files(_input_files, initial_inputs)
        ready = {'schema': 'las.p36-ready-handoff/1', 'family_sha256': initial_inputs['family'],
                 'pack_sha256': pack_hash, 'authority_sha256': p.digest(first),
                 'input_fingerprints': initial_inputs, 'admission_sha256': fresh['report_sha256'],
                 'concept_receipt': family['heads']['concept'], 'mode': family['mode'],
                 'evidence_state': 'implemented', 'generation_submitted': False,
                 'asset_copy_performed': True, 'assets_verified_at_export': True,
                 'revalidate_at_import': True, 'current_direct_import_allowed': False,
                 'native_import_performed': False, 'unreal_import': 'planned'}
        # Fully write and sync first, then atomically publish without replacing an
        # existing READY. The pending file is retained as part of the evidence.
        pending = output / 'READY.pending.json'
        _write_new(pending, ready)
        os.link(pending, output / 'READY.json', follow_symlinks=False)
        report['ready'] = True
        report['pack_sha256'] = pack_hash
        report['ready_sha256'] = p.digest(ready)
        return _finish(report)
    except Exception as error:
        _block(report, getattr(error, 'code', 'staging_failed'), detail=type(error).__name__ + ': ' + str(error))
        report['partial_retained'] = created
        if created and output is not None:
            try:
                _write_new(output / 'FAILED.json', {'schema': 'las.p36-export-failure/1',
                    'blockers': report['blockers'], 'generation_submitted': False, 'retry_allowed': False})
            except Exception:
                pass  # Preserve the original failure; PARTIAL and copied bytes remain.
        return _finish(report)


def _read_input(path):
    path = Path(path).absolute()
    return studio_authority.read_record(path.parent, path.name)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='command', required=True)
    for name in ('preflight', 'export'):
        sub = actions.add_parser(name)
        for flag in ('experiments', 'family', 'binding', 'asset-root', 'semantic-policy', 'annotations', 'ledger'):
            sub.add_argument('--' + flag, required=True)
        if name == 'preflight':
            sub.add_argument('--stage', required=True, choices=p.STAGES)
            sub.add_argument('--include-target', action='store_true')
        else:
            sub.add_argument('--metadata', required=True)
            sub.add_argument('--out', required=True)
            sub.add_argument('--release', action='store_true')
            sub.add_argument('--intended-use')
            sub.add_argument('--lumenfold-root')
    args = parser.parse_args(argv)
    try:
        paths = {'family': args.family, 'binding': args.binding,
                 'semantic_policy': args.semantic_policy, 'annotations': args.annotations}
        documents = {name: _read_input(path) for name, path in paths.items()}
        common = {'asset_root': args.asset_root, 'semantic_policy': documents['semantic_policy'],
                  'annotations': documents['annotations'], 'ledger_path': args.ledger}
        if args.command == 'preflight':
            result = check_transition(args.experiments, documents['family'], documents['binding'],
                                      args.stage, include_target=args.include_target, **common)
        else:
            paths['metadata'] = args.metadata
            metadata = _read_input(args.metadata)
            result = export_verified_bundle(args.experiments, documents['family'], documents['binding'],
                        metadata, args.out, release=args.release, intended_use=args.intended_use,
                        lumenfold_root=args.lumenfold_root, _input_files=paths, **common)
        sys.stdout.buffer.write(p.canonical_bytes(result))
        return 0 if result['passed'] else 2
    except Exception as error:
        result = {'passed': False, 'evidence_state': 'implemented', 'generation_submitted': False,
                  'submission_authority': False, 'error': getattr(error, 'code', 'invalid_input'),
                  'detail': _diagnostic(error, 400)}
        sys.stdout.buffer.write(p.canonical_bytes(result))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
