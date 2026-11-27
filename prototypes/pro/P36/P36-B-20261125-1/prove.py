"""One offline command: tests, adversarial evidence, export, hashes and optional consumer check.

All output is synthetic software evidence under .runtime. No generation/runtime
request is made. Timings/environment are separate from deterministic evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import statistics
import sys

# CLI runs keep regenerable bytecode out of the source tree.
if __name__ == '__main__':
    sys.dont_write_bytecode = True
import time
import unittest

import PIL

from consistency import score_sheet
from fixtures import build_fixture, metadata, policy, stage_receipt
from pack_export import export_bundle
from pipeline import (PipelineError, REPO_ROOT, RUN_DIR, STAGES, assess, attest,
                      canonical_bytes, digest, linked, next_gate, record_receipt,
                      require, seal, write_new_runtime)


def scenario_matrix(family):
    anchor = family['receipts'][family['heads']['concept']]['payload']['identity']['anchor_features']
    clean = family['receipts'][family['heads']['turnaround']]['payload']['identity']['sheet']
    metric_policy = {k: family['policy'][k] for k in ('version', 'features', 'required')}
    cases = []
    def add(name, mutation, expected, note=''):
        sheet = copy.deepcopy(clean); mutation(sheet)
        result = score_sheet(anchor, sheet, metric_policy, 'turnaround')
        cases.append({'name': name, 'expected_pass': expected, 'strict_pass': result['passed'],
                      'mean_baseline_pass': result['score'] >= 0.90, 'diagnostic_score': result['score'],
                      'blockers': result['blockers'], 'note': note})
    def feature(sheet, view, name):
        return next(v for v in sheet['views'] if v['id'] == view)['features'][name]
    add('valid-control', lambda s: None, True)
    add('allowed-costume-diagnostic', lambda s: s['views'][0]['features'].update(
        outfit={'value': 'different-intended-costume'}), True, 'Outfit is not an invariant in this frozen rubric.')
    add('allowed-expression-diagnostic', lambda s: s['views'][0]['features'].update(
        expression={'value': 'smile'}), True)
    add('small-palette-change', lambda s: feature(s, 'front', 'eyes').update(value=[123, 71, 150]), True)
    add('eye-colour-drift-one-view', lambda s: feature(s, 'front', 'eyes').update(value=[20, 180, 20]), False)
    add('hair-colour-drift-one-view', lambda s: feature(s, 'left', 'hair').update(value=[220, 20, 90]), False)
    add('face-proportion-drift', lambda s: feature(s, 'front', 'eye_spacing').update(value=0.50), False)
    add('mirrored-asymmetry', lambda s: feature(s, 'back', 'braid_side').update(value='anatomical-right'), False)
    add('missing-front-view', lambda s: s.update(views=[v for v in s['views'] if v['id'] != 'front']), False)
    add('missing-back-view', lambda s: s.update(views=[v for v in s['views'] if v['id'] != 'back']), False)
    add('missing-critical-eyes', lambda s: s['views'][0]['features'].pop('eyes'), False)
    add('occluded-critical-eyes', lambda s: feature(s, 'front', 'eyes').update(state='not_visible'), False)
    add('uncertain-face-proportion', lambda s: feature(s, 'front', 'eye_spacing').update(state='uncertain'), False)
    add('duplicate-view-label', lambda s: s['views'].append(copy.deepcopy(s['views'][0])), False)
    def duplicate_media(sheet):
        sheet['views'][1]['media_sha256'] = sheet['views'][0]['media_sha256']
        for f in sheet['views'][1]['features'].values(): f['media_sha256'] = sheet['views'][0]['media_sha256']
    add('one-image-reused-as-two-views', duplicate_media, False)
    add('stale-feature-media-hash', lambda s: feature(s, 'front', 'hair').update(media_sha256='f'*64), False)
    def bogus_cache(sheet):
        feature(sheet, 'front', 'eyes')['value'] = [20, 180, 20]
        sheet.update(passed=True, score=1.0, tolerance=999, required=[])
    add('candidate-forged-green-score', bogus_cache, False)
    add('boolean-proportion', lambda s: feature(s, 'front', 'eye_spacing').update(value=True), False)
    add('nan-proportion', lambda s: feature(s, 'front', 'eye_spacing').update(value=float('nan')), False)
    add('infinite-proportion', lambda s: feature(s, 'front', 'eye_spacing').update(value=float('inf')), False)
    require(all(c['strict_pass'] == c['expected_pass'] for c in cases), 'Synthetic scorer regression')
    return cases


def ancestry_matrix(root):
    drift = build_fixture(root / 'drift', through='turnaround',
                           mutations={'turnaround': {'view': 'front', 'eyes': [20, 180, 20]}})
    descendants = {stage: next_gate(drift, stage)['passed'] for stage in STAGES[2:]}
    require(not any(descendants.values()), 'Identity drift passed downstream')
    stable = build_fixture(root / 'replacement')
    replacement = stage_receipt(stable, 'concept', root / 'replacement')
    replacement['payload']['recipe']['controls']['revision'] = 2
    for dimension, state, actor in [('generation', 'completed', 'fixture'),
                                    ('inspection', 'inspected', 'fixture'),
                                    ('acceptance', 'accepted', 'owner')]:
        replacement = attest(replacement, dimension, state, actor, 'fixture:revision')
    revised = record_receipt(stable, replacement)
    stale = {stage: assess(revised, stage)['passed'] for stage in STAGES[1:]}
    require(not any(stale.values()), 'Replaced concept did not invalidate descendants')
    uncertain = build_fixture(root / 'uncertain', through='concept')
    attempt = stage_receipt(uncertain, 'turnaround', root / 'uncertain')
    attempt = attest(attempt, 'generation', 'uncertain', 'fixture', 'prompt:fixture-retained')
    uncertain = record_receipt(uncertain, attempt)
    require(not next_gate(uncertain, 'turnaround')['passed'], 'Uncertain attempt can be repeated')
    pending = build_fixture(root / 'pending', through='turnaround', unaccepted_stage='turnaround',
                            mutations={'turnaround': {'view': 'front', 'geometry': 'angular'}})
    pending_gate = assess(pending, 'turnaround')
    proxy_pass = pending_gate['identity']['turnaround']['passed']
    require(proxy_pass and not pending_gate['passed'], 'Known-limit fixture must need acceptance')
    return {'drift_descendant_gates': descendants, 'replaced_concept_gates': stale,
            'uncertain_same_stage_retry_blocked': True,
            'known_limit': {'geometry_changed_outside_rois': True, 'proxy_pass': proxy_pass,
                            'owner_acceptance': 'pending', 'next_stage_pass': next_gate(pending, 'mesh')['passed'],
                            'perceptual_identity_verified': False,
                            'meaning': 'ROI and annotation agreement cannot prove face geometry or identity.'}}


def run_tests():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(RUN_DIR), pattern='test_*.py')
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return result, stream.getvalue()


def consumer_check(lumenfold_root, pack, asset_store):
    root = Path(lumenfold_root).resolve(); path = root / 'pipelines' / 'characters' / 'validate_pack.py'
    schema = root / 'packs' / 'pack.schema.json'
    require(path.is_file() and schema.is_file(), 'Consumer source/schema unavailable')
    spec = importlib.util.spec_from_file_location('p36_lumenfold_consumer', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.ROOT = Path(asset_store).resolve()
    errors = module.validate_doc(pack, pack['id'], False, check_files=True)
    require(not errors, 'Actual Lumenfold consumer rejected export: ' + '; '.join(errors))
    return {'status': 'passed', 'check_files': True,
            'validator_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'schema_sha256': hashlib.sha256(schema.read_bytes()).hexdigest(),
            'native_import': 'not-run'}


def evidence(out, *, lumenfold_root=None, repetitions=100):
    out = Path(out).absolute()
    require(out.resolve().is_relative_to((REPO_ROOT / '.runtime').resolve()), 'Evidence must be under .runtime/')
    require(not any(linked(p) for p in (out, *out.parents)), 'Linked evidence destination refused')
    require(not out.exists(), 'Evidence destination exists; choose a new explicit run directory')
    require(type(repetitions) is int and 1 <= repetitions <= 10000, 'Invalid benchmark repetitions')
    out.mkdir(parents=True, exist_ok=False)
    result, test_log = run_tests()
    (out / 'tests.txt').write_text(test_log, encoding='utf-8', newline='\n')
    require(result.wasSuccessful(), 'Prototype tests failed; see tests.txt')
    asset_store = out / 'asset-store'; assets = asset_store / 'packs' / 'p36-fixture'
    family = build_fixture(assets)
    bundle = out / 'packs' / 'p36-fixture'
    export_bundle(family, assets, metadata(), bundle)
    pack = json.loads((bundle / 'pack.json').read_text(encoding='utf-8'))
    cases = scenario_matrix(family); ancestry = ancestry_matrix(out / 'cases')
    negative = [c for c in cases if not c['expected_pass']]
    positive = [c for c in cases if c['expected_pass']]
    deterministic = {
        'schema': 'las.p36-evidence/1', 'run': 'P36-B-20261125-1', 'evidence_state': 'implemented',
        'scope': 'Synthetic rubric and receipt tests; not real-character recognition accuracy.',
        'generation_jobs': 0, 'native_imports': 0, 'real_owner_acceptances': 0,
        'cases': cases, 'ancestry': ancestry,
        'metrics': {'scorer_cases': len(cases), 'labelled_invalid_cases': len(negative),
                    'strict_false_passes': sum(c['strict_pass'] for c in negative),
                    'mean_baseline_false_passes': sum(c['mean_baseline_pass'] for c in negative),
                    'valid_controls': len(positive),
                    'strict_valid_passes': sum(c['strict_pass'] for c in positive),
                    'blocked_drift_descendants': sum(not x for x in ancestry['drift_descendant_gates'].values()),
                    'blocked_stale_concept_descendants': sum(not x for x in ancestry['replaced_concept_gates'].values())},
        'pack_schema_sha256': hashlib.sha256((RUN_DIR / 'lumenfold.pack.schema.json').read_bytes()).hexdigest(),
        'fixture_file_count': len(pack['files']), 'family_sha256': digest(family), 'pack_sha256': digest(pack)}
    write_new_runtime(out / 'evidence.json', deterministic)
    durations = []
    for _ in range(repetitions):
        started = time.perf_counter(); assess(family, 'unreal'); durations.append((time.perf_counter()-started)*1000)
    ordered = sorted(durations)
    environment = {'python': sys.version, 'os': platform.platform(), 'machine': platform.machine(),
                   'pillow': PIL.__version__, 'compiler': 'not-applicable; Python prototype; no MSVC/Unreal run',
                   'tests': {'run': result.testsRun, 'skipped': len(result.skipped),
                             'failures': len(result.failures), 'errors': len(result.errors)},
                   'benchmark': {'operation': 'full eight-stage metadata gate (no disk I/O)',
                                 'repetitions': repetitions, 'median_ms': statistics.median(durations),
                                 'p95_ms': ordered[max(0, int(len(ordered)*.95)-1)], 'max_ms': max(durations)},
                   'consumer': {'status': 'not-run', 'reason': 'Pass --lumenfold-root for the actual consumer.'}}
    if lumenfold_root: environment['consumer'] = consumer_check(lumenfold_root, pack, asset_store)
    write_new_runtime(out / 'environment.json', environment)
    relative = ['evidence.json', 'packs/p36-fixture/pack.json', 'packs/p36-fixture/family.json',
                'packs/p36-fixture/handoff.json']
    lines = [hashlib.sha256((out / p).read_bytes()).hexdigest() + '  ' + p for p in relative]
    (out / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    return deterministic, environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output'); parser.add_argument('--lumenfold-root')
    parser.add_argument('--repetitions', type=int, default=100)
    parser.add_argument('--tests-only', action='store_true')
    parser.add_argument('--check-evidence', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.tests_only:
            result, log = run_tests(); print(log, end=''); return 0 if result.wasSuccessful() else 1
        require(args.output, '--output is required unless --tests-only is used')
        deterministic, environment = evidence(args.output, lumenfold_root=args.lumenfold_root,
                                              repetitions=args.repetitions)
        if args.check_evidence:
            require(args.check_evidence.read_bytes() == canonical_bytes(deterministic),
                    'Deterministic evidence differs from the committed reference')
        print(json.dumps({'metrics': deterministic['metrics'], 'verification': environment}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': getattr(exc, 'code', 'invalid_input'), 'message': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
