"""Qwen-Image 2.1 alpha routing (#878): full-frame recipes save RGB, the sprite keeps alpha.

The Qwen 2.1 VAE decodes RGBA with faint partial alpha, which poisons any
alpha-based crop. qwen21-t2i and qwen21-edit route SaveImage through a core
SplitImageWithAlpha node; qwen21-rgba keeps the direct VAEDecode wiring and
relies on the explicit `cleanup` finishing step instead.
"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def api(preset_id):
    return json.loads((ROOT / f'workflows/api/{preset_id}-api.json').read_text(encoding='utf-8'))


def save_source(graph):
    saves = [node for node in graph.values() if node['class_type'] == 'SaveImage']
    assert len(saves) == 1
    return saves[0]['inputs']['images']


class Qwen21AlphaRoutingTests(unittest.TestCase):
    def test_full_frame_recipes_drop_alpha(self):
        for preset_id in ('qwen21-t2i', 'qwen21-edit'):
            with self.subTest(preset=preset_id):
                graph = api(preset_id)
                key, slot = save_source(graph)
                self.assertEqual(slot, 0)
                self.assertEqual(graph[key]['class_type'], 'SplitImageWithAlpha')
                self.assertEqual(graph[key]['inputs'], {'image': ['7', 0]})
                self.assertEqual(graph['7']['class_type'], 'VAEDecode')

    def test_transparent_recipe_keeps_direct_decode(self):
        graph = api('qwen21-rgba')
        self.assertEqual(save_source(graph), ['7', 0])
        self.assertNotIn('SplitImageWithAlpha', {n['class_type'] for n in graph.values()})

    def test_visual_graphs_carry_every_api_link(self):
        """#1068: graph 60 once left LoadImage unwired (no `images.image_1` socket on node 4)."""
        catalog = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))
        for preset in catalog['presets']:
            if preset.get('backend_id') != 'qwen21' or not preset.get('visual'): continue
            with self.subTest(preset=preset['id']):
                graph = api(preset['id'])
                visual = json.loads((ROOT / preset['visual']).read_text(encoding='utf-8'))
                ids = {key: index + 1 for index, key in enumerate(graph)}  # build-expansion.visual numbering
                self.assertEqual([n['type'] for n in visual['nodes']], [n['class_type'] for n in graph.values()])
                by_id = {n['id']: n for n in visual['nodes']}
                wired = {(link[1], link[2], link[3], by_id[link[3]]['inputs'][link[4]]['name']) for link in visual['links']}
                expected = {(ids[value[0]], value[1], ids[key], field) for key, node in graph.items()
                            for field, value in node['inputs'].items() if isinstance(value, list)}
                self.assertEqual(wired, expected)

    def test_builder_matches_committed_graphs(self):
        spec = importlib.util.spec_from_file_location('qwen21_builder', ROOT / 'scripts/build-qwen21-recipes.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        for preset_id, graph in builder.graphs().items():
            with self.subTest(preset=preset_id):
                self.assertEqual(graph, api(preset_id))


if __name__ == '__main__':
    unittest.main()
