"""Registered graph projection, using real ticket journaling and a fake runtime."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from studio_workflow.core import catalog, digest, new_document
from studio_workflow.execution import prepare_ticket, run_ticket
from studio_workflow.preset_adapter import equivalent, graph_inputs, prepare_document, project_document

GRAPH = {
    '1': {'class_type': 'Model', 'inputs': {'ckpt_name': 'fixed.safetensors'}},
    '2': {'class_type': 'LoraLoader', 'inputs': {'model': ['1', 0], 'clip': ['1', 1],
          'lora_name': 'optional.safetensors', 'strength_model': 0.0, 'strength_clip': 0.0}},
    '3': {'class_type': 'Render', 'inputs': {'model': ['2', 0], 'clip': ['2', 1],
          'text': 'original', 'seed': 42, 'steps': 20, 'width': 512, 'height': 512, 'cfg': 7.0, 'batch_size': 1}},
    '4': {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0], 'filename_prefix': 'studio-test'}}}
PRESET = {'id': 'example', 'name': 'Example', 'modality': 'image', 'graph': 'workflows/api/example.json',
          'positive': ['3', 'text'], 'seed': ['3', 'seed'], 'steps': ['3', 'steps'],
          'width': ['3', 'width'], 'height': ['3', 'height'], 'cfg': ['3', 'cfg'],
          'lora': ['2', 'strength_model'], 'lora_name': ['2', 'lora_name'],
          'bindings_extra': {'lora': [['2', 'strength_clip']]}}
INFO = {'Model': {'input': {}, 'output': ['MODEL', 'CLIP']},
        'LoraLoader': {'input': {}, 'output': ['MODEL', 'CLIP']},
        'Render': {'input': {}, 'output': ['IMAGE']},
        'SaveImage': {'input': {}, 'output': [], 'output_node': True}}


class Runtime:
    def __init__(self, root):
        self.root = Path(root); self.experiments = self.root / 'experiments'
        self.runs = self.experiments / 'runs'; self.runs.mkdir(parents=True)
        self.comfy_root = self.root / 'comfy'; self.comfy_url = 'http://127.0.0.1:8188'
        self.lock = threading.RLock(); self.backends = SimpleNamespace(active='primary', busy=False)
        self.path = self.root / 'graph.json'; self.path.write_text(json.dumps(GRAPH), encoding='utf-8')
        self.definition = copy.deepcopy(PRESET); self.info = copy.deepcopy(INFO)
        self.jobs = {}; self.calls = 0; self.preparations = 0; self.blocked = False
    def node_info(self): return copy.deepcopy(self.info)
    def preset(self, key):
        if key != self.definition['id']: raise ValueError('Unknown recipe')
        return copy.deepcopy(self.definition)
    def graph_for(self, preset): return json.loads(self.path.read_bytes()), self.path
    def prepare(self, payload):
        self.preparations += 1
        if self.blocked: raise ValueError('Host commit headroom below threshold')
        preset = self.preset(payload['preset_id']); graph, path = self.graph_for(preset)
        if payload.get('expected_template_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Template changed')
        controls = payload.get('controls', {})
        for key, value in controls.items():
            if key == 'steps' and (type(value) is not int or not 1 <= value <= 150): raise ValueError('Invalid steps')
            if key == 'seed' and (type(value) is not int or not 0 <= value <= 2**63 - 1): raise ValueError('Invalid seed')
            for node, field in ([preset[key]] if preset.get(key) else []) + preset.get('bindings_extra', {}).get(key, []):
                graph[node]['inputs'][field] = float(value) if key in ('cfg', 'lora') else value
        self.prune_disabled_loras(graph)
        return preset, graph, path, controls, 1
    @staticmethod
    def prune_disabled_loras(graph):
        if '2' not in graph or graph['2']['class_type'] != 'LoraLoader': return
        inputs = graph['2']['inputs']
        if inputs['strength_model'] != 0 or inputs['strength_clip'] != 0: return
        for node in graph.values():
            for field, value in list(node['inputs'].items()):
                if value == ['2', 0]: node['inputs'][field] = inputs['model']
                elif value == ['2', 1]: node['inputs'][field] = inputs['clip']
        del graph['2']
    def create_job(self, payload, job_id):
        self.prepare(payload); self.calls += 1
        self.jobs[job_id] = {'id': job_id, 'status': 'queued', 'prompt_ids': []}
        return self.public(self.jobs[job_id])
    def public(self, job): return copy.deepcopy(job)


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.studio = Runtime(self.temp.name); self.schema = catalog(INFO, 'primary')
        self.doc = new_document(GRAPH, self.schema)
    def project(self, doc=None):
        return project_document(doc or self.doc, self.studio.definition, GRAPH, self.schema)
    def prepare(self): return prepare_document(self.studio, self.doc, 'example')
    def test_scalar_changes_and_explicit_companions(self):
        self.doc['nodes']['3']['inputs'].update(text='changed', seed=99, cfg=8)
        self.doc['nodes']['2']['inputs'].update(strength_model=0.6, strength_clip=0.6)
        original = copy.deepcopy(self.doc); result = self.project()
        self.assertEqual(result['recipe']['controls'], {'positive': 'changed', 'seed': 99, 'cfg': 8, 'lora': 0.6})
        self.assertEqual(result['changed_bindings']['lora'], [['2', 'strength_model'], ['2', 'strength_clip']])
        self.assertEqual(original, self.doc); self.assertEqual(self.studio.preparations, 0)
    def test_fixed_model_path_batch_and_connections_rejected_before_preparation(self):
        for key, field, value in [('1', 'ckpt_name', 'another.safetensors'), ('4', 'filename_prefix', '../elsewhere'),
                                  ('3', 'batch_size', 4), ('3', 'model', ['1', 0])]:
            with self.subTest(field=field):
                self.doc = new_document(GRAPH, self.schema); self.doc['nodes'][key]['inputs'][field] = value
                with self.assertRaisesRegex(ValueError, 'outside catalog'): self.prepare()
        self.assertEqual(self.studio.preparations, 0); self.assertEqual(self.studio.calls, 0)
    def test_companion_half_edit_is_not_silently_expanded(self):
        self.doc['nodes']['2']['inputs']['strength_model'] = 0.6
        with self.assertRaisesRegex(ValueError, 'all companion'): self.prepare()
        self.assertEqual(self.studio.preparations, 0)
    def test_unchanged_different_companion_defaults_are_not_rebound(self):
        template = copy.deepcopy(GRAPH); template['2']['inputs']['strength_clip'] = 1
        doc = new_document(template, self.schema)
        self.assertEqual(project_document(doc, PRESET, template, self.schema)['recipe']['controls'], {})
    def test_metadata_name_layout_and_source_do_not_change_recipe(self):
        before = self.project(); self.doc['name'] = 'Layout only'; self.doc['positions']['1'] = [100, 200]
        self.doc['nodes']['1']['_meta'] = {'title': 'Human label'}
        self.doc['source'] = {'preset_id': 'forged-untrusted-name'}
        after = self.project(); self.assertEqual(before['recipe'], after['recipe'])
        self.assertEqual(before['authored_graph_sha256'], after['authored_graph_sha256'])
        self.assertNotEqual(before['document_sha256'], after['document_sha256'])
    def test_schema_backend_and_switch_are_checked(self):
        self.doc['schema_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'schema changed'): self.prepare()
        self.doc['schema_sha256'] = self.schema['schema_sha256']; self.studio.backends.active = 'hidream'
        with self.assertRaisesRegex(ValueError, 'active environment'): self.prepare()
        self.studio.backends.busy = True
        with self.assertRaisesRegex(ValueError, 'switch'): self.prepare()
    def test_node_addition_removal_and_class_changes_refused(self):
        for action in ('add', 'remove', 'class'):
            self.doc = new_document(GRAPH, self.schema)
            if action == 'add': self.doc['nodes']['5'] = copy.deepcopy(GRAPH['1'])
            elif action == 'remove': del self.doc['nodes']['2']
            else: self.doc['nodes']['2']['class_type'] = 'Render'
            with self.subTest(action=action), self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.studio.preparations, 0)
    def test_disabled_and_unselected_outputs_refused(self):
        self.doc['disabled'] = ['2']
        with self.assertRaisesRegex(ValueError, 'Disabled nodes'): self.prepare()
        self.doc['disabled'] = []; self.doc['outputs'] = []
        with self.assertRaisesRegex(ValueError, 'every registered'): self.prepare()
    def test_missing_and_new_input_fields_refused(self):
        del self.doc['nodes']['3']['inputs']['steps']
        with self.assertRaisesRegex(ValueError, 'Input fields'): self.prepare()
        self.doc = new_document(GRAPH, self.schema); self.doc['nodes']['3']['inputs']['extra'] = 1
        with self.assertRaisesRegex(ValueError, 'Input fields'): self.prepare()
    def test_reference_presets_and_unbound_load_image_refused(self):
        for field in ('reference', 'last_reference', 'reference_slots', 'requires_rgba_mask'):
            self.studio.definition[field] = True
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'asset-lineage'): self.prepare()
            del self.studio.definition[field]
        graph = copy.deepcopy(GRAPH); graph['5'] = {'class_type': 'LoadImage', 'inputs': {'image': 'disk.png'}}
        with self.assertRaisesRegex(ValueError, 'asset-lineage'):
            project_document(self.doc, PRESET, graph, self.schema)
        self.assertEqual(self.studio.preparations, 0)
    def test_modality_and_missing_class_refused(self):
        self.studio.definition['modality'] = 'video'
        with self.assertRaisesRegex(ValueError, 'image recipes'): self.prepare()
        self.studio.definition['modality'] = 'image'; del self.studio.info['Model']
        self.doc['schema_sha256'] = digest(self.studio.info)
        with self.assertRaisesRegex(ValueError, 'unavailable'): self.prepare()
    def test_boolean_is_neither_one_nor_a_projectable_number(self):
        self.doc['nodes']['3']['inputs']['batch_size'] = True
        with self.assertRaises(ValueError): self.prepare()
        self.doc = new_document(GRAPH, self.schema); self.doc['nodes']['3']['inputs']['steps'] = True
        with self.assertRaisesRegex(ValueError, 'scalar'): self.prepare()
        self.assertFalse(equivalent(True, 1)); self.assertFalse(equivalent([1], [True]))
        self.assertTrue(equivalent(8, 8.0))
    def test_real_ticket_and_zero_strength_pruning_match(self):
        report = self.prepare(); ticket = report['ticket']
        self.assertEqual(ticket['format'], 'studio.run-ticket/v1'); self.assertFalse(report['generation_submitted'])
        self.assertEqual(ticket['pins']['graph_sha256'], report['prepared_graph_sha256'])
        self.assertNotEqual(report['prepared_graph_sha256'], report['authored_graph_sha256'])
        self.assertEqual(report['ticket_sha256'], digest(ticket)); self.assertEqual(self.studio.calls, 0)
        self.assertFalse((self.studio.runs / 'workflow-requests').exists())
    def test_integer_and_float_runtime_normalization_is_exact(self):
        self.doc['nodes']['3']['inputs']['cfg'] = 8
        self.assertEqual(self.prepare()['recipe']['controls']['cfg'], 8)
    def test_wide_seed_is_preserved_and_out_of_runtime_range_refused(self):
        self.doc['nodes']['3']['inputs']['seed'] = 2**63 - 1
        self.assertEqual(self.prepare()['ticket']['recipe']['controls']['seed'], 2**63 - 1)
        self.doc['nodes']['3']['inputs']['seed'] = 2**64 - 1
        with self.assertRaisesRegex(ValueError, 'Invalid seed'): self.prepare()
    def test_runtime_validation_and_resource_gate_remain_authoritative(self):
        self.doc['nodes']['3']['inputs']['steps'] = 151
        with self.assertRaisesRegex(ValueError, 'Invalid steps'): self.prepare()
        self.doc['nodes']['3']['inputs']['steps'] = 20; self.studio.blocked = True
        with self.assertRaisesRegex(ValueError, 'Host commit'): self.prepare()
        self.assertFalse(self.studio.jobs)
    def test_no_silent_server_transformation(self):
        original = self.studio.prepare
        def changed(payload):
            values = original(payload); values[1]['3']['inputs']['text'] = 'unexpected rewrite'; return values
        with patch.object(self.studio, 'prepare', changed), self.assertRaisesRegex(ValueError, 'differs'): self.prepare()
    def test_template_race_refused(self):
        def stale(preset):
            self.studio.path.write_text('{}', encoding='utf-8'); return copy.deepcopy(GRAPH), self.studio.path
        with patch.object(self.studio, 'graph_for', stale), self.assertRaisesRegex(ValueError, 'Template changed'): self.prepare()
    def test_ticket_graph_race_refused(self):
        def bad(studio, recipe):
            ticket = prepare_ticket(studio, recipe); ticket['pins']['graph_sha256'] = '0' * 64; return ticket
        with patch('studio_workflow.preset_adapter.prepare_ticket', bad), self.assertRaisesRegex(ValueError, 'graph changed'): self.prepare()
    def test_ticket_recovers_same_job_under_concurrent_clients(self):
        ticket = self.prepare()['ticket']
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: run_ticket(self.studio, ticket, True), range(4)))
        self.assertEqual(self.studio.calls, 1); self.assertEqual(len({r['job']['id'] for r in results}), 1)
        self.studio.jobs[results[0]['job']['id']]['status'] = 'uncertain'
        self.assertEqual(run_ticket(self.studio, ticket, True)['job']['status'], 'uncertain')
        self.assertEqual(self.studio.calls, 1)
    def test_ticket_still_requires_approval_and_retains_lost_job_intent(self):
        ticket = self.prepare()['ticket']
        with self.assertRaisesRegex(ValueError, 'approval'): run_ticket(self.studio, ticket)
        run_ticket(self.studio, ticket, True); self.studio.jobs.clear()
        result = run_ticket(self.studio, ticket, True)
        self.assertEqual(result['status'], 'reconciliation_required'); self.assertEqual(self.studio.calls, 1)


if __name__ == '__main__': unittest.main()
