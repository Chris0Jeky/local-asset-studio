"""Deterministic, zero-authority planning for the corrected-pose screening campaign."""
import copy
import hashlib
import json
import re

MANIFEST_SCHEMA = 'studio.pose-screening-manifest/v1'
PLAN_SCHEMA = 'studio.pose-screening-plan/v1'
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
_COMMON_PINS = frozenset({
    'model', 'encoder', 'vae', 'graph', 'nodes', 'runtime',
    'reference_transform', 'prompt_dialect',
})
_ROUTE_SPECS = (
    ('klein-geometry-reference', 'skeleton', 'route-native', frozenset({'renderer'})),
    ('copy-pose-rgb', 'rgb-pose-donor', 'not-applicable', frozenset({'lora'})),
    ('sdxl-precomputed-skeleton', 'precomputed-skeleton',
     'bypass-precomputed-guide', frozenset({'controlnet', 'renderer'})),
)
_CASE_SPECS = (
    ('familiar-difficult-bend', 'development', 'replicated-seeds'),
    ('unseen-crossed-legs', 'held-out', 'replicated-seeds'),
    ('seated-support', 'held-out', 'replicated-seeds'),
    ('overhead-reach', 'held-out', 'replicated-seeds'),
    ('strong-camera-foreshortening', 'held-out', 'replicated-seeds'),
    ('hand-prop-contact', 'held-out', 'replicated-seeds'),
    ('second-character-unseen-pose', 'held-out', 'replicated-seeds'),
    ('irrelevant-donor-counterfactual', 'held-out', 'paired-counterfactual'),
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
    mechanism, representation, detector, special_pins = expected
    if (value['mechanism'] != mechanism or
            value['input_representation'] != representation or
            value['detector_behavior'] != detector):
        raise ValueError('route mechanism, representation and detector behavior disagree')
    route_id = _id(value['id'], 'route id')
    backend_id = _id(value['backend_id'], 'backend id')
    required_pins = _COMMON_PINS | special_pins
    _keys(value['pins'], required_pins)
    pins = {key: _hash(value['pins'][key]) for key in sorted(required_pins)}
    _keys(value['noise_seeds'], ('replicate_a', 'replicate_b', 'counterfactual'))
    seeds = {key: _integer(value['noise_seeds'][key], 0, 2 ** 63 - 1, 'noise seed')
             for key in ('replicate_a', 'replicate_b', 'counterfactual')}
    if len(set(seeds.values())) != 3:
        raise ValueError('route-local replicate and counterfactual seeds must be distinct')
    return {
        'id': route_id,
        'mechanism': mechanism,
        'input_representation': representation,
        'backend_id': backend_id,
        'detector_behavior': detector,
        'pins': pins,
        'noise_seeds': seeds,
    }


def _case(value, ordinal, expected):
    case_id, scope, slot_mode = expected
    common = ('id', 'ordinal', 'title', 'scope', 'slot_mode', 'source_ref',
              'required_observations')
    _keys(value, common, ('pair_labels',))
    if (_id(value['id'], 'case id') != case_id or
            _integer(value['ordinal'], 1, 8, 'case ordinal') != ordinal or
            value['scope'] != scope or value['slot_mode'] != slot_mode):
        raise ValueError('case identity, order, scope or slot protocol changed')
    source_ref = _id(value['source_ref'], 'source reference')
    observations = value['required_observations']
    if (not isinstance(observations, list) or not observations or
            len(observations) > len(REVIEW_AXES) or
            any(not isinstance(item, str) or item not in REVIEW_AXES for item in observations) or
            len(set(observations)) != len(observations)):
        raise ValueError('required observations must be unique review axes')
    result = {
        'id': case_id,
        'ordinal': ordinal,
        'title': _title(value['title']),
        'scope': scope,
        'slot_mode': slot_mode,
        'source_ref': source_ref,
        'required_observations': list(observations),
    }
    if slot_mode == 'paired-counterfactual':
        if value.get('pair_labels') != ['baseline', 'variant']:
            raise ValueError('counterfactual case requires baseline and variant labels')
        result['pair_labels'] = ['baseline', 'variant']
    elif 'pair_labels' in value:
        raise ValueError('only the counterfactual case may declare pair labels')
    return result


def validate_manifest(manifest):
    """Return a canonical campaign manifest without granting execution authority."""
    _keys(manifest, (
        'schema', 'authority', 'execution_authorized', 'generation_submitted',
        'campaign_id', 'candidate_cap', 'additional_image_attempt_cap',
        'same_defect_repeat_limit', 'routes', 'cases', 'review_axes',
        'stop_conditions',
    ))
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
    routes = [_route(value, expected)
              for value, expected in zip(manifest['routes'], _ROUTE_SPECS)]
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


def _cell_id(manifest_sha256, case_id, route_id, slot, seed):
    return hashlib.sha256(canonical({
        'manifest_sha256': manifest_sha256,
        'case_id': case_id,
        'route_id': route_id,
        'slot': slot,
        'seed': seed,
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
                    ('replicate-a', route['noise_seeds']['replicate_a'], None),
                    ('replicate-b', route['noise_seeds']['replicate_b'], None),
                )
            else:
                pair_group = hashlib.sha256(canonical({
                    'manifest_sha256': manifest_sha256,
                    'case_id': case['id'],
                    'route_id': route['id'],
                    'kind': 'paired-counterfactual',
                })).hexdigest()
                seed = route['noise_seeds']['counterfactual']
                slots = (('baseline', seed, pair_group), ('variant', seed, pair_group))
            for slot, seed, pair_group in slots:
                cells.append({
                    'id': _cell_id(manifest_sha256, case['id'], route['id'], slot, seed),
                    'case_id': case['id'],
                    'case_ordinal': case['ordinal'],
                    'case_scope': case['scope'],
                    'source_ref': case['source_ref'],
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
