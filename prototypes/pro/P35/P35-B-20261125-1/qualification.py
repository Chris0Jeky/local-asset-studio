"""Pure, zero-authority behavioral qualification; Python 3.12+, stdlib only.

Consumes declarations; never runs inference, authenticates owners, writes marks,
or clears rights. studio_workflow.qualification retains static route provenance.
"""
from __future__ import annotations
from collections import Counter
import copy
from datetime import datetime
import hashlib
import json
import math
import re

SCHEMA = 'studio.reference-qualification/v1'
FAMILIES = ('ordinary', 'unusual', 'foreshortened', 'occluded', 'contact-heavy', 'floor', 'seated', 'lying', 'dynamic-action', 'multi-character')
AXES = ('identity', 'outfit_detail', 'pose_geometry', 'style', 'anatomy_contact', 'composition')
ROLES = {'identity', 'outfit', 'costume', 'pose', 'style', 'composition', 'scene', 'detail'}
MAX_BYTES = 4 * 1024 * 1024
HASH = re.compile(r'[0-9a-f]{64}\Z')
ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,95}\Z')
STATES = ('completed', 'failed', 'cancelled', 'submission_uncertain', 'unsupported')
ANCHORS = {
 'identity': ['Different or swapped subject', 'Major identity drift', 'Partial identity retention', 'Recognizable; minor repair', 'Strong declared identity match'],
 'outfit_detail': ['Wrong outfit or required detail absent', 'Major costume/detail loss', 'Some defining details retained', 'Required outfit/details mostly faithful', 'All declared distinguishing details retained'],
 'pose_geometry': ['Different pose or camera', 'Major limb or camera mismatch', 'Partial pose; visible geometry errors', 'Pose/camera meet brief with minor errors', 'Strong declared pose/camera match'],
 'style': ['Conflicting style', 'Major style mismatch', 'Mixed or inconsistent style', 'Requested style largely consistent', 'Strong consistent requested style'],
 'anatomy_contact': ['Broken topology or impossible contact', 'Major anatomy/support error', 'Visible anatomy/contact errors', 'Plausible body/contact/support; minor repair', 'Coherent anatomy, occlusion, contact and support'],
 'composition': ['Wrong framing, scene or arrangement', 'Major composition/scene mismatch', 'Partial framing or scene adherence', 'Composition/scene mostly met', 'Strong framing, scene and subject-position adherence'],
}

def _need(condition, message):
    if not condition: raise ValueError(message)

def _keys(value, required, optional=()):
    _need(isinstance(value, dict), 'Expected an object')
    _need(set(required) <= value.keys() <= set(required) | set(optional), 'Missing or unsupported fields')

def _text(value, maximum=4000):
    _need(isinstance(value, str) and 0 < len(value.strip()) <= maximum and '\0' not in value, 'Invalid text')
    return value

def _id(value):
    _need(isinstance(value, str) and ID.fullmatch(value), 'Invalid bounded identifier')
    return value

def _hash(value, nullable=False):
    if value is None and nullable: return None
    _need(isinstance(value, str) and HASH.fullmatch(value), 'Expected lowercase SHA-256')
    return value

def _number(value, low=0, high=math.inf, nullable=False, integer=False):
    if value is None and nullable: return None
    _need(type(value) is int if integer else type(value) in (int, float), 'Expected a number, not a boolean')
    try: valid = math.isfinite(value) and low <= value <= high
    except (ValueError, OverflowError): valid = False
    _need(valid, 'Number must be finite and in range')
    return value

def _json(value, depth=0):
    _need(depth <= 64, 'JSON nesting exceeds 64')
    if value is None or type(value) in (str, bool, int): return
    if type(value) is float:
        _need(math.isfinite(value), 'Non-finite JSON number'); return
    if isinstance(value, list):
        _need(len(value) <= 65536, 'JSON array exceeds bound')
        for item in value: _json(item, depth + 1)
        return
    if isinstance(value, dict):
        _need(all(type(key) is str for key in value), 'JSON object keys must be strings')
        for item in value.values(): _json(item, depth + 1)
        return
    raise ValueError('Expected ordinary finite JSON values')

def _canonical(value):
    _json(value)
    try: raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as error: raise ValueError('Invalid finite JSON') from error
    _need(len(raw) <= MAX_BYTES, 'JSON exceeds 4 MiB')
    return raw

def canonical_hash(value):
    """SHA-256 of bounded finite canonical JSON; does not authenticate an author."""
    return hashlib.sha256(_canonical(value)).hexdigest()

def rubric_fingerprint(minimum_score=3):
    _number(minimum_score, 3, 4, integer=True)
    return canonical_hash({'schema': 'studio.reference-rubric/v1', 'axes': list(AXES), 'anchors': ANCHORS, 'minimum_score': minimum_score})

def loads(data):
    """Duplicate keys, NaN, infinity and oversized JSON input refuse."""
    _need(isinstance(data, (bytes, str)), 'Expected JSON bytes or text')
    _need(len(data.encode('utf-8') if isinstance(data, str) else data) <= MAX_BYTES, 'JSON exceeds 4 MiB')
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'Duplicate JSON key'); result[key] = value
        return result
    def constant(value): raise ValueError('Non-finite JSON number: ' + value)
    try: result = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError) as error: raise ValueError('Invalid JSON encoding or nesting') from error
    _canonical(result)
    return result

def _snapshot(value): return loads(_canonical(value))

def _unique(values, label):
    _need(isinstance(values, list) and len(values) == len(set(values)), 'Duplicate or invalid ' + label)

def _reference(value):
    _keys(value, ('id', 'subject_id', 'roles', 'sha256', 'source_group', 'claims'))
    _id(value['id']); _id(value['source_group']); _hash(value['sha256'], nullable=True)
    if value['subject_id'] is not None: _id(value['subject_id'])
    roles = value['roles']
    _need(isinstance(roles, list) and roles and all(isinstance(r, str) and r in ROLES for r in roles), 'Unsupported reference role')
    _unique(roles, 'reference roles'); _unique(['costume' if r == 'outfit' else r for r in roles], 'normalized roles')
    claims = value['claims']; _need(isinstance(claims, dict) and set(claims) <= set(roles), 'Claims must name assigned roles')
    for fields in claims.values():
        _need(isinstance(fields, dict), 'Role claims must be explicit attribute/value objects')
        for name, expected in fields.items(): _text(name, 100); _text(expected, 1000)

def resolve_roles(references, route):
    """Use explicit metadata; route is the caller's capability projection, not a registry."""
    references, route = _snapshot(references), _snapshot(route)
    _need(isinstance(references, list) and len(references) <= 16, 'Use at most sixteen references')
    _need(isinstance(route, dict), 'Expected route capabilities'); _id(route.get('id'))
    supported = route.get('supported_roles')
    _need(isinstance(supported, list) and all(isinstance(r, str) and r in ROLES for r in supported), 'Invalid supported roles')
    supported = {'costume' if r == 'outfit' else r for r in supported}
    capacity = _number(route.get('max_references'), 0, 16, integer=True)
    _need(type(route.get('per_subject')) is bool, 'Declare per-subject support explicitly')
    ids, subjects, claims, conflicts, blockers, unsupported = set(), set(), {}, [], [], []
    for ref in references:
        _reference(ref); _need(ref['id'] not in ids, 'Duplicate reference ID'); ids.add(ref['id'])
        if ref['subject_id'] is not None: subjects.add(ref['subject_id'])
        if ref['sha256'] is None: blockers.append('missing_reference_bytes')
        normalized_claims = {}
        for role, fields in ref['claims'].items():
            role = 'costume' if role == 'outfit' else role; normalized_claims[role] = fields
            for name, value in fields.items():
                key = (ref['subject_id'], role, name)
                if key in claims and claims[key][0] != value:
                    conflicts.append({'subject_id': key[0], 'role': role, 'attribute': name,
                                      'reference_ids': [claims[key][1], ref['id']], 'values': [claims[key][0], value]})
                else: claims[key] = (value, ref['id'])
        ref['claims'] = normalized_claims; ref['roles'] = ['costume' if r == 'outfit' else r for r in ref['roles']]
        unsupported.extend({'reference_id': ref['id'], 'role': r} for r in ref['roles'] if r not in supported)
    if unsupported: blockers.append('unsupported_role')
    if conflicts: blockers.append('explicit_role_conflict')
    if len(references) > capacity: blockers.append('reference_capacity_exceeded')
    if len(subjects) > 1 and not route['per_subject']: blockers.append('per_subject_unsupported')
    return {'route_id': route['id'], 'references': references, 'conflicts': conflicts,
            'unsupported_roles': unsupported, 'blockers': sorted(set(blockers)), 'runnable': not blockers,
            'execution_authorized': False, 'scope': 'explicit_metadata_only'}

def validate_suite(suite):
    """Freeze the complete planned route × case × seed denominator, including blocked cells."""
    suite = _snapshot(suite)
    _keys(suite, ('schema', 'id', 'evidence_mode', 'canon', 'routes', 'route_pins', 'seeds', 'minimum_score', 'cases'))
    _need(suite['schema'] == SCHEMA, 'Unknown reference qualification schema'); _id(suite['id'])
    _need(suite['evidence_mode'] in ('planned', 'synthetic', 'prospective', 'owner_library'), 'Unknown evidence mode')
    _number(suite['minimum_score'], 3, 4, integer=True)
    canon = suite['canon']; _need(isinstance(canon, list) and 1 <= len(canon) <= 16, 'Declare canon characters')
    canon_ids = []
    for subject in canon:
        _keys(subject, ('id', 'label', 'reference_sha256')); canon_ids.append(_id(subject['id']))
        _text(subject['label'], 200); _hash(subject['reference_sha256'], nullable=True)
    _unique(canon_ids, 'canon IDs')
    routes = suite['routes']; _need(isinstance(routes, list) and 1 <= len(routes) <= 16, 'Declare route IDs')
    for route in routes: _id(route)
    _unique(routes, 'routes'); _keys(suite['route_pins'], routes)
    for value in suite['route_pins'].values(): _hash(value, nullable=True)
    seeds = suite['seeds']; _need(isinstance(seeds, list) and 2 <= len(seeds) <= 32, 'Use at least two paired seeds')
    for seed in seeds: _number(seed, 0, 2 ** 63 - 1, integer=True)
    _unique(seeds, 'seeds')
    cases = suite['cases']; _need(isinstance(cases, list) and 1 <= len(cases) <= 512, 'Declare 1..512 cases')
    identifiers, counts, blockers = [], Counter(), []
    for case in cases:
        _keys(case, ('id', 'family', 'title', 'brief', 'subject_ids', 'references'), ('route_inputs',))
        identifiers.append(_id(case['id'])); _text(case['title'], 200); _text(case['brief'])
        _need(case['family'] in FAMILIES, 'Unknown pose family'); counts[case['family']] += 1
        subjects = case['subject_ids']; _need(isinstance(subjects, list) and subjects, 'Declare each subject ID')
        for subject in subjects: _need(subject in canon_ids, 'Unknown canon subject')
        _unique(subjects, 'case subjects')
        _need((len(subjects) >= 2) == (case['family'] == 'multi-character'), 'Multi-character cases must preserve subject IDs')
        refs = case['references']; _need(isinstance(refs, list) and 1 <= len(refs) <= 16, 'Declare bounded references')
        for ref in refs:
            _reference(ref); _need(ref['subject_id'] is None or ref['subject_id'] in subjects, 'Reference belongs to another subject')
            if ref['sha256'] is None: blockers.append('missing_reference_bytes')
        _unique([r['id'] for r in refs], 'case reference IDs')
        if 'route_inputs' in case:
            _need(isinstance(case['route_inputs'], dict) and set(case['route_inputs']) <= set(routes), 'Unknown actual-input route')
            for inputs in case['route_inputs'].values():
                _need(isinstance(inputs, list) and len(inputs) <= 16, 'Invalid actual route inputs')
                for item in inputs:
                    _need(isinstance(item, dict) and 'sha256' in item and 'source_group' in item, 'Actual route input lacks identity')
                    _hash(item['sha256']); _id(item['source_group'])
    _unique(identifiers, 'case IDs')
    missing = [family for family in FAMILIES if counts[family] < 2]
    if missing: blockers.append('insufficient_family_coverage')
    if any(c['reference_sha256'] is None for c in canon): blockers.append('missing_canon_bytes')
    if any(pin is None for pin in suite['route_pins'].values()): blockers.append('missing_route_pins')
    suite_sha = canonical_hash(suite); trials = []
    for case in cases:
        for route in routes:
            for seed in seeds:
                identity = {'suite_sha256': suite_sha, 'case_sha256': canonical_hash(case),
                            'references_sha256': canonical_hash(case['references']), 'case_id': case['id'],
                            'route_id': route, 'route_sha256': suite['route_pins'][route], 'seed': seed,
                            'rubric_sha256': rubric_fingerprint(suite['minimum_score'])}
                if route in case.get('route_inputs', {}): identity['route_inputs_sha256'] = canonical_hash(case['route_inputs'][route])
                trials.append({'id': canonical_hash(identity), **identity, 'case': copy.deepcopy(case), 'minimum_score': suite['minimum_score']})
    return {'suite': suite, 'suite_sha256': suite_sha, 'trials': trials, 'ready': not blockers,
            'blockers': sorted(set(blockers)), 'coverage': {'cases_per_family': {f: counts[f] for f in FAMILIES},
            'missing_families': missing, 'seeds_per_case': len(seeds), 'canon_subjects': canon_ids},
            'execution_authorized': False, 'generation_submitted': False}

def _time(value):
    _text(value, 64)
    try: result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error: raise ValueError('Use an ISO-8601 timestamp') from error
    _need(result.tzinfo is not None, 'Timestamp requires timezone'); return result

def calibrate_metric(spec, rows):
    """One contradiction disables screening; declared owner evidence is not authentication."""
    spec, rows = _snapshot(spec), _snapshot(rows)
    _keys(spec, ('schema', 'id', 'kind', 'source', 'threshold', 'direction', 'frozen_at', 'holdout_revealed_at', 'development_groups', 'cohort', 'owner_declaration', 'spec_sha256'), ('rubric_sha256', 'scope'))
    if 'rubric_sha256' in spec: _hash(spec['rubric_sha256'])
    scope = spec.get('scope')
    if scope is not None:
        _keys(scope, ('suite_sha256', 'route_ids', 'families', 'implementation_sha256', 'preprocessing_sha256', 'model_sha256', 'method'))
        for field in ('suite_sha256', 'implementation_sha256', 'preprocessing_sha256'): _hash(scope[field])
        _need(isinstance(scope['route_ids'], list) and scope['route_ids'] and isinstance(scope['families'], list) and scope['families'], 'Calibration scope cannot be empty')
        for route in scope['route_ids']: _id(route)
        _unique(scope['route_ids'], 'calibration route scope'); _unique(scope['families'], 'calibration family scope')
        _need(all(family in FAMILIES for family in scope['families']), 'Unknown calibration family scope')
        _need(scope['method'] in ('human_rubric', 'automated_metric'), 'Declare calibration method')
        if scope['method'] == 'human_rubric':
            _need(spec['kind'] == 'subjective_rubric' and scope['model_sha256'] is None, 'Manual rubric declares no automated model')
        else: _hash(scope['model_sha256'])
    _need(spec['schema'] == 'studio.metric-calibration/v1', 'Unknown calibration schema'); _id(spec['id'])
    _need(spec['kind'] in ('subjective_rubric', 'geometry', 'palette', 'protection'), 'Unknown metric kind')
    _need(spec['source'] in ('synthetic', 'owner_library'), 'Unknown calibration source')
    _number(spec['threshold'], -1e12, 1e12); _need(spec['direction'] in ('higher', 'lower'), 'Unknown metric direction')
    _hash(spec['spec_sha256'])
    _need(spec['spec_sha256'] == canonical_hash({k: v for k, v in spec.items() if k != 'spec_sha256'}), 'Frozen metric specification changed')
    frozen, revealed = _time(spec['frozen_at']), _time(spec['holdout_revealed_at']); _need(frozen < revealed, 'Freeze before holdout reveal')
    development = spec['development_groups']; _need(isinstance(development, list), 'Declare development source groups')
    for group in development: _id(group)
    _unique(development, 'development groups')
    cohort = spec['cohort']; _need(isinstance(cohort, list) and len(cohort) <= 4096, 'Invalid calibration cohort')
    marks, bytes_seen, groups, owners, label_counts, exclusions = {}, {}, {}, set(), Counter(), Counter()
    scope_coverage = Counter()
    mapping = {'keep': 'keep', 'selected': 'keep', 'not_this': 'not_this', 'rejected': 'not_this', 'needs_work': None, 'unreviewed': None}
    for mark in cohort:
        _keys(mark, ('asset_id', 'output_sha256', 'source_group', 'split', 'owner_mark', 'owner_id', 'label_source'), ('route_id', 'family'))
        if 'route_id' in mark or 'family' in mark:
            _id(mark.get('route_id')); _need(mark.get('family') in FAMILIES, 'Incomplete or unknown calibration case scope')
            if scope is not None: _need(mark['route_id'] in scope['route_ids'] and mark['family'] in scope['families'], 'Owner mark lies outside frozen route/family scope')
        identifier = _id(mark['asset_id']); _hash(mark['output_sha256']); group = _id(mark['source_group']); _id(mark['owner_id'])
        _need(identifier not in marks, 'Duplicate or contradictory owner mark')
        _need(mark['output_sha256'] not in bytes_seen, 'Duplicate bytes cannot create independent labels')
        _need(mark['split'] in ('train', 'tune', 'holdout'), 'Unknown calibration split')
        _need(mark['owner_mark'] in mapping, 'Unknown existing Library mark')
        _need(mark['label_source'] == spec['source'], 'Reviewer/synthetic mark cannot masquerade as owner evidence')
        _need(group not in groups or groups[group] == mark['split'], 'Source lineage leaks between train/tune/holdout')
        _need(not (mark['split'] == 'holdout' and group in development), 'Development lineage leaks into holdout')
        marks[identifier] = mark; bytes_seen[mark['output_sha256']] = identifier; groups[group] = mark['split']; owners.add(mark['owner_id'])
        if mark['split'] == 'holdout':
            label = mapping[mark['owner_mark']]
            if label:
                label_counts[label] += 1
                if 'route_id' in mark: scope_coverage[(mark['route_id'], mark['family'], label)] += 1
            else: exclusions[mark['owner_mark']] += 1
    _need(len(owners) <= 1, 'Do not mix different owners')
    _need(isinstance(rows, list) and len(rows) <= 4096, 'Invalid metric rows')
    values, disagreements, false_passes, scored_labels, matches = {}, [], [], Counter(), 0
    for row in rows:
        _keys(row, ('asset_id', 'output_sha256', 'source_group', 'value', 'spec_sha256', 'scored_at'))
        identifier = _id(row['asset_id']); _need(identifier in marks and identifier not in values, 'Unknown or duplicate metric row')
        mark = marks[identifier]
        _need(row['output_sha256'] == mark['output_sha256'] and row['source_group'] == mark['source_group'], 'Metric row has stale bytes or lineage')
        _need(row['spec_sha256'] == spec['spec_sha256'], 'Metric row uses another frozen specification')
        value = _number(row['value'], -1e12, 1e12, nullable=True); stamp = _time(row['scored_at'])
        _need(frozen < stamp and (mark['split'] != 'holdout' or stamp < revealed), 'Scored before freeze or after reveal')
        values[identifier] = value; label = mapping[mark['owner_mark']]
        if label is None or value is None: continue
        if mark['split'] == 'holdout': scored_labels[label] += 1
        predicted = 'keep' if (value >= spec['threshold'] if spec['direction'] == 'higher' else value <= spec['threshold']) else 'not_this'
        if predicted == label:
            if mark['split'] == 'holdout': matches += 1
        else:
            disagreements.append(identifier)
            if predicted == 'keep': false_passes.append(identifier)
    expected = sum(label_counts.values()); scored = sum(scored_labels.values()); blockers = []
    if expected == 0: blockers.append('owner_labels_unavailable')
    if any(label_counts[label] < 2 for label in ('keep', 'not_this')): blockers.append('insufficient_both_label_coverage')
    if scored != expected: blockers.append('incomplete_holdout_predictions')
    if scope is None: blockers.append('calibration_scope_unavailable')
    elif any(scope_coverage[(route, family, label)] < 1 for route in scope['route_ids'] for family in scope['families'] for label in ('keep', 'not_this')):
        blockers.append('calibration_scope_coverage_incomplete')
    declaration = spec['owner_declaration']; owner_declared = False
    if declaration is not None:
        _keys(declaration, ('owner_id', 'snapshot_sha256', 'statement', 'statement_sha256', 'source_reference', 'kind', 'confirms_own_marks'))
        _text(declaration['statement']); _text(declaration['source_reference']); _hash(declaration['snapshot_sha256']); _hash(declaration['statement_sha256'])
        _need(declaration['snapshot_sha256'] == canonical_hash(cohort), 'Owner declaration names stale mark snapshot')
        _need(declaration['statement_sha256'] == hashlib.sha256(declaration['statement'].encode('utf-8')).hexdigest(), 'Owner statement bytes changed')
        owner_declared = (spec['source'] == 'owner_library' and declaration['kind'] == 'recorded_owner_statement'
                          and declaration['confirms_own_marks'] is True and owners == {declaration['owner_id']})
    if not owner_declared: blockers.append('owner_declaration_unavailable')
    if disagreements: blockers.append('metric_disagrees_with_owner_marks')
    if spec['source'] == 'synthetic': blockers.append('synthetic_evidence_only')
    if spec['kind'] != 'subjective_rubric': blockers.append('automatic_diagnostic_not_art_gate')
    elif spec.get('rubric_sha256') is None: blockers.append('rubric_identity_unavailable')
    if disagreements: status = 'disabled'
    elif scored != expected or not expected or any(label_counts[x] < 2 for x in ('keep', 'not_this')): status = 'blocked'
    elif spec['source'] == 'synthetic': status = 'synthetic_only'
    elif blockers: status = 'blocked'
    else: status = 'owner_concordant'
    return {'metric_id': spec['id'], 'status': status, 'expected': expected, 'scored': scored,
            'agreement': matches / expected if expected and scored == expected else None,
            'observed_agreement': matches / scored if scored else None, 'label_counts': dict(label_counts),
            'excluded_existing_marks': dict(exclusions), 'disagreements': len(disagreements), 'disagreement_ids': disagreements,
            'false_passes': len(false_passes), 'false_pass_ids': false_passes, 'blockers': sorted(set(blockers)),
            'gating_enabled': not blockers, 'rubric_sha256': spec.get('rubric_sha256'), 'calibration_scope': scope,
            'owner_declared': owner_declared, 'owner_authenticated': False,
            'human_review_required': True, 'art_acceptance': None, 'licence_clearance': None,
            'scope': 'Frozen cohort concordance only; local declaration is not authentication', 'inputs': {'spec': spec, 'rows': rows}}

def _cost(value):
    fields = ('attempts', 'retry_count', 'runtime_seconds', 'peak_vram_bytes', 'peak_ram_bytes', 'operator_seconds')
    _keys(value, fields)
    for field in fields:
        _number(value[field], 0, 2 ** 63 - 1, nullable=True, integer=field in ('attempts', 'retry_count', 'peak_vram_bytes', 'peak_ram_bytes'))
    if value['attempts'] is not None and value['retry_count'] is not None:
        _need(value['retry_count'] == max(0, value['attempts'] - 1), 'Retries must account for every additional attempt')
    return value

def score_case(case, receipt):
    """Score one expanded trial; human observations never imply owner acceptance."""
    case, receipt = _snapshot(case), _snapshot(receipt)
    identity_keys = ['suite_sha256', 'case_sha256', 'references_sha256', 'case_id', 'route_id', 'route_sha256', 'seed', 'rubric_sha256']
    _need(isinstance(case, dict) and all(k in case for k in (*identity_keys, 'id', 'case', 'minimum_score')), 'Expected an expanded planned trial')
    if 'route_inputs_sha256' in case: identity_keys.append('route_inputs_sha256')
    _need(canonical_hash({k: case[k] for k in identity_keys}) == case['id'], 'Trial identity changed')
    _need(canonical_hash(case['case']) == case['case_sha256'] and canonical_hash(case['case']['references']) == case['references_sha256'], 'Case or reference contract changed')
    actual_inputs = case['case'].get('route_inputs', {}).get(case['route_id'])
    if actual_inputs is not None:
        _need(case.get('route_inputs_sha256') == canonical_hash(actual_inputs), 'Actual route input bytes changed')
    _number(case['minimum_score'], 3, 4, integer=True)
    _need(case['rubric_sha256'] == rubric_fingerprint(case['minimum_score']), 'Rubric or threshold changed')
    _keys(receipt, ('trial_id', 'status', 'lineage', 'output_sha256', 'review', 'cost', 'reason'), ('automatic',))
    _need(receipt['trial_id'] == case['id'], 'Receipt belongs to another planned trial')
    _need(receipt['status'] in STATES, 'Unknown execution state'); _text(receipt['reason'])
    lineage = receipt['lineage']; _need(isinstance(lineage, dict), 'Expected lineage')
    for key in ('suite_sha256', 'case_sha256', 'references_sha256', 'route_sha256', 'seed', 'rubric_sha256'):
        _need(key in lineage and lineage[key] == case[key], 'Receipt source, seed or route lineage changed')
    if 'route_inputs_sha256' in case:
        _need(lineage.get('route_inputs_sha256') == case['route_inputs_sha256'], 'Actual input hash missing or stale')
    cost = _cost(receipt['cost']); completed = receipt['status'] == 'completed'
    if receipt['status'] == 'unsupported':
        _need(cost['attempts'] == 0 and cost['retry_count'] == 0, 'Unsupported cell cannot claim an attempt')
        _need(all(cost[field] in (None, 0) for field in ('runtime_seconds', 'peak_vram_bytes', 'peak_ram_bytes')), 'Unsupported cell cannot claim generation resources')
    _hash(receipt['output_sha256'], nullable=not completed)
    if completed:
        for key in ('graph_sha256', 'model_set_sha256', 'preprocessing_sha256', 'settings_sha256', 'environment_sha256'): _hash(lineage.get(key))
        _text(lineage.get('job_id'), 200); _text(lineage.get('prompt_id'), 200)
        _need(cost['attempts'] is None or cost['attempts'] >= 1, 'Completed output requires an attempt')
    else: _need(receipt['output_sha256'] is None and receipt['review'] is None, 'Incomplete execution cannot carry a completed output review')
    scores, minimum = None, {axis: None for axis in AXES}
    review_state, rubric_pass = 'needs_human_review' if completed else 'unavailable', None
    review = receipt['review']
    if review is not None:
        _keys(review, ('reviewer_id', 'reviewer_kind', 'reviewer_role', 'output_sha256', 'case_sha256', 'scores', 'notes'))
        _text(review['reviewer_id'], 200); _text(review['notes'])
        _need(review['reviewer_kind'] in ('human', 'agent'), 'Declare reviewer kind')
        _need(review['reviewer_role'] in ('owner', 'reviewer', 'agent'), 'Declare reviewer role')
        _need(not (review['reviewer_kind'] == 'agent' and review['reviewer_role'] == 'owner'), 'Agent cannot masquerade as owner')
        _need(not (review['reviewer_kind'] == 'human' and review['reviewer_role'] == 'agent'), 'Human reviewer kind contradicts explicit agent role')
        _need(not (review['reviewer_kind'] == 'human' and review['reviewer_id'] == 'local-agent'), 'Reviewer declaration contradicts actor')
        _need(review['output_sha256'] == receipt['output_sha256'] and review['case_sha256'] == case['case_sha256'], 'Review refers to stale output or criteria')
        scores = review['scores']; subjects = case['case']['subject_ids']
        _need(isinstance(scores, dict) and set(scores) <= set(subjects), 'Review contains another subject')
        complete = set(scores) == set(subjects)
        for subject_scores in scores.values():
            _need(isinstance(subject_scores, dict) and set(subject_scores) <= set(AXES), 'Unknown score axis')
            complete = complete and set(subject_scores) == set(AXES)
            for value in subject_scores.values():
                _number(value, 0, 4, nullable=True, integer=True)
                if value is None: complete = False
        for axis in AXES:
            values = [scores.get(subject, {}).get(axis) for subject in subjects]
            if all(value is not None for value in values): minimum[axis] = min(values)
        if complete and review['reviewer_kind'] == 'human':
            review_state = 'human_reviewed'; rubric_pass = all(value >= case['minimum_score'] for value in minimum.values())
    blockers = []
    if case['route_sha256'] is None: blockers.append('missing_route_pin')
    if any(ref['sha256'] is None for ref in case['case']['references']): blockers.append('missing_reference_bytes')
    if blockers: rubric_pass = None
    suggestions = {
        'identity': ('identity_drift', 'Re-anchor the named subject; propose a local identity repair and retain accepted outfit and pose regions.'),
        'outfit_detail': ('costume_detail_loss', 'Restore the missing named outfit/detail locally from the canonical reference.'),
        'pose_geometry': ('geometry', 'Inspect camera, crop and representation; compare a compatible skeleton/depth/edit route on paired seeds.'),
        'style': ('style_mismatch', 'Reduce conflicting style conditioning; compare scoped finishing while preserving accepted identity and outfit.'),
        'anatomy_contact': ('anatomy_contact', 'Inspect topology, occlusion and support; propose local hands/contact repair with human review.'),
        'composition': ('composition', 'Correct framing or subject placement against the declared composition/scene; preserve accepted subjects.'),
    }
    repairs = [{'axis': axis, 'failure': suggestions[axis][0], 'recommendation': suggestions[axis][1]}
               for axis, value in minimum.items() if value is not None and value < case['minimum_score']]
    return {'trial_id': case['id'], 'status': receipt['status'], 'review_state': review_state,
            'scores': scores, 'axis_minimum': minimum, 'rubric_pass': rubric_pass, 'blockers': blockers,
            'human_review_required': review_state == 'needs_human_review', 'owner_acceptance': None,
            'licence_clearance': None, 'cost': cost, 'repairs': repairs,
            'repair_policy': {'preserve_accepted_regions': True, 'new_candidate_required': True,
                              'parent_output_sha256': receipt['output_sha256'], 'execution_authorized': False},
            'automatic': automatic_metrics(receipt.get('automatic', {})), 'reviewer_authentication': 'local_declaration_only'}

def summarize(cases, receipts, calibration=None):
    """Recompute from the full suite; unsupported or omitted cells stay in denominators."""
    plan = validate_suite(cases); receipts = _snapshot(receipts)
    _need(isinstance(receipts, list) and len(receipts) <= len(plan['trials']), 'Invalid or oversized receipt set')
    trials = {t['id']: t for t in plan['trials']}; scored = {}; output_hashes = set()
    for receipt in receipts:
        _need(isinstance(receipt, dict), 'Expected a receipt object')
        key = receipt.get('trial_id'); _need(key in trials and key not in scored, 'Unknown or duplicate trial receipt')
        scored[key] = score_case(trials[key], receipt)
        if receipt['status'] == 'completed':
            _need(receipt['output_sha256'] not in output_hashes, 'Duplicate completed output bytes cannot fill distinct trials')
            output_hashes.add(receipt['output_sha256'])
    blockers = list(plan['blockers']); metric = None
    if calibration is not None:
        _need(isinstance(calibration, dict), 'Expected a calibration report')
        inputs = calibration.get('inputs')
        if isinstance(inputs, dict) and set(inputs) == {'spec', 'rows'}: metric = calibrate_metric(inputs['spec'], inputs['rows'])
        else: blockers.append('calibration_not_recomputed')
    if metric is None or not metric['gating_enabled']: blockers.append('owner_calibration_unavailable_or_disabled')
    if metric is not None and metric.get('rubric_sha256') != rubric_fingerprint(plan['suite']['minimum_score']): blockers.append('calibration_rubric_scope_mismatch')
    if metric is not None:
        scope = metric.get('calibration_scope')
        if not scope or scope['suite_sha256'] != plan['suite_sha256'] or set(scope['route_ids']) != set(plan['suite']['routes']) or set(scope['families']) != set(FAMILIES):
            blockers.append('calibration_route_family_scope_mismatch')
    if plan['suite']['evidence_mode'] in ('planned', 'synthetic'): blockers.append('no_representative_artwork_evidence')
    def group(items):
        counts = Counter(); passes = reviews = first_pass = 0; axes = {axis: [] for axis in AXES}
        for trial in items:
            result = scored.get(trial['id']); counts[result['status'] if result else 'missing'] += 1
            if not result: continue
            reviews += result['review_state'] == 'human_reviewed'; passes += result['rubric_pass'] is True
            first_pass += result['rubric_pass'] is True and result['cost']['retry_count'] == 0 and result['cost']['attempts'] == 1
            for axis, value in result['axis_minimum'].items():
                if value is not None and result['review_state'] == 'human_reviewed': axes[axis].append(value)
        size = len(items)
        return {'planned': size, 'status_counts': {name: counts[name] for name in (*STATES, 'missing')},
                'human_reviewed': reviews, 'rubric_passed': passes, 'rubric_pass_rate_lower_bound': passes / size if size else None,
                'first_pass_rubric_rate_lower_bound': first_pass / size if size else None,
                'axis_scores': {axis: {'observed': len(values), 'minimum': min(values) if values else None,
                                      'mean': sum(values) / len(values) if values else None} for axis, values in axes.items()},
                'all_planned_trials_pass': bool(size) and passes == size}
    overall = group(plan['trials']); routes = {}
    for route in plan['suite']['routes']:
        selected = [t for t in plan['trials'] if t['route_id'] == route]; item = group(selected)
        item['families'] = {family: group([t for t in selected if t['case']['family'] == family]) for family in FAMILIES}
        item['resource_evidence_complete'] = all(trial['id'] in scored and all(value is not None for value in scored[trial['id']]['cost'].values()) for trial in selected)
        item['qualification_complete'] = not blockers and item['resource_evidence_complete'] and all(v['all_planned_trials_pass'] for v in item['families'].values())
        routes[route] = item
    cost = {}
    for field in ('attempts', 'retry_count', 'runtime_seconds', 'operator_seconds'):
        values = [r['cost'][field] for r in scored.values() if r['cost'][field] is not None]
        cost[field + '_observed'] = sum(values) if values else None
        cost[field + '_total'] = sum(values) if len(values) == overall['planned'] else None
        cost[field + '_measured_trials'] = len(values)
    for field in ('peak_vram_bytes', 'peak_ram_bytes'):
        values = [r['cost'][field] for r in scored.values() if r['cost'][field] is not None]
        cost[field + '_observed_max'] = max(values) if values else None; cost[field + '_measured_trials'] = len(values)
    if len(scored) < len(trials): blockers.append('planned_trials_missing')
    if any(any(value is None for value in result['cost'].values()) for result in scored.values()): blockers.append('resource_or_intervention_evidence_incomplete')
    if not overall['all_planned_trials_pass']: blockers.append('human_rubric_incomplete_or_failed')
    return {**overall, 'suite_sha256': plan['suite_sha256'], 'routes': routes, 'cost': cost,
            'calibration': metric, 'blockers': sorted(set(blockers)), 'qualification_complete': not blockers,
            'owner_acceptance': None, 'licence_clearance': None, 'generation_submitted_by_evaluator': False,
            'scope': 'Paired case/seed evidence; unsupported, failed, cancelled, uncertain and missing trials stay visible'}

def automatic_metrics(observation):
    """Calculate supplied geometry/color/pixel observations; never semantic art approval."""
    observation = _snapshot(observation); _keys(observation, (), ('pose', 'silhouette', 'palette', 'protected_pixels'))
    result = {key: None for key in ('pose', 'silhouette', 'palette', 'protected_pixels')}
    if 'pose' in observation:
        pose = observation['pose']; _keys(pose, ('bbox', 'normalization', 'alignment', 'threshold', 'min_confidence', 'min_visible', 'joints'))
        box = pose['bbox']; _need(isinstance(box, list) and len(box) == 4, 'Declare reference bounding box')
        for value in box: _number(value, -1e9, 1e9)
        _need(box[2] > box[0] and box[3] > box[1], 'Reference box needs positive area')
        _need(pose['normalization'] == 'bbox_diagonal' and pose['alignment'] == 'none', 'PCK uses reference bbox and no fitted alignment')
        threshold = _number(pose['threshold'], 1e-9, 1); confidence = _number(pose['min_confidence'], 0.5, 1)
        minimum = _number(pose['min_visible'], 2, 256, integer=True)
        joints = pose['joints']; _need(isinstance(joints, list) and len(joints) <= 256, 'Invalid joints')
        visible = usable = correct = 0; seen = set(); diagonal = math.hypot(box[2] - box[0], box[3] - box[1])
        for joint in joints:
            _keys(joint, ('id', 'expected', 'actual', 'visible', 'confidence'))
            _id(joint['id']); _need(joint['id'] not in seen, 'Duplicate joint'); seen.add(joint['id'])
            _need(type(joint['visible']) is bool, 'Visibility must be explicit')
            for key in ('expected', 'actual'):
                point = joint[key]
                if point is None and key == 'actual': continue
                _need(isinstance(point, list) and len(point) == 2, 'Joint coordinates need x/y')
                for value in point: _number(value, -1e9, 1e9)
            _need(box[0] <= joint['expected'][0] <= box[2] and box[1] <= joint['expected'][1] <= box[3], 'Expected joint outside bbox')
            quality = _number(joint['confidence'], 0, 1)
            if not joint['visible']: continue
            visible += 1
            if joint['actual'] is None or quality < confidence: continue
            usable += 1; correct += math.dist(joint['expected'], joint['actual']) / diagonal <= threshold
        result['pose'] = {'pck': correct / visible if visible >= minimum and usable == visible else None,
                          'declared_visible': visible, 'usable': usable, 'correct': correct, 'normalization': 'declared_bbox_diagonal',
                          'uncertain': usable != visible or visible < minimum}
    if 'silhouette' in observation:
        item = observation['silhouette']; _keys(item, ('reference', 'candidate', 'confidence'))
        quality = _number(item['confidence'], 0, 1); reference, candidate = item['reference'], item['candidate']
        _need(isinstance(reference, list) and isinstance(candidate, list) and len(reference) == len(candidate) and reference, 'Silhouettes need matching nonempty grids')
        _need(all(type(x) is int and x in (0, 1) for x in reference + candidate), 'Silhouettes must be binary')
        intersection = sum(a == b == 1 for a, b in zip(reference, candidate)); union = sum(bool(a or b) for a, b in zip(reference, candidate))
        result['silhouette'] = {'iou': intersection / union if union and quality >= 0.5 else None, 'intersection': intersection, 'union': union}
    if 'palette' in observation:
        item = observation['palette']; _keys(item, ('reference_lab', 'candidate_lab', 'confidence'))
        quality = _number(item['confidence'], 0, 1)
        for key in ('reference_lab', 'candidate_lab'):
            values = item[key]; _need(isinstance(values, list) and len(values) == 3, 'Supply declared CIE Lab triples')
            _number(values[0], 0, 100); _number(values[1], -128, 128); _number(values[2], -128, 128)
        result['palette'] = {'delta_e76': math.dist(item['reference_lab'], item['candidate_lab']) if quality >= 0.5 else None,
                             'scope': 'Provided Lab values only; no image extraction or perceptual quality claim'}
    if 'protected_pixels' in observation:
        item = observation['protected_pixels']; _keys(item, ('source_size', 'candidate_size', 'alignment', 'pixel_format', 'color_space', 'mask', 'source_pixels', 'candidate_pixels'))
        size = item['source_size']; _need(isinstance(size, list) and len(size) == 2, 'Declare source canvas')
        for value in size: _number(value, 1, 8192, integer=True)
        _need(item['candidate_size'] == size and item['alignment'] == 'same_canvas', 'Protection requires same canvas, no resizing/alignment')
        _need(item['pixel_format'] == 'RGBA8' and item['color_space'] == 'sRGB', 'Protection requires matching sRGB RGBA8 pixels')
        length = size[0] * size[1]
        for key in ('mask', 'source_pixels', 'candidate_pixels'): _need(isinstance(item[key], list) and len(item[key]) == length, 'Pixels and mask must match canvas')
        _need(all(type(x) is int and x in (0, 1) for x in item['mask']), 'Protection mask must be binary')
        for pixel in item['source_pixels'] + item['candidate_pixels']:
            _need(isinstance(pixel, list) and len(pixel) == 4, 'RGBA8 pixel needs four channels')
            for channel in pixel: _number(channel, 0, 255, integer=True)
        protected = sum(item['mask']); changed = sum(bool(m) and a != b for m, a, b in zip(item['mask'], item['source_pixels'], item['candidate_pixels']))
        result['protected_pixels'] = {'protected': protected, 'changed': changed, 'unchanged': changed == 0 if protected else None,
                                      'scope': 'Exact supplied pixels only; semantic preservation needs review'}
    return {**result, 'diagnostics_only': True, 'human_review_required': True, 'art_acceptance': None, 'licence_clearance': None}
