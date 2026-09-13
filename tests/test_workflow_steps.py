"""Step commands share the document reducer and never introduce a second graph."""
import copy
from pathlib import Path
import shutil
import subprocess
import unittest
from types import SimpleNamespace
from studio_workflow.core import catalog, new_document, compile_document, document
from studio_workflow.commands import apply_commands, execution_inputs_sha256
from studio_workflow.document_http import route, PREFIX

INFO = {'Value': {'input': {'required': {'value': ['INT', {'default': 5, 'min': 0, 'max': 100}]}}, 'output': ['INT']},
        'Scale': {'input': {'required': {'source': ['INT', {'forceInput': True}], 'factor': ['FLOAT', {'default': 2, 'min': 0, 'max': 10}]}}, 'output': ['INT']},
        'Output': {'input': {'required': {'number': ['INT', {}]}}, 'output': [], 'output_node': True}}
GRAPH = {'1': {'class_type': 'Value', 'inputs': {'value': 5}},
         '2': {'class_type': 'Scale', 'inputs': {'source': ['1', 0], 'factor': 2.0}},
         '3': {'class_type': 'Output', 'inputs': {'number': ['2', 0]}}}
STEP = {'id': 'refine', 'name': 'Refine', 'description': 'An authored processing step', 'nodes': ['2'],
        'controls': [{'name': 'Strength', 'node': '2', 'input': 'factor'}]}


class StepTests(unittest.TestCase):
    def setUp(self):
        self.schema = catalog(INFO, 'primary'); self.base = new_document(GRAPH, self.schema)
        self.doc = apply_commands(self.base, [{'op': 'put_step', 'step': STEP}])
    def test_metadata_is_optional_and_has_no_execution_effect(self):
        self.assertNotIn('steps', document(self.base))
        self.assertEqual(execution_inputs_sha256(self.base), execution_inputs_sha256(self.doc))
        self.assertEqual(compile_document(self.base, self.schema)['graph_sha256'], compile_document(self.doc, self.schema)['graph_sha256'])
    def test_input_is_one_value_for_node_and_step(self):
        changed = apply_commands(self.doc, [{'op': 'set_input', 'id': '2', 'input': 'factor', 'value': 4.5}])
        self.assertEqual(changed['steps'], self.doc['steps'])
        self.assertEqual(compile_document(changed, self.schema)['graph']['2']['inputs']['factor'], 4.5)
    def test_toggle_does_not_guess_bypass(self):
        disabled = apply_commands(self.doc, [{'op': 'set_step_enabled', 'id': 'refine', 'enabled': False}])
        self.assertFalse(compile_document(disabled, self.schema)['valid'])
        bypassed = apply_commands(disabled, [{'op': 'set_bypass', 'id': '2', 'output': 0, 'input': 'source'}])
        self.assertTrue(compile_document(bypassed, self.schema)['valid'])
        self.assertEqual(apply_commands(bypassed, [{'op': 'set_step_enabled', 'id': 'refine', 'enabled': True}])['disabled'], [])
    def test_remove_group_preserves_disabled_nodes_and_values(self):
        disabled = apply_commands(self.doc, [{'op': 'set_step_enabled', 'id': 'refine', 'enabled': False}])
        removed = apply_commands(disabled, [{'op': 'remove_step', 'id': 'refine'}])
        self.assertEqual(removed['nodes'], self.doc['nodes']); self.assertEqual(removed['disabled'], ['2']); self.assertEqual(removed['steps'], [])
    def test_duplicate_rewires_internal_only_and_never_selects_new_outputs(self):
        step = copy.deepcopy(STEP); step['nodes'] = ['2', '3']
        doc = apply_commands(self.doc, [{'op': 'put_step', 'step': step}, {'op': 'set_bypass', 'id': '2', 'output': 0, 'input': 'source'}])
        doc['positions'] = {'2': [100, 200]}
        duplicate = apply_commands(doc, [{'op': 'duplicate_step', 'id': 'refine', 'new_id': 'copy', 'name': 'Copy', 'node_ids': {'2': '4', '3': '5'}}])
        self.assertEqual(duplicate['nodes']['4']['inputs']['source'], ['1', 0])
        self.assertEqual(duplicate['nodes']['5']['inputs']['number'], ['4', 0])
        self.assertEqual(duplicate['outputs'], ['3'])
        self.assertEqual(duplicate['steps'][1]['controls'][0]['node'], '4')
        self.assertEqual(duplicate['bypass']['4'], {'0': 'source'}); self.assertEqual(duplicate['positions']['4'], [140, 240])
        self.assertEqual(compile_document(duplicate, self.schema)['graph_sha256'], compile_document(doc, self.schema)['graph_sha256'])
    def test_duplicate_rejects_partial_or_colliding_mapping(self):
        for mapping in ({}, {'2': '1'}, {'2': '4', '3': '5'}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                apply_commands(self.doc, [{'op': 'duplicate_step', 'id': 'refine', 'new_id': 'copy', 'name': 'Copy', 'node_ids': mapping}])
        self.assertEqual(len(self.doc['nodes']), 3)
    def test_removing_member_retains_empty_group_and_dangling_edges(self):
        changed = apply_commands(self.doc, [{'op': 'remove_node', 'id': '2'}])
        self.assertEqual(changed['steps'][0]['nodes'], []); self.assertEqual(changed['steps'][0]['controls'], [])
        self.assertEqual(changed['nodes']['3']['inputs']['number'], ['2', 0])
    def test_membership_control_scope_and_caps_are_validated(self):
        invalid = [dict(STEP, nodes=['missing']), dict(STEP, controls=[{'node': '1', 'name': 'Bad', 'input': 'value'}]),
                   dict(STEP, surprise=True), dict(STEP, controls=STEP['controls'] * 33)]
        for step in invalid:
            with self.subTest(step=step), self.assertRaises(ValueError): apply_commands(self.doc, [{'op': 'put_step', 'step': step}])
        with self.assertRaises(ValueError): apply_commands(self.doc, [{'op': 'put_step', 'step': dict(STEP, id='overlap')}])
    def test_step_name_and_description_remain_inert_strings(self):
        step = dict(STEP, name='<script>not code</script>', description='http://not-fetched.invalid')
        changed = apply_commands(self.doc, [{'op': 'put_step', 'step': step}]); self.assertEqual(changed['steps'][0]['name'], step['name'])
    def test_reduce_route_needs_no_workspace_backend_or_worker(self):
        result = route(PREFIX + '/reduce', {'document': self.base, 'commands': [{'op': 'put_step', 'step': STEP}]}, SimpleNamespace())
        self.assertEqual(result['document'], self.doc); self.assertFalse(result['committed']); self.assertFalse(result['generation_submitted'])
    def test_strict_reduction_request_and_state_preservation(self):
        with self.assertRaises(ValueError): route(PREFIX + '/reduce', {'document': self.base, 'commands': [], 'run': True}, SimpleNamespace())
        self.assertNotIn('steps', self.base)


class BrowserStateTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for browser state contracts')
    def test_saved_document_state_contracts(self):
        result = subprocess.run(['node', str(Path(__file__).with_name('workflow_project_state.cjs'))], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
