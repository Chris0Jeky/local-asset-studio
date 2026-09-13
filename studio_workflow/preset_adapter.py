"""Prove a workflow is a registered image recipe before issuing its normal ticket.

This is deliberately not an arbitrary-graph executor. Only catalog-bound scalar
edits are projected. The ordinary Studio preparation and worker remain authoritative.
"""
from __future__ import annotations

import copy
import hashlib
import math
import uuid
from .core import canonical, catalog, decode, digest, document, need
from .execution import NAMESPACE, prepare_ticket

# This adapter's declared subset, not an alternative runtime control allow-list.
# Studio.prepare still checks every projected control against the actual preset.
CONTROLS = ('positive', 'negative', 'width', 'height', 'seed', 'steps', 'cfg',
            'denoise', 'sampler', 'scheduler') + tuple(
    name for slot in ('lora', 'lora2', 'lora3', 'lora4', 'lora5', 'lora6')
    for name in (slot, slot + '_name'))
VERSION = 'studio.preset-projection/v1'


def equivalent(left, right):
    """JSON equality with exact numeric equality, never True == 1 or str coercion."""
    numeric = lambda x: type(x) is int or (type(x) is float and math.isfinite(x))
    if numeric(left) and numeric(right): return left == right
    if type(left) is not type(right): return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equivalent(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equivalent(a, b) for a, b in zip(left, right))
    return left == right


def graph_inputs(graph):
    """Only _meta is presentation. Class IDs, input names and values remain exact."""
    return {key: {'class_type': node['class_type'], 'inputs': node['inputs']}
            for key, node in graph.items()}


def project_document(value, preset, template, schema):
    """Pure projection; no file writes, schema discovery, preparation or dispatch."""
    doc = document(value)
    need(doc['backend_id'] == schema['backend_id'] == preset.get('backend_id', 'primary'),
         'Workflow and recipe must use the active environment')
    need(doc['schema_sha256'] == schema['schema_sha256'],
         'Node schema changed; refresh, review and explicitly accept it before preparing')
    need(preset.get('modality') == 'image', 'This adapter supports registered image recipes only')
    need(not any(preset.get(k) for k in ('reference', 'last_reference', 'reference_slots', 'requires_rgba_mask'))
         and not any(n.get('class_type') == 'LoadImage' for n in template.values()),
         'Reference workflows need an asset-lineage adapter; use Create and its registered recipe instead')
    need(not doc['disabled'],
         'Disabled nodes require the authored-graph executor; for a registered LoRA use its strength control at zero')
    need(set(doc['nodes']) == set(template),
         'Added or removed nodes cannot be projected into a registered recipe')
    for key, node in template.items():
        definition = schema['nodes'].get(node.get('class_type'))
        need(definition is not None and not definition.get('schema_errors'),
             'Recipe node is unavailable or has an invalid schema: ' + key)
        proposed = doc['nodes'][key]
        need(proposed['class_type'] == node['class_type'], 'Node class changed: ' + key)
        need(proposed['inputs'].keys() == node['inputs'].keys(), 'Input fields changed: ' + key)
    outputs = {k for k, n in template.items() if schema['nodes'][n['class_type']]['output_node']}
    need(bool(outputs) and set(doc['outputs']) == outputs,
         'Keep every registered recipe output selected; subset execution needs the authored-graph adapter')
    expected = copy.deepcopy(template)
    controls, bindings = {}, {}
    extras = preset.get('bindings_extra') or {}
    need(isinstance(extras, dict), 'Invalid catalog companion bindings')
    for control in CONTROLS:
        targets = ([preset[control]] if preset.get(control) else []) + extras.get(control, [])
        if not targets: continue
        checked = []
        for binding in targets:
            need(isinstance(binding, list) and len(binding) == 2, 'Invalid catalog binding: ' + control)
            key, field = str(binding[0]), str(binding[1])
            need(key in template and field in template[key]['inputs'], 'Missing catalog binding: ' + control)
            checked.append((key, field))
        # Unchanged companion defaults may legitimately differ. Do not fan out
        # a default unless the user actually changed that logical control.
        if not any(not equivalent(doc['nodes'][k]['inputs'][f], template[k]['inputs'][f]) for k, f in checked):
            continue
        candidate = doc['nodes'][checked[0][0]]['inputs'][checked[0][1]]
        need(type(candidate) in (str, int, float), 'A projected control must be scalar: ' + control)
        need(all(equivalent(doc['nodes'][k]['inputs'][f], candidate) for k, f in checked),
             'Edit all companion inputs together for ' + control)
        controls[control] = candidate
        bindings[control] = [list(x) for x in checked]
        for key, field in checked: expected[key]['inputs'][field] = copy.deepcopy(candidate)
    need(equivalent(graph_inputs(expected), graph_inputs(doc['nodes'])),
         'The workflow changes fixed inputs or connections outside catalog controls; no ticket was created')
    return {'format': VERSION, 'document_sha256': digest(doc),
            'authored_graph_sha256': digest(graph_inputs(doc['nodes'])),
            'recipe': {'preset_id': preset['id'], 'controls': controls, 'batch_count': 1},
            'changed_bindings': bindings, 'generation_submitted': False}


def prepare_document(studio, value, preset_id):
    """Issue the existing recipe ticket after pure projection and final graph proof.

    Reference workflows are excluded before Studio.prepare can stage any inputs.
    The source report is a companion artifact, not a shared-document job lineage claim.
    """
    value = document(value)  # One source snapshot, including the final equivalence proof.
    with studio.lock:
        need(not studio.backends.busy, 'Environment switch is in progress')
        schema = catalog(studio.node_info(), studio.backends.active)
        preset = studio.preset(preset_id)
        template, path = studio.graph_for(preset)
        raw = path.read_bytes()
        need(decode(raw) == template, 'Template changed during projection')
        report = project_document(value, preset, template, schema)
        recipe = report['recipe']
        recipe['expected_template_sha256'] = hashlib.sha256(raw).hexdigest()
        # Validation includes the existing resource gate. It cannot submit a job.
        _, prepared, _, _, _ = studio.prepare(recipe)
        desired = copy.deepcopy(value['nodes'])
        studio.prune_disabled_loras(desired)
        need(equivalent(graph_inputs(desired), graph_inputs(prepared)),
             'Prepared recipe differs from the requested workflow; no ticket was created')
        ticket = prepare_ticket(studio, recipe)
        need(ticket['pins']['graph_sha256'] == digest(prepared)
             and ticket['pins']['template_sha256'] == recipe['expected_template_sha256'],
             'Prepared graph changed while issuing the ticket; prepare again before any execution')
        # A final identity check catches a changing schema without mutating its cache.
        need(digest(studio.node_info()) == schema['schema_sha256'], 'Node schema changed during preparation')
    return {**report, 'ticket': ticket, 'ticket_sha256': digest(ticket),
            'job_id': str(uuid.uuid5(NAMESPACE, ticket['request_id'])),
            'prepared_graph_sha256': ticket['pins']['graph_sha256'],
            'notice': 'Registered recipe projection only. Retain this report with the source document. '
                      'Run the returned ticket explicitly; one graph may produce several outputs. '
                      'Model/package bytes and future schema changes are not frozen by this adapter.'}
