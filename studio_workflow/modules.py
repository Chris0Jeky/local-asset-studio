"""Portable, inert Step projections. Explicit imports use the existing reducer.

This is not a native ComfyUI subgraph format. Provenance is retained evidence,
not authentication, model compatibility, asset availability or run permission.
"""
from __future__ import annotations
import copy
import re
from .core import canonical, decode, digest, document, link, need
from .commands import fields, identifier

FORMAT = 'studio.workflow-module/v1'
MAX_MODULE_BYTES = 256 * 1024
MAX_IMPORTS = 64
HASH = re.compile(r'[0-9a-f]{64}\Z')


def _boundary(doc):
    ports = []
    for key, node in sorted(doc['nodes'].items()):
        for field, value in sorted(node['inputs'].items()):
            if link(value) and value[0] not in doc['nodes']:
                identifier(value[0])
                need(value[1] <= 9999, 'External output index exceeds the module limit')
                ports.append({'id': 'input' + str(len(ports) + 1), 'node': key,
                              'input': field, 'source': copy.deepcopy(value)})
    return ports


def validate_module(value):
    need(isinstance(value, dict), 'Module object required')
    raw = canonical(value)
    need(len(raw) <= MAX_MODULE_BYTES, 'Module exceeds 256 KiB')
    value = decode(raw)
    fields(value, ('format', 'document', 'inputs', 'origin'))
    need(value['format'] == FORMAT, 'Unsupported module format')
    doc = document(value['document'])
    need(doc['revision'] == 0, 'A portable module has revision zero')
    steps = doc.get('steps', [])
    need(len(steps) == 1 and set(steps[0]['nodes']) == set(doc['nodes']),
         'A module must contain exactly one Step covering every node')
    need(doc['name'] == steps[0]['name'], 'Module name must match its Step')
    # Equality is canonical-byte based: JSON booleans must not alias integers.
    need(canonical(value['inputs']) == canonical(_boundary(doc)), 'Module boundary must list every external input exactly')
    origin = value['origin']
    fields(origin, ('document_id', 'revision', 'document_sha256', 'step_id'))
    if origin['document_id'] is not None: identifier(origin['document_id'])
    need(type(origin['revision']) is int and 0 <= origin['revision'] <= 2**53 - 1, 'Invalid module source revision')
    need(isinstance(origin['document_sha256'], str) and HASH.fullmatch(origin['document_sha256']), 'Invalid module source digest')
    need(origin['step_id'] == steps[0]['id'], 'Module source Step differs')
    return value


def export_module(source, step_id, *, document_id=None):
    source = document(source); identifier(step_id)
    if document_id is not None: identifier(document_id)
    step = next((row for row in source.get('steps', []) if row['id'] == step_id), None)
    need(step is not None, 'Unknown Step for export')
    members = set(step['nodes'])
    doc = copy.deepcopy(source)
    doc.update(name=step['name'], revision=0, nodes={key: node for key, node in doc['nodes'].items() if key in members},
               outputs=[key for key in doc['outputs'] if key in members],
               disabled=[key for key in doc['disabled'] if key in members],
               bypass={key: value for key, value in doc['bypass'].items() if key in members},
               positions={key: value for key, value in doc['positions'].items() if key in members}, steps=[copy.deepcopy(step)])
    return validate_module({'format': FORMAT, 'document': doc, 'inputs': _boundary(doc),
                            'origin': {'document_id': document_id, 'revision': source['revision'],
                                       'document_sha256': digest(source), 'step_id': step_id}})


def insert_module(source, command):
    fields(command, ('op', 'module', 'module_sha256', 'node_ids', 'step_id', 'name', 'bindings'))
    need(command['op'] == 'import_module', 'Expected import_module')
    doc = document(source); module = validate_module(command['module'])
    need(isinstance(command['module_sha256'], str) and HASH.fullmatch(command['module_sha256'])
         and command['module_sha256'] == digest(module), 'Reviewed module digest changed')
    inner = module['document']; step_id = identifier(command['step_id'])
    need(all(doc[key] == inner[key] for key in ('backend_id', 'schema_sha256')),
         'Module backend/schema differs; explicitly review the environment before import')
    need(all(row['id'] != step_id for row in doc.get('steps', [])), 'Step already exists')
    name = command['name']
    need(isinstance(name, str) and 0 < len(name.strip()) <= 120, 'Imported Step name required (120 characters)')
    mapping = command['node_ids']
    need(isinstance(mapping, dict) and set(mapping) == set(inner['nodes']), 'Map every module node explicitly')
    new_ids = [identifier(key) for key in mapping.values()]
    need(len(new_ids) == len(set(new_ids)) and not set(new_ids).intersection(doc['nodes']), 'Imported node IDs must be new and unique')
    bindings = command['bindings']
    need(isinstance(bindings, dict) and set(bindings) == {row['id'] for row in module['inputs']},
         'Bind every external module input explicitly')
    for value in bindings.values():
        need(link(value) and value[0] in doc['nodes'] and value[1] <= 9999,
             'Module input must connect to a pre-existing target node and bounded output')
    boundary = {(row['node'], row['input']): bindings[row['id']] for row in module['inputs']}
    for old, new in mapping.items():
        node = copy.deepcopy(inner['nodes'][old])
        for field, value in node['inputs'].items():
            if (old, field) in boundary: node['inputs'][field] = copy.deepcopy(boundary[(old, field)])
            elif link(value): node['inputs'][field] = [mapping[value[0]], value[1]]
        doc['nodes'][new] = node
        for field in ('bypass', 'positions'):
            if old in inner[field]: doc[field][new] = copy.deepcopy(inner[field][old])
        if old in inner['disabled']: doc['disabled'].append(new)
    step = copy.deepcopy(inner['steps'][0]); step.update(id=step_id, name=name)
    step['nodes'] = [mapping[key] for key in step['nodes']]
    for control in step['controls']: control['node'] = mapping[control['node']]
    doc.setdefault('steps', []).append(step)
    # Existing source declarations are never coerced or replaced to fit ours.
    lineage = doc.setdefault('source', {})
    need(isinstance(lineage, dict), 'Opaque source cannot accept module provenance; preserve it and choose an explicit target')
    imports = lineage.setdefault('module_imports', [])
    need(isinstance(imports, list) and len(imports) < MAX_IMPORTS, 'Module import provenance is unavailable or full')
    imports.append({'format': 'studio.workflow-module-import/v1', 'step_id': step_id,
                    'module_sha256': command['module_sha256'], 'origin': copy.deepcopy(module['origin']),
                    'node_ids': copy.deepcopy(mapping), 'bindings': copy.deepcopy(bindings),
                    'source': copy.deepcopy(inner.get('source'))})
    # No copied output is selected; no outside consumer or input source is changed.
    return document(doc)
