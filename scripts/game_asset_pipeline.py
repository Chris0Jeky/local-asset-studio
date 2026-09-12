"""Agent-facing asset planning and evidence checks. No network or generation submission.
CLI JSON is data, never code. Python 3.12+. See docs/game-assets/AGENT-CONTRACT.md.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 4 * 1024 * 1024
ROLES = {'identity', 'style', 'pose', 'costume', 'composition', 'geometry', 'motion', 'mask'}
KINDS = {'image', 'video', 'mesh', 'rig', 'document'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(items):
    result = {}
    for k, v in items:
        require(k not in result, f'Duplicate JSON key: {k}')
        result[k] = v
    return result


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    require(len(raw) <= LIMIT, 'JSON exceeds 4 MiB')
    def reject(value):
        raise ValueError(f'Non-finite number: {value}')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def text(value, name):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 12000, f'Invalid {name}')


def slug(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{1,63}', value), 'Invalid ID')


def relative(value):
    text(value, 'relative path')
    require('\\' not in value and ':' not in value and '\0' not in value, 'Use portable relative paths')
    p = PurePosixPath(value)
    require(not p.is_absolute() and '..' not in p.parts and p.parts, 'Path escapes workspace')
    require(all(part not in {'.', ''} for part in value.split('/')), 'Non-canonical relative path')
    return p


def inside(root, value):
    relative(value)
    base = Path(root).resolve()
    path = (base / value).resolve()
    require(path.is_relative_to(base), 'Symlink escapes workspace')
    require(path.is_file(), f'Artifact missing: {value}')
    return path


def integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, f'{name}: expected integer {low}..{high}')


def catalog():
    result = read_json(ROOT / 'research/game-assets/routes.json')
    require(result.get('schema_version') == 1 and isinstance(result.get('routes'), dict), 'Invalid route catalog')
    return result


def validate_brief(brief, routes):
    require(isinstance(brief, dict) and brief.get('schema_version') == 1, 'Expected brief schema 1')
    slug(brief.get('asset_id')); text(brief.get('description'), 'description')
    require(brief.get('route') in routes['routes'], 'Unknown route; use the routes command')
    refs = brief.get('references', [])
    require(isinstance(refs, list) and len(refs) <= 12, 'At most 12 reference records')
    ids = set()
    for ref in refs:
        require(isinstance(ref, dict), 'Reference must be an object')
        slug(ref.get('id')); require(ref['id'] not in ids, 'Duplicate reference ID'); ids.add(ref['id'])
        require(ref.get('role') in ROLES and ref.get('kind') in KINDS, 'Unknown reference role/kind')
        relative(ref.get('path'))
        require(re.fullmatch('[0-9a-f]{64}', str(ref.get('sha256', ''))), 'Each reference needs a SHA-256')
        for field in ('take', 'ignore'):
            require(isinstance(ref.get(field), list), f'Reference {field} must be a list')
            for value in ref[field]: text(value, field)
    target = brief.get('target')
    require(isinstance(target, dict), 'Explicit target object required')
    require(target.get('engine') in {'godot', 'unity', 'unreal', 'web', 'generic'}, 'Unknown target engine')
    outputs = target.get('outputs')
    require(isinstance(outputs, list) and outputs, 'Declare desired output files/types')
    for value in outputs: text(value, 'output')
    require(isinstance(brief.get('constraints'), list), 'Declare constraints, even if empty')
    for value in brief['constraints']: text(value, 'constraint')
    budget = brief.get('budget', {})
    integer(budget.get('generation_attempts'), 1, 256, 'generation_attempts')
    integer(budget.get('repair_attempts_per_stage'), 0, 3, 'repair_attempts_per_stage')
    require(budget.get('allow_paid_services') is False, 'This local starter does not authorize paid services')
    return brief


def reference_prompt(brief):
    lines = [brief['description'], '\nReference contributions (not interchangeable):']
    image_index = 0
    for ref in brief.get('references', []):
        if ref['kind'] == 'image': image_index += 1
        # TextEncodeQwenImageEditPlus injects "Picture {i+1}:" before the brief; name the same slots.
        label = f'Picture {image_index}' if ref['kind'] == 'image' else ref['id']
        lines.append(f"{label} [{ref['role']}]: take {'; '.join(ref['take']) or 'only the named role'}. "
                     f"Do not copy {'; '.join(ref['ignore']) or 'unrequested features'}.")
    lines.append('Constraints: ' + '; '.join(brief['constraints']))
    lines.append('Preserve approved identity and costume unless the brief explicitly requests a change.')
    return '\n'.join(lines)


def make_plan(brief, routes):
    validate_brief(brief, routes)
    plan_brief = copy.deepcopy(brief)
    route = routes['routes'][plan_brief['route']]
    tasks = []
    for stage in route['stages']:
        tasks.append({**copy.deepcopy(stage), 'state': 'pending',
                      'budget': copy.deepcopy(plan_brief['budget']),
                      'target': copy.deepcopy(plan_brief['target'])})
    result = {'schema_version': 1, 'kind': 'agent_asset_plan', 'submits_generation': False,
              'brief': plan_brief, 'brief_sha256': sha(plan_brief), 'routes_sha256': sha(routes),
              'reference_instructions': reference_prompt(plan_brief), 'tasks': tasks,
              'contract': 'External agent performs tasks. Receipts are hashed attestations, not art judgment.'}
    result['plan_sha256'] = sha(result)
    return result


def check_plan(plan):
    require(isinstance(plan, dict) and plan.get('kind') == 'agent_asset_plan', 'Not an asset plan')
    copy_plan = {k: v for k, v in plan.items() if k != 'plan_sha256'}
    require(plan.get('plan_sha256') == sha(copy_plan), 'Plan hash mismatch')
    require(plan.get('brief_sha256') == sha(plan.get('brief')), 'Brief hash mismatch')
    require(isinstance(plan.get('tasks'), list) and 1 <= len(plan['tasks']) <= 64, 'Expected 1..64 tasks')
    seen = set()
    for task in plan['tasks']:
        require(isinstance(task, dict), 'Task must be an object')
        require(isinstance(task.get('depends_on'), list), 'Task dependencies must be a list')
        require(isinstance(task.get('outputs'), list) and task['outputs'], 'Task outputs required')
        require(all(isinstance(v, str) and v for v in task['outputs']), 'Output roles must be text')
        require(len(set(task['outputs'])) == len(task['outputs']), 'Duplicate output role')
        slug(task['id']); require(task['id'] not in seen, 'Duplicate task')
        require(set(task['depends_on']) <= seen, 'Invalid dependency ordering or cycle')
        seen.add(task['id'])
    return plan


def next_tasks(plan, receipts, workspace):
    check_plan(plan)
    require(isinstance(receipts, list), 'Receipts must be an array')
    for ref in plan['brief'].get('references', []):
        require(file_sha(inside(workspace, ref['path'])) == ref['sha256'], f"Changed reference: {ref['id']}")
    by_id = {}
    task_ids = {t['id'] for t in plan['tasks']}
    for receipt in receipts:
        require(isinstance(receipt, dict), 'Receipt must be an object')
        key = receipt.get('task_id')
        require(key in task_ids and key not in by_id, 'Unknown or duplicate receipt')
        require(receipt.get('plan_sha256') == plan['plan_sha256'], 'Receipt belongs to another plan')
        require(receipt.get('receipt_sha256') == sha({k: v for k, v in receipt.items() if k != 'receipt_sha256'}),
                'Receipt hash mismatch')
        by_id[key] = receipt
    done = set()
    for task in plan['tasks']:
        receipt = by_id.get(task['id'])
        if not receipt: continue
        require(set(task['depends_on']) <= done, 'Receipt cannot bypass a prerequisite')
        text(receipt.get('reviewer'), 'reviewer'); text(receipt.get('note'), 'evidence note')
        require(receipt.get('accepted') is True, 'Only accepted receipts unlock dependents')
        artifacts = receipt.get('artifacts')
        require(isinstance(artifacts, list) and len(artifacts) == len(task['outputs']), 'Output count mismatch')
        require(all(isinstance(a, dict) for a in artifacts), 'Artifact must be an object')
        require([a.get('role') for a in artifacts] == task['outputs'], 'Output roles mismatch')
        for artifact in artifacts:
            p = inside(workspace, artifact['path'])
            require(p.stat().st_size > 0 and file_sha(p) == artifact['sha256'], 'Changed or empty artifact')
        done.add(task['id'])
    ready = [t for t in plan['tasks'] if t['id'] not in done and set(t['depends_on']) <= done]
    return {'plan_sha256': plan['plan_sha256'], 'completed': sorted(done), 'ready': ready,
            'finished': len(done) == len(plan['tasks']),
            'warning': 'Reviewer identities and semantic quality are attestations, not authenticated or machine-certified.'}


def receipt_for(plan, receipts, workspace, task_id, paths, reviewer, note):
    state = next_tasks(plan, receipts, workspace)
    task = next((t for t in state['ready'] if t['id'] == task_id), None)
    require(task is not None, 'Task is not ready')
    require(len(paths) == len(task['outputs']), 'Provide one artifact per listed output role, in order')
    text(reviewer, 'reviewer'); text(note, 'evidence note')
    result = {'schema_version': 1, 'task_id': task_id, 'plan_sha256': plan['plan_sha256'],
              'accepted': True, 'reviewer': reviewer, 'note': note, 'artifacts': []}
    for role, value in zip(task['outputs'], paths):
        p = inside(workspace, value); require(p.stat().st_size > 0, 'Empty artifact')
        result['artifacts'].append({'role': role, 'path': value, 'sha256': file_sha(p)})
    result['receipt_sha256'] = sha(result)
    return result


def expanded_input_contract(contract, live_inputs):
    """Resolve V3 dynamic-combo branches using ComfyUI's dotted input names."""
    fields, required = {}, set()
    def visit(inputs, prefix='', depth=0):
        require(depth <= 8, 'Dynamic input nesting exceeds eight levels')
        for group in ('required', 'optional'):
            for name, spec in inputs.get(group, {}).items():
                key = prefix + name
                fields[key] = spec
                if group == 'required': required.add(key)
                if spec[0] == 'COMFY_DYNAMICCOMBO_V3':
                    options = spec[1].get('options', [])
                    selected = next((o for o in options if o['key'] == live_inputs.get(key)), None)
                    require(selected is not None, 'Unknown dynamic input option: '+key)
                    fields[key] = ['COMBO', dict(spec[1], options=[o['key'] for o in options])]
                    visit(selected['inputs'], key+'.', depth+1)
    visit(contract.get('input', {}))
    return fields, required


def graph_check(graph, info=None):
    require(isinstance(graph, dict) and 0 < len(graph) <= 512, 'Expected bounded API graph')
    edges = {}
    for key, node in graph.items():
        require(isinstance(key, str) and isinstance(node, dict), 'Invalid node')
        text(node.get('class_type'), 'class_type')
        require(isinstance(node.get('inputs'), dict), 'Missing inputs')
        edges[key] = set()
        contract = None
        if info is not None:
            require(node['class_type'] in info, f"Missing node class: {node['class_type']}")
            contract = info[node['class_type']]
            fields, required = expanded_input_contract(contract, node['inputs'])
            require(required <= set(node['inputs']), 'Missing required input')
            require(set(node['inputs']) <= set(fields), 'Unknown input (snapshot may be stale)')
        for name, value in node['inputs'].items():
            descriptor = fields[name] if info is not None else None
            expected = descriptor[0] if descriptor else None
            enum = None
            if info is not None:
                require(isinstance(descriptor, list) and descriptor, f'Invalid input descriptor: {name}')
                require(isinstance(expected, (str, list)), f'Invalid input descriptor: {name}')
                if isinstance(expected, list):
                    enum = expected
                elif expected == 'COMBO':
                    require(len(descriptor) > 1 and isinstance(descriptor[1], dict),
                            f'Invalid COMBO enum: {name}')
                    enum = descriptor[1].get('options')
                if enum is not None:
                    require(isinstance(enum, list) and enum and all(
                        type(option) in {str, int, float, bool}
                        and (type(option) is not float or math.isfinite(option)) for option in enum),
                        f'Invalid COMBO enum: {name}')
            if isinstance(value, list):
                require(len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int
                        and value[1] >= 0 and value[0] in graph, 'Invalid graph link')
                edges[key].add(value[0])
                if info is not None:
                    source = info.get(graph[value[0]]['class_type'], {})
                    outputs = source.get('output', [])
                    require(value[1] < len(outputs), 'Output index out of range')
                    require(isinstance(expected, str) and (expected == outputs[value[1]] or expected == '*'),
                            'Linked input type mismatch')
            else:
                require(type(value) in {str, int, float, bool}, 'Unsupported literal')
                require(not isinstance(value, float) or math.isfinite(value), 'Non-finite graph literal')
                if info is not None:
                    if enum is not None: require(value in enum, f'Unavailable enum: {name}')
                    elif expected in {'INT', 'FLOAT', 'STRING', 'BOOLEAN'}:
                        valid = {'INT': type(value) is int, 'FLOAT': type(value) in {int, float},
                                 'STRING': isinstance(value, str), 'BOOLEAN': type(value) is bool}
                        require(valid[expected], f'Literal type mismatch: {name}')
                        constraints = fields[name][1] if len(fields[name]) > 1 else {}
                        if expected in {'INT', 'FLOAT'}:
                            require('min' not in constraints or value >= constraints['min'], 'Below input minimum')
                            require('max' not in constraints or value <= constraints['max'], 'Above input maximum')
                    else: raise ValueError(f'Opaque input {name} requires a typed link')
    remaining = set(edges); visited = set()
    while remaining:
        ready = {k for k in remaining if edges[k] <= visited}
        require(ready, 'Graph contains a cycle')
        visited |= ready; remaining -= ready
    return {'nodes': len(graph), 'static_topology': 'passed', 'node_snapshot_checked': info is not None,
            'inference_verified': False}


def qwen_variants(source):
    """Derive, never submit, 1/2/3-ref graphs from the repo's known Qwen API graph."""
    graph_check(source)
    expected = {'4': 'LoadImage', '5': 'ImageScale', '6': 'TextEncodeQwenImageEditPlus',
                '7': 'TextEncodeQwenImageEditPlus', '11': 'KSampler', '13': 'SaveImage'}
    require(all(source.get(k, {}).get('class_type') == v for k, v in expected.items()), 'Unexpected baseline graph')
    require('16' not in source and '17' not in source, 'Reserved node ID collision')
    require(all('image2' not in source[k]['inputs'] and 'image3' not in source[k]['inputs'] for k in ('6','7')),
            'Baseline already contains extra references')
    result = {}
    for count in (1, 2, 3):
        graph = copy.deepcopy(source)
        graph['4']['inputs']['image'] = 'asset-identity.png'
        graph['6']['inputs']['prompt'] = ('Use the character identity and costume from Picture 1. '
            + ('Use only the pose from Picture 2, not its identity or clothes. ' if count >= 2 else '')
            + ('Use only the rendering style and palette from Picture 3. ' if count == 3 else '')
            + 'Create a non-explicit fantasy portrait. Preserve the approved character design.')
        for index, name in ((2, 'pose'), (3, 'style')):
            if index <= count:
                node_id = str(14 + index)
                graph[node_id] = {'class_type': 'LoadImage', 'inputs': {'image': f'asset-{name}.png'}}
                for encoder in ('6', '7'):
                    graph[encoder]['inputs'][f'image{index}'] = [node_id, 0]
        graph['13']['inputs']['filename_prefix'] = f'GameAssets/Qwen-{count}ref'
        graph_check(graph)
        result[f'qwen-{count}ref-api.json'] = graph
    return result


def write_json(value, path=None):
    payload = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    if path:
        with Path(path).open('x', encoding='utf-8') as stream: stream.write(payload)
    else: print(payload, end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('routes')
    p = sub.add_parser('plan'); p.add_argument('brief'); p.add_argument('--out', required=True)
    for name in ('next', 'receipt'):
        p = sub.add_parser(name); p.add_argument('--plan', required=True)
        p.add_argument('--receipts'); p.add_argument('--workspace', required=True)
        if name == 'receipt':
            p.add_argument('--task', required=True); p.add_argument('--artifact', action='append', required=True)
            p.add_argument('--reviewer', required=True); p.add_argument('--note', required=True)
            p.add_argument('--out', required=True)
    p = sub.add_parser('graph-check'); p.add_argument('graph'); p.add_argument('--object-info')
    p = sub.add_parser('qwen-variants'); p.add_argument('--source', default=str(ROOT / 'workflows/api/qwen-api.json'))
    p.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'routes': write_json(catalog())
        elif args.cmd == 'plan': write_json(make_plan(read_json(args.brief), catalog()), args.out)
        elif args.cmd in {'next', 'receipt'}:
            plan = read_json(args.plan); receipts = read_json(args.receipts) if args.receipts else []
            if args.cmd == 'next': write_json(next_tasks(plan, receipts, args.workspace))
            else:
                receipt = receipt_for(plan, receipts, args.workspace, args.task, args.artifact, args.reviewer, args.note)
                write_json(receipts + [receipt], args.out)
        elif args.cmd == 'graph-check':
            write_json(graph_check(read_json(args.graph), read_json(args.object_info) if args.object_info else None))
        else:
            source = read_json(args.source); outputs = qwen_variants(source)
            folder = Path(args.out); folder.mkdir(parents=True, exist_ok=False)
            for name, graph in outputs.items(): write_json(graph, folder / name)
            write_json({'baseline_sha256': sha(source), 'files': list(outputs), 'inference_verified': False}, folder / 'provenance.json')
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
