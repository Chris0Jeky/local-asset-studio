"""Catalog ownership contracts for the saved-board lineage invariant (#630).

No model execution: capability describes authored graph wiring, not visual fidelity.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import continuation


class ContinuationSourceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.presets = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']

    def boards(self):
        for preset in self.presets:
            graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
            if continuation.capability(preset, graph)['source_input'] == 'last_reference':
                yield preset, graph

    def test_every_named_source_is_an_authored_consumed_binding(self):
        boards = list(self.boards())
        self.assertTrue(boards, 'Exercise actual named-source recipes, not a vacuous assertion')
        for preset, graph in boards:
            with self.subTest(preset=preset['id']):
                self.assertTrue(preset['reference_board'])
                self.assertIn(preset['last_reference'], continuation.reference_bindings(preset))
                self.assertTrue(continuation.consumes_reference(graph, preset['last_reference']))
                self.assertTrue(continuation.capability(preset, graph)['consumes_source'])

    def test_removing_the_named_binding_cannot_advertise_a_named_source(self):
        for preset, graph in self.boards():
            with self.subTest(preset=preset['id']):
                mutated = copy.deepcopy(preset)
                del mutated['last_reference']
                # A stale/forged catalog projection cannot supply the missing binding.
                mutated['continuation_capability'] = {'source_input': 'last_reference', 'consumes_source': True}
                self.assertEqual(continuation.capability(mutated, graph)['source_input'], 'reference')

    def test_disconnected_named_loader_cannot_claim_consumed_source(self):
        for preset, graph in self.boards():
            with self.subTest(preset=preset['id']):
                del graph[str(preset['last_reference'][0])]
                capability = continuation.capability(preset, graph)
                self.assertFalse(capability['consumes_source'])
                self.assertEqual(capability['source_input'], 'reference')
