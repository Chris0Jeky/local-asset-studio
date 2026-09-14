"""Diagnostic graph differences preserve distinct same-class producers."""
import copy
import unittest
import test_i2v_diagnostics  # Install the repository's app import path.
from i2v_diagnostics import graph_diff


def graph():
    return {'1': {'class_type': 'LoadImage', 'inputs': {'image': 'first.png'}},
            '2': {'class_type': 'LoadImage', 'inputs': {'image': 'second.png'}},
            '3': {'class_type': 'Consumer', 'inputs': {'source': ['1', 0]}}}


class GraphDiffTests(unittest.TestCase):
    def test_same_class_rewiring_is_not_reported_as_equal(self):
        canonical = graph(); actual = copy.deepcopy(canonical)
        actual['3']['inputs']['source'] = ['2', 0]
        changes = graph_diff(actual, canonical)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['field'], 'source')
        self.assertEqual(changes[0]['canonical']['ref_position'], 0)
        self.assertEqual(changes[0]['actual']['ref_position'], 1)

    def test_added_and_removed_nodes_have_correct_direction_and_identity(self):
        canonical = graph(); actual = copy.deepcopy(canonical)
        actual['4'] = {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0]}}
        added = graph_diff(actual, canonical)
        self.assertEqual(len(added), 1)
        self.assertEqual((added[0]['kind'], added[0]['actual_node_id'], added[0]['canonical_node_id']), ('added', '4', None))
        removed = graph_diff(canonical, actual)
        self.assertEqual((removed[0]['kind'], removed[0]['actual_node_id'], removed[0]['canonical_node_id']), ('removed', None, '4'))

    def test_null_and_missing_inputs_are_distinguished(self):
        canonical = graph(); canonical['3']['inputs']['optional'] = None
        changes = graph_diff(graph(), canonical)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['field'], 'optional')
        self.assertTrue(changes[0]['canonical_present'])
        self.assertFalse(changes[0]['actual_present'])

    def test_nested_connections_keep_producer_identity(self):
        canonical = graph(); actual = copy.deepcopy(canonical)
        canonical['3']['inputs']['options'] = {'references': [['1', 0]]}
        actual['3']['inputs']['options'] = {'references': [['2', 0]]}
        self.assertEqual([item['field'] for item in graph_diff(actual, canonical)], ['options'])

    def test_consistent_id_renumbering_is_still_ignored(self):
        canonical = graph(); actual = {}
        for old, new in (('1', '70'), ('2', '90'), ('3', '5')):
            actual[new] = copy.deepcopy(canonical[old])
        actual['5']['inputs']['source'] = ['70', 0]
        before = copy.deepcopy((actual, canonical))
        self.assertEqual(graph_diff(actual, canonical), [])
        self.assertEqual((actual, canonical), before)

    def test_output_index_changes_remain_visible(self):
        canonical = graph(); actual = copy.deepcopy(canonical)
        actual['3']['inputs']['source'] = ['1', 1]
        self.assertEqual(len(graph_diff(actual, canonical)), 1)

    def test_boolean_socket_values_are_not_normalized_as_integer_links(self):
        canonical = graph(); actual = copy.deepcopy(canonical)
        actual['3']['inputs']['source'] = ['1', False]
        self.assertEqual(len(graph_diff(actual, canonical)), 1)


if __name__ == '__main__':
    unittest.main()
