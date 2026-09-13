"""Authoring fixtures, not an installed workstation schema or runtime validator."""
import copy
import unittest
from studio_workflow.core import catalog, new_document, compile_document


class SchemaContracts(unittest.TestCase):
    def case(self, descriptor, value=1, optional=False):
        info = {'Node': {'input': {'optional' if optional else 'required': {'value': descriptor}}, 'output': [], 'output_node': True}}
        schema = catalog(info, 'primary')
        doc = new_document({'1': {'class_type': 'Node', 'inputs': {'value': value}}}, schema)
        return schema, doc, info

    def test_unrecognized_descriptors_are_diagnostics_not_key_errors(self):
        for descriptor in (None, [], 'not a tuple', 17):
            with self.subTest(descriptor=descriptor):
                schema, doc, _ = self.case(descriptor)
                spec = schema['nodes']['Node']['inputs'][0]
                self.assertEqual(spec['widget'], 'unsupported'); self.assertFalse(spec['hidden'])
                report = compile_document(doc, schema)
                self.assertFalse(report['valid'])
                self.assertIn('native_adapter_required', {e['code'] for e in report['errors']})

    def test_invalid_numeric_control_metadata_needs_adapter(self):
        for options in ({'min': 'small'}, {'max': True}, {'min': 5, 'max': 2}, {'step': 0}, {'step': 'auto'}):
            with self.subTest(options=options):
                schema, doc, info = self.case(['FLOAT', options])
                before = copy.deepcopy(doc)
                self.assertEqual(schema['nodes']['Node']['inputs'][0]['widget'], 'unsupported')
                self.assertFalse(compile_document(doc, schema)['valid'])
                self.assertEqual(doc, before); self.assertEqual(info['Node']['input']['required']['value'][1], options)

    def test_malformed_input_group_does_not_take_down_other_nodes(self):
        for bad in ('fields', ['value'], 9):
            info = {'Broken': {'input': {'required': bad}, 'output_node': True, 'output': []},
                    'Good': {'input': {'required': {'text': ['STRING', {}]}}, 'output': ['STRING']}}
            schema = catalog(info, 'primary')
            self.assertIn('Good', schema['nodes']); self.assertTrue(schema['nodes']['Broken']['schema_errors'])
            doc = new_document({'1': {'class_type': 'Broken', 'inputs': {}}}, schema)
            report = compile_document(doc, schema)
            self.assertFalse(report['valid'])
            self.assertIn('invalid_node_schema', {e['code'] for e in report['errors']})

    def test_legacy_v3_and_v2_combos_preserve_typed_choices(self):
        for descriptor in ([['fast', 'precise'], {}], ['COMBO', {'options': ['fast', 'precise']}],
                           {'type': 'COMBO', 'options': ['fast', 'precise'], 'isOptional': False}):
            schema, doc, _ = self.case(descriptor, 'fast')
            self.assertTrue(compile_document(doc, schema)['valid'])
            doc['nodes']['1']['inputs']['value'] = 'unknown'
            self.assertFalse(compile_document(doc, schema)['valid'])
        schema, doc, _ = self.case([[1, True, '1'], {}], True)
        self.assertTrue(compile_document(doc, schema)['valid'])
        self.assertEqual(schema['nodes']['Node']['inputs'][0]['options']['options'], [1, True, '1'])

    def test_native_behaviours_keep_data_and_require_adapters(self):
        descriptors = [['DYNAMIC_COMBO', {'options': [{'key': 'mp4'}]}], ['DYNAMIC_AUTOGROW', {}],
                       ['COLOR', {'socketless': True, 'default': '#000000'}],
                       ['INT', {'remote': {'route': '/choices'}}], ['IMAGE', {'rawLink': True}]]
        for descriptor in descriptors:
            schema, doc, _ = self.case(descriptor, {'opaque': [1, 2]})
            before = copy.deepcopy(doc)
            self.assertFalse(compile_document(doc, schema)['valid']); self.assertEqual(doc, before)
            self.assertTrue(schema['nodes']['Node']['inputs'][0]['reason'])

    def test_force_input_hidden_and_list_metadata_are_not_lost(self):
        info = {'Node': {'input': {'required': {'value': ['INT', {'forceInput': True}]}, 'hidden': {'prompt': 'PROMPT'}},
                         'output': ['INT'], 'output_name': ['numbers'], 'output_is_list': [True]}}
        schema = catalog(info, 'primary'); kind = schema['nodes']['Node']
        self.assertEqual(kind['inputs'][0]['widget'], 'socket')
        self.assertEqual([x['name'] for x in kind['inputs']], ['value'])
        self.assertTrue(kind['outputs'][0]['is_list']); self.assertEqual(kind['outputs'][0]['name'], 'numbers')
        self.assertEqual(info['Node']['input']['hidden'], {'prompt': 'PROMPT'})

    def test_valid_int64_ranges_and_unknown_optional_inputs_remain_drafts(self):
        schema, doc, _ = self.case(['INT', {'min': 0, 'max': 2**64-1, 'step': 1}], 2**64-1)
        self.assertTrue(compile_document(doc, schema)['valid'])
        self.assertEqual(doc['nodes']['1']['inputs']['value'], 2**64-1)
        schema, doc, _ = self.case(None, optional=True)
        doc['nodes']['1']['inputs'] = {}
        self.assertTrue(compile_document(doc, schema)['valid'], 'Unset unsupported optional inputs do not invent a requirement')

    def test_nodedef_v2_top_level_inputs_and_outputs(self):
        info = {'V2': {'inputs': {'count': {'type': 'INT', 'min': 0, 'max': 12, 'isOptional': False},
                                 'label': {'type': 'STRING', 'isOptional': True}},
                       'outputs': [{'index': 0, 'type': 'INT', 'name': 'count', 'is_list': False}], 'output_node': True}}
        schema = catalog(info, 'primary')
        self.assertEqual([x['required'] for x in schema['nodes']['V2']['inputs']], [True, False])
        doc = new_document({'1': {'class_type': 'V2', 'inputs': {'count': 3}}}, schema)
        self.assertTrue(compile_document(doc, schema)['valid'])
