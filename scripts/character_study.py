"""Character canon, bounded study plans and evidence accounting; never submits jobs.

This is an offline specialization of the existing game-asset lane, not a queue,
reviewer authentication system, licence grant or artistic-quality oracle.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON = 4 * 1024 * 1024
OBSERVATIONS = {'pass', 'fail', 'not_visible', 'uncertain'}
ROLES = {'identity', 'costume', 'pose', 'style', 'composition'}
SHA = re.compile(r'[0-9a-f]{64}\Z')
ID = re.compile(r'[a-z][a-z0-9-]{1,63}\Z')


def require(condition: bool, message: str) -> None:
    if not condition: raise ValueError(message)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    with Path(path).open('rb') as stream: raw = stream.read(MAX_JSON + 1)
    require(len(raw) <= MAX_JSON, 'JSON exceeds 4 MiB')
    def reject(value): raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=reject)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path: Path) -> str:
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream: stream.write(raw)


def text(value: Any, label: str, maximum: int = 12000) -> None:
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum and '\0' not in value,
            'Invalid ' + label)


def identifier(value: Any) -> None:
    require(isinstance(value, str) and bool(ID.fullmatch(value)), 'Invalid identifier')


def integer(value: Any, low: int, high: int, label: str) -> None:
    require(type(value) is int and low <= value <= high, f'{label}: expected integer {low}..{high}')


def strings(value: Any, label: str, minimum: int = 0, maximum: int = 64) -> None:
    require(isinstance(value, list) and minimum <= len(value) <= maximum, 'Invalid ' + label)
    for item in value: text(item, label)


def keys(value: Any, required: set[str], optional: set[str] = frozenset()) -> None:
    require(isinstance(value, dict), 'Expected an object')
    require(required <= value.keys() and value.keys() <= required | optional,
            'Missing or unsupported fields: ' + ', '.join(sorted((required - value.keys()) | (value.keys() - required - optional))))


def relative(value: Any) -> None:
    text(value, 'workspace-relative path', 240)
    require('\\' not in value and ':' not in value, 'Use a portable POSIX relative path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in {'', '.', '..'} for p in value.split('/')),
            'Path escapes workspace or is not canonical')
    for part in path.parts:
        stem = part.split('.')[0].upper()
        require(not part.endswith((' ', '.')) and not any(ord(c) < 32 for c in part)
                and not any(c in '<>"|?*' for c in part)
                and stem not in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))},
                'Non-portable path component')


def inside(root: Path, value: str) -> Path:
    relative(value)
    base = Path(root).resolve(strict=True)
    target = (base / value).resolve(strict=True)
    require(target.is_relative_to(base) and target.is_file(), 'File escapes workspace')
    return target


def artifact(value: Any) -> None:
    keys(value, {'path', 'sha256'})
    relative(value['path'])
    require(isinstance(value['sha256'], str) and bool(SHA.fullmatch(value['sha256'])), 'Invalid SHA-256')


def verify_artifact(root: Path, value: dict) -> Path:
    artifact(value)
    path = inside(root, value['path'])
    require(path.stat().st_size > 0 and file_sha(path) == value['sha256'], 'Changed or empty artifact: ' + value['path'])
    return path


def canon_subject(canon: dict) -> str:
    return sha({key: value for key, value in canon.items() if key != 'approval'})


def validate_canon(canon: dict) -> dict:
    keys(canon, {'schema_version', 'kind', 'asset_id', 'revision', 'identity', 'costume',
                 'representation', 'style', 'references', 'checks', 'approval'})
    require(type(canon['schema_version']) is int and canon['schema_version'] == 1
            and canon['kind'] == 'character_canon', 'Expected character canon v1')
    identifier(canon['asset_id']); integer(canon['revision'], 1, 1000000, 'canon revision')
    for field in ('identity', 'costume', 'representation', 'style'):
        keys(canon[field], {'id', 'description', 'invariants'})
        identifier(canon[field]['id']); text(canon[field]['description'], field)
        strings(canon[field]['invariants'], field + ' invariants', 1)
    require(isinstance(canon['references'], list) and 1 <= len(canon['references']) <= 12, 'Expected 1..12 references')
    seen = set()
    for ref in canon['references']:
        keys(ref, {'id', 'path', 'sha256', 'role', 'take', 'ignore'})
        identifier(ref['id']); require(ref['id'] not in seen, 'Duplicate reference'); seen.add(ref['id'])
        artifact({k: ref[k] for k in ('path', 'sha256')})
        require(ref['role'] in ROLES, 'Unsupported reference role')
        strings(ref['take'], 'reference take', 1); strings(ref['ignore'], 'reference ignore')
    require(isinstance(canon['checks'], dict) and 1 <= len(canon['checks']) <= 32, 'Expected 1..32 named checks')
    for check, description in canon['checks'].items(): identifier(check); text(description, 'check description')
    approval = canon['approval']
    keys(approval, {'state', 'reviewer', 'reviewer_kind', 'note', 'subject_sha256'})
    require(approval['state'] in {'draft', 'selected', 'approved'}, 'Unknown canon approval state')
    text(approval['note'], 'approval note')
    if approval['state'] == 'draft':
        require(approval['reviewer'] is None and approval['reviewer_kind'] is None
                and approval['subject_sha256'] is None, 'Draft cannot claim approval evidence')
    else:
        text(approval['reviewer'], 'reviewer', 160)
        require(approval['reviewer_kind'] in {'human', 'agent'}, 'Unknown reviewer kind')
        require(approval['state'] != 'approved' or approval['reviewer_kind'] == 'human', 'Agent selection is not owner approval')
        require(approval['subject_sha256'] == canon_subject(canon), 'Stale canon approval: design changed')
    return canon


def attest_canon(canon: dict, reviewer: str, reviewer_kind: str, note: str) -> dict:
    validate_canon(canon)
    result = copy.deepcopy(canon)
    result['approval'] = {'state': 'approved' if reviewer_kind == 'human' else 'selected',
                          'reviewer': reviewer, 'reviewer_kind': reviewer_kind, 'note': note,
                          'subject_sha256': canon_subject(canon)}
    return validate_canon(result)


def validate_request(request: dict, canon: dict) -> None:
    keys(request, {'schema_version', 'kind', 'study_id', 'routes', 'tasks', 'seeds', 'budget', 'hypotheses'})
    require(type(request['schema_version']) is int and request['schema_version'] == 1
            and request['kind'] == 'character_study_request', 'Expected character study request v1')
    identifier(request['study_id']); strings(request['hypotheses'], 'hypotheses', 1, 16)
    require(isinstance(request['routes'], list) and 1 <= len(request['routes']) <= 8, 'Expected 1..8 routes')
    seen = set()
    for route in request['routes']:
        keys(route, {'id', 'preset_id', 'notes'})
        identifier(route['id']); identifier(route['preset_id']); text(route['notes'], 'route notes')
        require(route['id'] not in seen, 'Duplicate route'); seen.add(route['id'])
    require(isinstance(request['tasks'], list) and 1 <= len(request['tasks']) <= 16, 'Expected 1..16 tasks')
    ref_ids = {r['id'] for r in canon['references']}; seen = set()
    for task in request['tasks']:
        keys(task, {'id', 'instruction', 'reference_ids', 'required_checks'})
        identifier(task['id']); text(task['instruction'], 'task instruction')
        require(task['id'] not in seen, 'Duplicate task'); seen.add(task['id'])
        for field, allowed in [('reference_ids', ref_ids), ('required_checks', set(canon['checks']))]:
            strings(task[field], field, 1, 12 if field == 'reference_ids' else 32)
            require(len(task[field]) == len(set(task[field])) and set(task[field]) <= allowed, 'Duplicate or unknown ' + field)
    seeds = request['seeds']
    require(isinstance(seeds, list) and 1 <= len(seeds) <= 16, 'Expected 1..16 seeds')
    for seed in seeds: integer(seed, 0, 2**53 - 1, 'seed')
    require(len(set(seeds)) == len(seeds), 'Duplicate seed')
    budget = request['budget']
    keys(budget, {'max_generation_attempts', 'max_repairs_per_case', 'allow_paid_services'})
    integer(budget['max_generation_attempts'], 1, 256, 'generation budget')
    integer(budget['max_repairs_per_case'], 0, 3, 'repair budget')
    require(budget['allow_paid_services'] is False, 'Paid services are not authorized')
    require(len(request['routes']) * len(request['tasks']) * len(seeds) <= budget['max_generation_attempts'], 'Primary matrix exceeds the plan-wide budget')


def make_plan(canon: dict, request: dict) -> dict:
    validate_canon(canon); validate_request(request, canon)
    cases = []
    for route in request['routes']:
        for task in request['tasks']:
            for seed in request['seeds']:
                case = {'route_id': route['id'], 'preset_id': route['preset_id'], 'task_id': task['id'],
                        'instruction': task['instruction'], 'reference_ids': task['reference_ids'],
                        'required_checks': task['required_checks'], 'seed': seed}
                case['id'] = 'case-' + sha({'canon': sha(canon), 'request': sha(request), 'case': case})[:20]
                cases.append(copy.deepcopy(case))
    result = {'schema_version': 1, 'kind': 'character_study_plan', 'submits_generation': False,
              'canon': copy.deepcopy(canon), 'request': copy.deepcopy(request),
              'canon_sha256': sha(canon), 'request_sha256': sha(request), 'cases': cases,
              'evidence_state': 'not_run'}
    result['plan_sha256'] = sha(result)
    return result


def check_plan(plan: dict) -> dict:
    require(isinstance(plan, dict) and plan.get('kind') == 'character_study_plan', 'Not a character study plan')
    expected = make_plan(plan.get('canon'), plan.get('request'))
    require(canonical(plan) == canonical(expected), 'Plan changed; author a new branch plan instead')
    return plan


def get_case(plan: dict, case_id: str) -> dict:
    check_plan(plan)
    case = next((c for c in plan['cases'] if c['id'] == case_id), None)
    require(case is not None, 'Unknown case')
    return case


def preflight(plan: dict, workspace: Path) -> dict:
    check_plan(plan)
    blockers = []
    if plan['canon']['approval']['state'] != 'approved': blockers.append('Canon is not explicitly human-approved; do not infer acceptance from the example.')
    for ref in plan['canon']['references']:
        try: verify_artifact(workspace, {k: ref[k] for k in ('path', 'sha256')})
        except (OSError, ValueError) as exc: blockers.append(ref['id'] + ': ' + str(exc))
    return {'plan_sha256': plan['plan_sha256'], 'reference_and_canon_checks_passed': not blockers,
            'blockers': blockers, 'runtime_preflight': 'not_performed', 'submission_authorized': False,
            'remaining_checks': ['Live model/node/runtime pins', 'Shared queue/resource ownership',
                                 'Model and input terms for this use', 'Explicit Generate through the existing Studio']}


def case_brief(plan: dict, case_id: str) -> dict:
    """Produce the existing game-assets v1 brief; its copied budget is NOT new credit."""
    case = get_case(plan, case_id); canon = plan['canon']
    references = {r['id']: r for r in canon['references']}
    lines = [case['instruction']]
    for field in ('identity', 'costume', 'representation', 'style'):
        lines.append(field.title() + ': ' + canon[field]['description'])
        lines.extend(canon[field]['invariants'])
    budget = plan['request']['budget']
    return {'schema_version': 1, 'asset_id': case['id'], 'route': 'reference-image',
            'description': '\n'.join(lines),
            'references': [dict(copy.deepcopy(references[k]), kind='image') for k in case['reference_ids']],
            'target': {'engine': 'generic', 'outputs': ['review-panel.png', 'execution-receipt.json']},
            'constraints': [canon['checks'][k] for k in case['required_checks']] +
                           ['One panel only; no lettering. Return to the approved canon, not an unreviewed derivative.',
                            'Budget belongs to study ' + plan['plan_sha256'] + '; do not multiply it by the number of case briefs.'],
            'budget': {'generation_attempts': budget['max_generation_attempts'],
                       'repair_attempts_per_stage': budget['max_repairs_per_case'], 'allow_paid_services': False}}


def prepare_handoff(plan: dict, case_id: str, workspace: Path, repo_root: Path) -> dict:
    """Pin an existing preset/template and list uploads; never return an armed job.

    The Studio must still upload/bind references, inspect live models/nodes,
    reserve the shared budget and use its ordinary Prepare/Generate path.
    """
    case = get_case(plan, case_id)
    report = preflight(plan, workspace)
    require(report['reference_and_canon_checks_passed'], '; '.join(report['blockers']))
    catalog = read_json(inside(repo_root, 'presets/catalog.json'))
    presets = catalog.get('presets')
    require(isinstance(presets, list), 'Invalid Studio catalog')
    matched = [p for p in presets if isinstance(p, dict) and p.get('id') == case['preset_id']]
    require(len(matched) == 1, 'Preset is missing or ambiguous; do not substitute another model')
    preset = matched[0]
    require(preset.get('modality', 'image') == 'image', 'Character panels require an image preset')
    relative(preset.get('graph'))
    require(preset['graph'].startswith('workflows/api/'), 'Not an API template')
    graph_path = inside(repo_root, preset['graph']); graph = read_json(graph_path)
    require(isinstance(graph, dict), 'Invalid API template')
    binding_report = {}
    for control in ('positive', 'seed'):
        bindings = [preset.get(control)] + preset.get('bindings_extra', {}).get(control, [])
        for binding in bindings:
            require(isinstance(binding, list) and len(binding) == 2, 'Missing native ' + control + ' binding')
            node, field = binding
            require(str(node) in graph and field in graph[str(node)].get('inputs', {}), 'Stale ' + control + ' binding')
        binding_report[control] = copy.deepcopy(bindings)
    slots = preset.get('reference_slots')
    if slots:
        require(isinstance(slots, list) and len(slots) == len(case['reference_ids']), 'Reference slot count mismatch; nothing may be silently discarded')
        reference_bindings = [slot['binding'] for slot in slots]
    else:
        require(len(case['reference_ids']) == 1 and preset.get('reference'), 'This preset needs a supported reference binding')
        reference_bindings = [preset['reference']]
    for binding in reference_bindings:
        require(isinstance(binding, list) and len(binding) == 2 and str(binding[0]) in graph
                and binding[1] in graph[str(binding[0])].get('inputs', {}), 'Stale reference binding')
    refs = {r['id']: r for r in plan['canon']['references']}
    brief = case_brief(plan, case_id)
    instructions = [brief['description']]
    uploads = []
    for index, rid in enumerate(case['reference_ids']):
        ref = refs[rid]
        instructions.append(f"Image {index + 1} [{ref['role']}]: take {'; '.join(ref['take'])}. Ignore {'; '.join(ref['ignore']) or 'unrequested changes'}.")
        uploads.append(dict(copy.deepcopy(ref), slot_index=index, binding=reference_bindings[index]))
    result = {'schema_version': 1, 'kind': 'character_study_handoff', 'plan_sha256': plan['plan_sha256'],
              'case_id': case_id, 'preset_id': preset['id'], 'catalog_entry_sha256': sha(preset),
              'template_path': preset['graph'], 'template_sha256': file_sha(graph_path),
              'proposed_controls': {'positive': '\n'.join(instructions), 'seed': case['seed']},
              'control_bindings': binding_report, 'upload_requirements': uploads,
              'reference_policy': copy.deepcopy(preset.get('reference_policy', {})),
              'submits_generation': False, 'submission_payload': None,
              'unresolved': ['Upload original reference bytes through the existing Studio and retain returned names.',
                             'Check actual resize/crop, batch size, model/encoder/VAE/adapter and live node/runtime pins.',
                             'Reserve all image-producing attempts in the shared Production coordinator.',
                             'Recheck template/catalog/reference hashes; use normal Studio Prepare and explicit Generate.']}
    result['handoff_sha256'] = sha(result)
    return result


def _measurement(value: Any, label: str) -> None:
    require(value is None or (type(value) in {int, float} and math.isfinite(value) and value >= 0), 'Invalid measurement: ' + label)


def summarize(plan: dict, records: list, workspace: Path) -> dict:
    """Check chronological attempt attestations and report nulls, not invented metrics.

    Every record consumes one declared image-producing attempt, including failed,
    cancelled and uncertain work. No online budget enforcement is claimed.
    """
    check_plan(plan)
    require(isinstance(records, list) and len(records) <= 256, 'Expected at most 256 attempt records')
    budget = plan['request']['budget']
    require(len(records) <= budget['max_generation_attempts'], 'Plan-wide attempt budget exceeded')
    if records:
        require(preflight(plan, workspace)['reference_and_canon_checks_passed'], 'Verify approved canon and unchanged reference bytes before reporting attempts')
    cases = {c['id']: c for c in plan['cases']}; seen = {}; by_case = {}; selected = {}; repaired = {}
    blocked = set(); elapsed = []; cleanup = []; completed = 0; accepted = set(); primary_selected = set()
    for rec in records:
        keys(rec, {'id', 'plan_sha256', 'case_id', 'kind', 'state', 'parent_attempt_id', 'prompt_id',
                   'output', 'execution_evidence', 'elapsed_seconds', 'cleanup_seconds', 'review'})
        identifier(rec['id']); require(rec['id'] not in seen, 'Duplicate attempt ID')
        require(rec['plan_sha256'] == plan['plan_sha256'], 'Attempt belongs to another plan')
        require(rec['case_id'] in cases, 'Unknown attempt case')
        cid = rec['case_id']; case = cases[cid]
        require(rec['kind'] in {'primary', 'repair', 'warmup'}, 'Unknown attempt kind')
        require(rec['state'] in {'completed', 'failed', 'cancelled', 'submission_uncertain'}, 'Unknown execution state')
        require(cid not in blocked, 'Uncertain submission must be reconciled before more work on this case')
        if rec['prompt_id'] is not None: text(rec['prompt_id'], 'prompt ID', 256)
        verify_artifact(workspace, rec['execution_evidence'])
        if rec['kind'] == 'repair':
            parent = seen.get(rec['parent_attempt_id'])
            require(parent is not None and parent['case_id'] == cid and parent['state'] == 'completed'
                    and parent['kind'] != 'warmup', 'Repair requires a completed same-case parent')
            repaired[cid] = repaired.get(cid, 0) + 1
            require(repaired[cid] <= budget['max_repairs_per_case'], 'Per-case repair allowance exceeded')
        else:
            require(rec['parent_attempt_id'] is None, 'Only repairs have a parent')
            if rec['kind'] == 'primary': require(cid not in by_case, 'A case already has a primary attempt; branch a new plan for another trial')
        if rec['kind'] == 'primary': by_case[cid] = rec['id']
        if rec['state'] == 'submission_uncertain': blocked.add(cid)
        for name in ('elapsed_seconds', 'cleanup_seconds'): _measurement(rec[name], name)
        elapsed.append(rec['elapsed_seconds']); cleanup.append(rec['cleanup_seconds'])
        if rec['state'] == 'completed':
            require(rec['prompt_id'] is not None, 'Completed neural attempt needs its actual prompt ID')
            verify_artifact(workspace, rec['output']); completed += 1
        else: require(rec['output'] is None, 'Noncompleted outputs belong in retained execution evidence, not selected candidates')
        review = rec['review']
        if review is not None:
            require(rec['state'] == 'completed' and rec['kind'] != 'warmup', 'Only completed candidates can be reviewed')
            keys(review, {'reviewer', 'reviewer_kind', 'decision', 'checks', 'note', 'output_sha256'})
            text(review['reviewer'], 'reviewer', 160); text(review['note'], 'review note')
            require(review['reviewer_kind'] in {'human', 'agent'}, 'Unknown reviewer kind')
            require(review['decision'] in {'selected', 'rejected', 'needs_review', 'accepted'}, 'Unknown decision')
            require(review['output_sha256'] == rec['output']['sha256'], 'Review refers to different output bytes')
            require(isinstance(review['checks'], dict) and set(review['checks']) == set(case['required_checks']), 'Review must cover exactly the required checks')
            require(all(v in OBSERVATIONS for v in review['checks'].values()), 'Unknown observation state')
            if review['decision'] in {'selected', 'accepted'}:
                require(all(v == 'pass' for v in review['checks'].values()), 'Fail, uncertain or not_visible cannot pass a hard requirement')
                require(cid not in selected, 'Multiple selected candidates for one case; choose one in a new assessment snapshot and retain the old snapshot')
                selected[cid] = rec['id']
                if rec['kind'] == 'primary': primary_selected.add(cid)
            if review['decision'] == 'accepted':
                require(review['reviewer_kind'] == 'human', 'Agent selection is not human acceptance')
                accepted.add(cid)
        seen[rec['id']] = rec
    def total(values): return sum(values) if values and all(v is not None for v in values) else None
    total_elapsed = total(elapsed); total_cleanup = total(cleanup)
    effort = total_elapsed + total_cleanup if total_elapsed is not None and total_cleanup is not None else None
    return {'schema_version': 1, 'kind': 'character_study_summary', 'plan_sha256': plan['plan_sha256'],
            'attempts_used': len(records), 'attempts_remaining': budget['max_generation_attempts'] - len(records),
            'planned_cases': len(cases), 'primary_cases_attempted': len(by_case), 'completed_attempts': completed,
            'selected_cases': len(selected), 'human_accepted_cases': len(accepted),
            'selected_case_ids': sorted(selected), 'unresolved_submission_case_ids': sorted(blocked),
            'first_pass_selection_rate': len(primary_selected) / len(by_case) if by_case else None,
            'planned_case_coverage': len(selected) / len(cases),
            'total_elapsed_seconds': total_elapsed, 'total_cleanup_seconds': total_cleanup,
            'seconds_per_selected_case': effort / len(selected) if effort is not None and selected else None,
            'records_sha256': sha(records), 'generation_submitted': False,
            'limits': ['Records are local attestations, not authenticated execution or reviews.',
                       'One record declares one image-producing attempt; the trusted coordinator must enforce actual work.',
                       'Empty/missing measurements stay null; no significance or automatic winner is claimed.',
                       'Image selection does not certify rights, transparency, animation or target-engine acceptance.']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan'); p.add_argument('--canon', required=True, type=Path); p.add_argument('--study', required=True, type=Path); p.add_argument('--out', required=True, type=Path)
    p = commands.add_parser('attest-canon'); p.add_argument('--canon', required=True, type=Path); p.add_argument('--reviewer', required=True); p.add_argument('--reviewer-kind', choices=['human', 'agent'], required=True); p.add_argument('--note', required=True); p.add_argument('--out', required=True, type=Path)
    for name in ('preflight', 'summarize', 'brief', 'handoff'):
        p = commands.add_parser(name); p.add_argument('--plan', required=True, type=Path); p.add_argument('--out', required=True, type=Path)
        if name != 'brief': p.add_argument('--workspace', required=True, type=Path)
        if name == 'summarize': p.add_argument('--records', required=True, type=Path)
        if name in {'brief', 'handoff'}: p.add_argument('--case', required=True)
        if name == 'handoff': p.add_argument('--repo-root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        if args.command == 'plan': result = make_plan(read_json(args.canon), read_json(args.study))
        elif args.command == 'attest-canon': result = attest_canon(read_json(args.canon), args.reviewer, args.reviewer_kind, args.note)
        elif args.command == 'preflight': result = preflight(read_json(args.plan), args.workspace)
        elif args.command == 'brief': result = case_brief(read_json(args.plan), args.case)
        elif args.command == 'handoff': result = prepare_handoff(read_json(args.plan), args.case, args.workspace, args.repo_root)
        else: result = summarize(read_json(args.plan), read_json(args.records), args.workspace)
        write_json(args.out, result)
        print(json.dumps({'output': str(args.out), 'sha256': file_sha(args.out), 'submits_generation': False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc: parser.exit(2, f'character-study: {exc}\n')


if __name__ == '__main__': raise SystemExit(main())
