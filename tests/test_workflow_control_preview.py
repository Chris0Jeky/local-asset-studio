"""Read-only fan-out planning over the installed schema and existing commands."""
import copy
import unittest
from studio_workflow.core import catalog, canonical, digest, new_document
from studio_workflow.commands import apply_commands
try:
    from studio_workflow.control_preview import preview
except ImportError:
    preview = None


def fixture(kind='INT', first=None, second=None):
    options = {'min': 0, 'max': 100, 'step': 1} if kind in ('INT', 'FLOAT') else {}
    info = {key: {'input': {'required': {'value': [kind, copy.deepcopy(options)]}},
                  'output': []} for key in ('Source', 'Finish')}
    if first is not None: info['Source']['input']['required']['value'] = first
    if second is not None: info['Finish']['input']['required']['value'] = second
    doc = new_document({'a': {'class_type': 'Source', 'inputs': {'value': 1}},
                        'b': {'class_type': 'Finish', 'inputs': {'value': 2}}}, catalog(info, 'primary'))
    control = {'format': 'studio.control/v1', 'name': 'Shared setting',
               'targets': [{'node': 'a', 'input': 'value'}, {'node': 'b', 'input': 'value'}]}
    return {'document': doc, 'expected_revision': doc['revision'], 'control': control, 'value': 12}, info


class ControlPreviewTests(unittest.TestCase):
    def call(self, value, info, backend='primary'):
        self.assertTrue(callable(preview), 'The shared control preview planner is missing')
        return preview(value, info, backend)

    def codes(self, report):
        return {row['code'] for row in report['diagnostics']}

    def block(self, request, info, code, backend='primary'):
        report = self.call(request, info, backend)
        self.assertEqual(report['state'], 'blocked')
        self.assertEqual(report['commands'], [])
        self.assertIn(code, self.codes(report))
        self.assertFalse(report['generation_submitted']); self.assertFalse(report['committed'])
        return report

    def repin(self, request, info):
        request['document']['schema_sha256'] = digest(info)

    def test_all_targets_produce_one_ordered_batch_without_mutating_sources(self):
        value, info = fixture(); before = copy.deepcopy((value, info))
        result = self.call(value, info)
        self.assertEqual(result['state'], 'ready')
        expected = [{'op': 'set_input', 'id': key, 'input': 'value', 'value': 12} for key in ('a', 'b')]
        self.assertEqual(result['commands'], expected)
        self.assertEqual(result['document_sha256'], digest(value['document']))
        self.assertEqual(result['document_revision'], 0)
        self.assertEqual(result['control_sha256'], digest(value['control']))
        self.assertEqual(result['schema_sha256'], digest(info)); self.assertTrue(result['mixed'])
        changed = apply_commands(value['document'], result['commands'])
        self.assertEqual([n['inputs']['value'] for n in changed['nodes'].values()], [12, 12])
        self.assertEqual((value, info), before)
        self.assertFalse(result['committed']); self.assertFalse(result['generation_submitted'])
        self.assertEqual(result, self.call(value, info))

    def test_current_values_and_optional_absence_are_distinct(self):
        value, info = fixture(); value['document']['nodes']['b']['inputs'].clear()
        result = self.call(value, info)
        self.assertTrue(result['mixed']); self.assertFalse(result['targets'][1]['present'])
        self.assertIsNone(result['targets'][1]['current'])
        value['document']['nodes']['b']['inputs']['value'] = 1
        self.assertFalse(self.call(value, info)['mixed'])

    def test_mixed_comparison_keeps_json_types_distinct(self):
        value, info = fixture()
        for other in (True, 1.0, '1', None):
            value['document']['nodes']['b']['inputs']['value'] = other
            self.assertTrue(self.call(value, info)['mixed'], repr(other))

    def test_numeric_ranges_intersect_without_rounding_or_step_divisibility(self):
        value, info = fixture('FLOAT', ['FLOAT', {'min': 0.25, 'max': 2, 'step': .5}], ['FLOAT', {'min': 1, 'max': 3, 'step': .2}])
        value['value'] = 1.17
        report = self.call(value, info)
        self.assertEqual(report['state'], 'ready')
        self.assertEqual(report['interface']['minimum'], 1)
        self.assertEqual(report['interface']['maximum'], 2)
        self.assertEqual(report['commands'][0]['value'], 1.17)
        self.assertEqual(report['targets'][0]['step_hint'], .5)

    def test_empty_range_and_empty_integer_range_are_blocked(self):
        for first, second in (({'max': 1}, {'min': 2}), ({'min': .1}, {'max': .9})):
            value, info = fixture('INT', ['INT', first], ['INT', second])
            self.block(value, info, 'empty_range')

    def test_value_outside_any_target_range_blocks_every_command(self):
        value, info = fixture(); info['Finish']['input']['required']['value'][1]['max'] = 10
        self.repin(value, info); report = self.block(value, info, 'out_of_range')
        self.assertTrue(any(d['node'] == 'b' for d in report['diagnostics']))

    def test_combo_intersection_is_ordered_deduplicated_and_type_exact(self):
        value, info = fixture(first=[['x', 1, True, '1', 'x']], second=[['1', True, 'x']])
        value['value'] = True
        result = self.call(value, info)
        self.assertEqual(result['interface']['choices'], ['x', True, '1'])
        self.assertEqual(result['state'], 'ready')
        value['value'] = 1
        self.block(value, info, 'invalid_value')

    def test_disjoint_combos_are_blocked(self):
        value, info = fixture(first=[['left']], second=[['right']]); value['value'] = 'left'
        self.block(value, info, 'empty_choices')

    def test_different_types_are_not_silently_coerced(self):
        value, info = fixture(second=['FLOAT', {}])
        self.block(value, info, 'type_mismatch')

    def test_boolean_integer_string_and_float_validation(self):
        for kind, bad, good in [('INT', True, 12), ('INT', 12.0, 12), ('FLOAT', True, 12.0),
                                ('BOOLEAN', 1, False), ('STRING', 1, 'words')]:
            with self.subTest(kind=kind, bad=bad):
                value, info = fixture(kind); value['value'] = bad
                self.block(value, info, 'invalid_value')
                value['value'] = good; self.assertEqual(self.call(value, info)['state'], 'ready')

    def test_wide_integers_are_preserved_by_python(self):
        value, info = fixture('INT', ['INT', {'max': 2**64 - 1}], ['INT', {}]); value['value'] = 2**64 - 1
        value['document']['nodes']['a']['inputs']['value'] = 2**60 + 3
        result = self.call(value, info)
        self.assertEqual(result['commands'][0]['value'], 2**64 - 1)
        self.assertEqual(result['targets'][0]['current'], 2**60 + 3)

    def test_changed_revision_schema_and_backend_are_blocked(self):
        value, info = fixture(); value['expected_revision'] = 1
        self.block(value, info, 'stale_revision')
        value['expected_revision'] = 0
        self.block(value, info, 'stale_schema', backend='other')
        info['Source']['category'] = 'Changed schema'
        self.block(value, info, 'stale_schema')

    def test_duplicate_and_unknown_targets_are_reported_not_partially_emitted(self):
        value, info = fixture(); value['control']['targets'].append({'node': 'a', 'input': 'value'})
        self.block(value, info, 'duplicate_target')
        value['control']['targets'][-1] = {'node': 'missing', 'input': 'value'}
        self.block(value, info, 'missing_node')
        value['control']['targets'][-1] = {'node': 'a', 'input': 'missing'}
        self.block(value, info, 'missing_input')

    def test_connected_input_is_never_replaced_by_a_literal(self):
        value, info = fixture(); value['document']['nodes']['b']['inputs']['value'] = ['a', 0]
        self.block(value, info, 'connected_input')

    def test_dynamic_union_and_custom_inputs_stay_inert(self):
        for descriptor in (['COMFY_DYNAMICCOMBO_V3', {}], ['INT,FLOAT', {}], ['COLOR', {'default': '#000000'}]):
            value, info = fixture(second=descriptor)
            self.block(value, info, 'unsupported_input')

    def test_behavior_flags_refuse_without_downloading_or_evaluating_widgets(self):
        for flag in ('forceInput', 'defaultInput', 'rawLink', 'remote', 'lazy', 'is_list', 'widgetType'):
            value, info = fixture(second=['INT', {flag: True}])
            self.block(value, info, 'unsupported_input')
        for annotation in (True, 'false', 1, None):
            value, info = fixture(); info['Finish']['input_is_list'] = annotation; self.repin(value, info)
            self.block(value, info, 'unsupported_input')

    def test_duplicate_schema_input_names_and_hidden_inputs_refuse(self):
        value, info = fixture(); info['Finish']['input']['optional'] = {'value': ['INT', {}]}; self.repin(value, info)
        self.block(value, info, 'ambiguous_input')
        value, info = fixture(second=['INT', {'hidden': True}])
        self.block(value, info, 'unsupported_input')

    def test_malformed_bounds_and_step_metadata_refuse(self):
        for options in ({'min': '0'}, {'max': True}, {'step': 0}, {'min': 5, 'max': 2}):
            value, info = fixture(second=['INT', options])
            self.block(value, info, 'unsupported_input')

    def test_declared_model_and_image_selections_remain_literal_advice_only(self):
        value, info = fixture(first=[['model.safetensors']], second=[['model.safetensors']]); value['value'] = 'model.safetensors'
        result = self.call(value, info)
        self.assertEqual(result['state'], 'ready'); self.assertIn('runtime', result['notice'])
        self.assertNotIn('ticket', result); self.assertNotIn('job_id', result)

    def test_unrelated_document_metadata_and_disabled_nodes_are_not_mutated(self):
        value, info = fixture(); doc = value['document']
        doc['disabled'] = ['b']; doc['source'] = {'unrecognized': {'retain': ['yes']}}
        doc['steps'] = [{'id': 'old', 'name': 'Old control', 'description': '', 'nodes': ['a'],
                         'controls': [{'name': 'Keep', 'node': 'a', 'input': 'value'}]}]
        before = canonical(doc); self.call(value, info); self.assertEqual(canonical(doc), before)

    def test_strict_envelope_and_control_version_are_required(self):
        value, info = fixture()
        cases = [{**value, 'approved': True}, {k:v for k,v in value.items() if k!='expected_revision'},
                 {**value, 'expected_revision': False}, {**value, 'control': {**value['control'], 'format': 'studio.control/v2'}},
                 {**value, 'control': {**value['control'], 'name': ''}},
                 {**value, 'control': {**value['control'], 'targets': []}},
                 {**value, 'control': {**value['control'], 'targets': value['control']['targets'] * 17}}]
        for request in cases:
            with self.subTest(request=request), self.assertRaises(ValueError): self.call(request, info)

    def test_invalid_literal_shapes_and_nonfinite_values_refuse(self):
        for bad in (float('nan'), float('inf'), ['a', 0], {'not': 'scalar'}, None, 'x' * 65537):
            value, info = fixture(); value['value'] = bad
            with self.subTest(value=repr(bad)[:80]), self.assertRaises(ValueError): self.call(value, info)

    def test_response_size_is_bounded_without_truncating_evidence(self):
        value, info = fixture('STRING')
        value['control']['targets'] = []
        value['document']['nodes'] = {}
        for i in range(20):
            key = str(i); value['document']['nodes'][key] = {'class_type': 'Source', 'inputs': {'value': 'old'}}
            value['control']['targets'].append({'node': key, 'input': 'value'})
        value['value'] = 'x' * 65536
        with self.assertRaisesRegex(ValueError, 'limit|large'): self.call(value, info)
