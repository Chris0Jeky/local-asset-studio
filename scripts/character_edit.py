"""Actor-bound edit plans and tool-policy reports. No inference, downloads or shell.

Uses the character-study contracts from PR #70. Plans are proposals; runtime
reservation, native document revision locks and neural jobs stay with Production.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_study import (SHA, artifact, canonical, identifier, integer,
    keys, read_json, require, sha, strings, text, write_json)

OPERATIONS = {'anatomy-repair', 'costume-change', 'scenario', 'interaction', 'local-repaint'}
FACETS = {'anatomy', 'costume', 'pose', 'expression', 'appearance', 'placement'}
ALLOWED_CHANGES = {
    'anatomy-repair': {'anatomy'}, 'costume-change': {'costume'},
    'scenario': {'placement', 'pose', 'expression'},
    'interaction': {'pose', 'expression', 'placement'}, 'local-repaint': {'appearance'},
}
ROLES = {'identity', 'costume', 'pose', 'style', 'composition'}
FILTER_STATES = {'none_in_adapter', 'present', 'unknown'}
FILTER_PREFERENCES = {'allow_with_warning', 'exclude'}


def version(value: dict, kind: str) -> None:
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and value['kind'] == kind, 'Unsupported contract version/kind')


def digest(value: str) -> None:
    require(isinstance(value, str) and bool(SHA.fullmatch(value)), 'Invalid digest')


def box(value: list, canvas: list) -> None:
    require(isinstance(value, list) and len(value) == 4, 'Expected x0,y0,x1,y1')
    for v in value: integer(v, 0, 8192, 'box coordinate')
    x0, y0, x1, y1 = value
    require(0 <= x0 < x1 <= canvas[0] and 0 <= y0 < y1 <= canvas[1], 'Box outside canvas')


def document(value: dict) -> dict:
    keys(value, {'schema_version', 'kind', 'id', 'revision', 'canvas', 'source',
                 'actors', 'scene', 'relations'})
    version(value, 'character_edit_document'); identifier(value['id'])
    integer(value['revision'], 1, 1000000, 'revision')
    canvas = value['canvas']
    require(isinstance(canvas, list) and len(canvas) == 2, 'Expected canvas width,height')
    for v in canvas: integer(v, 1, 8192, 'canvas')
    require(canvas[0] * canvas[1] <= 24000000, 'Canvas exceeds 24 million pixels')
    artifact(value['source'])
    require(isinstance(value['actors'], list) and 1 <= len(value['actors']) <= 8, 'Expected 1..8 actors')
    seen = set()
    for actor in value['actors']:
        keys(actor, {'id', 'canon', 'bounds', 'references'})
        identifier(actor['id']); require(actor['id'] not in seen, 'Duplicate actor'); seen.add(actor['id'])
        artifact(actor['canon']); box(actor['bounds'], canvas)
        require(isinstance(actor['references'], list) and 1 <= len(actor['references']) <= 8, 'Expected 1..8 actor references')
        ids, roles = set(), set()
        for ref in actor['references']:
            keys(ref, {'id', 'role', 'image', 'take', 'ignore'})
            identifier(ref['id']); require(ref['id'] not in ids, 'Duplicate actor reference'); ids.add(ref['id'])
            require(ref['role'] in ROLES, 'Unsupported reference role'); roles.add(ref['role'])
            artifact(ref['image']); strings(ref['take'], 'reference take', 1); strings(ref['ignore'], 'reference ignore')
        require('identity' in roles, 'Every actor needs its own identity reference')
    keys(value['scene'], {'description', 'camera', 'lighting'})
    for field in value['scene']: text(value['scene'][field], field)
    require(isinstance(value['relations'], list) and len(value['relations']) <= 32, 'Too many relations')
    for rel in value['relations']:
        keys(rel, {'from', 'to', 'kind', 'note'})
        require(rel['from'] in seen and rel['to'] in seen and rel['from'] != rel['to'], 'Invalid relation actors')
        require(rel['kind'] in {'in_front_of', 'beside', 'looking_at', 'contact'}, 'Unsupported relation')
        text(rel['note'], 'relation note')
    # A front-of cycle is not a realizable global occlusion order. Partial limb
    # crossings need separate contact regions, not a cyclic whole-actor ordering.
    edges = {k: set() for k in seen}
    for rel in value['relations']:
        if rel['kind'] == 'in_front_of': edges[rel['from']].add(rel['to'])
    _acyclic(edges)
    return value


def _acyclic(edges: dict[str, set[str]]) -> None:
    pending = {k: set(v) for k, v in edges.items()}
    while pending:
        ready = {k for k, deps in pending.items() if not deps}
        require(bool(ready), 'Cyclic dependencies/occlusion order')
        pending = {k: deps - ready for k, deps in pending.items() if k not in ready}


def intent(value: dict, doc: dict) -> dict:
    keys(value, {'schema_version', 'kind', 'id', 'document_sha256', 'operation',
                 'changes', 'scene_change', 'context_box', 'edit_mask', 'protect_mask',
                 'budget', 'policy_preference', 'patch_alignment', 'layout'})
    version(value, 'character_edit_intent'); identifier(value['id']); digest(value['document_sha256'])
    require(value['document_sha256'] == sha(doc), 'Stale document revision or source snapshot')
    op = value['operation']; require(op in OPERATIONS, 'Unknown edit operation')
    box(value['context_box'], doc['canvas']); artifact(value['edit_mask'])
    require(type(value['patch_alignment']) is int and value['patch_alignment'] in {1, 8, 16, 32}, 'Unsupported patch alignment')
    if value['protect_mask'] is not None: artifact(value['protect_mask'])
    require(isinstance(value['changes'], list) and 1 <= len(value['changes']) <= 16, 'Expected 1..16 changes')
    actors = {a['id'] for a in doc['actors']}; changed, pairs = set(), set()
    for change in value['changes']:
        keys(change, {'actor', 'facet', 'instruction'})
        require(change['actor'] in actors, 'Unknown target actor')
        require(change['facet'] in ALLOWED_CHANGES[op], 'Change outside operation scope')
        text(change['instruction'], 'change instruction')
        pair = (change['actor'], change['facet']); require(pair not in pairs, 'Duplicate change'); pairs.add(pair)
        changed.add(change['actor'])
    if op in {'anatomy-repair', 'costume-change', 'local-repaint'}:
        require(len(changed) == 1, 'Local edits target exactly one actor; use interaction for coupled edits')
        require(value['scene_change'] is None, 'Local edit cannot silently redesign the scene')
    elif op == 'scenario':
        keys(value['scene_change'], {'description', 'camera', 'lighting'})
        for k, v in value['scene_change'].items(): text(v, k)
    else:
        require(len(changed) >= 2, 'Interaction needs at least two target actors')
        require(value['scene_change'] is None, 'Separate interaction from scene redesign')
        require(any(r['kind'] == 'contact' and {r['from'], r['to']} <= changed for r in doc['relations']),
                'Interaction requires an explicit contact relation')
    layout = value['layout']
    if op in {'scenario', 'interaction'}:
        keys(layout, {'actors', 'occlusion_order', 'contact_regions'})
        require(isinstance(layout['actors'], list) and len(layout['actors']) == len(changed), 'Layout must bind every target actor exactly once')
        layout_ids = set()
        for entry in layout['actors']:
            keys(entry, {'id', 'bounds', 'pose_reference'})
            require(entry['id'] in changed and entry['id'] not in layout_ids, 'Invalid layout actor')
            layout_ids.add(entry['id']); box(entry['bounds'], doc['canvas'])
            if entry['pose_reference'] is not None: artifact(entry['pose_reference'])
        order = layout['occlusion_order']
        strings(order, 'back-to-front actor order', len(actors), len(actors))
        require(set(order) == actors, 'Occlusion order must contain every actor exactly once')
        for relation in doc['relations']:
            if relation['kind'] == 'in_front_of':
                require(order.index(relation['from']) > order.index(relation['to']), 'Layout contradicts front-of relation')
        contacts = layout['contact_regions']
        require(isinstance(contacts, list) and (1 if op == 'interaction' else 0) <= len(contacts) <= 16, 'Expected bounded contact regions')
        for contact in contacts:
            keys(contact, {'actors', 'bounds', 'instruction'})
            strings(contact['actors'], 'contact participants', 2, 8)
            require(set(contact['actors']) <= changed and len(set(contact['actors'])) == len(contact['actors']), 'Invalid contact participants')
            box(contact['bounds'], doc['canvas']); text(contact['instruction'], 'contact instruction')
        _contact_coverage(doc['relations'], contacts, changed)
    else: require(layout is None, 'Local operation cannot silently move actors')
    budget = value['budget']; keys(budget, {'owner', 'max_candidates', 'max_repairs'})
    identifier(budget['owner']); integer(budget['max_candidates'], 1, 64, 'candidate cap')
    integer(budget['max_repairs'], 0, 3, 'repair cap')
    require(budget['max_repairs'] < budget['max_candidates'], 'Repairs consume the same candidate cap')
    pref = value['policy_preference']; keys(pref, {'local_only', 'exclude_known_filters', 'exclude_documented_weight_restrictions', 'unknown_policy'})
    require(all(type(pref[k]) is bool for k in ('local_only', 'exclude_known_filters', 'exclude_documented_weight_restrictions')), 'Policy switches must be booleans')
    require(pref['unknown_policy'] in FILTER_PREFERENCES, 'Invalid unknown-policy choice')
    return value


def _contact_coverage(relations: list, regions: list, changed: set[str]) -> None:
    """Joint review regions must cover the declared, undirected contact graph.

    A three-actor region may cover A-B and B-C without inventing A-C. Disconnected
    groups need separate regions; no actor can hitchhike on somebody else's pair.
    Relationships involving an unchanged actor remain outside this target scope.
    """
    declared = {frozenset((r['from'], r['to'])) for r in relations
                if r['kind'] == 'contact' and {r['from'], r['to']} <= changed}
    covered = set()
    for region in regions:
        participants = set(region['actors'])
        edges = {pair for pair in declared if pair <= participants}
        reached = {next(iter(participants))}
        while True:
            expanded = reached | {actor for pair in edges if pair & reached for actor in pair}
            if expanded == reached: break
            reached = expanded
        require(reached == participants, 'A contact region must form a connected group of declared contact relations')
        covered.update(edges)
    require(declared <= covered, 'Every declared contact between target actors needs a matching contact region')


def route_catalog(value: dict) -> dict:
    keys(value, {'schema_version', 'kind', 'as_of', 'routes'})
    version(value, 'character_edit_routes'); text(value['as_of'], 'review date', 32)
    require(isinstance(value['routes'], list) and 1 <= len(value['routes']) <= 32, 'Expected route catalog')
    ids = set()
    for route in value['routes']:
        keys(route, {'id', 'title', 'operations', 'execution', 'status', 'preset_ids',
                     'content_policy', 'capabilities', 'sources', 'limitations'})
        identifier(route['id']); require(route['id'] not in ids, 'Duplicate route'); ids.add(route['id'])
        text(route['title'], 'title'); strings(route['operations'], 'operations', 1)
        require(set(route['operations']) <= OPERATIONS | {'mask', 'composite', 'inspect', 'agent'}, 'Unknown operation capability')
        require(route['execution'] in {'local', 'hosted'}, 'Invalid execution mode')
        require(route['status'] in {'implemented_offline', 'existing_studio_candidate', 'researched'}, 'Invalid route status')
        strings(route['preset_ids'], 'preset IDs'); strings(route['capabilities'], 'capabilities', 1)
        strings(route['sources'], 'sources', 1); strings(route['limitations'], 'limitations', 1)
        p = route['content_policy']
        keys(p, {'input_filter', 'output_filter', 'learned_restrictions', 'upstream_filters', 'evidence_scope', 'note'})
        require(p['input_filter'] in FILTER_STATES and p['output_filter'] in FILTER_STATES, 'Invalid filter evidence')
        require(p['learned_restrictions'] in {'not_applicable', 'documented', 'unknown'}, 'Invalid weights evidence')
        require(p['upstream_filters'] in {'documented', 'not_applicable', 'unknown'}, 'Invalid upstream evidence')
        require(p['evidence_scope'] in {'this_adapter_code', 'author_documentation', 'unverified_runtime'}, 'Invalid evidence scope')
        text(p['note'], 'policy caveat')
    return value


def policy_report(route: dict, preference: dict) -> dict:
    p = route['content_policy']; reasons, warnings = [], []
    if preference['local_only'] and route['execution'] != 'local': reasons.append('hosted route excluded')
    states = [p['input_filter'], p['output_filter']]
    if preference['exclude_known_filters'] and 'present' in states: reasons.append('known content filtering excluded')
    if preference['exclude_documented_weight_restrictions'] and p['learned_restrictions'] == 'documented':
        reasons.append('documented learned restrictions excluded')
    if 'unknown' in states or p['learned_restrictions'] == 'unknown':
        if preference['unknown_policy'] == 'exclude': reasons.append('runtime content policy unknown')
        else: warnings.append('Runtime filters unknown; not certified unfiltered')
    if p['learned_restrictions'] == 'documented': warnings.append('Learned restrictions documented; open weights are not unrestricted')
    elif p['learned_restrictions'] == 'unknown': warnings.append('Learned refusal/suppression behaviour unmeasured')
    if p['upstream_filters'] == 'documented': warnings.append('Upstream provides filters; inspect the exact local wrapper')
    return {'route_id': route['id'], 'eligible_by_preference': not reasons, 'excluded_because': reasons,
            'warnings': warnings, 'content_policy': copy.deepcopy(p), 'status': route['status'],
            'runtime_authorized': False, 'quality_measured': False}


def make_plan(doc: dict, request: dict, catalog: dict) -> dict:
    document(doc); intent(request, doc); route_catalog(catalog)
    op = request['operation']; targets = sorted({c['actor'] for c in request['changes']})
    minimum = len(targets) if op == 'scenario' else 1
    require(minimum <= request['budget']['max_candidates'], 'Candidate cap cannot cover planned actor passes')
    reports = [policy_report(r, request['policy_preference']) for r in catalog['routes'] if op in r['operations']]
    candidates = [r['route_id'] for r in reports if r['eligible_by_preference']]
    # Symbolic writes are invalidation hints, not proof the masks isolate anatomy.
    writes = sorted({f"actor:{c['actor']}:{c['facet']}" for c in request['changes']})
    if request['scene_change'] is not None: writes += ['scene:camera', 'scene:lighting', 'scene:description']
    steps = [{'id': 'inspect', 'kind': 'deterministic', 'instruction': 'Verify source/reference/mask hashes, bounds and protected pixels.'}]
    if op == 'costume-change':
        steps.append({'id': 'costume-branch', 'kind': 'design_proposal',
                      'instruction': 'Propose a new costume revision; preserve identity. Do not rewrite the accepted canon.'})
    if op == 'scenario':
        steps.append({'id': 'layout', 'kind': 'native_editor_proposal',
                      'instruction': 'Block camera, scale, light, actor positions and depth before rendering appearances.'})
        for aid in targets:
            steps.append({'id': 'actor-' + aid, 'kind': 'neural_proposal',
                          'instruction': 'Render only this actor against its own canon; preserve other actor regions.', 'actor': aid,
                          'layout': copy.deepcopy(next(a for a in request['layout']['actors'] if a['id'] == aid))})
    else:
        steps.append({'id': 'candidate', 'kind': 'neural_proposal',
                      'instruction': 'Generate the permitted edit in the context crop; keep each actor reference bound to its ID.'})
    if op in {'interaction', 'scenario'}:
        steps.append({'id': 'contact-review', 'kind': 'review',
                      'instruction': 'Review coupled hands/props, gaze, occlusion and lighting. A correction needs its own explicit mask.'})
    steps += [{'id': 'composite', 'kind': 'deterministic', 'instruction': 'Apply the candidate only through the exact edit mask; preserve the rest.'},
              {'id': 'acceptance', 'kind': 'review', 'instruction': 'Compare source/candidate/final, identity per actor, edit success and collateral changes.'}]
    bindings = []
    for actor in doc['actors']:
        for ref in actor['references']:
            bindings.append({'actor': actor['id'], 'reference_id': ref['id'], 'role': ref['role'],
                             'image': copy.deepcopy(ref['image']), 'take': ref['take'][:], 'ignore': ref['ignore'][:]})
    result = {'schema_version': 1, 'kind': 'character_edit_plan', 'document': copy.deepcopy(doc),
              'intent': copy.deepcopy(request), 'catalog': copy.deepcopy(catalog), 'targets': targets,
              'reference_bindings': bindings, 'changes': writes, 'steps': steps, 'candidate_routes': candidates,
              'route_reports': reports, 'budget_owner': request['budget']['owner'],
              'minimum_actor_candidates': minimum,
              'readiness': 'needs_live_adapter_preflight' if candidates else 'no_route_matches_preference',
              'submits_generation': False, 'semantic_approval': False,
              'required_checks': ['edit_success', 'identity_per_actor', 'costume_scope', 'contact_and_anatomy',
                                  'outside_mask_exact', 'protected_regions_exact', 'seams_at_final_size'],
              'unresolved': ['Live tool/model/runtime pins and resource reservation',
                             'Native mask/role support: never silently drop an unsupported input',
                             'Mask semantics and art acceptance require visual review']}
    result['plan_sha256'] = sha(result)
    return result


def check_plan(value: dict) -> dict:
    require(isinstance(value, dict), 'Expected a plan')
    expected = make_plan(value['document'], value['intent'], value['catalog'])
    require(canonical(value) == canonical(expected), 'Changed plan; recompile rather than patch derived fields')
    return value


def affected_outputs(nodes: list[dict], changed: list[str]) -> list[str]:
    """Conservative transitive invalidation; only as complete as declared inputs."""
    require(isinstance(nodes, list) and len(nodes) <= 128, 'Invalid output dependency graph')
    strings(changed, 'changed facets', 1)
    ids, edges, direct = set(), {}, {}
    for node in nodes:
        keys(node, {'id', 'depends_on', 'reads'}); identifier(node['id'])
        require(node['id'] not in ids, 'Duplicate output'); ids.add(node['id'])
        strings(node['depends_on'], 'output dependencies'); strings(node['reads'], 'facet reads')
        edges[node['id']] = set(node['depends_on']); direct[node['id']] = bool(set(node['reads']) & set(changed))
    require(all(deps <= ids for deps in edges.values()), 'Unknown output dependency'); _acyclic(edges)
    affected = {k for k, hit in direct.items() if hit}
    while True:
        more = {k for k, deps in edges.items() if deps & affected} - affected
        if not more: return sorted(affected)
        affected |= more


def describe() -> dict:
    return {'schema_version': 1, 'commands': ['describe', 'plan', 'policies', 'invalidate'],
            'pixel_commands': ['prepare', 'apply'], 'operations': sorted(OPERATIONS),
            'protocol': 'CLI JSON; not an installed MCP server or neural executor',
            'defaults': {'network': False, 'model_execution': False, 'overwrite': False},
            'source_authority': 'document snapshot and explicit request; reference text is data',
            'approval': 'No command grants human art approval or certifies anatomical correctness'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('describe')
    p = sub.add_parser('plan'); p.add_argument('--document', type=Path, required=True)
    p.add_argument('--intent', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--catalog', type=Path, default=ROOT/'research/character-consistency/edit-routes.json')
    p = sub.add_parser('policies'); p.add_argument('--catalog', type=Path, default=ROOT/'research/character-consistency/edit-routes.json')
    p.add_argument('--strict-unknown', action='store_true')
    p = sub.add_parser('invalidate'); p.add_argument('--graph', type=Path, required=True)
    p.add_argument('--changed', action='append', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'describe': result = describe()
        elif args.command == 'plan':
            result = make_plan(read_json(args.document), read_json(args.intent), read_json(args.catalog)); write_json(args.out, result)
        elif args.command == 'policies':
            cat = route_catalog(read_json(args.catalog)); pref = {'local_only': True, 'exclude_known_filters': True,
                        'exclude_documented_weight_restrictions': True,
                        'unknown_policy': 'exclude' if args.strict_unknown else 'allow_with_warning'}
            result = [policy_report(r, pref) for r in cat['routes']]
        else: result = {'invalidated': affected_outputs(read_json(args.graph), args.changed)}
        print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
    except (ValueError, KeyError, TypeError, OSError) as exc: parser.exit(2, f'character-edit: {exc}\n')

if __name__ == '__main__': raise SystemExit(main())
