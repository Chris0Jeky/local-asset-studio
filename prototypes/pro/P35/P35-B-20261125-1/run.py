#!/usr/bin/env python3
"""P35 reproducible evidence and explicit owner-run entry point (stdlib only)."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tempfile
import unittest
import uuid

sys.dont_write_bytecode = True

import plan
import qualification

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN_ID = 'P35-B-20261125-1'
PACKAGE_REL = 'prototypes/pro/P35/' + RUN_ID
RUNTIME = ROOT / '.runtime' / RUN_ID
DEFAULT_OWNER = RUNTIME / 'owner-inputs.json'


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def frontier_report(package):
    value = plan.read_json(Path(package) / 'frontier-recipes.json')
    if (value.get('state') != 'planned' or value.get('verified') is not False
            or value.get('runtime_admitted') is not False
            or value.get('added_to_current_run_plan') is not False):
        raise ValueError('Frontier proposals must remain planned, unverified and excluded from current execution')
    rows = []
    for route in value['recipes']:
        preset = route['sidecar_preset']
        if (route['state'] != 'planned' or route['verified'] is not False
                or route['runtime_admitted'] is not False or preset.get('submit_enabled') is not False):
            raise ValueError('Frontier recipe cannot acquire submission authority')
        graph = route['graph']
        counts = plan.validate_graph(graph)
        if plan.stable_hash(graph) != route['graph_sha256_canonical']:
            raise ValueError('Frontier graph identity changed')
        for slot in preset['reference_slots']:
            for name in ('binding', 'conditioning_binding'):
                node, field = slot[name]
                if node not in graph or field not in graph[node]['inputs']:
                    raise ValueError('Frontier reference has no declared native binding')
        rows.append({'id': route['id'], 'graph_nodes': counts['nodes'],
                     'graph_sha256': route['graph_sha256_canonical'], 'output_claim': 'planned'})
    return {'runtime_admitted': False, 'validation': 'structural_proposal_only', 'recipes': rows}


def offline_evidence(package):
    """Deterministic software evidence; no owner input or service access."""
    package = Path(package)
    suite, bundle = plan.read_json(package / 'suite.json'), plan.read_json(package / 'routes.json')
    structure = plan.validate_bundle(package, bundle)
    planned = plan.compile_plan(suite, bundle)
    full = plan.compile_plan(suite, bundle, profile='full')
    fixtures = plan.read_json(package / 'fixtures/calibration.json')
    calibration = {}
    for name, example in fixtures['examples'].items():
        result = qualification.calibrate_metric(example['spec'], example['rows'])
        calibration[name] = {key: value for key, value in result.items() if key != 'inputs'}
    return {
        'qualification-summary.json': qualification.summarize(suite, []),
        'calibration-demo.json': {
            'schema': 'p35.calibration-demo/v1', 'scope': fixtures['scope'],
            'examples': calibration, 'owner_library_available': False,
            'any_gate_enabled': any(row['gating_enabled'] for row in calibration.values())},
        'route-summary.json': {
            'schema': 'p35.route-evidence/v1', 'source_structure': structure,
            'frontier': frontier_report(package), 'output_claim': 'planned',
            'image_generation_submitted': False, 'smoke_selected_slots': planned['selected_slots'],
            'full_selected_slots': full['selected_slots'], 'smoke_ready_without_owner_inputs': planned['ready'],
            'smoke_blocker_count': len(planned['blockers']), 'full_blocker_count': len(full['blockers']),
            'smoke_estimated_warm_seconds_range': planned['estimated_warm_seconds_range'],
            'smoke_conservative_budget_seconds': planned['conservative_chunk_budget_seconds'],
            'estimates_are_measurements': False,
            'routes': [{'id': route['id'], 'preset_id': route['preset_id'], 'graph_sha256': route['graph_sha256'],
                        'runtime_estimate': route['runtime_estimate'], 'capabilities': route['capabilities']}
                       for route in bundle['routes']]},
    }


def check_hashes(package, outputs):
    """Verify committed compact evidence and freshly reproduced bytes independently."""
    package = Path(package)
    manifest = package / 'HASHES.sha256'
    entries = {}
    prefix = PACKAGE_REL + '/evidence/'
    raw = manifest.read_bytes()
    if b'\r' in raw or not raw.endswith(b'\n'):
        raise ValueError('Hash manifest must use UTF-8 and LF')
    for line in raw.decode('utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([^\r\n]+)', line)
        if not match or not match[2].startswith(prefix):
            raise ValueError('Invalid evidence hash manifest entry')
        name = match[2][len(prefix):]
        if PurePosixPath(name).name != name or name in entries:
            raise ValueError('Unsafe or duplicate evidence manifest path')
        entries[name] = match[1]
    if set(entries) != set(outputs):
        raise ValueError('Hash manifest does not cover exactly the deterministic outputs')
    for name, expected in entries.items():
        path = package / 'evidence' / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Changed committed evidence: ' + name)
        if hashlib.sha256(json_bytes(outputs[name])).hexdigest() != expected:
            raise ValueError('Changed regenerated evidence: ' + name)
    return {'checked': len(entries), 'matches': True}


def validate_compiled(value):
    if not isinstance(value, dict) or value.get('schema') != 'p35.plan/v1':
        raise ValueError('Expected a complete compiler plan')
    if value.get('plan_sha256') != plan.stable_hash({key: item for key, item in value.items() if key != 'plan_sha256'}):
        raise ValueError('Compiler plan hash changed')
    frozen = qualification.validate_suite(value['bound_suite'])
    if value['suite_sha256'] != frozen['suite_sha256']:
        raise ValueError('Compiled suite hash changed')
    trials = {row['id']: row for row in frozen['trials']}
    ledger = value.get('trial_ledger')
    if not isinstance(ledger, list) or any(not isinstance(row, dict) for row in ledger):
        raise ValueError('Compiler trial ledger must be a list of planned trials')
    selected = [row.get('id') for row in ledger]
    if (type(value.get('selected_slots')) is not int or len(selected) != value['selected_slots']
            or len(set(selected)) != len(selected) or not set(selected) <= set(trials)
            or type(value.get('full_suite_slots')) is not int or value['full_suite_slots'] != len(trials)):
        raise ValueError('Compiler trial denominator changed')
    for row in ledger:
        immutable = {key: item for key, item in row.items() if key not in ('status', 'output_claim')}
        if (plan.canonical(immutable) != plan.canonical(trials[row['id']])
                or row.get('status') not in ('planned', 'blocked', 'unsupported') or row.get('output_claim') != 'planned'):
            raise ValueError('Compiler ledger changed an immutable expanded trial')
    bundle = plan.read_json(HERE / 'routes.json')
    plan.validate_bundle(HERE, bundle)
    routes = {route['id']: route for route in bundle['routes']}
    for route_id, pin in value['bound_suite']['route_pins'].items():
        if route_id not in routes or pin != plan.stable_hash(routes[route_id]):
            raise ValueError('Compiled route pin differs from the frozen route bundle')
    admitted = value.get('owner_run')
    if type(value.get('ready')) is not bool or value['ready'] != (admitted is not None):
        raise ValueError('Compiler readiness and admitted execution contract differ')
    if admitted is not None:
        import owner_run
        owner_run.validate_plan(admitted)
        if admitted['campaign_id'] != value['campaign_id']:
            raise ValueError('Inner and outer campaign identities differ')
        if value.get('blockers') or any(row['status'] != 'planned' for row in ledger):
            raise ValueError('Blocked compiler cells cannot acquire an execution contract')
        selected_keys = {(row['route_id'], row['case_id'], row['seed']) for row in ledger}
        cases = {case['id']: case for case in value['bound_suite']['cases']}
        covered, chunk_cases, budget = set(), set(), 0
        for chunk in admitted['chunks']:
            route_id, case_id = chunk.get('route_id'), chunk.get('case_id')
            if route_id not in routes or case_id not in cases or chunk['id'] != f'{route_id}-{case_id}':
                raise ValueError('Execution chunk does not identify a frozen route and case')
            if (route_id, case_id) in chunk_cases:
                raise ValueError('Duplicate execution chunk for one selected route and case')
            chunk_cases.add((route_id, case_id))
            route, case = routes[route_id], cases[case_id]
            actual_inputs = case.get('route_inputs', {}).get(route_id)
            expected_request = request_from_frozen_inputs(case, route, actual_inputs)
            expected_inputs = [{'file': item['file'], 'sha256': item['sha256']} for item in actual_inputs]
            if chunk['expected_inputs'] != expected_inputs:
                raise ValueError('Execution chunk input sources differ from the frozen actual route inputs')
            request = chunk['payload']['recipe']
            positive = request['controls'].get('positive')
            if not isinstance(positive, str) or not positive.strip() or len(positive) > 7500 or '\x00' in positive:
                raise ValueError('Execution recipe needs bounded declared prompt text')
            # Prompt authorship/meaning is declared, not authenticated. Its exact
            # bytes still bind the graph and the expected settings fingerprint.
            expected_request['controls']['positive'] = positive
            if plan.canonical(request) != plan.canonical(expected_request):
                raise ValueError('Execution recipe controls, native reference order or roles differ from the frozen contract')
            if chunk['expected_models'] != plan._model_pins(route):
                raise ValueError('Execution model pins differ from the frozen route')
            pruned = [{'slot': index + 1, 'role': slot['role']} for index, slot in enumerate(route['native_reference_slots'])
                      if index >= len(request['references'])]
            if chunk.get('expected_pruned_reference_slots', []) != pruned or chunk.get('detector_behavior') != route['detector_behavior']:
                raise ValueError('Execution reference pruning or detector behavior differs from the frozen route')
            variants = chunk['payload']['variants']
            expected_graphs = []
            for variant in variants:
                seed = variant['controls']['seed']
                key = (route_id, case_id, seed)
                if key not in selected_keys or key in covered or variant['label'] != f'seed-{seed}':
                    raise ValueError('Execution chunk variants do not uniquely match the selected trials')
                covered.add(key)
                graph = plan.materialize_graph(route, plan.read_json(HERE / route['graph']), request, seed)
                expected_graphs.append(plan.studio_hash(graph))
            if chunk['expected_graph_sha256'] != expected_graphs:
                raise ValueError('Execution graph pins differ from the frozen native materialization')
            seconds = max(route['runtime_estimate']['max_seconds_per_chunk'],
                          route['runtime_estimate']['warm_seconds_range'][1] * len(variants) + plan.CHUNK_HEADROOM_SECONDS)
            if chunk['payload']['max_seconds'] != seconds:
                raise ValueError('Execution chunk time allowance differs from the compiled route allowance')
            budget += seconds
        if covered != selected_keys or admitted['max_attempts'] != len(selected_keys):
            raise ValueError('Execution chunks do not cover the complete frozen selection')
        if budget > 14400 or admitted['max_seconds'] != budget or value['conservative_chunk_budget_seconds'] != budget:
            raise ValueError('Execution campaign time allowance differs from the frozen chunk budget')
    return value


def request_from_frozen_inputs(case, route, actual_inputs):
    """Reapply the compiler's native slot contract without inventing owner prose."""
    if not isinstance(actual_inputs, list) or not actual_inputs:
        raise ValueError('An execution chunk lacks frozen actual route inputs')
    owner = {'reference_bindings': {}, 'guides': {}, 'characters': {
        subject: {'description': 'Declared character', 'outfit': 'Declared outfit', 'style': 'Declared style', 'details': []}
        for subject in case['subject_ids']}}
    for item in actual_inputs:
        if not isinstance(item, dict) or not all(key in item for key in ('file', 'sha256', 'source_group')):
            raise ValueError('Frozen actual route input lacks its source identity')
        source = {'file': item['file'], 'sha256': item['sha256']}
        if item.get('representation') == 'precomputed-skeleton':
            source.update(representation=item['representation'], renderer=item.get('renderer'))
            owner['guides'][case['id']] = source
        elif item['source_group'] == 'owner-declared-default-style':
            owner['default_style'] = source
        else:
            owner['reference_bindings'][item['source_group']] = source
    for reference in case['references']:
        source = owner['reference_bindings'].get(reference['source_group'])
        if source is not None and source['sha256'] != reference['sha256']:
            raise ValueError('Actual route input bytes differ from the declared case reference')
    inputs, problems, unsupported = plan._case_inputs(case, route, owner)
    if problems or unsupported or plan.canonical(inputs) != plan.canonical(actual_inputs):
        raise ValueError('Frozen actual route inputs violate the native reference contract')
    return plan._request(case, route, owner, inputs)


def expected_execution(value):
    result = {}
    run = value.get('owner_run')
    if run is not None:
        for chunk in run['chunks']:
            for variant, graph_hash in zip(chunk['payload']['variants'], chunk['expected_graph_sha256']):
                result[(chunk['route_id'], chunk['case_id'], variant['controls']['seed'])] = {
                    'graph_sha256': graph_hash,
                    'model_set_sha256': plan.stable_hash(chunk['expected_models']),
                    'model_set_convention': 'sorted normalized file/sha256/bytes rows; compact UTF-8 JSON',
                    'settings_sha256': plan.stable_hash({'recipe': chunk['payload']['recipe'], 'variant': variant})}
    return result


def review_template(value):
    validate_compiled(value)
    expected = expected_execution(value)
    rows = []
    for trial in value['trial_ledger']:
        lineage = {key: trial[key] for key in ('suite_sha256', 'case_sha256', 'references_sha256', 'route_sha256',
                                              'seed', 'rubric_sha256', 'route_inputs_sha256') if key in trial}
        lineage.update({key: None for key in ('graph_sha256', 'model_set_sha256', 'preprocessing_sha256',
                                             'settings_sha256', 'environment_sha256', 'job_id', 'prompt_id')})
        rows.append({
            'case_id': trial['case_id'], 'route_id': trial['route_id'], 'seed': trial['seed'],
            'planned_status': trial['status'], 'expected_execution': expected.get((trial['route_id'], trial['case_id'], trial['seed'])),
            'receipt': {'trial_id': trial['id'], 'status': None, 'lineage': lineage, 'output_sha256': None,
                        'review': None, 'reason': '', 'cost': {key: None for key in ('attempts', 'retry_count', 'runtime_seconds',
                                                                                'peak_vram_bytes', 'peak_ram_bytes', 'operator_seconds')}},
            'review_fields': {'reviewer_id': '', 'reviewer_kind': None, 'reviewer_role': None, 'output_sha256': None,
                              'case_sha256': trial['case_sha256'], 'notes': '',
                              'scores': {subject: {axis: None for axis in qualification.AXES} for subject in trial['case']['subject_ids']}}})
    return {'schema': 'p35.review-template/v1', 'output_claim': 'planned', 'suite_sha256': value['suite_sha256'],
            'note': 'Authoring template, not receipts. Populate from actual job/output/measurement records; copy review_fields only after inspection. Expected hashes are not observed hashes. Keep/Not this and licence remain separate.',
            'rows': rows}


def score_receipts(value, receipts, calibration):
    validate_compiled(value)
    expected = expected_execution(value)
    trials = {row['id']: row for row in value['trial_ledger']}
    if not isinstance(receipts, list):
        raise ValueError('Receipt input must be a JSON list; authoring templates are not receipts')
    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get('trial_id') not in trials:
            raise ValueError('Receipt is outside this frozen plan selection')
        if receipt.get('status') != 'completed':
            continue
        trial = trials[receipt['trial_id']]
        pins = expected.get((trial['route_id'], trial['case_id'], trial['seed']))
        if pins is None:
            raise ValueError('No admitted execution contract for completed receipt')
        lineage = receipt.get('lineage', {})
        for key in ('graph_sha256', 'model_set_sha256', 'settings_sha256'):
            if lineage.get(key) != pins[key]:
                raise ValueError('Completed receipt differs from frozen ' + key)
    return qualification.summarize(value['bound_suite'], receipts, calibration)


def compile_owner(args):
    if not args.owner.is_file():
        raise ValueError('Owner input file is missing. Run init, then fill exact Studio workspace, upload names/hashes and character descriptions: ' + str(args.owner))
    value = plan.compile_plan(plan.read_json(HERE / 'suite.json'), plan.read_json(HERE / 'routes.json'), plan.read_json(args.owner),
                              profile=args.profile, route_ids=args.routes, case_ids=args.cases, seed_count=args.seeds,
                              allow_heavy=args.allow_heavy, prospective=args.prospective)
    validate_compiled(value)
    out = args.out or RUNTIME / 'plans' / value['campaign_id']
    plan.runtime_write(out / 'plan.json', value, ROOT)
    plan.runtime_write(out / 'review-template.json', review_template(value), ROOT)
    if value['owner_run'] is not None:
        plan.runtime_write(out / 'owner-run.json', value['owner_run'], ROOT)
    return value, out


def verify(args):
    import source_contract_check
    out = args.out or RUNTIME / 'evidence'
    # All generated test fixtures and retained logs stay under the repository .runtime.
    scratch = RUNTIME / 'tmp'
    previous = {key: os.environ.get(key) for key in ('P35_SOURCE_ROOT', 'TMPDIR', 'TMP', 'TEMP', 'PYTHONDONTWRITEBYTECODE')}
    previous_tempdir = tempfile.tempdir
    log = io.StringIO()
    result, outputs, hashes, error = None, {}, None, None
    phase, interrupted = 'fixture_directory', False
    try:
        plan.runtime_write(scratch / 'purpose.json', {'scope': 'Temporary synthetic offline verification fixtures only'}, ROOT)
        os.environ['P35_SOURCE_ROOT'] = str(args.source_root.resolve())
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        for key in ('TMPDIR', 'TMP', 'TEMP'):
            os.environ[key] = str(scratch)
        tempfile.tempdir = str(scratch)
        phase = 'unit_tests'
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            tests = unittest.defaultTestLoader.discover(str(HERE), pattern='test_*.py')
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(tests)
        phase = 'deterministic_evidence'
        produced = offline_evidence(HERE)
        if not isinstance(produced, dict):
            raise ValueError('Deterministic evidence must be a named output mapping')
        outputs = produced
        phase = 'source_contract'
        outputs['source-contract.json'] = source_contract_check.check_contract(args.source_root, HERE)
        phase = 'hash_manifest'
        hashes = check_hashes(HERE, outputs)
        phase = 'deterministic_output'
        for name, value in outputs.items():
            plan.runtime_write(out / 'deterministic' / name, value, ROOT)
    except (Exception, KeyboardInterrupt) as exc:
        interrupted = isinstance(exc, KeyboardInterrupt)
        error = {'phase': phase, 'type': type(exc).__name__, 'message': str(exc) or type(exc).__name__}
    finally:
        tempfile.tempdir = previous_tempdir
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
    source_report = outputs.get('source-contract.json')
    receipt = {'schema': 'p35.software-verification/v1', 'run': RUN_ID,
               'utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'os': platform.platform(), 'python': sys.version, 'python_compiler': platform.python_compiler(),
               'compiler_invoked': None, 'compiler_flags': [],
               'tests_run': result.testsRun if result is not None else 0,
               'failures': len(result.failures) if result is not None else 0,
               'errors': len(result.errors) if result is not None else 0,
               'skipped': len(result.skipped) if result is not None else 0,
               'passed': bool(result is not None and result.wasSuccessful() and not result.skipped and error is None),
               'verification_error': error,
               'source_graph_comparisons': source_report.get('graph_comparisons') if isinstance(source_report, dict) else None,
               'deterministic_hashes': hashes,
               'image_generation_submitted': False, 'live_studio_used': False, 'owner_calibration_available': False,
               'windows_gpu_validation': False,
               'repository_checks': 'Separate full-repository CI; this command checks the isolated prototype and pinned preparation subset.',
               'test_log': log.getvalue()}
    filename = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8] + '.json'
    receipt_path = out / 'runs' / filename
    try:
        plan.runtime_write(receipt_path, receipt, ROOT)
    except (OSError, ValueError, TypeError) as exc:
        receipt['passed'] = False
        write_error = {'phase': 'receipt_output', 'type': type(exc).__name__, 'message': str(exc)}
        receipt['receipt_write_error'] = write_error
        receipt['verification_error'] = receipt['verification_error'] or write_error
        receipt_path = RUNTIME / 'evidence' / 'failed-runs' / filename
        try:
            plan.runtime_write(receipt_path, receipt, ROOT)
        except (OSError, ValueError, TypeError) as fallback:
            print(log.getvalue())
            print(json.dumps({'ok': False, 'verification_error': receipt['verification_error'],
                              'receipt_error': str(fallback), 'test_log_retained': False}, indent=2))
            return 130 if interrupted else 2
    print(json.dumps({key: value for key, value in receipt.items() if key != 'test_log'}, indent=2))
    print('Retained software verification receipt: ' + str(receipt_path))
    if not receipt['passed']:
        print(log.getvalue())
    return 130 if interrupted else 2 if receipt['verification_error'] else 0 if receipt['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create an owner input template; no network')
    init.add_argument('--out', type=Path, default=DEFAULT_OWNER)
    check = commands.add_parser('verify', help='Reproduce offline tests, source checks and deterministic evidence; no live service')
    check.add_argument('--source-root', type=Path, default=ROOT)
    check.add_argument('--out', type=Path)
    for name in ('plan', 'prepare', 'owner-start'):
        child = commands.add_parser(name)
        child.add_argument('--owner', type=Path, default=DEFAULT_OWNER)
        child.add_argument('--profile', choices=('smoke', 'full'), default='smoke')
        child.add_argument('--routes', nargs='+')
        child.add_argument('--cases', nargs='+')
        child.add_argument('--seeds', type=int, choices=(2, 3))
        child.add_argument('--allow-heavy', action='store_true')
        child.add_argument('--prospective', action='store_true', help='Freeze a prospective protocol before running; image claims remain planned')
        child.add_argument('--out', type=Path)
        if name != 'plan':
            child.add_argument('--base-url', default='http://127.0.0.1:8191')
            child.add_argument('--prepare-timeout', type=float, default=600)
    status = commands.add_parser('status', help='Read-only observation; never retries or clears a lock')
    status.add_argument('--plan', type=Path, required=True, help='The exact owner-run.json retained before the first effect')
    status.add_argument('--base-url', default='http://127.0.0.1:8191')
    score = commands.add_parser('score', help='Score declared receipts against the full frozen suite; no network')
    score.add_argument('--plan', type=Path, required=True, help='The complete compiler plan.json')
    score.add_argument('--receipts', type=Path, required=True)
    score.add_argument('--calibration', type=Path)
    score.add_argument('--out', type=Path, required=True)
    calibrate = commands.add_parser('calibrate', help='Evaluate a frozen {spec,rows} file; no labels are invented')
    calibrate.add_argument('--input', type=Path, required=True)
    calibrate.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 12):
            raise ValueError('Python 3.12 or newer is required')
        if args.command == 'init':
            plan.runtime_write(args.out, plan.owner_template(plan.read_json(HERE / 'suite.json')), ROOT)
            print('Wrote owner input template: ' + str(args.out))
            print('No service contacted; no generation submitted.')
            return 0
        if args.command == 'verify':
            return verify(args)
        if args.command in ('plan', 'prepare', 'owner-start'):
            if args.command != 'plan' and not args.prospective:
                raise ValueError('Use --prospective to freeze the real experiment protocol before any Studio action. Image output claims remain planned.')
            value, out = compile_owner(args)
            print(json.dumps({'ready': value['ready'], 'selected_slots': value['selected_slots'],
                              'campaign_id': value['campaign_id'], 'plan_directory': str(out),
                              'blockers': value['blockers'], 'output_claim': 'planned'}, indent=2))
            if not value['ready']:
                return 2
            if args.command == 'plan':
                return 0
            import owner_run
            action = '--start' if args.command == 'owner-start' else '--prepare'
            return owner_run.main(['--plan', str(out / 'owner-run.json'), action, '--runtime', str(ROOT / '.runtime'),
                                   '--base-url', args.base_url, '--prepare-timeout', str(args.prepare_timeout)])
        if args.command == 'status':
            import owner_run
            return owner_run.main(['--plan', str(args.plan), '--status', '--runtime', str(ROOT / '.runtime'), '--base-url', args.base_url])
        if args.command == 'calibrate':
            value = plan.read_json(args.input)
            if not isinstance(value, dict) or set(value) != {'spec', 'rows'}:
                raise ValueError('Calibration input must contain exactly spec and rows')
            result = qualification.calibrate_metric(value['spec'], value['rows'])
        else:
            result = score_receipts(plan.read_json(args.plan), plan.read_json(args.receipts),
                                    plan.read_json(args.calibration) if args.calibration else None)
        plan.runtime_write(args.out, result, ROOT)
        print('Wrote declared-evidence assessment: ' + str(args.out))
        print('Assessment does not submit generation, create an owner Keep, or clear a licence.')
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc), 'output_claim': 'planned'}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
