"""Step presentation ordering through the real shared reducer and compiler."""
import copy
import unittest
from studio_workflow.commands import apply_commands, changes, execution_inputs_sha256
from studio_workflow.core import compile_document, document


def fixture():
    return {'format': 'studio.workflow/v1', 'name': 'Character workflow', 'revision': 7,
            'backend_id': 'primary', 'schema_sha256': '0' * 64,
            'nodes': {'1': {'class_type': 'Source', 'inputs': {'seed': 2**60 + 3}},
                      '2': {'class_type': 'Pass', 'inputs': {'image': ['1', 0]}},
                      '3': {'class_type': 'Save', 'inputs': {'image': ['2', 0]}}},
            'outputs': ['3'], 'disabled': [], 'bypass': {'2': {'0': 'image'}},
            'positions': {'1': [20, 30]}, 'source': {'description': 'Retained annotation'},
            'steps': [{'id': key, 'name': name, 'description': 'Keep me', 'nodes': [node],
                       'controls': [{'name': 'Setting', 'node': node, 'input': field}]}
                      for key, name, node, field in [('a', 'Source', '1', 'seed'),
                                                    ('b', 'Process', '2', 'image'),
                                                    ('c', 'Output', '3', 'image')]]}


def move(key, before):
    return {'op': 'move_step', 'id': key, 'before': before}


class StepOrderTests(unittest.TestCase):
    def setUp(self):
        self.doc = document(fixture())

    def order(self, doc):
        return [step['id'] for step in doc['steps']]

    def test_move_before_first_and_to_end(self):
        moved = apply_commands(self.doc, [move('c', 'a')])
        self.assertEqual(self.order(moved), ['c', 'a', 'b'])
        self.assertEqual(self.order(apply_commands(moved, [move('c', None)])), ['a', 'b', 'c'])

    def test_every_pair_preserves_relative_order_of_other_steps(self):
        original = self.order(self.doc)
        for key in original:
            for before in [*original, None]:
                with self.subTest(key=key, before=before):
                    result = apply_commands(self.doc, [move(key, before)])
                    self.assertEqual(sorted(self.order(result)), sorted(original))
                    self.assertEqual([x for x in self.order(result) if x != key], [x for x in original if x != key])
                    if before is None:
                        self.assertEqual(self.order(result)[-1], key)
                    elif before != key:
                        self.assertEqual(self.order(result).index(key) + 1, self.order(result).index(before))

    def test_noop_moves_do_not_change_the_document(self):
        for command in [move('b', 'b'), move('a', 'b'), move('c', None)]:
            self.assertEqual(apply_commands(self.doc, [command]), self.doc)

    def test_move_is_only_a_presentation_change(self):
        original = copy.deepcopy(self.doc)
        result = apply_commands(self.doc, [move('c', 'a')])
        self.assertEqual(self.doc, original)
        self.assertEqual({k: v for k, v in result.items() if k != 'steps'},
                         {k: v for k, v in self.doc.items() if k != 'steps'})
        self.assertEqual({s['id']: s for s in result['steps']}, {s['id']: s for s in self.doc['steps']})
        self.assertEqual(execution_inputs_sha256(result), execution_inputs_sha256(self.doc))
        self.assertEqual(changes(self.doc, result), {'added_nodes': [], 'removed_nodes': [],
                         'changed_nodes': [], 'changed_fields': ['steps'], 'execution_inputs_changed': False})
        result['steps'][0]['name'] = 'Changed result'
        self.assertEqual(self.doc, original, 'The reducer must not alias its input')

    def test_invalid_target_fails_without_applying_an_earlier_command(self):
        for target in ['missing', 0, False, [], {}, '__proto__', '']:
            with self.subTest(target=target):
                before = copy.deepcopy(self.doc)
                with self.assertRaisesRegex(ValueError, 'destination|identifier'):
                    apply_commands(self.doc, [move('c', 'a'), move('a', target)])
                self.assertEqual(self.doc, before)

    def test_unknown_source_and_malformed_commands_are_rejected(self):
        for command in [move('missing', None), {'op': 'move_step', 'id': 'a'},
                        {**move('a', None), 'position': 1}, move(None, 'a')]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                apply_commands(self.doc, [command])

    def test_maximum_sized_step_list_reorders_without_deleting_groups(self):
        self.doc['steps'] = [{'id': str(i), 'name': 'Step ' + str(i), 'description': '',
                             'nodes': [], 'controls': []} for i in range(64)]
        result = apply_commands(self.doc, [move('63', '0')])
        self.assertEqual(self.order(result), ['63', *map(str, range(63))])

    def test_legacy_document_without_steps_is_not_mutated_by_failed_move(self):
        del self.doc['steps']
        with self.assertRaisesRegex(ValueError, 'Unknown step'):
            apply_commands(self.doc, [move('a', None)])
        self.assertNotIn('steps', self.doc)

    def test_compiled_graph_and_output_hash_do_not_change(self):
        def field(name, kind, widget):
            return {'name': name, 'type': kind, 'widget': widget, 'required': True, 'hidden': False, 'options': {}}
        schema = {'backend_id': 'primary', 'schema_sha256': '0' * 64, 'nodes': {
            'Source': {'inputs': [field('seed', 'INT', 'int')], 'outputs': [{'index': 0, 'type': 'IMAGE'}]},
            'Pass': {'inputs': [field('image', 'IMAGE', 'socket')], 'outputs': [{'index': 0, 'type': 'IMAGE'}]},
            'Save': {'inputs': [field('image', 'IMAGE', 'socket')], 'outputs': [], 'output_node': True}}}
        before = compile_document(self.doc, schema)
        after = compile_document(apply_commands(self.doc, [move('c', 'a')]), schema)
        self.assertTrue(before['valid'], before['errors']); self.assertTrue(after['valid'], after['errors'])
        self.assertEqual(before['graph'], after['graph'])
        self.assertEqual(before['graph_sha256'], after['graph_sha256'])
        self.assertNotEqual(before['document_sha256'], after['document_sha256'])
        self.assertFalse(after['generation_submitted'])
