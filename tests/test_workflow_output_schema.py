"""Malformed output definitions stay node-local; no ComfyUI/GPU invocation."""
import copy
import unittest
from studio_workflow.core import catalog, compile_document, new_document


class OutputSchemaTests(unittest.TestCase):
    def schema(self, raw):
        original = copy.deepcopy(raw)
        schema = catalog({'Broken': raw, 'Good': {'output': [], 'output_node': True}}, 'primary')
        self.assertEqual(raw, original)
        self.assertIn('Good', schema['nodes'])
        return schema

    def test_invalid_legacy_output_containers_never_invent_ports(self):
        for raw in ('IMAGE', 12, True, {}, None):
            with self.subTest(raw=raw):
                spec = self.schema({'output': raw})['nodes']['Broken']
                self.assertEqual(spec['outputs'], [])
                self.assertTrue(spec['schema_errors']); self.assertTrue(spec['unsupported'])

    def test_invalid_parallel_metadata_is_local_and_not_coerced(self):
        for name, value in (('output_name', 'images'), ('output_is_list', True),
                            ('output_name', [17]), ('output_is_list', ['false']),
                            ('output_name', ['image', 'phantom'])):
            with self.subTest(name=name, value=value):
                spec = self.schema({'output': ['IMAGE'], name: value})['nodes']['Broken']
                self.assertTrue(spec['schema_errors'])
                self.assertTrue(spec['unsupported'])

    def test_bad_v2_container_does_not_fallback_to_legacy(self):
        for value in (None, 1, {}, 'IMAGE'):
            spec = self.schema({'outputs': value, 'output': ['IMAGE']})['nodes']['Broken']
            self.assertEqual(spec['outputs'], []); self.assertTrue(spec['schema_errors'])

    def test_invalid_v2_records_are_not_skipped_as_valid_definitions(self):
        for value in (None, 'IMAGE', [], {}, {'type': ['IMAGE']}, {'type': ''},
                      {'type': 'IMAGE', 'index': True}, {'type': 'IMAGE', 'index': 1.5},
                      {'type': 'IMAGE', 'index': -1}, {'type': 'IMAGE', 'index': 10000},
                      {'type': 'IMAGE', 'name': []}, {'type': 'IMAGE', 'is_list': 1}):
            with self.subTest(value=value):
                spec = self.schema({'outputs': [value]})['nodes']['Broken']
                self.assertTrue(spec['schema_errors']); self.assertEqual(spec['outputs'], [])

    def test_duplicate_index_is_diagnostic_and_later_ports_keep_their_ids(self):
        spec = self.schema({'outputs': [{'index': 3, 'type': 'IMAGE'}, {'index': 3, 'type': 'MASK'},
                                       {'index': 8, 'type': 'INT'}]})['nodes']['Broken']
        self.assertEqual([x['index'] for x in spec['outputs']], [3, 8])
        self.assertIn('Duplicate output index: 3', spec['schema_errors'])

    def test_skipped_bad_slot_does_not_renumber_valid_ports(self):
        spec = self.schema({'outputs': [None, {'type': 'IMAGE'}]})['nodes']['Broken']
        self.assertEqual(spec['outputs'][0]['index'], 1)

    def test_legacy_optional_metadata_defaults_preserve_list_union_and_names(self):
        schema = self.schema({'output': ['MESH,FILE_3D_GLB', '*', 'INT'],
                              'output_name': ['Mesh'], 'output_is_list': [True]})
        spec = schema['nodes']['Broken']
        self.assertEqual(spec['schema_errors'], [])
        self.assertEqual(spec['outputs'], [
            {'index': 0, 'type': 'MESH,FILE_3D_GLB', 'name': 'Mesh', 'is_list': True},
            {'index': 1, 'type': '*', 'name': '*', 'is_list': False},
            {'index': 2, 'type': 'INT', 'name': 'INT', 'is_list': False}])

    def test_errors_block_selected_closure_not_unrelated_documents(self):
        schema = self.schema({'output': 'IMAGE'})
        schema['nodes']['Consumer'] = {'inputs': [{'name': 'images', 'type': 'IMAGE', 'widget': 'socket',
            'required': True, 'hidden': False, 'options': {}}], 'outputs': [], 'output_node': True}
        doc = new_document({'a': {'class_type': 'Broken', 'inputs': {}},
                            'b': {'class_type': 'Consumer', 'inputs': {'images': ['a', 0]}},
                            'c': {'class_type': 'Good', 'inputs': {}}}, schema)
        before = copy.deepcopy(doc)
        report = compile_document(doc, schema)
        self.assertFalse(report['valid']); self.assertEqual(before, doc)
        self.assertIn('invalid_node_schema', {e['code'] for e in report['errors']})
        doc['outputs'] = ['c']
        self.assertTrue(compile_document(doc, schema)['valid'])

    def test_output_node_requires_real_boolean_not_truthiness(self):
        for value in ('false', 1, [], {}):
            spec = self.schema({'output': [], 'output_node': value})['nodes']['Broken']
            self.assertFalse(spec['output_node']); self.assertTrue(spec['schema_errors'])

    def test_v2_valid_outputs_and_outputless_sinks_still_work(self):
        spec = self.schema({'outputs': [{'index': 0, 'type': 'IMAGE', 'is_list': True}]})['nodes']['Broken']
        self.assertFalse(spec['schema_errors']); self.assertTrue(spec['outputs'][0]['is_list'])
        spec = self.schema({'output': [], 'output_node': True})['nodes']['Broken']
        self.assertFalse(spec['schema_errors']); self.assertTrue(spec['output_node'])
