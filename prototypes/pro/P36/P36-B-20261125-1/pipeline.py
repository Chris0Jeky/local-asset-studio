"""Offline, content-bound character family receipts. No network or generation calls.

Digests detect changed content; they are not signatures and cannot authenticate a
human decision. The caller supplies the trusted family and records explicit reviews.
This prototype does not replace the Studio Workspace or its metadata authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys

SCHEMA = 'las.character-family/1'
STAGES = ('concept', 'turnaround', 'expressions', 'outfits', 'mesh', 'rig', 'toon', 'unreal')
PARENTS = {
    'concept': (), 'turnaround': ('concept',),
    'expressions': ('concept', 'turnaround'), 'outfits': ('concept', 'turnaround'),
    'mesh': ('concept', 'turnaround', 'expressions', 'outfits'),
    'rig': ('concept', 'mesh'), 'toon': ('concept', 'mesh', 'rig'),
    'unreal': ('concept', 'expressions', 'outfits', 'rig', 'toon'),
}
STATES = {'generation': {'planned', 'completed', 'uncertain', 'failed'},
          'inspection': {'unreviewed', 'inspected'},
          'acceptance': {'pending', 'accepted', 'rejected'},
          'licence': {'unknown', 'recorded', 'cleared', 'restricted'}}
HEX64 = re.compile(r'^[0-9a-f]{64}$')
ENTITY = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')
CHARACTER = re.compile(r'^[a-z][a-z0-9-]{1,31}$')
MAX_JSON = 2 * 1024 * 1024
MAX_RECEIPT = 256 * 1024
MAX_RECEIPTS = 128
RUN_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUN_DIR.parents[3]


class PipelineError(ValueError):
    def __init__(self, message, code='invalid_record'):
        super().__init__(message); self.code = code


def require(condition, message, code='invalid_record'):
    if not condition: raise PipelineError(message, code)


def _bounded(value):
    budget = 60000
    def visit(item, depth):
        nonlocal budget
        budget -= 1
        require(budget >= 0 and depth <= 24, 'JSON structure exceeds bounds')
        if type(item) is dict:
            require(len(item) <= 4096 and all(type(k) is str and len(k) <= 256 for k in item),
                    'Invalid or oversized JSON object')
            for child in item.values(): visit(child, depth + 1)
        elif type(item) is list:
            require(len(item) <= 4096, 'Oversized JSON array')
            for child in item: visit(child, depth + 1)
        elif type(item) is str: require(len(item) <= 65536, 'Oversized JSON string')
        elif type(item) is float: require(math.isfinite(item), 'Nonfinite JSON number')
        elif type(item) is int: require(item.bit_length() <= 128, 'Oversized JSON integer')
        else: require(item is None or type(item) is bool, 'Unsupported JSON value')
    visit(value, 0)


def canonical_bytes(value):
    _bounded(value)
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False) + '\n').encode('utf-8')
    require(len(raw) <= MAX_JSON, 'JSON document exceeds byte limit')
    return raw


def digest(value): return hashlib.sha256(canonical_bytes(value)).hexdigest()


def decode_json(raw):
    require(type(raw) in (str, bytes) and len(raw) <= MAX_JSON, 'JSON input exceeds byte limit')
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key: ' + key)
            out[key] = value
        return out
    def invalid(value): raise PipelineError('Nonfinite JSON number: ' + value)
    try: value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PipelineError('Invalid JSON: ' + str(exc)) from exc
    canonical_bytes(value)
    return value


def load_json(path):
    path = Path(path)
    require(path.is_file() and path.stat().st_size <= MAX_JSON, 'Missing or oversized JSON file')
    with path.open('rb') as handle: raw = handle.read(MAX_JSON + 1)
    return decode_json(raw)


def safe_relative(path):
    require(type(path) is str and 0 < len(path) <= 240 and '\\' not in path and ':' not in path,
            'Use a portable relative POSIX path')
    parts = path.split('/')
    require(not path.startswith('/') and all(x and x not in ('.', '..') for x in parts),
            'Path traversal or noncanonical path')
    require(not any(x.endswith((' ', '.')) or any(ord(c) < 32 for c in x) for x in parts),
            'Nonportable path component')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                *(f'LPT{i}' for i in range(1, 10))}
    require(not any(x.split('.')[0].upper() in reserved for x in parts), 'Windows reserved path')
    require(not any(PureWindowsPath(x).is_reserved() or x.upper() in ('CONIN$', 'CONOUT$') or
                    x.split('.')[0].upper() in ('CONIN$', 'CONOUT$') for x in parts), 'Windows reserved path')
    require(not any(any(c in '<>"|?*' for c in x) for x in parts), 'Nonportable path character')
    require(not any(x.lower() in ('_owner', 'owner-models') for x in parts), 'Private owner path refused')
    return PurePosixPath(path)


def linked(path): return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def contained_file(root, relative):
    safe_relative(relative)
    root = Path(root).absolute()
    require(not any(part.lower() in ('_owner', 'owner-models') for part in root.parts), 'Private owner root refused')
    require(not any(linked(p) for p in (root, *root.parents)), 'Linked asset root refused')
    path = root.joinpath(*relative.split('/'))
    require(not any(linked(p) for p in (path, *path.parents)), 'Linked asset path refused')
    require(path.resolve().is_relative_to(root.resolve()), 'File leaves asset root')
    require(path.is_file(), 'Missing asset bytes: ' + relative)
    return path


def verify_artifact(root, artifact):
    path = contained_file(root, artifact['path'])
    before = path.stat()
    require(before.st_size == artifact['bytes'], 'Asset byte count changed: ' + artifact['path'])
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''): h.update(chunk)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) ==
            (after.st_size, after.st_mtime_ns, after.st_ino), 'Asset changed during read')
    require(h.hexdigest() == artifact['sha256'], 'Asset digest changed: ' + artifact['path'])
    return path


def write_new_runtime(path, value):
    path = Path(path).absolute(); runtime = REPO_ROOT / '.runtime'
    require(path.resolve().is_relative_to(runtime.resolve()), 'Output must be under repository .runtime/')
    require(not any(linked(p) for p in (path, *path.parents)), 'Linked output path refused')
    raw = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: no overwrite/replay of an uncertain prior publication.
    try:
        with path.open('xb') as handle: handle.write(raw)
    except FileExistsError as exc:
        raise PipelineError('Output already exists; inspect it and choose a new destination', 'output_exists') from exc
    require(path.read_bytes() == raw, 'Unconfirmed output publication; inspect before retrying')
    return path


def validate_policy(policy):
    require(type(policy) is dict and policy.get('version') == 1, 'Unsupported identity policy')
    require(type(policy.get('features')) is dict and 0 < len(policy['features']) <= 64,
            'Policy requires bounded identity features')
    require(type(policy.get('required')) is dict and set(policy['required']) == set(STAGES),
            'Policy must define every stage')
    for stage, views in policy['required'].items():
        require(type(views) is dict and 0 < len(views) <= 24, 'Policy requires bounded views')
        for view, features in views.items():
            require(type(view) is str and ENTITY.fullmatch(view), 'Invalid policy view')
            require(type(features) is list and features and len(features) == len(set(features))
                    and all(x in policy['features'] for x in features), 'Invalid required identity features')
    for feature in policy['features'].values():
        require(type(feature) is dict and feature.get('kind') in ('rgb', 'ratio', 'trait'),
                'Unsupported feature kind')
        if feature['kind'] != 'trait':
            tolerance = feature.get('tolerance')
            require(type(tolerance) in (float, int) and math.isfinite(tolerance) and 0 < tolerance <= 1,
                    'Invalid identity tolerance')
    quality = policy.get('quality_required', {})
    require(type(quality) is dict and set(quality) <= set(STAGES), 'Invalid native quality policy')
    for checks in quality.values():
        require(type(checks) is list and len(checks) <= 32 and len(set(checks)) == len(checks)
                and all(type(x) is str and ENTITY.fullmatch(x) for x in checks), 'Invalid quality check names')
    canonical_bytes(policy)


def create_family(family_id, workspace_id, character_id, policy, *, mode='production'):
    require(type(family_id) is str and ENTITY.fullmatch(family_id), 'Invalid family ID')
    require(type(workspace_id) is str and re.fullmatch('[0-9a-f]{32}', workspace_id), 'Invalid Workspace ID')
    require(type(character_id) is str and CHARACTER.fullmatch(character_id), 'Invalid character ID')
    require(mode in ('production', 'synthetic'), 'Invalid family mode')
    validate_policy(policy)
    return {'schema': SCHEMA, 'family_id': family_id, 'workspace_id': workspace_id,
            'character_id': character_id, 'mode': mode, 'policy': copy.deepcopy(policy),
            'policy_sha256': digest(policy), 'receipts': {}, 'heads': {}}


def validate_family(family):
    require(type(family) is dict and family.get('schema') == SCHEMA, 'Unsupported family schema')
    canonical_bytes(family)
    base = create_family(family.get('family_id'), family.get('workspace_id'),
                         family.get('character_id'), family.get('policy'), mode=family.get('mode'))
    require(family.get('policy_sha256') == base['policy_sha256'], 'Frozen policy digest changed')
    require(type(family.get('receipts')) is dict and len(family['receipts']) <= MAX_RECEIPTS,
            'Receipt collection exceeds bound')
    require(type(family.get('heads')) is dict and set(family['heads']) <= set(STAGES), 'Invalid stage heads')
    for identifier, receipt in family['receipts'].items():
        validate_receipt(receipt); _scope(family, receipt)
        require(identifier == receipt['id'], 'Historical receipt digest mismatch')
    for stage, identifier in family['heads'].items():
        require(type(identifier) is str and identifier in family['receipts'], 'Missing active receipt')
        receipt = family['receipts'][identifier]
        validate_receipt(receipt)
        require(receipt['id'] == identifier and receipt['payload']['stage'] == stage, 'Mismatched active receipt')
        _scope(family, receipt)


def seal(receipt):
    out = copy.deepcopy(receipt); out.pop('id', None)
    require(len(canonical_bytes(out)) <= MAX_RECEIPT, 'Receipt exceeds byte limit')
    out['id'] = digest(out)
    return out


def subject(receipt): return digest(receipt['payload'])


def _scope(family, receipt):
    payload = receipt['payload']
    for key in ('family_id', 'workspace_id', 'character_id', 'mode', 'policy_sha256'):
        require(payload.get(key) == family[key], 'Receipt scope mismatch: ' + key)
    if family['mode'] == 'production':
        require(payload['recipe'].get('fixture') is not True and
                not payload['recipe']['route_id'].startswith(('fixture', 'synthetic')),
                'Explicit synthetic recipe cannot qualify production')
        for artifact in payload['artifacts']:
            require(not artifact.get('source', '').startswith('fixture:') and
                    not artifact['asset_id'].startswith('fixture-') and
                    not artifact['licence']['source'].startswith('fixture:'),
                    'Explicit synthetic artifact cannot qualify production')
        require(not any(check['evidence_ref'].startswith('fixture:') for check in payload['quality']),
                'Explicit synthetic quality evidence cannot qualify production')


def validate_receipt(receipt):
    require(type(receipt) is dict and type(receipt.get('id')) is str, 'Missing receipt identity')
    require(seal(receipt)['id'] == receipt['id'], 'Receipt digest mismatch')
    payload = receipt.get('payload')
    require(type(payload) is dict and payload.get('stage') in STAGES, 'Invalid receipt payload')
    stage = payload['stage']
    require(type(payload.get('parents')) is dict and set(payload['parents']) == set(PARENTS[stage])
            and all(type(v) is str and HEX64.fullmatch(v) for v in payload['parents'].values()),
            'Missing or invalid mandatory parents')
    require(payload.get('concept_id') is None if stage == 'concept' else
            payload.get('concept_id') == payload['parents'].get('concept'), 'Invalid concept anchor')
    artifacts = payload.get('artifacts')
    require(type(artifacts) is list and 0 < len(artifacts) <= 48, 'Receipt needs bounded artifacts')
    keys, paths = set(), set()
    for artifact in artifacts:
        require(type(artifact) is dict, 'Invalid artifact')
        key = artifact.get('key'); asset_id = artifact.get('asset_id')
        require(type(key) is str and re.fullmatch('[a-z0-9][a-z0-9_.-]*', key) and key not in keys,
                'Invalid or duplicate artifact key'); keys.add(key)
        require(type(asset_id) is str and ENTITY.fullmatch(asset_id), 'Invalid Workspace asset ID')
        safe_relative(artifact.get('path'))
        folded = artifact['path'].casefold()
        require(folded not in paths, 'Duplicate artifact path'); paths.add(folded)
        require(type(artifact.get('sha256')) is str and HEX64.fullmatch(artifact['sha256']), 'Invalid media digest')
        require(type(artifact.get('bytes')) is int and 0 < artifact['bytes'] <= 8 * 1024**3, 'Invalid media size')
        require(type(artifact.get('media_type')) is str and type(artifact.get('role')) is str, 'Missing media type/role')
        licence = artifact.get('licence')
        require(type(licence) is dict and all(type(licence.get(k)) is str and licence[k]
                for k in ('name', 'source', 'commercial')) and licence['commercial'] in ('yes', 'no', 'unknown'),
                'Separate artifact licence facts are required')
        if artifact['media_type'].startswith('image/'):
            dims = artifact.get('dimensions')
            require(type(dims) is list and len(dims) == 2 and all(type(d) is int and 0 < d <= 16384 for d in dims),
                    'Image dimensions required')
            require(artifact.get('colour_space') in ('srgb', 'linear-srgb') and
                    artifact.get('alpha') in ('opaque', 'straight', 'premultiplied'), 'Image colour/alpha required')
    recipe = payload.get('recipe')
    require(type(recipe) is dict and type(recipe.get('route_id')) is str and recipe['route_id']
            and type(recipe.get('controls')) is dict, 'Full route/controls recipe is required')
    refs = payload.get('references')
    require(type(refs) is list and len(refs) <= 32, 'Invalid reference list')
    for ref in refs:
        require(type(ref) is dict and type(ref.get('asset_id')) is str and ENTITY.fullmatch(ref['asset_id'])
                and type(ref.get('sha256')) is str and HEX64.fullmatch(ref['sha256'])
                and ref.get('role') in ('identity', 'pose', 'style', 'outfit', 'geometry', 'expression'),
                'Invalid role-bound reference')
    require(type(payload.get('identity')) is dict and type(payload.get('quality')) is list,
            'Missing identity/native evidence')
    require(len(payload['quality']) <= 32, 'Too many quality observations')
    quality_names = set()
    for check in payload['quality']:
        require(type(check) is dict and type(check.get('name')) is str and ENTITY.fullmatch(check['name'])
                and check['name'] not in quality_names and check.get('outcome') in ('pass', 'fail', 'unknown')
                and type(check.get('evidence_ref')) is str and check['evidence_ref'], 'Invalid native quality evidence')
        quality_names.add(check['name'])
    for dimension, allowed in STATES.items():
        evidence = receipt.get(dimension)
        require(type(evidence) is dict and evidence.get('state') in allowed, 'Invalid ' + dimension + ' state')
        if evidence['state'] not in ('planned', 'unreviewed', 'pending', 'unknown'):
            require(all(type(evidence.get(k)) is str and evidence[k]
                        for k in ('actor', 'evidence_ref', 'subject_sha256')), 'Incomplete ' + dimension + ' attestation')
            require(HEX64.fullmatch(evidence['subject_sha256']), 'Invalid attestation subject')
        if dimension == 'acceptance' and evidence['state'] == 'accepted':
            require(evidence['actor'] == 'owner', 'Only an explicit owner acceptance record is supported')
        if dimension == 'licence' and evidence['state'] == 'cleared':
            require(evidence['actor'] == 'owner' and type(evidence.get('intended_use')) is str
                    and evidence['intended_use'], 'Clearance needs an owner decision for a named use')


def prepare_receipt(family, stage, *, artifacts, recipe, references, identity, quality=None, asset_root=None):
    validate_family(family)
    require(stage in STAGES, 'Unsupported stage')
    gate = next_gate(family, stage, asset_root=asset_root)
    require(gate['passed'], 'Next stage blocked: ' + ', '.join(b['code'] for b in gate['blockers']), 'stage_blocked')
    payload = {key: family[key] for key in ('family_id', 'workspace_id', 'character_id', 'mode', 'policy_sha256')}
    payload.update(stage=stage, parents={s: family['heads'][s] for s in PARENTS[stage]},
                   concept_id=None if stage == 'concept' else family['heads']['concept'],
                   artifacts=copy.deepcopy(artifacts), recipe=copy.deepcopy(recipe),
                   references=copy.deepcopy(references), identity=copy.deepcopy(identity),
                   quality=copy.deepcopy(quality or []))
    result = seal({'payload': payload, 'generation': {'state': 'planned'},
                   'inspection': {'state': 'unreviewed'}, 'acceptance': {'state': 'pending'},
                   'licence': {'state': 'unknown'}})
    validate_receipt(result)
    return result


def attest(receipt, dimension, state, actor, evidence_ref, *, intended_use=None):
    require(dimension in STATES and state in STATES[dimension], 'Unsupported evidence decision')
    require(type(actor) is str and actor and type(evidence_ref) is str and evidence_ref,
            'Explicit actor and evidence reference required')
    out = copy.deepcopy(receipt)
    out[dimension] = {'state': state, 'actor': actor, 'evidence_ref': evidence_ref,
                      'subject_sha256': subject(receipt)}
    if intended_use is not None: out[dimension]['intended_use'] = intended_use
    out = seal(out); validate_receipt(out)
    return out


def record_receipt(family, receipt, *, asset_root=None):
    validate_family(family); validate_receipt(receipt); _scope(family, receipt)
    stage = receipt['payload']['stage']
    require(family['mode'] != 'production' or asset_root is not None,
            'Production receipt admission requires an explicit asset root and fresh media verification')
    if receipt['id'] in family['receipts']:
        require(family['receipts'][receipt['id']] == receipt, 'Immutable receipt conflict')
        require(family['heads'].get(stage) == receipt['id'], 'Historical receipt requires a new explicit revision')
        if asset_root is not None:
            from pack_export import verify_family_media
            verify_family_media(family, asset_root, stages={stage})
        return copy.deepcopy(family)
    require(len(family['receipts']) < MAX_RECEIPTS, 'Family receipt limit reached; archive explicitly')
    expected = {s: family['heads'].get(s) for s in PARENTS[stage]}
    require(receipt['payload']['parents'] == expected, 'Receipt parents are stale or missing')
    gate = next_gate(family, stage, asset_root=asset_root)
    require(gate['passed'], 'Next stage blocked: ' + ', '.join(b['code'] for b in gate['blockers']), 'stage_blocked')
    out = copy.deepcopy(family)
    out['receipts'][receipt['id']] = copy.deepcopy(receipt); out['heads'][stage] = receipt['id']
    canonical_bytes(out)
    if asset_root is not None:
        from pack_export import verify_family_media
        verify_family_media(out, asset_root, stages={stage})
    return out


def resolve_uncertain(family, stage, outcome, prompt_ref, observation_ref, *, asset_root=None):
    """Record external observation of the exact retained attempt; never resubmit.

    This is a receipt operation only. It does not query ComfyUI or prove the caller's
    observation authentic. Production integration must use retained Studio history.
    """
    validate_family(family)
    require(stage in family['heads'] and outcome in ('completed', 'failed'), 'Invalid uncertainty resolution')
    receipt = family['receipts'][family['heads'][stage]]
    require(receipt['generation']['state'] == 'uncertain', 'Stage is not uncertain')
    require(type(prompt_ref) is str and prompt_ref == receipt['generation'].get('evidence_ref'),
            'Uncertainty resolution must retain the exact prompt reference')
    require(type(observation_ref) is str and observation_ref, 'External history observation is required')
    require(len(family['receipts']) < MAX_RECEIPTS, 'Family receipt limit reached')
    require(family['mode'] != 'production' or asset_root is not None, 'Production resolution needs media verification')
    resolved = attest(receipt, 'generation', outcome, receipt['generation']['actor'], prompt_ref)
    resolved['generation']['observation_ref'] = observation_ref
    resolved['generation']['resolves_receipt'] = receipt['id']; resolved = seal(resolved)
    out = copy.deepcopy(family); out['receipts'][resolved['id']] = resolved; out['heads'][stage] = resolved['id']
    if asset_root is not None and outcome == 'completed':
        from pack_export import verify_family_media
        verify_family_media(out, asset_root, stages={stage})
    return out


def _identity_media(receipt):
    payload = receipt['payload']; identity = payload['identity']
    hashes = {a['sha256'] for a in payload['artifacts'] if a['media_type'].startswith('image/')}
    sheet = identity.get('sheet')
    if type(sheet) is not dict or type(sheet.get('views')) is not list: return False
    for view in sheet['views']:
        if type(view) is not dict or view.get('media_sha256') not in hashes: return False
    if payload['stage'] == 'concept':
        features = identity.get('anchor_features')
        if type(features) is not dict or not features: return False
        if any(type(x) is not dict or x.get('media_sha256') not in hashes for x in features.values()): return False
    return True


def assess(family, stage, *, require_licence=False, intended_use=None):
    validate_family(family); require(stage in STAGES, 'Unsupported stage')
    require(type(require_licence) is bool, 'Licence gate must be boolean')
    require(not require_licence or type(intended_use) is str and intended_use, 'A named intended use is required')
    blockers, scored, visited = [], {}, set()
    def block(code, current, detail=''):
        item = {'code': code, 'stage': current}
        if detail: item['detail'] = detail
        blockers.append(item)
    def visit(current):
        if current in visited: return
        visited.add(current)
        identifier = family['heads'].get(current)
        if identifier is None:
            block('missing_stage', current); return
        receipt = family['receipts'][identifier]; payload = receipt['payload']
        for parent in PARENTS[current]:
            if payload['parents'].get(parent) != family['heads'].get(parent): block('stale_parent', current, parent)
            visit(parent)
        if current != 'concept' and payload['concept_id'] != family['heads'].get('concept'):
            block('stale_concept', current)
        for dimension, expected in [('generation', 'completed'), ('inspection', 'inspected'), ('acceptance', 'accepted')]:
            evidence = receipt[dimension]
            if evidence['state'] != expected:
                block('uncertain_submission' if dimension == 'generation' and evidence['state'] == 'uncertain'
                      else dimension + '_required', current)
            elif evidence.get('subject_sha256') != subject(receipt): block('stale_attestation', current, dimension)
        if require_licence:
            licence = receipt['licence']
            if licence['state'] != 'cleared' or licence.get('intended_use') != intended_use:
                block('licence_clearance_required', current)
            elif licence.get('subject_sha256') != subject(receipt): block('stale_attestation', current, 'licence')
        quality = payload['quality']
        names = [x.get('name') for x in quality if type(x) is dict]
        if len(names) != len(quality) or len(set(names)) != len(names): block('invalid_quality_evidence', current)
        for name in family['policy'].get('quality_required', {}).get(current, []):
            matches = [x for x in quality if type(x) is dict and x.get('name') == name]
            if len(matches) != 1 or matches[0].get('outcome') != 'pass' or not matches[0].get('evidence_ref'):
                block('quality_gate_failed', current, name)
        if not _identity_media(receipt): block('unbound_identity_media', current)
        concept_id = family['heads'].get('concept')
        concept = family['receipts'].get(concept_id, {})
        anchor = concept.get('payload', {}).get('identity', {}).get('anchor_features', {})
        from consistency import score_sheet
        metric_policy = {k: family['policy'][k] for k in ('version', 'features', 'required')}
        result = score_sheet(anchor, payload['identity'].get('sheet'), metric_policy, current)
        scored[current] = result
        if not result['passed']: block('identity_drift', current, ', '.join(map(str, result.get('blockers', []))))
    visit(stage)
    return {'schema': 'las.character-gate/1', 'stage': stage, 'passed': not blockers,
            'blockers': blockers, 'identity': scored, 'mode': family['mode'],
            'evidence_state': 'implemented', 'generation_submitted': False,
            'policy_sha256': family['policy_sha256'], 'media_bytes_verified': False,
            'perceptual_identity_verified': False,
            'licence_gate_requested': require_licence, 'intended_use': intended_use}


def next_gate(family, stage, *, asset_root=None):
    validate_family(family); require(stage in STAGES, 'Unsupported stage')
    blockers = []
    current = family['receipts'].get(family['heads'].get(stage), {})
    if current.get('generation', {}).get('state') == 'uncertain':
        blockers.append({'code': 'uncertain_submission', 'stage': stage,
                         'detail': 'Observe the retained prompt; a fresh submission is blocked'})
    for parent in PARENTS[stage]:
        blockers.extend(assess(family, parent)['blockers'])
    closure = set()
    def ancestors(node):
        for parent in PARENTS[node]:
            if parent not in closure:
                closure.add(parent); ancestors(parent)
    ancestors(stage)
    media_verified = False
    if asset_root is None and family['mode'] == 'production' and closure:
        blockers.append({'code': 'media_verification_required', 'stage': stage})
    elif asset_root is not None and closure and not blockers:
        try:
            from pack_export import verify_family_media
            verify_family_media(family, asset_root, stages=closure)
            media_verified = True
        except (ValueError, OSError, KeyError, TypeError) as exc:
            blockers.append({'code': 'media_verification_failed', 'stage': stage, 'detail': str(exc)})
    unique = {digest(b): b for b in blockers}
    return {'stage': stage, 'passed': not unique, 'blockers': list(unique.values()),
            'generation_submitted': False, 'action': 'prepare-only', 'media_bytes_verified': media_verified}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--family-id', required=True)
    init.add_argument('--workspace-id', required=True); init.add_argument('--character-id', required=True)
    init.add_argument('--policy', required=True); init.add_argument('--out', required=True)
    for name in ('check', 'next'):
        item = sub.add_parser(name); item.add_argument('--family', required=True)
        item.add_argument('--stage', choices=STAGES, required=True)
        item.add_argument('--asset-root')
        if name == 'check':
            item.add_argument('--require-licence', action='store_true'); item.add_argument('--intended-use')
    record = sub.add_parser('record'); record.add_argument('--family', required=True)
    record.add_argument('--receipt', required=True); record.add_argument('--out', required=True)
    record.add_argument('--asset-root')
    resolve = sub.add_parser('resolve'); resolve.add_argument('--family', required=True)
    resolve.add_argument('--stage', choices=STAGES, required=True)
    resolve.add_argument('--outcome', choices=('completed', 'failed'), required=True)
    resolve.add_argument('--prompt-ref', required=True); resolve.add_argument('--observation-ref', required=True)
    resolve.add_argument('--asset-root'); resolve.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = create_family(args.family_id, args.workspace_id, args.character_id, load_json(args.policy))
            write_new_runtime(args.out, result)
        elif args.command == 'record':
            result = record_receipt(load_json(args.family), load_json(args.receipt), asset_root=args.asset_root)
            write_new_runtime(args.out, result)
        elif args.command == 'resolve':
            result = resolve_uncertain(load_json(args.family), args.stage, args.outcome, args.prompt_ref,
                                       args.observation_ref, asset_root=args.asset_root)
            write_new_runtime(args.out, result)
        elif args.command == 'next': result = next_gate(load_json(args.family), args.stage, asset_root=args.asset_root)
        else:
            family = load_json(args.family)
            result = assess(family, args.stage, require_licence=args.require_licence,
                            intended_use=args.intended_use)
            if args.asset_root:
                from pack_export import verify_family_media
                verify_family_media(family, args.asset_root); result['media_bytes_verified'] = True
            elif family['mode'] == 'production':
                result['passed'] = False
                result['blockers'].append({'code': 'media_verification_required', 'stage': args.stage})
        sys.stdout.buffer.write(canonical_bytes(result))
        return 0 if result.get('passed', True) else 2
    except (PipelineError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'error': getattr(exc, 'code', 'invalid_input'), 'message': str(exc),
                          'generation_submitted': False}), file=sys.stderr)
        return 2


if __name__ == '__main__': raise SystemExit(main())
