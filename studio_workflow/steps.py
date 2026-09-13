"""Named step projections over API nodes, not a second graph or native subgraph."""
from __future__ import annotations
import copy
from .core import ID, RESERVED, link, need

MAX_STEPS = 64
MAX_CONTROLS = 32


def _id(value):
    need(isinstance(value, str) and bool(ID.fullmatch(value)) and value not in RESERVED, 'Invalid step/node identifier')
    return value


def validate_steps(doc):
    steps = doc.get('steps', [])
    need(isinstance(steps, list) and len(steps) <= MAX_STEPS, 'Use at most 64 steps')
    ids, members = set(), set()
    for step in steps:
        need(isinstance(step, dict) and set(step) == {'id', 'name', 'description', 'nodes', 'controls'}, 'Invalid step fields')
        key = _id(step['id']); need(key not in ids, 'Duplicate step ID'); ids.add(key)
        need(isinstance(step['name'], str) and 0 < len(step['name'].strip()) <= 120, 'Step name required (120 characters)')
        need(isinstance(step['description'], str) and len(step['description']) <= 2000, 'Step description too long')
        nodes = step['nodes']
        need(isinstance(nodes, list) and all(isinstance(x, str) and x in doc['nodes'] for x in nodes), 'Unknown step node')
        need(len(set(nodes)) == len(nodes) and not members.intersection(nodes), 'A node can belong to only one step')
        members.update(nodes)
        controls = step['controls']; seen = set()
        need(isinstance(controls, list) and len(controls) <= MAX_CONTROLS, 'Use at most 32 exposed controls per step')
        for control in controls:
            need(isinstance(control, dict) and set(control) == {'name', 'node', 'input'}, 'Invalid exposed control')
            need(isinstance(control['name'], str) and 0 < len(control['name'].strip()) <= 120, 'Control name required')
            need(control['node'] in nodes, 'Control must belong to a node in this step')
            field = control['input']
            need(isinstance(field, str) and 0 < len(field) <= 256 and field not in RESERVED, 'Invalid control input name')
            pair = (control['node'], field); need(pair not in seen, 'Duplicate exposed control'); seen.add(pair)
            # An optional/dynamic input can be absent in a draft. The UI looks it
            # up in the active schema; unknown fields stay visible as diagnostics.
    return steps


def apply_step_command(doc, command):
    from .commands import fields
    op = command['op']
    steps = doc.setdefault('steps', [])
    if op == 'put_step':
        fields(command, ('op', 'step'))
        step = copy.deepcopy(command['step'])
        need(isinstance(step, dict), 'Step object required'); key = _id(step.get('id'))
        found = next((i for i, item in enumerate(steps) if item['id'] == key), None)
        if found is None: steps.append(step)
        else: steps[found] = step
        return
    key = _id(command.get('id'))
    step = next((item for item in steps if item['id'] == key), None)
    need(step is not None, 'Unknown step')
    if op == 'remove_step':
        fields(command, ('op', 'id'))
        doc['steps'] = [item for item in steps if item['id'] != key]
        # Removing the grouping never removes or enables its nodes.
    elif op == 'set_step_enabled':
        fields(command, ('op', 'id', 'enabled')); need(type(command['enabled']) is bool, 'enabled must be boolean')
        doc['disabled'] = [node for node in doc['disabled'] if node not in step['nodes']]
        if not command['enabled']: doc['disabled'].extend(step['nodes'])
    elif op == 'duplicate_step':
        fields(command, ('op', 'id', 'new_id', 'name', 'node_ids'))
        new_id = _id(command['new_id']); need(all(item['id'] != new_id for item in steps), 'Step already exists')
        mapping = command['node_ids']
        need(isinstance(mapping, dict) and set(mapping) == set(step['nodes']), 'Map every step node explicitly')
        new_nodes = [_id(x) for x in mapping.values()]
        need(len(set(new_nodes)) == len(new_nodes) and not set(new_nodes).intersection(doc['nodes']), 'New node IDs must be unique')
        duplicate = copy.deepcopy(step); duplicate.update(id=new_id, name=command['name'])
        duplicate['nodes'] = [mapping[x] for x in step['nodes']]
        for control in duplicate['controls']: control['node'] = mapping[control['node']]
        for old, new in mapping.items():
            node = copy.deepcopy(doc['nodes'][old])
            for field, value in node['inputs'].items():
                if link(value) and value[0] in mapping: node['inputs'][field] = [mapping[value[0]], value[1]]
            doc['nodes'][new] = node
            if old in doc['bypass']: doc['bypass'][new] = copy.deepcopy(doc['bypass'][old])
            if old in doc['disabled']: doc['disabled'].append(new)
            if old in doc['positions']:
                doc['positions'][new] = [min(100000, value + 40) for value in doc['positions'][old]]
        # External sources remain shared; no outside consumer is rewired. Copies
        # of output nodes are intentionally NOT selected outputs.
        steps.append(duplicate)
    else:
        raise ValueError('Unknown step command')


def remove_member(doc, key):
    for step in doc.get('steps', []):
        step['nodes'] = [node for node in step['nodes'] if node != key]
        step['controls'] = [c for c in step['controls'] if c['node'] != key]
