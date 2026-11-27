"""Deterministic continuation evidence over actual P36 staged fixture bundles.

Command from the Studio root:
  python prototypes/pro/P36/P36-B-20261126-2/consumer_evidence.py \
      --out .runtime/pro/P36-B-20261126-2/consumer-evidence

Scope: thirteen authored controls/challenges, not the complete test suite and not
a perceptual benchmark. Every Workspace, acceptance and byte is synthetic test
data created beneath a fresh output directory. No model generation, network,
dispatch, native import, owner authentication or production acceptance occurs.
Returned evidence excludes paths, UUIDs, times and source-root-bound hashes.
Raw bundles are retained locally for inspection. Reusing an output is refused.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shutil
import sys

if __name__ == '__main__': sys.dont_write_bytecode = True

import admission
import admission_fixtures
import attempt_ledger
import authority_fixtures
import fixtures
import handoff_verifier
import pipeline as p
import sheet_identity

FALSE_CLAIMS = ('native_import_allowed', 'native_import_performed', 'generation_submitted',
                'production_promoted', 'owner_authenticated', 'acceptance_inferred',
                'licence_clearance_inferred', 'perceptual_identity_verified')


def _read(bundle, name): return p.load_json(bundle / name)
def _write(bundle, name, value): (bundle / name).write_bytes(p.canonical_bytes(value))


def _rehash(bundle):
    """Adversarial helper repairs unkeyed outer links, not false inner facts."""
    names = {'family': 'family.json', 'binding': 'binding.json', 'metadata': 'character-metadata.json',
             'semantic_policy': 'semantic-policy.json', 'annotations': 'annotations.json'}
    docs = {key: _read(bundle, name) for key, name in names.items()}
    hashes = {key: p.digest(value) for key, value in docs.items()}
    captured = _read(bundle, 'current-authority.json')
    captured['input_fingerprints'].update(family_sha256=hashes['family'], binding_sha256=hashes['binding'],
        annotations_sha256=hashes['annotations'],
        semantic_policy_sha256=sheet_identity.semantic_policy_digest(docs['semantic_policy']))
    for key, field in (('authority', 'capture_sha256'), ('ledger', 'snapshot_sha256')):
        value = captured[key]
        if key == 'authority': value.update(family_sha256=hashes['family'], binding_sha256=hashes['binding'])
        value.pop(field); value[field] = p.digest(value)
    captured['capture_fingerprints'] = {'authority_sha256': captured['authority']['capture_sha256'],
        'ledger_sha256': captured['ledger']['snapshot_sha256'], 'semantic_sha256': p.digest(captured['semantic'])}
    captured.pop('report_sha256'); captured['report_sha256'] = p.digest(captured)
    _write(bundle, 'current-authority.json', captured)
    pack = _read(bundle, 'pack.json'); extension = pack['x-studio-character-pipeline']
    extension.update(family_sha256=hashes['family'], stage_receipts=docs['family']['heads'])
    extension['consumer_admission'].update(source_family_sha256=hashes['family'],
        source_metadata_sha256=hashes['metadata'], admission_sha256=captured['report_sha256'])
    _write(bundle, 'pack.json', pack)
    ready = _read(bundle, 'READY.json')
    ready.update(family_sha256=hashes['family'], pack_sha256=p.digest(pack), authority_sha256=p.digest(captured),
                 admission_sha256=captured['report_sha256'], input_fingerprints=hashes)
    _write(bundle, 'READY.json', ready); _write(bundle, 'READY.pending.json', ready)
    partial = _read(bundle, 'PARTIAL.json')
    partial.update(family_sha256=hashes['family'], pack_sha256=p.digest(pack))
    _write(bundle, 'PARTIAL.json', partial)


def prove_consumer(out: Path) -> dict:
    """Create a fresh runtime proof, assert real outcomes, return stable evidence."""
    out = admission._output_path(out)
    out.mkdir(parents=True, exist_ok=False)
    context = authority_fixtures.make_workspace(out / 'source')
    policy, annotations = admission_fixtures.semantic_inputs(context)
    ledger = out / 'attempts.sqlite3'; attempt_ledger.initialize(ledger)
    baseline = out / 'baseline'
    exported = admission.export_verified_bundle(context['experiments'], context['family'], context['binding'],
        fixtures.metadata(), baseline, asset_root=context['asset_root'], semantic_policy=policy,
        annotations=annotations, ledger_path=ledger)
    p.require(exported['passed'] is True and exported['ready'] is True, 'Evidence baseline export failed', 'proof_failed')
    p.require(exported['generation_submitted'] is False and exported['native_import_performed'] is False,
              'Evidence exporter claimed execution', 'proof_failed')
    cases = []

    def run(name, expected, mutate=None, *, code=None, current=False, synthetic=True, source=None,
            integrity=None, matches=None, rehash=False):
        bundle = out / name; shutil.copytree(baseline, bundle)
        if mutate: mutate(bundle)
        if rehash: _rehash(bundle)
        options = {'allow_synthetic': synthetic, 'expected_pack_id': context['family']['character_id']}
        if current:
            options.update(require_current=True, experiments=source or context['experiments'], ledger_path=ledger)
        report = handoff_verifier.verify_handoff(bundle, **options)
        observed_codes = sorted({item['code'] for item in report['blockers']})
        p.require(report['passed'] is expected and observed_codes == ([] if expected else [code]),
                  'Unexpected consumer outcome in ' + name + ': ' + ','.join(observed_codes), 'proof_failed')
        p.require(all(report[key] is False for key in FALSE_CLAIMS), 'Consumer claimed execution/authority', 'proof_failed')
        if integrity is not None: p.require(report['integrity_verified'] is integrity, 'Unexpected integrity flag: ' + name)
        if matches is not None: p.require(report['current_authority_matches'] is matches, 'Unexpected current flag: ' + name)
        cases.append({'case': name, 'expected_passed': expected, 'passed': report['passed'],
            'blocker_codes': observed_codes, 'integrity_verified': report['integrity_verified'],
            'current_authority_checked': report['current_authority_checked'],
            'current_authority_matches': report['current_authority_matches'],
            **{key: report[key] for key in FALSE_CLAIMS}})

    run('valid-offline', True, integrity=True, matches=False)
    run('valid-current', True, current=True, integrity=True, matches=True)
    run('unchanged-rehash-control', True, rehash=True, integrity=True)
    run('ready-missing', False, lambda bundle: (bundle / 'READY.json').unlink(), code='staged_destination_changed')
    run('synthetic-default-denial', False, synthetic=False, code='synthetic_refused')

    def drift_bytes(bundle):
        pack = _read(bundle, 'pack.json'); record = next(iter(pack['files'].values()))
        (bundle / 'assets' / 'packs' / pack['id'] / record['path']).write_bytes(b'authored-byte-drift')
    run('copied-bytes-drift', False, drift_bytes, code='asset_bytes_changed')

    def change_index(bundle):
        captured = _read(bundle, 'current-authority.json')
        captured['authority']['snapshot']['assets']['concept/front']['output_index'] = 1
        _write(bundle, 'current-authority.json', captured)
    run('rehashed-captured-index', False, change_index, rehash=True, code='captured_subject_mismatch')

    def swap_side(bundle):
        declared = _read(bundle, 'annotations.json')
        declared['turnaround']['views'][0]['anchors']['left-iris']['value'] = 'blue'
        _write(bundle, 'annotations.json', declared)
    run('rehashed-semantic-side-swap', False, swap_side, rehash=True, code='semantic_identity_failed')

    def conflict(bundle):
        family = _read(bundle, 'family.json')
        receipt = copy.deepcopy(family['receipts'][family['heads']['unreal']])
        artifact = copy.deepcopy(family['receipts'][family['heads']['concept']]['payload']['artifacts'][0])
        artifact['key'] = 'reused-concept'; artifact['licence']['commercial'] = 'no'
        receipt['payload']['artifacts'].append(artifact)
        for dimension, state, actor in (('generation', 'completed', 'fixture'), ('inspection', 'inspected', 'fixture'),
                                        ('acceptance', 'accepted', 'owner')):
            receipt = p.attest(receipt, dimension, state, actor, 'fixture:consumer-evidence-conflict')
        family['receipts'][receipt['id']] = receipt; family['heads']['unreal'] = receipt['id']
        _write(bundle, 'family.json', family)
    run('rehashed-provenance-conflict', False, conflict, rehash=True, code='artifact_provenance_conflict')

    with context['workspace'].connection() as db:
        count = db.execute("UPDATE asset_acceptances SET withdrawn_at=2 WHERE id='test-concept-front'").rowcount
        p.require(count == 1, 'Evidence withdrawal did not affect its synthetic row', 'proof_failed')
    try:
        run('withdrawn-source-offline-unknown', True, integrity=True, matches=False)
        run('withdrawn-source-current-denial', False, current=True, code='current_authority_refused',
            integrity=True, matches=False)
    finally:
        with context['workspace'].connection() as db:
            db.execute("UPDATE asset_acceptances SET withdrawn_at=NULL WHERE id='test-concept-front'")
    other = authority_fixtures.make_workspace(out / 'other-source')
    run('wrong-explicit-source-root', False, current=True, source=other['experiments'], code='claim_mismatch',
        integrity=True, matches=False)

    def coherent_description(bundle):
        metadata = _read(bundle, 'character-metadata.json'); pack = _read(bundle, 'pack.json')
        metadata['display_name'] = pack['display_name'] = 'Coherent untrusted descriptive edit'
        _write(bundle, 'character-metadata.json', metadata); _write(bundle, 'pack.json', pack)
    run('coherent-description-integrity-only', True, coherent_description, rehash=True, integrity=True, matches=False)

    refused = sum(not case['expected_passed'] for case in cases)
    evidence = {'schema': 'las.p36-consumer-evidence/1', 'evidence_state': 'implemented',
        'scope': 'authored synthetic integrity/current-source cases; no perceptual or native qualification',
        'fixture_only': True, 'case_count': len(cases), 'expected_passes': len(cases) - refused,
        'expected_refusals': refused, 'matched_outcomes': len(cases), 'false_admissions': 0, 'false_refusals': 0,
        'actual_staging_export_used': True, 'raw_local_cases_retained': True,
        **{key: False for key in FALSE_CLAIMS}, 'cases': cases}
    p.require(len(cases) == 13 and refused == 8, 'Consumer evidence inventory changed', 'proof_failed')
    evidence['evidence_sha256'] = p.digest(evidence)
    admission._write_new(out / 'consumer-evidence.json', evidence)
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prove_consumer(args.out); sys.stdout.buffer.write(p.canonical_bytes(result)); return 0
    except Exception as error:
        result = {'passed': False, 'code': admission._diagnostic(getattr(error, 'code', 'proof_failed'), 128),
                  'detail': admission._diagnostic(error, 400), **{key: False for key in FALSE_CLAIMS}}
        sys.stdout.buffer.write(p.canonical_bytes(result)); return 2


if __name__ == '__main__': raise SystemExit(main())
