"""Deterministic, zero-authority planning for the corrected-pose screening campaign."""
import copy
import hashlib
import json
import re

from . import pose_route_contract

MANIFEST_SCHEMA = 'studio.pose-screening-manifest/v2'
PLAN_SCHEMA = 'studio.pose-screening-plan/v2'
LEGACY_MANIFEST_SCHEMA = 'studio.pose-screening-manifest/v1'
REVIEW_AXES = (
    'hard_constraints', 'body_pose', 'camera', 'identity', 'outfit', 'style',
    'hands_contact_support', 'anatomy_occlusion', 'ignored_facet_leakage',
    'owner_acceptance',
)
STOP_CONDITIONS = (
    'uncertain_dispatch', 'invalid_binding', 'runtime_instability',
    'candidate_cap_exhausted',
)

_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z')
_COMMON_PINS = pose_route_contract.COMMON_PINS
_CASE_SPECS = (
    ('familiar-difficult-bend', 'development', 'replicated-seeds',
     ('body_pose', 'camera')),
    ('unseen-crossed-legs', 'held-out', 'replicated-seeds',
     ('body_pose', 'anatomy_occlusion')),
    ('seated-support', 'held-out', 'replicated-seeds',
     ('body_pose', 'hands_contact_support')),
    ('overhead-reach', 'held-out', 'replicated-seeds',
     ('body_pose', 'anatomy_occlusion')),
    ('strong-camera-foreshortening', 'held-out', 'replicated-seeds',
     ('body_pose', 'camera')),
    ('hand-prop-contact', 'held-out', 'replicated-seeds',
     ('body_pose', 'hands_contact_support')),
    ('second-character-unseen-pose', 'held-out', 'replicated-seeds',
     ('body_pose', 'identity', 'outfit')),
    ('irrelevant-donor-counterfactual', 'held-out', 'paired-counterfactual',
     ('body_pose', 'ignored_facet_leakage')),
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def _keys(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError('expected an object')
    required = set(required); allowed = required | set(optional)
    missing, extra = required - set(value), set(value) - allowed
    if missing or extra:
        raise ValueError('missing or unsupported fields')


def _id(value, label='identifier'):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(label + ' must be a lowercase bounded identifier')
    return value


def _hash(value):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError('expected lowercase SHA-256')
    return value


def _integer(value, low, high, label='integer'):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ' is outside its declared integer range')
    return value


def _title(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 200 or
            any(ord(char) < 32 for char in value)):
        raise ValueError('case title must be nonempty printable text of at most 200 characters')
    return value


def _route(value, expected):
    _keys(value, ('id', 'mechanism', 'input_representation', 'backend_id',
                  'detector_behavior', 'pins', 'noise_seeds'))
    route_id = _id(value['id'], 'route id')
    if (route_id != expected['id'] or value['mechanism'] != expected['mechanism'] or
            value['input_representation'] != expected['input_representation'] or
            value['detector_behavior'] != expected['detector_behavior']):
        raise ValueError('route identity, mechanism, representation and detector behavior disagree')
    backend_id = pose_route_contract.validate_backend(route_id, value['backend_id'])
    required_pins = _COMMON_PINS | expected['pins']
    _keys(value['pins'], required_pins)
    pins = {key: _hash(value['pins'][key]) for key in sorted(required_pins)}
    _keys(value['noise_seeds'], ('replicate_a', 'replicate_b', 'counterfactual'))
    seeds = {key: _integer(value['noise_seeds'][key], 0, 2 ** 63 - 1, 'noise seed')
             for key in ('replicate_a', 'replicate_b', 'counterfactual')}
    if len(set(seeds.values())) != 3:
        raise ValueError('route-local replicate and counterfactual seeds must be distinct')
    return {
        'id': route_id,
        'mechanism': expected['mechanism'],
        'input_representation': expected['input_representation'],
        'backend_id': backend_id,
        'detector_behavior': expected['detector_behavior'],
        'pins': pins,
        'noise_seeds': seeds,
    }


def _case(value, ordinal, expected):
    case_id, scope, slot_mode, expected_observations = expected
    common = ('id', 'ordinal', 'title', 'scope', 'slot_mode',
              'required_observations')
    if slot_mode == 'paired-counterfactual':
        _keys(value, common + ('pair_labels', 'source_refs'))
    else:
        _keys(value, common + ('source_ref',))
    if (_id(value['id'], 'case id') != case_id or
            _integer(value['ordinal'], 1, 8, 'case ordinal') != ordinal or
            value['scope'] != scope or value['slot_mode'] != slot_mode):
        raise ValueError('case identity, order, scope or slot protocol changed')
    observations = value['required_observations']
    if (not isinstance(observations, list) or
            observations != list(expected_observations)):
        raise ValueError('case-specific required observations changed')
    result = {
        'id': case_id,
        'ordinal': ordinal,
        'title': _title(value['title']),
        'scope': scope,
        'slot_mode': slot_mode,
        'required_observations': list(observations),
    }
    if slot_mode == 'paired-counterfactual':
        if value['pair_labels'] != ['baseline', 'variant']:
            raise ValueError('counterfactual case requires baseline and variant labels')
        _keys(value['source_refs'], ('baseline', 'variant'))
        source_refs = {
            label: _id(value['source_refs'][label], label + ' source reference')
            for label in ('baseline', 'variant')
        }
        if source_refs['baseline'] == source_refs['variant']:
            raise ValueError('counterfactual baseline and variant sources must be distinct')
        result['pair_labels'] = ['baseline', 'variant']
        result['source_refs'] = source_refs
    else:
        result['source_ref'] = _id(value['source_ref'], 'source reference')
    return result


def validate_manifest(manifest):
    """Return a canonical campaign manifest without granting execution authority."""
    _keys(manifest, (
        'schema', 'authority', 'execution_authorized', 'generation_submitted',
        'campaign_id', 'candidate_cap', 'additional_image_attempt_cap',
        'same_defect_repeat_limit', 'routes', 'cases', 'review_axes',
        'stop_conditions',
    ))
    if manifest['schema'] == LEGACY_MANIFEST_SCHEMA:
        raise ValueError('pose screening manifest v1 used contradictory Klein route vocabulary; regenerate it as v2')
    if (manifest['schema'] != MANIFEST_SCHEMA or manifest['authority'] != 'none' or
            manifest['execution_authorized'] is not False or
            manifest['generation_submitted'] is not False):
        raise ValueError('screening manifests have zero execution authority')
    if (_integer(manifest['candidate_cap'], 48, 48, 'candidate cap') != 48 or
            _integer(manifest['additional_image_attempt_cap'], 0, 0,
                     'additional attempt cap') != 0 or
            _integer(manifest['same_defect_repeat_limit'], 2, 2,
                     'same-defect repeat limit') != 2):
        raise ValueError('screening budget or repeat policy changed')
    if manifest['review_axes'] != list(REVIEW_AXES):
        raise ValueError('review axes changed')
    if manifest['stop_conditions'] != list(STOP_CONDITIONS):
        raise ValueError('stop conditions changed')
    if not isinstance(manifest['routes'], list) or len(manifest['routes']) != 3:
        raise ValueError('exactly three frozen routes are required')
    routes = [
        _route(value, pose_route_contract.screening_projection(route_id))
        for value, route_id in zip(manifest['routes'], pose_route_contract.ROUTE_IDS)
    ]
    if len({route['id'] for route in routes}) != len(routes):
        raise ValueError('route ids must be unique')
    if not isinstance(manifest['cases'], list) or len(manifest['cases']) != 8:
        raise ValueError('exactly eight screening cases are required')
    cases = [_case(value, ordinal, expected)
             for ordinal, (value, expected) in enumerate(
                 zip(manifest['cases'], _CASE_SPECS), 1)]
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('case ids must be unique')
    return {
        'schema': MANIFEST_SCHEMA,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'campaign_id': _id(manifest['campaign_id'], 'campaign id'),
        'candidate_cap': 48,
        'additional_image_attempt_cap': 0,
        'same_defect_repeat_limit': 2,
        'routes': routes,
        'cases': cases,
        'review_axes': list(REVIEW_AXES),
        'stop_conditions': list(STOP_CONDITIONS),
    }


def _cell_id(manifest_sha256, case_id, route_id, slot, seed, source_ref):
    return hashlib.sha256(canonical({
        'manifest_sha256': manifest_sha256,
        'case_id': case_id,
        'route_id': route_id,
        'slot': slot,
        'seed': seed,
        'source_ref': source_ref,
    })).hexdigest()


def compile_plan(manifest):
    """Enumerate the fixed 48 first-pass cells; never reserve or submit work."""
    source = validate_manifest(manifest)
    manifest_sha256 = hashlib.sha256(canonical(source)).hexdigest()
    cells = []
    for route in source['routes']:
        for case in source['cases']:
            if case['slot_mode'] == 'replicated-seeds':
                slots = (
                    ('replicate-a', route['noise_seeds']['replicate_a'],
                     None, case['source_ref']),
                    ('replicate-b', route['noise_seeds']['replicate_b'],
                     None, case['source_ref']),
                )
            else:
                pair_group = hashlib.sha256(canonical({
                    'manifest_sha256': manifest_sha256,
                    'case_id': case['id'],
                    'route_id': route['id'],
                    'kind': 'paired-counterfactual',
                })).hexdigest()
                seed = route['noise_seeds']['counterfactual']
                slots = (
                    ('baseline', seed, pair_group, case['source_refs']['baseline']),
                    ('variant', seed, pair_group, case['source_refs']['variant']),
                )
            for slot, seed, pair_group, source_ref in slots:
                cells.append({
                    'id': _cell_id(manifest_sha256, case['id'], route['id'],
                                   slot, seed, source_ref),
                    'case_id': case['id'],
                    'case_ordinal': case['ordinal'],
                    'case_scope': case['scope'],
                    'source_ref': source_ref,
                    'route_id': route['id'],
                    'mechanism': route['mechanism'],
                    'input_representation': route['input_representation'],
                    'slot': slot,
                    'seed': seed,
                    'pair_group': pair_group,
                    'attempt_kind': 'first-pass',
                    'execution_authorized': False,
                    'generation_submitted': False,
                })
    if len(cells) != 48:
        raise ValueError('compiled candidate count does not match the frozen cap')
    body = {
        'schema': PLAN_SCHEMA,
        'campaign_id': source['campaign_id'],
        'manifest_sha256': manifest_sha256,
        'authority': 'none',
        'execution_authorized': False,
        'generation_submitted': False,
        'candidate_cap': 48,
        'candidate_count': len(cells),
        'additional_image_attempt_cap': 0,
        'same_defect_repeat_limit': 2,
        'route_order': [route['id'] for route in source['routes']],
        'case_order': [case['id'] for case in source['cases']],
        'review_axes': list(REVIEW_AXES),
        'stop_conditions': list(STOP_CONDITIONS),
        'cells': cells,
    }
    result = copy.deepcopy(body)
    result['plan_id'] = hashlib.sha256(canonical(body)).hexdigest()
    return result


def validate_plan(plan, manifest):
    """Refuse any plan that differs from a fresh deterministic compilation."""
    expected = compile_plan(manifest)
    if not isinstance(plan, dict) or plan != expected:
        raise ValueError('plan does not match the canonical screening manifest')
    return copy.deepcopy(expected)
