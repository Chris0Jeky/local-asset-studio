"""Bounded, declarative Comfy API graph inspection; never imports or executes nodes.

Reachability is evidence about the supplied graph, not about the actual pixels or
runtime. Conditioning traces stop at unknown operators rather than guessing roles.
"""
from collections import deque
import hashlib
from .core import canonical, need

GRAPH_CAP = 128 * 1024
NODE_CAP = 512
EDGE_CAP = 8192
WALK_CAP = 50000
REPORT_CAP = 1024 * 1024
OUTPUTS = {'SaveImage', 'PreviewImage'}
TEXT_FIELDS = {
    'CLIPTextEncode': ('text',),
    'CLIPTextEncodeSDXL': ('text_g', 'text_l'),
    'CLIPTextEncodeSDXLRefiner': ('text',),
    'TextEncodeQwenImageEdit': ('prompt',),
    'TextEncodeQwenImageEditPlus': ('prompt',),
}
SAMPLERS = {
    'KSampler': ('seed', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'),
    'KSamplerAdvanced': ('noise_seed', 'steps', 'cfg', 'sampler_name', 'scheduler',
                         'start_at_step', 'end_at_step', 'add_noise', 'return_with_leftover_noise'),
    'SamplerCustom': ('noise_seed', 'cfg', 'add_noise'),
}
# Each entry is an output-slot -> input-port contract, not a name heuristic.
CONDITIONING = {
    name: {0: ('conditioning',)} for name in (
        'ConditioningSetArea', 'ConditioningSetAreaPercentage', 'ConditioningSetAreaStrength',
        'ConditioningSetMask', 'ConditioningSetTimestepRange', 'ConditioningZeroOut',
        'ControlNetApply', 'FluxGuidance')
}
CONDITIONING.update({
    'ConditioningCombine': {0: ('conditioning_1', 'conditioning_2')},
    'ConditioningConcat': {0: ('conditioning_to', 'conditioning_from')},
    'ConditioningAverage': {0: ('conditioning_to', 'conditioning_from')},
    'ControlNetApplyAdvanced': {0: ('positive',), 1: ('negative',)},
    'InpaintModelConditioning': {0: ('positive',), 1: ('negative',)},
})
# These nodes receive structural link inspection only, not tensor evaluation.
STRUCTURAL = {'VAEDecode', 'VAEDecodeTiled', 'VAEEncode', 'VAEEncodeTiled',
              'VAEEncodeForInpaint', 'LoadImage', 'EmptyLatentImage', 'ImageScale',
              'ImageScaleBy', 'ImageScaleToTotalPixels', 'LatentUpscale', 'LatentUpscaleBy'}
MODEL_FIELDS = {
    'CheckpointLoaderSimple': ('ckpt_name',), 'CheckpointLoader': ('ckpt_name', 'config_name'),
    'UNETLoader': ('unet_name', 'weight_dtype'), 'UnetLoaderGGUF': ('unet_name',),
    'CLIPLoader': ('clip_name', 'type'), 'DualCLIPLoader': ('clip_name1', 'clip_name2', 'type'),
    'VAELoader': ('vae_name',), 'LoraLoader': ('lora_name', 'strength_model', 'strength_clip'),
    'LoraLoaderModelOnly': ('lora_name', 'strength_model'),
}


def link(value):
    """Only a complete native API link counts; booleans are not integer slots."""
    if (isinstance(value, list) and len(value) == 2 and type(value[0]) in (str, int)
            and type(value[1]) is int and 0 <= value[1] < 256):
        return str(value[0]), value[1]
    return None


def scalars(inputs, names):
    return {k: inputs[k] for k in names if k in inputs and type(inputs[k]) in (str, int, float, bool)}


def _graph(value):
    need(isinstance(value, dict) and 0 < len(value) <= NODE_CAP, 'Expected bounded Comfy API node map')
    for node_id, node in value.items():
        need(isinstance(node_id, str) and 0 < len(node_id) <= 128, 'Invalid graph node ID')
        need(isinstance(node, dict) and isinstance(node.get('class_type'), str)
             and 0 < len(node['class_type']) <= 128 and isinstance(node.get('inputs'), dict)
             and len(node['inputs']) <= 64, 'Expected API nodes, not a visual workflow')
        need(all(isinstance(k, str) and 0 < len(k) <= 128 for k in node['inputs']), 'Invalid input port name')
    need(len(canonical(value)) <= GRAPH_CAP, 'Graph exceeds inspection byte budget')
    return value


class Inspector:
    def __init__(self, graph):
        self.graph = _graph(graph); self.work = 0; self.report_bytes = 0; self.edges = {}; self.diagnostics = []
        count = 0
        for node_id, node in self.graph.items():
            edges = []
            for field, value in sorted(node['inputs'].items()):
                ref = link(value)
                if ref:
                    count += 1
                    if ref[0] not in graph:
                        self.diagnostics.append({'code': 'missing_node', 'node': node_id, 'field': field,
                                                 'target': ref[0]})
                    else: edges.append(ref[0])
            self.edges[node_id] = edges
        need(count <= EDGE_CAP, 'Graph edge budget exceeded')
        # Kahn's algorithm avoids recursion and exponential path enumeration.
        pending = {key: len(set(refs)) for key, refs in self.edges.items()}; consumers = {k: [] for k in graph}
        for key, refs in self.edges.items():
            for ref in set(refs): consumers[ref].append(key)
        ready = deque(sorted(k for k, count in pending.items() if count == 0)); visited = 0
        while ready:
            key = ready.popleft(); visited += 1
            for child in consumers[key]:
                pending[child] -= 1
                if pending[child] == 0: ready.append(child)
        self.cyclic = {k for k, count in pending.items() if count}
        if visited != len(graph):
            self.diagnostics.append({'code': 'cycle_or_dependent_on_cycle',
                                     'nodes': sorted(k for k, count in pending.items() if count)})

    def evidence(self, value):
        # Charge repeated evidence before appending: small graphs may fan out huge text reports.
        self.report_bytes += len(canonical(value))
        need(self.report_bytes <= REPORT_CAP, 'Graph report byte budget exceeded')
        return value

    def tick(self):
        self.work += 1; need(self.work <= WALK_CAP, 'Graph traversal budget exceeded')

    def ancestors(self, root):
        found = set(); todo = [root]
        while todo:
            self.tick(); node_id = todo.pop()
            if node_id in found: continue
            found.add(node_id); todo.extend(self.edges[node_id])
        return found

    def conditioning(self, start):
        todo = deque([(start, False, ())]); seen = set(); texts = []; unresolved = []; transforms = {}
        while todo:
            self.tick(); value, zeroed, witness = todo.popleft(); ref = link(value)
            if ref is None or ref[0] not in self.graph:
                unresolved.append(self.evidence({'reason': 'missing_or_nonlink_conditioning', 'value': value})); continue
            node_id, slot = ref; state = (node_id, slot, zeroed)
            if state in seen: continue
            seen.add(state); node = self.graph[node_id]; cls = node['class_type']; inputs = node['inputs']
            if cls in TEXT_FIELDS and slot == 0:
                for field in TEXT_FIELDS[cls]:
                    text = inputs.get(field)
                    if not isinstance(text, str):
                        unresolved.append({'node': node_id, 'field': field, 'reason': 'dynamic_or_missing_text'}); continue
                    texts.append(self.evidence({'node': node_id, 'class_type': cls, 'field': field, 'value': text,
                                  'effect': 'zeroed_text_embeddings' if zeroed else 'declared_conditioning',
                                  'witness': list(witness)}))
                continue
            ports = CONDITIONING.get(cls, {}).get(slot)
            if ports is None:
                unresolved.append({'node': node_id, 'class_type': cls, 'slot': slot,
                                   'reason': 'unsupported_conditioning_output'}); continue
            token = f'{node_id}:{slot}'
            transforms[token] = self.evidence({'node': node_id, 'class_type': cls, 'slot': slot,
                                 'parameters': scalars(inputs, sorted(inputs))})
            for port in ports:
                todo.append((inputs.get(port), zeroed or cls == 'ConditioningZeroOut', witness + (token,)))
        if any(node_id in self.cyclic for node_id, _, _ in seen):
            unresolved.append({'reason': 'cycle_or_dependent_on_cycle'})
        return {'texts': texts, 'transforms': list(transforms.values()), 'unresolved': unresolved,
                'status': 'partial' if unresolved else 'traced',
                'semantics': 'Reachability witnesses, not flattened text, tensor weights or proof of runtime influence.'}

    def sampler(self, node_id):
        node = self.graph[node_id]; cls = node['class_type']; inputs = node['inputs']
        report = {'node': node_id, 'class_type': cls, 'settings': self.evidence(scalars(inputs, SAMPLERS[cls])),
                  'positive': self.conditioning(inputs.get('positive')),
                  'negative': self.conditioning(inputs.get('negative')),
                  'runtime_effect': 'unverified'}
        report['linked_settings'] = {k: inputs[k] for k in SAMPLERS[cls] if link(inputs.get(k))}
        return report


def inspect_graph(graph, output_node=None):
    """Return separate outputs/stages. Never infer which output owns supplied pixels."""
    inspector = Inspector(graph); roots = sorted(k for k, n in graph.items() if n['class_type'] in OUTPUTS)
    need(len(roots) <= 16, 'Output-node budget exceeded')
    if output_node is not None:
        need(isinstance(output_node, str) and output_node in roots, 'Select a known SaveImage/PreviewImage node')
    samplers = sorted(k for k, n in graph.items() if n['class_type'] in SAMPLERS)
    need(len(samplers) <= 64, 'Sampler-stage budget exceeded')
    output_sets = {root: inspector.ancestors(root) for root in roots}
    included = set().union(*output_sets.values()) if roots else set()
    stage_ids = sorted(k for k in samplers if k in included)
    stages = [inspector.sampler(k) for k in stage_ids]
    outputs = [{'node': root, 'class_type': graph[root]['class_type'],
                'samplers': [k for k in stage_ids if k in ancestors],
                'declared_ancestors': sorted(ancestors)} for root, ancestors in output_sets.items()]
    claims = []
    for node_id, node in sorted(graph.items()):
        for field, value in scalars(node['inputs'], TEXT_FIELDS.get(node['class_type'], ())).items():
            claims.append(inspector.evidence({'node': node_id, 'class_type': node['class_type'], 'field': field, 'value': value,
                           'outputs': [k for k, nodes in output_sets.items() if node_id in nodes],
                           'scope': 'declared_output_dependency' if node_id in included else
                                    ('not_connected_to_known_output' if roots else 'output_unknown')}))
    models = [inspector.evidence({'node': key, 'class_type': node['class_type'],
               'claims': scalars(node['inputs'], MODEL_FIELDS[node['class_type']]),
               'outputs': [k for k, nodes in output_sets.items() if key in nodes], 'identity_verified': False})
              for key, node in sorted(graph.items()) if node['class_type'] in MODEL_FIELDS]
    understood = OUTPUTS | set(TEXT_FIELDS) | set(SAMPLERS) | set(CONDITIONING) | set(MODEL_FIELDS) | STRUCTURAL
    uninterpreted = [{'node': key, 'class_type': graph[key]['class_type'], 'semantics': 'declared_links_only'}
                     for key in sorted(included) if graph[key]['class_type'] not in understood]
    diagnostics = inspector.diagnostics
    if uninterpreted: diagnostics.append({'code': 'uninterpreted_output_dependencies'})
    for output in outputs:
        if not output['samplers']: diagnostics.append({'code': 'no_known_sampler_for_output', 'node': output['node']})
    if not roots: diagnostics.append({'code': 'no_known_output', 'message': 'No output selected by heuristic.'})
    if len(roots) > 1 and output_node is None:
        diagnostics.append({'code': 'multiple_outputs', 'message': 'Metadata does not bind pixels to a save node.'})
    if any(s[role]['unresolved'] for s in stages for role in ('positive', 'negative')):
        diagnostics.append({'code': 'incomplete_conditioning_trace'})
    result = {'kind': 'comfy_graph_provenance', 'schema_version': 1,
            'graph_sha256': hashlib.sha256(canonical(graph)).hexdigest(),
            'selected_output': output_node, 'outputs': outputs, 'stages': stages,
            'text_claims': claims, 'model_claims': models, 'diagnostics': diagnostics,
            'uninterpreted_nodes': uninterpreted,
            'unconnected_samplers': [k for k in samplers if k not in included],
            'authority': 'supplied_graph_claim', 'workflow_executed': False,
            'warning': 'Static links do not prove execution, final-image ownership, model identity, or effective negative guidance. '
                       'Unknown custom nodes may hide additional stages. ZeroOut zeros text embeddings, not necessarily all auxiliary conditioning.'}
    need(len(canonical(result)) <= REPORT_CAP, 'Graph report byte budget exceeded')
    return result
