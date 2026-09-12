"""Explicit proposal acceptance, guarded text bindings and experiment intent."""
import copy
from .schema import validate, need, fields, text, strings, digest, EDITABLE
from .compiler import compile_brief


def proposal(b, changes, observations=None, unknowns=None):
    observations = [] if observations is None else observations
    unknowns = [] if unknowns is None else unknowns
    validate(b); need(isinstance(changes, list) and len(changes) <= 16, 'At most sixteen proposals')
    seen = set()
    for c in changes:
        fields(c, ('field', 'value', 'reason', 'source'))
        need(c['field'] in EDITABLE and c['field'] not in seen, 'Invalid/duplicate proposed field'); seen.add(c['field'])
        text(c['reason'], 1000); text(c['source'], 100)
        if c['field'] in ('tags', 'avoid'): strings(c['value'], 80, 120)
        else: text(c['value'], 1000 if c['field'].startswith('facets.') else 4000)
        need(c['source'] == 'brief' or c['source'] in {r['id'] for r in b['references']}, 'Unknown evidence source')
        if c['source'] != 'brief':
            role = next(r['role'] for r in b['references'] if r['id'] == c['source'])
            permitted = {'identity': {'subject'}, 'costume': {'subject'}, 'pose': {'action','composition','motion'},
                         'style': {'style','palette','lighting','mood'}, 'composition': {'composition','camera'},
                         'motion': {'motion','action','camera'}, 'voice': {'voice'}, 'geometry': {'subject'}, 'mask': set()}
            need(c['field'].startswith('facets.') and c['field'].split('.')[1] in permitted[role], 'Proposal crosses reference-role boundary')
    need(isinstance(observations, list) and len(observations) <= 24, 'Invalid observations')
    for o in observations:
        fields(o, ('reference_id', 'description', 'uncertain'))
        need(o['reference_id'] in {r['id'] for r in b['references']} and type(o['uncertain']) is bool, 'Invalid observation')
        text(o['description'], 1000)
    strings(unknowns, 16, 1000)
    result = {'schema_version': 1, 'kind': 'intent_proposal', 'base_sha256': digest(b), 'changes': copy.deepcopy(changes),
              'observations': copy.deepcopy(observations), 'unknowns': list(unknowns), 'authority': 'untrusted_suggestion'}
    result['proposal_sha256'] = digest(result)
    return result


def apply_proposal(b, p, accepted_fields):
    validate(b)
    need(p['proposal_sha256'] == digest({k: v for k, v in p.items() if k != 'proposal_sha256'}), 'Proposal was modified')
    need(p['base_sha256'] == digest(b), 'Stale brief revision')
    proposal(b, p['changes'], p['observations'], p['unknowns'])
    strings(accepted_fields, 16, 100)
    need(len(set(accepted_fields)) == len(accepted_fields) and set(accepted_fields) <= {c['field'] for c in p['changes']}, 'Invalid accepted selection')
    q = copy.deepcopy(b); operations = []
    for c in p['changes']:
        field = c['field']
        if field not in accepted_fields: continue
        need(not any(field == lock or field.startswith(lock + '.') for lock in b['locked']), f'Locked field: {field}')
        target, key = (q['facets'], field.split('.')[1]) if field.startswith('facets.') else (q, field)
        operations.append({'field': field, 'before': copy.deepcopy(target.get(key)), 'after': copy.deepcopy(c['value'])})
        target[key] = copy.deepcopy(c['value'])
    validate(q)
    return {'intent': q, 'revision': digest(q), 'parent_revision': digest(b), 'operations': operations}


def bind_graph(artifact, graph, binding):
    """Preview only. Explicit registered text fields; never inference or sampler edits."""
    need(artifact['artifact_sha256'] == digest({k: v for k, v in artifact.items() if k != 'artifact_sha256'}), 'Changed compilation')
    need(artifact == compile_brief(artifact['intent'], artifact['profile']['id']), 'Profile/compiler drift; recompile')
    need(not artifact['errors'] and not artifact['reference_map'], 'Resolve errors/reference binding before text-only handoff')
    fields(binding, ('preset_id', 'profile_sha256', 'graph_sha256', 'bindings'))
    need(binding['profile_sha256'] == artifact['profile_sha256'] and binding['graph_sha256'] == digest(graph), 'Stale or wrong graph/profile')
    need(set(artifact['fields']) <= {'positive', 'negative'} and set(artifact['fields']) == set(binding['bindings']), 'Incomplete or non-text handoff')
    q = copy.deepcopy(graph); used = set()
    for key, target in binding['bindings'].items():
        need(isinstance(target, list) and len(target) == 2 and all(isinstance(x, str) for x in target), 'Invalid binding')
        node, field = target; need(tuple(target) not in used, 'Binding collision'); used.add(tuple(target))
        need(q[node]['class_type'] in ('CLIPTextEncode', 'TextEncodeQwenImageEditPlus', 'TextEncodeQwenImageEdit'), 'Unapproved text node class')
        need(field in ('text', 'prompt') and isinstance(q[node]['inputs'].get(field), str), 'Only existing text inputs may change')
        q[node]['inputs'][field] = artifact['fields'][key]
    return {'preset_id': binding['preset_id'], 'controls': copy.deepcopy(artifact['fields']), 'workflow_preview': q,
            'source_graph_sha256': digest(graph), 'generation_submitted': False,
            'note': 'Canonical graph hash is not Studio expected_template_sha256 (raw file hash). Recheck the file at submission.'}


def experiment_plan(b, profile_id, seeds, maximum=6):
    need(type(maximum) is int and 1 <= maximum <= 12, 'Experiment cap must be 1..12')
    need(isinstance(seeds, list) and 1 <= len(seeds) <= maximum and len(set(seeds)) == len(seeds), 'Invalid seed set')
    need(all(type(x) is int and 0 <= x < 2**63 for x in seeds), 'Invalid seed')
    a = compile_brief(b, profile_id)
    return {'kind': 'prompt_experiment', 'compiled': a, 'runs': [{'seed': x, 'state': 'proposed'} for x in seeds],
            'generation_submitted': False, 'compare': 'Fixed model/graph/reference bytes; include unchanged baseline and rejected outputs. Seeds do not align noise across model families.'}
