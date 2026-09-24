"""Optional-board auxiliary cleanup cannot consume an independently named source."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from test_optional_style_board import optional_wai
from test_references import ref


class OptionalBoardNamedSourceTests(unittest.TestCase):
    def test_named_unused_auxiliary_refuses_without_mutating_inputs(self):
        for name in ('reference', 'last_reference'):
            for node in ('12', '13'):
                for numeric in (False, True):
                    with self.subTest(name=name, node=node, numeric=numeric):
                        preset, graph = optional_wai()
                        preset[name] = (int(node), 'image') if numeric else [node, 'image']
                        before, before_preset = copy.deepcopy(graph), copy.deepcopy(preset)
                        with patch.object(ref, 'image_record', side_effect=AssertionError('Empty board read media')):
                            with self.assertRaisesRegex(ValueError, 'optional board'):
                                ref.compile_references(preset, graph, [], Path('unused'))
                        self.assertEqual(graph, before, 'A refused bypass must not partially mutate the caller graph')
                        self.assertEqual(preset, before_preset)

    def test_named_shared_auxiliary_is_retained_without_unnecessary_refusal(self):
        for name in ('reference', 'last_reference'):
            for node in ('12', '13'):
                with self.subTest(name=name, node=node):
                    preset, graph = optional_wai()
                    preset[name] = [node, 'image']
                    graph['shared'] = {'class_type':'AnotherEncoder', 'inputs':{'resource':[node, 0]}}
                    original = copy.deepcopy(graph)
                    reversed_graph = dict(reversed(list(copy.deepcopy(graph).items())))
                    with patch.object(ref, 'image_record', side_effect=AssertionError('Empty board read media')):
                        records = ref.compile_references(preset, graph, [], Path('unused'))
                        self.assertEqual(ref.compile_references(preset, reversed_graph, [], Path('unused')), records)
                    self.assertEqual(graph, reversed_graph)
                    self.assertEqual(graph[node], original[node])
                    self.assertEqual(graph['shared'], original['shared'])
                    self.assertEqual(graph['5']['inputs']['model'], ['9', 0])
                    self.assertNotIn('14', graph)
                    self.assertTrue(all(record['pruned'] for record in records))


if __name__ == '__main__':
    unittest.main()
