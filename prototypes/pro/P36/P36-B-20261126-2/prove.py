"""One-command offline P36 proof. Synthetic fixtures only; no generation or native import."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path: sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))

import pipeline as p
import fixtures
import pack_export
import export_guard
import studio_authority as authority
import attempt_ledger as attempts
import sheet_identity
from consistency import score_sheet
from authority_fixtures import make_workspace, set_job
from test_sheet_identity import challenge_cases

RUN = 'P36-B-20261126-2'


def write(path, value):
    p.write_new_runtime(path, value)


def check(value, message):
    p.require(value, message, 'proof_failed')


def prove_semantics(repetitions):
    rows, timings = [], []
    for case in challenge_cases():
        data = case['inputs']
        prior = score_sheet(data['anchor_features'], data['sheet'], data['proxy_policy'], data['stage'])
        guarded = sheet_identity.score_sheet_identity(**data)
        weak = sum(case['baseline_scores']) / len(case['baseline_scores']) >= 0.90
        check(guarded['passed'] == case['expected_pass'], 'Semantic challenge disagrees: ' + case['name'])
        rows.append({'name': case['name'], 'expected_pass': case['expected_pass'],
                     'mean_only_pass': weak, 'retained_proxy_pass': prior['passed'],
                     'semantic_pass': guarded['passed'], 'blockers': guarded['blockers']})
    sample = challenge_cases()[0]['inputs']
    for _ in range(repetitions):
        start = time.perf_counter_ns(); sheet_identity.score_sheet_identity(**sample)
        timings.append(time.perf_counter_ns() - start)
    bad = [r for r in rows if not r['expected_pass']]; good = [r for r in rows if r['expected_pass']]
    return {'kind': 'authored-synthetic-descriptor-challenges', 'cases': rows,
            'invalid_cases': len(bad), 'valid_controls': len(good),
            'mean_only_false_accepts': sum(r['mean_only_pass'] for r in bad),
            'retained_proxy_false_accepts': sum(r['retained_proxy_pass'] for r in bad),
            'semantic_false_accepts': sum(r['semantic_pass'] for r in bad),
            'semantic_false_rejects': sum(not r['semantic_pass'] for r in good),
            'perceptual_accuracy_claimed': False}, timings


def _sql(context, statement, parameters=()):
    with context['workspace'].connection() as db: db.execute(statement, parameters)


def prove_current_authority(out):
    def changed_bytes(c):
        path = c['workspace'].file(c['binding']['concept_asset_id'])
        path.write_bytes(path.read_bytes() + b'changed-test-bytes')
    cases = [
        ('withdrawn-root', lambda c: _sql(c, "UPDATE asset_acceptances SET withdrawn_at=2 WHERE id='test-concept-front'")),
        ('other-workspace', lambda c: _sql(c, 'UPDATE workspace_identity SET id=?', ('b' * 32,))),
        ('forged-review-subject', lambda c: _sql(c, "UPDATE asset_acceptances SET sha256=? WHERE id='test-concept-front'", ('f' * 64,))),
        ('other-intended-use', lambda c: _sql(c, "UPDATE asset_acceptances SET use='other' WHERE id='test-concept-front'")),
        ('changed-canon', lambda c: _sql(c, "UPDATE cards SET lineage='[]'")),
        ('uncertain-upstream', lambda c: set_job(c, 'concept', status='uncertain', pending_submission={'index': 0})),
        ('changed-workspace-bytes', changed_bytes),
        ('rejected-current-asset', lambda c: _sql(c, "UPDATE assets SET review='rejected'")),
        ('selected-without-acceptance', lambda c: (_sql(c, 'DELETE FROM asset_acceptances'), _sql(c, "UPDATE assets SET review='selected'"))),
    ]
    rows = []
    for name, mutate in cases:
        context = make_workspace(out / 'authority-cases' / name, through='turnaround')
        initial = authority.capture_authority(context['experiments'], context['family'], context['binding'])
        check(initial['passed'], 'Valid current-authority control was refused')
        mutate(context)
        offline = p.next_gate(context['family'], 'expressions', asset_root=context['asset_root'])
        current = authority.capture_authority(context['experiments'], context['family'], context['binding'], stages=['turnaround'])
        check(offline['passed'] and not current['passed'], 'Current authority challenge failed: ' + name)
        rows.append({'name': name, 'initial_control_pass': initial['passed'],
                     'retained_offline_gate_pass': offline['passed'], 'current_authority_pass': current['passed'],
                     'blocker_codes': sorted({b['code'] for b in current['blockers']})})
    return {'kind': 'actual-Studio-SQLite-API-with-synthetic-records', 'cases': rows,
            'invalid_cases': len(rows), 'valid_controls_admitted': sum(r['initial_control_pass'] for r in rows),
            'retained_offline_false_accepts': sum(r['retained_offline_gate_pass'] for r in rows),
            'current_authority_false_accepts': sum(r['current_authority_pass'] for r in rows)}


def prove_attempts(out):
    context = make_workspace(out / 'attempt-context', through='concept')
    path = out / 'attempts.sqlite3'; attempts.initialize(path)
    parameters = {'family_id': context['family']['family_id'], 'stage': 'turnaround',
                  'request_id': 'proof-request', 'job_id': 'proof-future-job', 'intent_sha256': 'd' * 64,
                  'experiments': context['experiments'], 'workspace_id': context['family']['workspace_id']}
    first = attempts.reserve(path, **parameters); replay = attempts.reserve(path, **parameters)
    pending = attempts.inspect(path, family_id=parameters['family_id'], stages=['turnaround'], experiments=context['experiments'])
    refused = False
    try: attempts.reserve(path, **{**parameters, 'request_id': 'other-request', 'job_id': 'other-job'})
    except p.PipelineError: refused = True
    check(first['created'] and not replay['created'] and first['attempt_id'] == replay['attempt_id']
          and not pending['passed'] and refused, 'No-output attempt gate failed')
    root = context['experiments'] / 'runs' / parameters['job_id']; root.mkdir(parents=True)
    job = {'id': parameters['job_id'], 'status': 'completed', 'operation': 'asset.import',
           'prompt_ids': [], 'submissions': [], 'outputs': [{'filename': 'fixture.png'}],
           'p36_attempt': first['job_binding']}
    (root / 'state.json').write_bytes(p.canonical_bytes(job)); (root / 'workflow.json').write_bytes(p.canonical_bytes({}))
    observed = attempts.resolve(path, first['attempt_id'], experiments=context['experiments'])
    settled = attempts.inspect(path, family_id=parameters['family_id'], stages=['turnaround'], experiments=context['experiments'])
    check(observed['state'] == 'completed' and settled['passed'], 'Exact observed completion did not resolve')
    job['status'] = 'uncertain'; (root / 'state.json').write_bytes(p.canonical_bytes(job))
    changed = attempts.inspect(path, family_id=parameters['family_id'], stages=['turnaround'], experiments=context['experiments'])
    check(not changed['passed'], 'Changed terminal observation was reused')
    changed_refused = False
    try: attempts.reserve(path, **{**parameters, 'request_id': 'later-request', 'job_id': 'later-job'})
    except p.PipelineError: changed_refused = True
    check(changed_refused, 'Changed terminal observation allowed a fresh reservation')
    return {'new_reservations': 1, 'same_request_reissued': 0, 'fresh_request_while_unresolved_refused': refused,
            'no_artifact_or_prompt_required_to_block': True, 'explicit_exact_resolution_pass': settled['passed'],
            'changed_resolved_observation_blocks': not changed['passed'], 'generation_submissions': 0,
            'fresh_request_after_changed_resolution_refused': changed_refused,
            'worker_integration': 'planned; every future attempt must reserve and persist its exact marker'}


def prove_provenance():
    from test_export_guard import ExportGuardTests
    test = ExportGuardTests(); test.setUp()
    try:
        family = test.reused_family(earlier='yes', later='no')
        old = pack_export.build_manifest(family, test.assets, test.metadata)
        concept_artifact = family['receipts'][family['heads']['concept']]['payload']['artifacts'][0]
        exported = next(v for v in old['files'].values() if v['path'] == concept_artifact['path'])
        refused, code = False, None
        try: export_guard.build_guarded_manifest(family, test.assets, test.metadata)
        except p.PipelineError as error: refused, code = True, error.code
        check(exported['commercial'] == 'yes' and refused and code == 'artifact_provenance_conflict',
              'Conflicting licence fact was not rejected before deduplication')
        return {'first_record_commercial': 'yes', 'later_record_commercial': 'no',
                'retained_export_commercial': exported['commercial'], 'guarded_export_refused': refused,
                'blocker': code, 'licence_clearance_inferred': False}
    finally: test.doCleanups()


def prove_staging(out, lumenfold_root):
    import admission
    from admission_fixtures import semantic_inputs
    context = make_workspace(out / 'complete-context')
    semantic_policy, annotations = semantic_inputs(context)
    ledger = out / 'complete-attempts.sqlite3'; attempts.initialize(ledger)
    metadata = fixtures.metadata()
    report = admission.export_verified_bundle(context['experiments'], context['family'], context['binding'],
                metadata, out / 'staged', asset_root=context['asset_root'], semantic_policy=semantic_policy,
                annotations=annotations, ledger_path=ledger, lumenfold_root=lumenfold_root)
    check(report['passed'], 'Complete fixture staging failed: ' + json.dumps(report.get('blockers')))
    bundle = out / 'staged'
    pack = p.load_json(bundle / 'pack.json')
    import jsonschema
    jsonschema.Draft202012Validator(p.load_json(HERE / 'lumenfold.pack.schema.json')).validate(pack)
    copied = bundle / 'assets' / 'packs' / pack['id']
    for record in pack['files'].values(): p.verify_artifact(copied, record)
    for name, value in [('family.json', context['family']), ('workspace-binding.json', context['binding']),
                        ('semantic-policy.json', semantic_policy), ('annotations.json', annotations), ('metadata.json', metadata)]:
        write(out / name, value)
    # Keep deterministic model/scorer outputs separate from observation-only readiness.
    stable_pack = export_guard.build_guarded_manifest(context['family'], context['asset_root'], metadata)
    write(out / 'pack.json', stable_pack)
    return {'stages': list(p.STAGES), 'accepted_fixture_receipts': len(context['family']['heads']),
            'copied_files': len(pack['files']), 'schema_valid': True, 'copied_bytes_verified': True,
            'ready_marker_present': (bundle / 'READY.json').is_file(),
            'pack_status': pack['status'], 'current_direct_import_allowed': pack['x-studio-character-pipeline']['consumer_admission']['current_direct_import_allowed'],
            'native_import_state': 'planned', 'real_character_acceptance_claimed': False}, report


def test_suite(out, consumer_root):
    if consumer_root: os.environ['P36_LUMENFOLD_ROOT'] = str(Path(consumer_root).resolve())
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern='test_*.py')
    started = time.perf_counter()
    with (out / 'tests.log').open('w', encoding='utf-8', newline='\n') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    summary = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
               'seconds': time.perf_counter() - started, 'passed': result.wasSuccessful()}
    write(out / 'tests-summary.json', summary)
    check(result.wasSuccessful(), 'Prototype tests failed; inspect ' + str(out / 'tests.log'))
    return summary


def verify_retained_sources():
    inventory = p.load_json(HERE / 'UPSTREAM.json')
    for row in inventory['files']:
        check(hashlib.sha256((HERE / row['path']).read_bytes()).hexdigest() == row['sha256'],
              'Retained upstream source changed: ' + row['path'])
    return len(inventory['files'])


def prove_continuation(out):
    from indexing_evidence import prove_indexing
    from production_evidence import prove_preparation
    from dispatch_evidence import prove_dispatch
    from consumer_evidence import prove_consumer
    suites = [('indexing', prove_indexing), ('preparation', prove_preparation),
              ('dispatch', prove_dispatch), ('consumer', prove_consumer)]
    result = {}
    for name, build in suites:
        evidence = build(out / (name + '-cases'))
        write(out / (name + '-evidence.json'), evidence)
        result[name] = {key: value for key, value in evidence.items() if key not in ('cases', 'controls', 'limitations')}
        result[name]['deterministic_file'] = name + '-evidence.json'
        result[name]['canonical_sha256'] = p.digest(evidence)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Fresh directory under repository .runtime/')
    parser.add_argument('--tests-only', action='store_true')
    parser.add_argument('--lumenfold-root', help='Existing trusted checkout/snapshot; only pinned validator/schema are loaded')
    parser.add_argument('--check-evidence', help='Compare the deterministic evidence with this committed JSON')
    parser.add_argument('--check-hashes', help='Compare all eleven deterministic output hashes with this UTF-8 LF manifest')
    parser.add_argument('--repetitions', type=int, default=50)
    args = parser.parse_args(argv)
    try:
        check(1 <= args.repetitions <= 10000, 'Repetitions must be in 1..10000')
        out = Path(args.output).absolute()
        check(out.resolve().is_relative_to((REPO / '.runtime').resolve()), 'Proof output must be under repository .runtime/')
        check(not any(p.linked(x) for x in (out, *out.parents)), 'Linked proof output refused')
        check(not out.exists(), 'Proof output already exists; inspect it and use a new path')
        out.mkdir(parents=True)
        retained = verify_retained_sources()
        tests = test_suite(out, args.lumenfold_root)
        environment = {'python': sys.version, 'platform': platform.platform(), 'compiler': platform.python_compiler(),
                       'packages': {name: importlib.metadata.version(name) for name in ('Pillow', 'jsonschema', 'psutil')},
                       'generation_submitted': False, 'native_applications_started': False,
                       'cpp_compiler_invoked': False, 'msvc_flags': None}
        write(out / 'environment.json', environment)
        if args.tests_only:
            print(json.dumps({'passed': True, 'tests': tests['tests'], 'skipped': len(tests['skipped']), 'output': str(out)})); return 0
        semantics, nanoseconds = prove_semantics(args.repetitions)
        current = prove_current_authority(out)
        attempts_evidence = prove_attempts(out)
        provenance = prove_provenance()
        staging, staging_observation = prove_staging(out, args.lumenfold_root)
        continuation = prove_continuation(out)
        evidence = {'schema': 'las.p36-evidence/3', 'run': RUN, 'evidence_state': 'implemented',
                    'scope': 'synthetic offline software proof; no perceptual accuracy or native qualification',
                    'retained_source_files': retained, 'prototype_tests_discovered': tests['tests'],
                    'semantics': semantics, 'current_authority': current, 'attempts': attempts_evidence,
                    'provenance': provenance, 'staging': staging, 'generation_submissions': 0,
                    'continuation': continuation}
        write(out / 'evidence.json', evidence)
        write(out / 'staging-observation.json', staging_observation)
        ordered = sorted(nanoseconds)
        write(out / 'timing.json', {'scope': 'Linux/Windows host Python descriptor-check overhead only, not GPU throughput',
              'repetitions': len(ordered), 'median_ms': statistics.median(ordered) / 1e6,
              'p95_ms': ordered[math.ceil(len(ordered) * .95) - 1] / 1e6,
              'p95_method': 'nearest-rank-ceiling',
              'min_ms': ordered[0] / 1e6, 'max_ms': ordered[-1] / 1e6})
        deterministic = ['evidence.json', 'family.json', 'workspace-binding.json', 'semantic-policy.json',
                         'annotations.json', 'metadata.json', 'pack.json', 'indexing-evidence.json',
                         'preparation-evidence.json', 'dispatch-evidence.json', 'consumer-evidence.json']
        hashes = ''.join(hashlib.sha256((out / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in deterministic)
        with (out / 'OUTPUT_HASHES.sha256').open('x', encoding='utf-8', newline='\n') as handle: handle.write(hashes)
        if args.check_evidence:
            check(p.load_json(args.check_evidence) == evidence, 'Deterministic evidence differs from the recorded file')
        if args.check_hashes:
            check(Path(args.check_hashes).read_bytes() == hashes.encode('utf-8'),
                  'Deterministic output hashes differ from the recorded manifest')
        print(json.dumps({'passed': True, 'tests': tests['tests'], 'skipped': len(tests['skipped']),
                          'semantic_false_accepts': semantics['semantic_false_accepts'],
                          'authority_false_accepts': current['current_authority_false_accepts'],
                          'copied_files': staging['copied_files'], 'deterministic_outputs': len(deterministic),
                          'duplicate_simulated_callbacks': continuation['dispatch']['duplicate_callbacks'],
                          'output': str(out)}))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({'passed': False, 'error': str(error), 'generation_submitted': False}), file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
