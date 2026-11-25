"""Deterministic P35 plans. This module performs no network or generation calls."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

MAX_JSON_BYTES = 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}')
UPLOAD = re.compile(r'[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)')
SMOKE_CASES = ('ordinary-neutral', 'foreshortened-arm', 'contact-heavy-grip')
SMOKE_ROUTES = ('klein4-reference', 'klein9-copy-pose')
CHUNK_HEADROOM_SECONDS = 600


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError('Expected finite JSON data') from exc


def stable_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def studio_hash(value):
    """Pinned app.production.fingerprint convention (ASCII JSON escaping)."""
    canonical(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode('utf-8')).hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('JSON input is too large')
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-finite JSON')))
        canonical(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Invalid UTF-8 JSON') from exc


def validate_graph(graph):
    if not isinstance(graph, dict) or not 1 <= len(graph) <= 256:
        raise ValueError('Invalid graph size')
    edges = {}
    for identifier, node in graph.items():
        if not isinstance(identifier, str) or not isinstance(node, dict):
            raise ValueError('Invalid graph node')
        if not isinstance(node.get('class_type'), str) or not isinstance(node.get('inputs'), dict):
            raise ValueError('Invalid graph node contract')
        edges[identifier] = []
        for value in node['inputs'].values():
            if isinstance(value, list):
                if len(value) != 2 or not isinstance(value[0], str) or value[0] not in graph or type(value[1]) is not int or value[1] < 0:
                    raise ValueError('Invalid graph link')
                edges[identifier].append(value[0])
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting:
            raise ValueError('Graph contains a cycle')
        if node in visited:
            return
        visiting.add(node)
        for dependency in edges[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)
    return {'nodes': len(graph), 'links': sum(map(len, edges.values()))}


def validate_bundle(root, bundle):
    canonical(bundle)
    if bundle.get('schema') != 'p35.routes/v1' or not isinstance(bundle.get('routes'), list):
        raise ValueError('Unknown route bundle')
    seen, counts = set(), []
    for route in bundle['routes']:
        identifier = route.get('id')
        if not isinstance(identifier, str) or identifier in seen:
            raise ValueError('Invalid or duplicate route')
        seen.add(identifier)
        relative = route.get('graph', '')
        posix = PurePosixPath(relative)
        if not isinstance(relative, str) or posix.is_absolute() or '..' in posix.parts or '\\' in relative or posix.parts[:1] != ('graphs',):
            raise ValueError('Unsafe graph path')
        path = Path(root) / relative
        if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()):
            raise ValueError('Unsafe graph path')
        raw = path.read_bytes()
        if len(raw) >= 300000 or hashlib.sha256(raw).hexdigest() != route.get('graph_sha256'):
            raise ValueError('Graph source hash mismatch')
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != route['source']['graph_git_blob']:
            raise ValueError('Graph Git blob hash mismatch')
        graph = read_json(path)
        counts.append(validate_graph(graph))
        bindings = list(route['bindings'].values())
        bindings += [b for rows in route.get('bindings_extra', {}).values() for b in rows]
        bindings += [s['binding'] for s in route['native_reference_slots']]
        for binding in bindings:
            if not isinstance(binding, list) or len(binding) != 2 or binding[0] not in graph or binding[1] not in graph[binding[0]]['inputs']:
                raise ValueError('Missing graph binding')
        for control in route['controls']:
            if control not in route['bindings']:
                raise ValueError('Control has no native binding: ' + control)
        if route.get('state') != 'planned' or route.get('verified') is not False:
            raise ValueError('Route evidence must remain planned and unverified')
        if route.get('backend_id') != 'primary':
            raise ValueError('Current bundle admits only the pinned primary backend')
    return {'routes': len(seen), 'graphs': len(counts), 'nodes': sum(x['nodes'] for x in counts),
            'source_revision': bundle['source_revision'], 'validation': 'structural_only',
            'generation_submitted': False}


def owner_template(suite):
    bindings = {}
    for case in suite['cases']:
        for ref in case['references']:
            bindings.setdefault(ref['source_group'], {'file': None, 'sha256': None})
    return {'schema': 'p35.owner-inputs/v1',
            'expected_identity': {'app': 'local-asset-studio', 'workspace': '', 'version': 'production-workspace-1'},
            'reference_bindings': bindings,
            'characters': {c['id']: {'description': '', 'outfit': '', 'style': '', 'details': []} for c in suite['canon']},
            'guides': {c['id']: {'file': None, 'sha256': None, 'renderer': 'studio.coco18-lines/v1',
                                'representation': 'precomputed-skeleton'} for c in suite['cases']},
            'default_style': {'file': None, 'sha256': None},
            'note': 'Fill from exact existing Studio uploads and retained byte hashes. These declarations do not prove review or licence clearance.'}


def _text(value, label, limit=1500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise ValueError(label + ' is missing or too long')
    return value.strip()


def _input(source, label, group, roles, subject=None, **extra):
    if not isinstance(source, dict) or not isinstance(source.get('file'), str) or not UPLOAD.fullmatch(source['file']):
        raise ValueError('Missing or invalid Studio upload for ' + label)
    sha = source.get('sha256')
    if not isinstance(sha, str) or not HEX.fullmatch(sha):
        raise ValueError('Missing byte hash for ' + label)
    return {'source_group': group, 'file': source['file'], 'sha256': sha, 'roles': list(roles),
            'subject_id': subject, 'representation': extra.pop('representation', 'rgb'), **extra}


def _case_inputs(case, route, owner):
    """Resolve explicit sources to native slots; unsupported facets remain blockers."""
    problems, inputs = [], []
    unsupported = False
    if len(case['subject_ids']) != 1:
        return inputs, ['multi-character: the inherited route admits one subject'], True
    refs = case['references']
    if any('scene' in r['roles'] for r in refs):
        return inputs, ['scene has no independent native input on this route'], True
    if any(set(r['roles']) <= {'outfit', 'costume', 'detail'} for r in refs):
        return inputs, ['independent outfit/detail reference has no native slot'], True
    identities = [r for r in refs if 'identity' in r['roles']]
    poses = [r for r in refs if 'pose' in r['roles']]
    styles = [r for r in refs if 'style' in r['roles']]
    if len(identities) != 1 or len(poses) != 1 or len(styles) > 1:
        return inputs, ['ambiguous reference role ownership'], True
    if styles and route['id'] != 'qwen-3ref':
        return inputs, ['separate style reference is unsupported by this two-reference contract'], True
    consumed = {r['id'] for r in identities + poses + styles}
    if consumed != {r['id'] for r in refs}:
        return inputs, ['extra reference has no declared native slot; no source may be discarded'], True
    from qualification import resolve_roles
    role_report = resolve_roles(refs, {'id': route['id'], **route['capabilities']})
    if role_report['conflicts']:
        return inputs, ['explicit reference role conflict: ' + json.dumps(role_report['conflicts'], sort_keys=True)], False
    if role_report['unsupported_roles']:
        return inputs, ['unsupported reference role: ' + json.dumps(role_report['unsupported_roles'], sort_keys=True)], True
    facet_contracts = [
        ('identity', identities[0], {'identity', 'outfit', 'costume', 'detail'}),
        ('pose', poses[0], {'pose', 'composition'}),
    ]
    if styles:
        facet_contracts.append(('style', styles[0], {'style'}))
    for native_role, reference, allowed in facet_contracts:
        extra_facets = set(reference['roles']) - allowed
        if extra_facets:
            return inputs, [native_role + ' input does not support requested facets: ' + ', '.join(sorted(extra_facets))], True
    bindings = owner.get('reference_bindings', {})
    if not isinstance(bindings, dict):
        raise ValueError('reference_bindings must be an object')
    identity, pose = identities[0], poses[0]
    try:
        inputs.append(_input(bindings.get(identity['source_group']), 'identity', identity['source_group'],
                             identity['roles'], identity['subject_id']))
    except ValueError as exc:
        problems.append(str(exc))
    try:
        if route['input_representation'] == 'precomputed-skeleton':
            guide = owner.get('guides', {}).get(case['id'])
            if not isinstance(guide, dict) or guide.get('renderer') != route['renderer'] or guide.get('representation') != 'precomputed-skeleton':
                raise ValueError('Corrected guide renderer/representation is missing or unqualified')
            inputs.append(_input(guide, 'corrected skeleton', 'guide-' + case['id'], pose['roles'], pose['subject_id'],
                                 representation='precomputed-skeleton', renderer=guide['renderer']))
        else:
            inputs.append(_input(bindings.get(pose['source_group']), 'pose', pose['source_group'], pose['roles'], pose['subject_id']))
    except ValueError as exc:
        problems.append(str(exc))
    if route['id'] == 'qwen-3ref':
        try:
            source = bindings.get(styles[0]['source_group']) if styles else owner.get('default_style')
            group = styles[0]['source_group'] if styles else 'owner-declared-default-style'
            inputs.append(_input(source, 'style', group, ['style']))
        except ValueError as exc:
            problems.append(str(exc))
    files, hashes = [r['file'] for r in inputs], [r['sha256'] for r in inputs]
    if len(set(files)) != len(files) or len(set(hashes)) != len(hashes):
        problems.append('Distinct roles resolve to the same source; review the alias before planning')
    return inputs, problems, unsupported


def _prompt(case, route, character):
    who = _text(character.get('description'), 'Character description')
    outfit = _text(character.get('outfit'), 'Outfit description')
    style = _text(character.get('style'), 'Style description')
    details = character.get('details', [])
    if not isinstance(details, list) or len(details) > 12 or any(not isinstance(x, str) or len(x) > 200 for x in details):
        raise ValueError('Character details must be up to twelve short descriptions')
    detail_text = '; '.join(details) or 'the character design details'
    if route['id'] == 'klein9-skeleton':
        prefix = 'Image 1 is the corrected pose skeleton. Use its body position and camera. Draw the character from image 2.'
    elif route['id'] == 'klein9-copy-pose':
        prefix = 'change the actions and poses in Image 1 to match those in Image 2. Image 1 supplies the character; image 2 supplies only pose and requested composition.'
    elif route['id'] == 'qwen-3ref':
        prefix = 'Picture 1 supplies character identity and outfit; Picture 2 supplies pose, camera and support relationships; Picture 3 supplies rendering style only, without recolouring the costume.'
    else:
        prefix = 'Redraw the character in image 1 in the pose and requested composition of image 2.'
    text = (f'{prefix} Character: {who}. Preserve outfit and colours: {outfit}. Preserve details: {detail_text}. '
            f'Rendering: {style}. Target: {case["brief"]} '
            'Do not copy the pose donor identity, costume, palette, lettering or background. '
            'Keep one character, coherent anatomy and the requested hand/prop/support contacts. '
            'Do not add objects or substitute an easier pose.')
    return _text(text, 'Compiled brief', 7500)


def _request(case, route, owner, inputs):
    character = owner.get('characters', {}).get(case['subject_ids'][0], {})
    controls = copy.deepcopy(route['controls'])
    controls['positive'] = _prompt(case, route, character)
    if route['id'] == 'qwen-3ref':
        references = [{'file': ref['file'], 'sha256': ref['sha256'], 'role': role,
                       'contribution': contribution, 'avoid': avoid} for ref, role, contribution, avoid in zip(inputs,
                      ('identity', 'pose', 'style'),
                      ('Face, hair, body design, outfit and distinctive details', 'Pose, camera, support and contacts', 'Linework and shading'),
                      ('Unrequested character or costume changes', 'Donor identity, costume, palette or background', 'Reference person, costume colours or composition'))]
    else:
        controls['last_reference'] = inputs[0]['file']
        references = [{'file': inputs[1]['file'], 'sha256': inputs[1]['sha256'], 'role': 'pose',
                       'contribution': '', 'avoid': ''}]
    return {'preset_id': route['preset_id'], 'controls': controls, 'references': references,
            'expected_template_sha256': route['graph_sha256']}


def _selection(values, available, defaults, label):
    chosen = list(defaults if values is None else values)
    if not chosen or len(set(chosen)) != len(chosen) or any(x not in available for x in chosen):
        raise ValueError('Invalid or duplicate ' + label + ' selection')
    return chosen


def _model_pins(route):
    result = {}
    for component in route['components']:
        matches = component.get('catalog_matches')
        if not isinstance(matches, list) or len(matches) != 1:
            raise ValueError('A model component has no unique frozen inventory pin')
        model = matches[0]
        if not isinstance(model.get('sha256'), str) or not HEX.fullmatch(model['sha256']) or type(model.get('bytes')) is not int or model['bytes'] <= 0:
            raise ValueError('A model component lacks its frozen byte identity')
        entry = {key: model[key] for key in ('file', 'sha256', 'bytes')}
        if entry['file'] in result and result[entry['file']] != entry:
            raise ValueError('Conflicting frozen model pins')
        result[entry['file']] = entry
    return [result[key] for key in sorted(result)]


def _prune_slot(graph, node):
    """The narrow native ReferenceLatent board bypass, independently checked against Studio."""
    removed = {node}
    graph.pop(node)
    while True:
        change = False
        for key, item in list(graph.items()):
            for field, value in list(item['inputs'].items()):
                if not isinstance(value, list) or len(value) != 2 or value[0] not in removed:
                    continue
                if item['class_type'] == 'ReferenceLatent' and field == 'latent':
                    upstream = item['inputs']['conditioning']
                    del graph[key]
                    removed.add(key)
                    for other in graph.values():
                        for name, edge in list(other['inputs'].items()):
                            if isinstance(edge, list) and len(edge) == 2 and edge[0] == key:
                                other['inputs'][name] = list(upstream)
                else:
                    del graph[key]
                    removed.add(key)
                change = True
                break
            if change:
                break
        if not change:
            break


def materialize_graph(route, source_graph, request, seed):
    """Expected prepared graph for these four fixed contracts, never a submission path.

    An upstream prepare change must cause a hash refusal, not be guessed around.
    Geometry, actual pixels and model tensors are not evaluated here.
    """
    graph = copy.deepcopy(source_graph)
    controls = dict(request['controls'], seed=seed)
    for key, value in controls.items():
        if key not in route['bindings']:
            raise ValueError('Unsupported native control binding')
        if key in ('seed', 'steps', 'width', 'height'):
            if type(value) is not int:
                raise ValueError('Integer native control required')
        elif key in ('cfg', 'lora'):
            value = float(value)
        for node, field in [route['bindings'][key], *route.get('bindings_extra', {}).get(key, [])]:
            graph[node]['inputs'][field] = value
    refs = request['references']
    for index, slot in enumerate(route['native_reference_slots']):
        node, field = slot['binding']
        if index >= len(refs):
            if not route['reference_board']:
                raise ValueError('Missing required native image slot')
            _prune_slot(graph, node)
        else:
            graph[node]['inputs'][field] = refs[index]['file']
    if not route['reference_board']:
        guidance = '\n'.join(f"Picture {i + 1} — {r['role']}: use {r['contribution'] or 'the assigned visual role'}. Avoid transferring: {r['avoid'] or 'unrequested details'}." for i, r in enumerate(refs))
        node, field = route['bindings']['positive']
        graph[node]['inputs'][field] = guidance + '\n\nRequested result:\n' + graph[node]['inputs'][field]
    validate_graph(graph)
    return graph


def compile_plan(suite, bundle, owner=None, *, profile='smoke', route_ids=None, case_ids=None,
                 seed_count=None, allow_heavy=False, prospective=False):
    from qualification import validate_suite
    canonical([suite, bundle, owner])
    here = Path(__file__).resolve().parent
    validate_bundle(here, bundle)
    validate_suite(suite)
    if profile not in ('smoke', 'full'):
        raise ValueError('Choose smoke or full profile')
    if type(prospective) is not bool:
        raise ValueError('Prospective evidence protocol must be an explicit boolean')
    owner = copy.deepcopy(owner if owner is not None else owner_template(suite))
    if not isinstance(owner, dict) or owner.get('schema') != 'p35.owner-inputs/v1':
        raise ValueError('Unknown owner input schema')
    routes = {r['id']: r for r in bundle['routes']}
    cases = {c['id']: c for c in suite['cases']}
    selected_routes = _selection(route_ids, routes, SMOKE_ROUTES if profile == 'smoke' else suite['routes'], 'route')
    selected_cases = _selection(case_ids, cases, SMOKE_CASES if profile == 'smoke' else list(cases), 'case')
    count = (2 if profile == 'smoke' else 3) if seed_count is None else seed_count
    if type(count) is not int or not 2 <= count <= len(suite['seeds']):
        raise ValueError('Use at least two paired seeds from the fixed suite')
    seeds = suite['seeds'][:count]
    bound = copy.deepcopy(suite)
    if prospective:
        bound['evidence_mode'] = 'prospective'
    bound['route_pins'] = {rid: stable_hash(routes[rid]) for rid in suite['routes']}
    for canon in bound['canon']:
        canon['reference_sha256'] = owner.get('reference_bindings', {}).get(canon['id'], {}).get('sha256')
    resolved = {}
    for case in bound['cases']:
        for ref in case['references']:
            ref['sha256'] = owner.get('reference_bindings', {}).get(ref['source_group'], {}).get('sha256')
        actual = {}
        for rid, route in routes.items():
            inputs, problems, unsupported = _case_inputs(case, route, owner)
            resolved[(rid, case['id'])] = (inputs, problems, unsupported)
            if inputs and not problems:
                actual[rid] = inputs
        if actual:
            case['route_inputs'] = actual
    expanded = validate_suite(bound)
    suite_sha = expanded['suite_sha256']
    campaign = stable_hash({'suite': bound, 'bundle': bundle, 'owner': owner, 'routes': selected_routes,
                            'cases': selected_cases, 'seeds': seeds, 'profile': profile, 'allow_heavy': allow_heavy})
    blockers, chunks, ledger = [], [], []
    identity = owner.get('expected_identity')
    workspace = identity.get('workspace') if isinstance(identity, dict) else None
    if (not isinstance(identity, dict) or set(identity) != {'app', 'workspace', 'version'}
            or identity.get('app') != 'local-asset-studio' or identity.get('version') != 'production-workspace-1'
            or not isinstance(workspace, str) or not workspace.strip() or len(workspace) > 2048 or '\x00' in workspace
            or not (Path(workspace).is_absolute() or PureWindowsPath(workspace).is_absolute())):
        blockers.append({'code': 'missing_studio_identity', 'reason': 'Fill the exact app, absolute workspace and version from the owner Studio /api/identity response'})
    warm_low = warm_high = budget = 0
    for rid in selected_routes:
        route = routes[rid]
        for cid in selected_cases:
            case = next(c for c in bound['cases'] if c['id'] == cid)
            inputs, problems, unsupported = resolved[(rid, cid)]
            reasons = list(problems)
            if route['runtime_estimate']['heavy_opt_in'] and not allow_heavy:
                reasons.append('Heavy Qwen feasibility route requires explicit --allow-heavy')
            request = None
            if not reasons:
                try:
                    request = _request(case, route, owner, inputs)
                except ValueError as exc:
                    reasons.append(str(exc))
            for reason in reasons:
                blockers.append({'code': 'unsupported' if unsupported else 'missing_or_conflicting_input',
                                 'route_id': rid, 'case_id': cid, 'reason': reason})
            status = 'unsupported' if unsupported else 'blocked' if reasons else 'planned'
            for trial in expanded['trials']:
                if trial['route_id'] == rid and trial['case_id'] == cid and trial['seed'] in seeds:
                    ledger.append({**copy.deepcopy(trial), 'status': status, 'output_claim': 'planned'})
            low, high = route['runtime_estimate']['warm_seconds_range']
            warm_low += low * len(seeds)
            warm_high += high * len(seeds)
            per_chunk = max(route['runtime_estimate']['max_seconds_per_chunk'],
                            high * len(seeds) + CHUNK_HEADROOM_SECONDS)
            budget += per_chunk
            if request is not None and not reasons:
                chunk_id = f'{rid}-{cid}'
                name = f'P35 {campaign[:16]} {chunk_id}'
                chunks.append({'id': chunk_id, 'name': name,
                               'route_id': rid, 'case_id': cid, 'detector_behavior': route['detector_behavior'],
                               'expected_graph_sha256': [studio_hash(materialize_graph(route, read_json(here / route['graph']), request, seed)) for seed in seeds],
                               'expected_models': _model_pins(route),
                               'expected_pruned_reference_slots': ([{'slot': 2, 'role': 'pose'}] if rid == 'klein4-reference' else []),
                               'expected_inputs': [{'file': x['file'], 'sha256': x['sha256']} for x in inputs],
                               'payload': {'name': name, 'recipe': request,
                                           'variants': [{'label': f'seed-{seed}', 'controls': {'seed': seed}} for seed in seeds],
                                           'max_generations': len(seeds), 'max_seconds': per_chunk}})
    if budget > 14400:
        blockers.append({'code': 'time_budget_exceeded', 'reason': f'{budget} seconds of conservative chunk budgets exceeds four hours; select an explicit route/case shard'})
    total = len(selected_routes) * len(selected_cases) * len(seeds)
    if len(ledger) != total:
        raise ValueError('Expanded suite lost selected trial cells')
    ready = not blockers
    owner_run = None
    if ready:
        owner_run = {'schema': 'p35-owner-run/v1', 'campaign_id': campaign, 'backend_id': 'primary',
                     'expected_identity': identity, 'max_attempts': total, 'max_seconds': max(60, min(14400, budget)),
                     'chunks': chunks}
        owner_run['plan_id'] = stable_hash(owner_run)
    result = {'schema': 'p35.plan/v1', 'profile': profile, 'output_claim': 'planned', 'ready': ready,
              'campaign_id': campaign, 'bound_suite': bound, 'suite_sha256': suite_sha,
              'selected_slots': total, 'full_suite_slots': len(expanded['trials']), 'trial_ledger': ledger,
              'blockers': blockers, 'owner_run': owner_run,
              'estimated_warm_seconds_range': [warm_low, warm_high], 'conservative_chunk_budget_seconds': budget,
              'estimates_are_measurements': False, 'measured_runtime_seconds': None, 'measured_peak_vram_gib': None,
              'image_evidence': {'generation': 'planned', 'visual_review': 'unreviewed', 'project_acceptance': None,
                                 'licence_clearance': None}}
    result['plan_sha256'] = stable_hash(result)
    return result


def runtime_write(path, value, repo_root):
    """Write UTF-8/LF JSON under .runtime; exact reruns verify rather than overwrite."""
    target = Path(path)
    allowed = Path(repo_root).resolve() / '.runtime'
    if allowed.is_symlink() or not target.resolve().is_relative_to(allowed.resolve()):
        raise ValueError('Generated output must stay under the repository .runtime directory')
    for ancestor in (target, *target.parents):
        if ancestor == Path(repo_root).resolve():
            break
        if ancestor.is_symlink():
            raise ValueError('Generated output cannot traverse symlinks')
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError('Different output already exists; choose a new .runtime directory')
        return
    with target.open('xb') as stream:
        stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', type=Path)
    parser.add_argument('--profile', choices=('smoke', 'full'), default='smoke')
    parser.add_argument('--routes', nargs='+')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--seeds', type=int)
    parser.add_argument('--allow-heavy', action='store_true')
    parser.add_argument('--prospective', action='store_true',
                        help='Freeze the prospective evidence protocol before owner execution; no generation is performed')
    parser.add_argument('--out', type=Path, default=Path('.runtime/P35-B-20261125-1/plan'))
    parser.add_argument('--template', action='store_true')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    suite, bundle = read_json(here / 'suite.json'), read_json(here / 'routes.json')
    validate_bundle(here, bundle)
    if args.template:
        runtime_write(args.out / 'owner-inputs.json', owner_template(suite), root)
        print('Wrote owner input template; no server contacted and no generation submitted.')
        return
    result = compile_plan(suite, bundle, read_json(args.owner) if args.owner else None,
                          profile=args.profile, route_ids=args.routes, case_ids=args.cases,
                          seed_count=args.seeds, allow_heavy=args.allow_heavy, prospective=args.prospective)
    runtime_write(args.out / 'plan.json', result, root)
    if result['owner_run']:
        runtime_write(args.out / 'owner-run.json', result['owner_run'], root)
    print(json.dumps({'selected_slots': result['selected_slots'], 'ready': result['ready'],
                      'blockers': len(result['blockers']), 'generation_submitted': False,
                      'plan_sha256': result['plan_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
