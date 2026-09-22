"""Qualification must refuse declarations rejected by their existing owners."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_prompt import schema
from studio_workflow import qualification as q


def fixture(identifier='anime'):
    def read(relative):
        return json.loads((ROOT / relative).read_text(encoding='utf-8'))
    preset = next(p for p in read('presets/catalog.json')['presets'] if p['id'] == identifier)
    return preset, read(preset['graph']), read('models/library.json'), read('research/prompt-studio/profiles.json')


def exact_profile(document):
    return next(p for p in document['profiles'] if p['id'] == 'animagine40-opt-tags-v1')


class QualificationOwnerContractTests(unittest.TestCase):
    def test_exact_profile_owner_rejections_are_inspector_rejections(self):
        cases = {
            'invalid_hash': lambda p: p['template_bindings'][0].update(graph_sha256='invalid'),
            'empty_templates': lambda p: p.update(template_bindings=[]),
            'duplicate_templates': lambda p: p['template_bindings'].append(copy.deepcopy(p['template_bindings'][0])),
            'mismatched_recipes': lambda p: p['recipes'].append('not-a-template'),
            'missing_dialect_check': lambda p: p.pop('dialect_check'),
            'wrong_dialect': lambda p: p.update(dialect='prose'),
            'missing_templates': lambda p: p.pop('template_bindings'),
            'missing_negative_binding': lambda p: p['template_bindings'][0]['bindings'].pop('negative'),
            'unknown_template_key': lambda p: p['template_bindings'][0].update(unreviewed=True),
            'colliding_text_bindings': lambda p: p['template_bindings'][0]['bindings'].update(
                negative=p['template_bindings'][0]['bindings']['positive']),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                inputs = fixture()
                mutate(exact_profile(inputs[3]))
                with patch.object(schema, 'read_json', return_value=inputs[3]), self.assertRaises(ValueError):
                    schema.profiles()
                with self.assertRaises(ValueError):
                    q.inspect_route(*inputs)

    def test_owner_and_inspector_reject_numeric_aliases_in_exact_profile_contract(self):
        for field, alias in (('min_refs', False), ('max_refs', False), ('min_refs', 0.0)):
            with self.subTest(field=field, alias=alias):
                inputs = fixture()
                exact_profile(inputs[3])[field] = alias
                with patch.object(schema, 'read_json', return_value=inputs[3]), self.assertRaises(ValueError):
                    schema.profiles()
                with self.assertRaises(ValueError):
                    q.inspect_route(*inputs)
        inputs = fixture()
        inputs[3]['schema_version'] = True
        with patch.object(schema, 'read_json', return_value=inputs[3]), self.assertRaises(ValueError):
            schema.profiles()

    def test_missing_opt_in_fields_have_typed_refusals_not_key_errors(self):
        for field in ('dialect', 'negative', 'tasks', 'min_refs', 'max_refs'):
            with self.subTest(field=field):
                inputs = fixture()
                exact_profile(inputs[3]).pop(field)
                with self.assertRaises(ValueError):
                    q.inspect_route(*inputs)

    def test_reference_roles_require_the_catalog_vocabulary(self):
        for role in (None, '', 'unknown', 'voice', [], {}, 1):
            with self.subTest(role=role):
                inputs = fixture('qwen-3ref')
                inputs[0]['reference_slots'][0]['role'] = role
                with self.assertRaisesRegex(ValueError, 'catalog reference role'):
                    q.inspect_route(*inputs)
        inputs = fixture('qwen-3ref')
        inputs[0]['reference_slots'][0].pop('role')
        with self.assertRaisesRegex(ValueError, 'catalog reference role'):
            q.inspect_route(*inputs)

    def test_reference_binding_shape_refuses_before_reporting(self):
        for pair in (None, [], ['1'], ['1', 'image', 'extra'], [[], 'image'], ['1', {}]):
            with self.subTest(pair=pair):
                inputs = fixture('qwen-3ref')
                inputs[0]['reference_slots'][0]['binding'] = pair
                with self.assertRaisesRegex(ValueError, 'catalog reference binding'):
                    q.inspect_route(*inputs)
        inputs = fixture('qwen-3ref')
        inputs[0]['reference_slots'][0].pop('binding')
        with self.assertRaisesRegex(ValueError, 'catalog reference binding'):
            q.inspect_route(*inputs)

    def test_reference_binding_targets_must_exist_in_the_selected_graph(self):
        for part, value in ((0, 'nonexistent-node'), (1, 'nonexistent-input')):
            with self.subTest(part=part):
                inputs = fixture('qwen-3ref')
                inputs[0]['reference_slots'][0]['binding'][part] = value
                with self.assertRaisesRegex(ValueError, 'catalog reference target'):
                    q.inspect_route(*inputs)

    def test_valid_catalog_roles_preserve_order_without_claiming_native_capacity(self):
        roles = ('identity', 'pose', 'style', 'costume', 'composition', 'geometry', 'motion', 'mask')
        for role in roles:
            with self.subTest(role=role):
                inputs = fixture('qwen-3ref')
                inputs[0]['reference_slots'][0]['role'] = role
                report = q.inspect_route(*inputs)
                self.assertEqual(report['references']['catalog_slots'], inputs[0]['reference_slots'])
                self.assertIsNone(report['references']['native_slot_maximum'])
                self.assertFalse(report['qualification_complete'])

    def test_valid_profile_loading_and_inspection_do_not_read_twice(self):
        inputs = fixture()
        with patch.object(schema, 'read_json', side_effect=AssertionError('pure inspection must not read')):
            report = q.inspect_route(*inputs)
        profiles = {p['id']: p for p in report['prompt_profiles']}
        self.assertTrue(profiles['animagine40-opt-tags-v1']['template_match'])
        self.assertIsNone(profiles['animagine4-tags-v1']['template_match'])

    def test_cli_returns_refusal_envelope_for_each_owner_contract(self):
        for kind in ('profile', 'reference'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                inputs = fixture('anime' if kind == 'profile' else 'qwen-3ref')
                if kind == 'profile':
                    exact_profile(inputs[3]).pop('dialect_check')
                else:
                    inputs[0]['reference_slots'][0]['binding'] = ['missing', 'image']
                documents = {
                    'presets/catalog.json': {'presets': [inputs[0]]},
                    'models/library.json': inputs[2],
                    'research/prompt-studio/profiles.json': inputs[3],
                    inputs[0]['graph']: inputs[1],
                }
                for relative, value in documents.items():
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(value), encoding='utf-8')
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    result = q.main(['--root', str(root), '--preset', inputs[0]['id']])
                self.assertEqual(result, 2)
                envelope = json.loads(stream.getvalue())
                self.assertEqual(set(envelope), {'error', 'generation_submitted', 'qualification_complete'})
                self.assertFalse(envelope['generation_submitted'])
                self.assertFalse(envelope['qualification_complete'])


if __name__ == '__main__':
    unittest.main()
