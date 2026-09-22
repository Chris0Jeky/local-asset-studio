"""Every catalog-owned API graph receives the same link contract."""
import copy
import json
import unittest

from test_validate_repo_integer_types import ROOT, CATALOG, _read_json, _run_validator


class CanonicalGraphPayloadTests(unittest.TestCase):
    def fixture(self):
        preset = next(p for p in _read_json(CATALOG)['presets'] if p.get('canonical_graph'))
        path = ROOT / preset['canonical_graph']
        graph = _read_json(path)
        for node_id, node in graph.items():
            for field, value in node['inputs'].items():
                if isinstance(value, list) and len(value) == 2 and type(value[1]) is int:
                    return preset, path, graph, node_id, field, value
        self.fail('canonical graph must contain a connection')

    def test_canonical_graph_rejects_boolean_and_float_output_slots(self):
        preset, path, graph, node_id, field, value = self.fixture()
        for slot in (True, False, 1.0):
            with self.subTest(slot=slot):
                changed = copy.deepcopy(graph)
                changed[node_id]['inputs'][field] = [value[0], slot]
                with self.assertRaisesRegex(AssertionError, rf"{preset['id']}.*{node_id}.*{field}.*output slot.*integer"):
                    _run_validator({path: json.dumps(changed)})
        changed[node_id]['inputs'][field] = [value[0], 0]
        _run_validator({path: json.dumps(changed)})

    def test_canonical_graph_rejects_unknown_link_nodes_and_malformed_pairs(self):
        preset, path, graph, node_id, field, value = self.fixture()
        for pair, message in ((['missing-node', 0], 'unknown node'),
                              ([value[0]], 'exactly two items'),
                              (['missing-node', False], 'output slot.*integer')):
            with self.subTest(pair=pair):
                changed = copy.deepcopy(graph)
                changed[node_id]['inputs'][field] = pair
                with self.assertRaisesRegex(AssertionError, message):
                    _run_validator({path: json.dumps(changed)})


if __name__ == '__main__':
    unittest.main()
