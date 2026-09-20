"""Malformed installed schemas must remain visible, inert and non-executable."""
import copy
import json
import shutil
import subprocess
import unittest

from studio_workflow.core import catalog, canonical, compile_document, compatible, decode, new_document


def inspect(raw, values=None):
    info = {'Node': {**raw, 'output_node': True, 'output': []}}
    schema = catalog(info, 'local-fixture')
    doc = new_document({'1': {'class_type': 'Node', 'inputs': values or {}}}, schema)
    return schema['nodes']['Node'], compile_document(doc, schema), doc, info


class InputAdapters(unittest.TestCase):
    def test_present_malformed_containers_never_become_empty_executable_nodes(self):
        for key in ('input', 'inputs'):
            for value in (None, False, 17, 'opaque', [], ['INT', {}]):
                with self.subTest(key=key, value=value):
                    node, result, _, info = inspect({key: value})
                    self.assertFalse(result['valid'])
                    self.assertIn('invalid_node_schema', {x['code'] for x in result['errors']})
                    self.assertEqual(info['Node'], json.loads(node['source_definition_json']))

    def test_explicit_null_groups_unknown_groups_and_dual_forms_are_not_dropped(self):
        for raw in ({'input': {'required': None}}, {'input': {'hidden': None}},
                    {'input': {'extra': {'value': ['INT', {}]}}},
                    {'input': {}, 'inputs': {}}, {'input': None, 'inputs': {}},
                    {'inputs': None, 'input': {}}):
            with self.subTest(raw=raw):
                node, result, _, _ = inspect(raw)
                self.assertTrue(node['schema_errors'])
                self.assertFalse(result['valid'])

    def test_duplicate_names_cannot_weaken_required_or_shadow_hidden_runtime_values(self):
        for later in ('optional', 'hidden'):
            raw = {'input': {'required': {'value': ['INT', {}]},
                             later: {'value': ['STRING', {}] if later == 'optional' else 'PROMPT'}}}
            node, result, _, _ = inspect(raw)
            self.assertFalse(result['valid'])
            self.assertTrue(any('Duplicate' in x for x in node['schema_errors']))

    def test_malformed_descriptor_shape_and_flags_are_opaque_without_losing_the_raw_value(self):
        descriptors = [['INT', None], ['INT', {} , {'extension': [2**64-1]}],
                       ['INT', {'forceInput': 'false'}], {'type': 'INT', 'isOptional': 'yes'},
                       ['INT', {'hidden': 'false'}], ['IMAGE', {'lazy': 1}],
                       ['INT', {'defaultInput': None}], [' ', {}], ['IMAGE,,MASK', {}],
                       [['first'], {'options': ['different']}]]
        for value in descriptors:
            with self.subTest(value=value):
                node, report, doc, _ = inspect({'input': {'required': {'value': value}}}, {'value': 1})
                field = node['inputs'][0]
                self.assertEqual('unsupported', field['widget'])
                self.assertFalse(field['hidden'])
                self.assertEqual(value, json.loads(field['source_descriptor_json']))
                self.assertFalse(report['valid'])
                self.assertIsNone(report['graph'])
                self.assertEqual(1, doc['nodes']['1']['inputs']['value'])

    def test_remote_flag_requires_a_real_boolean_before_static_authoring(self):
        for value in (0, '', None, [], {}):
            with self.subTest(value=value):
                node, report, _, _ = inspect(
                    {'input': {'required': {'value': ['INT', {'remote': value}]}}},
                    {'value': 1},
                )
                field = node['inputs'][0]
                self.assertEqual('unsupported', field['widget'])
                self.assertIn('remote must be boolean', field['reason'])
                self.assertFalse(field['capabilities']['static_validation'])
                self.assertFalse(report['valid'])
                self.assertIsNone(report['graph'])
        node, report, _, _ = inspect(
            {'input': {'required': {'value': ['INT', {'remote': False}]}}},
            {'value': 1},
        )
        self.assertEqual('int', node['inputs'][0]['widget'])
        self.assertTrue(report['valid'])
        node, report, _, _ = inspect(
            {'input': {'required': {'value': ['INT', {'remote': True}]}}},
            {'value': 1},
        )
        self.assertEqual('unsupported', node['inputs'][0]['widget'])
        self.assertIn('remote behaviour needs a native adapter', node['inputs'][0]['reason'])
        self.assertFalse(report['valid'])

    def test_diagnostics_are_node_local_and_disconnected_opaque_data_survives(self):
        info = {'Good': {'input': {}, 'output': [], 'output_node': True},
                'Bad': {'input': 17, 'output': [], 'output_node': True}}
        schema = catalog(info, 'local-fixture')
        doc = new_document({'1': {'class_type': 'Good', 'inputs': {}},
                            '2': {'class_type': 'Bad', 'inputs': {'opaque': [None, {'seed': 2**64-1}]}}}, schema)
        doc['outputs'] = ['1']; before = canonical(doc)
        self.assertTrue(compile_document(doc, schema)['valid'])
        self.assertEqual(before, canonical(doc))
        doc['outputs'] = ['2']
        self.assertFalse(compile_document(doc, schema)['valid'])
        self.assertEqual(2**64-1, decode(canonical(doc))['nodes']['2']['inputs']['opaque'][1]['seed'])

    def test_supported_adapters_have_explicit_capabilities_not_runtime_approval(self):
        for description, widget in ((['INT', {'min': 0, 'max': 2**64-1}], 'int'),
                                     (['FLOAT', {}], 'float'), (['BOOLEAN', {}], 'boolean'),
                                     (['STRING', {'multiline': True}], 'string'),
                                     ([['a', 'b'], {}], 'combo'),
                                     (['IMAGE,MASK', {'lazy': True}], 'socket'),
                                     (['INT', {'forceInput': True}], 'socket')):
            node, _, _, _ = inspect({'input': {'required': {'value': description}}})
            field = node['inputs'][0]
            self.assertEqual(widget, field['widget'])
            self.assertTrue(field['capabilities']['static_validation'])
            self.assertTrue(field['capabilities']['document_round_trip'])
            self.assertFalse(field['capabilities']['runtime_qualified'])
            self.assertTrue(field['adapter'].endswith('/v1'))

    def test_python_int64_and_hidden_list_metadata_keep_exact_identity(self):
        raw = {'input': {'required': {'value': ['INT', {'min': -(2**63), 'max': 2**64-1}]},
                         'hidden': {'prompt': 'PROMPT'}}, 'input_is_list': True,
               'vendor_metadata': {'future': ['literal', {'seed': 2**64-1, 'fraction': 1.0}]}}
        original = copy.deepcopy(raw)
        for number in (-(2**63), 2**53-1, 2**53, 2**63-1, 2**64-1):
            node, report, doc, info = inspect(raw, {'value': number})
            self.assertTrue(report['valid'])
            self.assertEqual(number, decode(canonical(doc))['nodes']['1']['inputs']['value'])
            self.assertEqual(info['Node'], json.loads(node['source_definition_json']))
        self.assertEqual(original, raw)
        for invalid in ('true', 1, None):
            _, report, _, _ = inspect({**raw, 'input_is_list': invalid}, {'value': 1})
            self.assertFalse(report['valid'])

    @unittest.skipUnless(shutil.which('node'), 'Node required for actual browser-number JSON semantics')
    def test_json_transport_preserves_raw_schema_numbers_as_text_through_javascript(self):
        raw = {'input': {'required': {'value': ['INT', {'max': 2**64-1}]}},
               'vendor': {'small_float': 1.0, 'negative': -(2**63)}}
        node, _, _, _ = inspect(raw)
        payload = canonical(node)
        program = 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",x=>s+=x);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))));'
        result = subprocess.run(['node', '-e', program], input=payload, capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        received = json.loads(result.stdout)
        self.assertEqual(node['source_definition_json'], received['source_definition_json'])
        self.assertEqual(node['inputs'][0]['source_descriptor_json'], received['inputs'][0]['source_descriptor_json'])
        restored = json.loads(received['source_definition_json'])
        self.assertEqual(2**64-1, restored['input']['required']['value'][1]['max'])
        self.assertIs(type(restored['vendor']['small_float']), float)

    def test_empty_socket_tokens_are_not_compatible_even_with_wildcards(self):
        for source, target in (('', ''), (' ', '*'), ('IMAGE,', 'IMAGE'), ('IMAGE', ',IMAGE'), ('*', ',MASK')):
            with self.subTest(source=source, target=target):
                self.assertFalse(compatible(source, target))
        for source, target in (('IMAGE', 'IMAGE,MASK'), ('IMAGE', 'MASK,*'), ('*', 'IMAGE')):
            self.assertTrue(compatible(source, target))


if __name__ == '__main__': unittest.main()
