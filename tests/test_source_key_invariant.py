"""Bind the source-key rule to the catalog and to its browser copy (#600).

A preset declares that the user supplies the picture through one of `SOURCE_KEYS`. `preset_adapter`'s
`project_document` and the browser bundle guard inspect the graph for an image input as well, so they are
belt-and-braces; `studio_workflow.guidance.project` and the browser's reference staging read the keys alone.
Nothing used to assert the invariant the key-only readers depend on: that every catalog preset whose API graph
loads a picture actually declares one of those keys. Under an undeclared key the preset reads to them as
text-only, and the bundled authored example gets bound in place of the user's image.

Green means the invariant holds over every graph the shipped catalog owns (`graph` and `canonical_graph`),
that `missing_source_key` — the predicate `scripts/validate-repo.py` runs — reports the offending nodes, and
that the browser copy of both lists still matches the Python tuples. It does not prove the guards themselves
refuse correctly; those have their own tests.
"""
import json
import re
import unittest
from pathlib import Path

from studio_workflow.preset_adapter import IMAGE_INPUT_CLASSES, SOURCE_KEYS, missing_source_key

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'app/static/bundle-workflow-core.js'


class CatalogInvariant(unittest.TestCase):
    """Every shipped preset whose graph loads a picture declares a source key."""

    @classmethod
    def setUpClass(cls):
        cls.presets = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))['presets']

    def test_every_image_loading_preset_declares_a_source_key(self):
        offenders = []
        loading = 0
        for preset in self.presets:
            for key in ('graph', 'canonical_graph'):
                if not preset.get(key): continue
                graph = json.loads((ROOT / preset[key]).read_text(encoding='utf-8'))
                if any(node.get('class_type') in IMAGE_INPUT_CLASSES for node in graph.values()): loading += 1
                nodes = missing_source_key(preset, graph)
                if nodes: offenders.append((preset['id'], preset[key], nodes))
        self.assertGreater(loading, 0, 'no catalog graph loads a picture; the sweep is checking nothing')
        self.assertEqual(offenders, [], 'presets whose graph loads a picture without declaring one of '
                         + repr(SOURCE_KEYS) + ': ' + repr(offenders))


class Predicate(unittest.TestCase):
    """`missing_source_key` over temporary preset/graph fixtures, the shape validate-repo.py asserts on."""

    GRAPH = {'3': {'class_type': 'KSampler', 'inputs': {}},
             '9': {'class_type': 'LoadImage', 'inputs': {'image': 'example.png'}}}

    def test_undeclared_image_input_is_reported_with_its_node(self):
        self.assertEqual(missing_source_key({'id': 'drift'}, self.GRAPH), ['9'])

    def test_every_source_key_clears_the_same_graph(self):
        for key in SOURCE_KEYS:
            with self.subTest(key=key):
                self.assertEqual(missing_source_key({'id': 'sound', key: ['9', 'image']}, self.GRAPH), [])

    def test_a_falsy_declaration_does_not_count(self):
        """An empty `reference_slots` list declares no source; the runtime guards read it the same way."""
        self.assertEqual(missing_source_key({'id': 'empty', 'reference_slots': []}, self.GRAPH), ['9'])

    def test_a_graph_without_an_image_input_needs_no_key(self):
        self.assertEqual(missing_source_key({'id': 'text-only'}, {'3': {'class_type': 'KSampler', 'inputs': {}}}), [])

    def test_all_offending_nodes_are_reported(self):
        graph = dict(self.GRAPH, **{'2': {'class_type': 'LoadImage', 'inputs': {}}})
        self.assertEqual(missing_source_key({'id': 'two'}, graph), ['2', '9'])


class BrowserCopy(unittest.TestCase):
    """The bundle guard carries its own copy of the list; hold it to the Python tuple."""

    @classmethod
    def setUpClass(cls):
        cls.source = BUNDLE.read_text(encoding='utf-8')

    def test_bundle_guard_keys_match_source_keys(self):
        match = re.search(r"!\[((?:'[a-z_]+',?)+)\]\.some\(k=>", self.source)
        self.assertIsNotNone(match, BUNDLE.name + ' no longer guards on an inline source-key array; '
                             'update this test and keep the list in step with SOURCE_KEYS')
        self.assertEqual(tuple(re.findall(r"'([a-z_]+)'", match.group(1))), SOURCE_KEYS)

    def test_bundle_image_input_guard_matches_the_python_classes(self):
        found = tuple(re.findall(r"\.some\(n=>n\.class_type==='([A-Za-z]+)'\)", self.source))
        self.assertEqual(found, IMAGE_INPUT_CLASSES, BUNDLE.name + ' guards a different set of image-input '
                         'classes than studio_workflow/preset_adapter.py')


if __name__ == '__main__':
    unittest.main()
