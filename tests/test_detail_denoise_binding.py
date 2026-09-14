"""Actual catalog/Prepare regression; no model calls or changes to historical recipes."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_server import FakeStudio, server

ROOT = Path(__file__).resolve().parents[1]


class DetailDenoiseBindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        for path in ('presets', 'workflows/api', 'config', 'comfy/input'): (self.root/path).mkdir(parents=True)
        catalog = json.loads((ROOT/'presets/catalog.json').read_bytes())
        self.preset = next(p for p in catalog['presets'] if p['id'] == 'anime-detail-fix')
        self.original = json.loads((ROOT/self.preset['graph']).read_bytes())
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[self.preset]}), encoding='utf-8')
        (self.root/self.preset['graph']).write_text(json.dumps(self.original), encoding='utf-8')
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'comfy')}), encoding='utf-8')
        with patch.object(threading.Thread, 'start'): self.studio = FakeStudio(self.root, [])

    def prepare(self, controls, **kwargs):
        result = self.studio.prepare({'preset_id':'anime-detail-fix', 'controls':controls, **kwargs})
        self.assertFalse(self.studio.jobs); self.assertTrue(self.studio.queue.empty()); self.assertEqual(self.studio.requests, [])
        return result[1]

    def test_browser_defaults_preserve_authored_face_hand_pair(self):
        exposed = self.studio.catalog()['presets'][0]
        controls = dict(exposed['defaults']); controls.pop('reference', None)  # file inputs require an explicitly staged upload
        graph = self.prepare(controls)
        self.assertEqual(graph['12']['inputs']['denoise'], .4)
        self.assertEqual(graph['13']['inputs']['denoise'], .45)

    def test_explicit_face_strength_never_overwrites_hand_strength(self):
        for value in ('0', '0.3', '0.40', '0.55', '1'):
            with self.subTest(value=value):
                expected = copy.deepcopy(self.original); expected['12']['inputs']['denoise'] = float(value)
                self.assertEqual(self.prepare({'denoise':value}), expected)

    def test_named_variants_make_face_only_scope_visible(self):
        self.assertIn('face-only', self.preset['description'])
        for variant in self.preset['variants']:
            controls = variant.get('controls', {}); graph = self.prepare(controls, batch_count=variant.get('batch_count', 1))
            self.assertEqual(graph['13']['inputs']['denoise'], .45)
            if 'denoise' in controls:
                self.assertIn('face', variant['name'].lower()); self.assertIn('hand 0.45', variant['name'].lower())
                self.assertEqual(graph['12']['inputs']['denoise'], controls['denoise'])
        self.assertFalse(self.preset['verified'])
        self.assertIn('14caa4fb', self.preset['execution_note'])
        self.assertIn('not rerun', self.preset['execution_note'])

    def test_original_no_control_recipe_preserves_the_recorded_pair(self):
        path = ROOT/'experiments/curated/anime-fantasy-atelier/anime-detail-fix-noob-hands-recipe.json'
        before = path.read_bytes(); recorded = json.loads(before)
        self.assertNotIn('denoise', recorded['controls'])
        graph = self.prepare({})
        for node in ('12', '13'):
            self.assertEqual(graph[node]['inputs']['denoise'], recorded['workflow'][node]['inputs']['denoise'])
            self.assertEqual(graph[node]['inputs']['denoise'], recorded['submissions'][0]['graph'][node]['inputs']['denoise'])
        self.assertEqual(path.read_bytes(), before)

    def test_old_coupled_recipe_is_not_silently_certified_as_current(self):
        old = copy.deepcopy(self.original)
        for node in ('12', '13'): old[node]['inputs']['denoise'] = .3
        recipe = {'preset_id':'anime-detail-fix', 'controls':{'denoise':.3}, 'workflow':old}
        before = copy.deepcopy(recipe)
        with self.assertRaisesRegex(server.StudioError, 'differs from the current preset'):
            self.studio.check_recipe(recipe)
        self.assertEqual(recipe, before); self.assertFalse(self.studio.jobs); self.assertTrue(self.studio.queue.empty())
        self.assertEqual(self.studio.requests, [])

    def test_other_shared_controls_and_batch_seed_expansion_are_preserved(self):
        controls = {'seed':31, 'steps':24, 'cfg':5.5, 'sampler':'euler', 'scheduler':'normal', 'denoise':.3}
        graph = self.prepare(controls)
        expected = {'seed':31, 'steps':24, 'cfg':5.5, 'sampler_name':'euler', 'scheduler':'normal'}
        for node in ('12', '13'):
            for key, value in expected.items(): self.assertEqual(graph[node]['inputs'][key], value)
        job = {'graph':graph, 'preset_id':'anime-detail-fix'}
        batch, seed = self.studio._batch_graph(job, 2)
        self.assertEqual(seed, 33)
        for node in ('12', '13'): self.assertEqual(batch[node]['inputs']['seed'], 33)
        self.assertEqual(batch['12']['inputs']['denoise'], .3); self.assertEqual(batch['13']['inputs']['denoise'], .45)
        self.assertEqual(graph['12']['inputs']['seed'], 31)

    def test_hand_adjustment_handoff_names_the_shipped_hand_only_workflow(self):
        catalog = json.loads((ROOT/'presets/catalog.json').read_bytes())
        hand = next(p for p in catalog['presets'] if p['id'] == 'anime-hand')
        visual = hand['visual']
        self.assertEqual(visual, 'workflows/comfyui/27 - WAI Auto Hand Detail.json')
        self.assertTrue((ROOT/visual).is_file())
        nodes = json.loads((ROOT/visual).read_bytes())['nodes']
        self.assertTrue(any(n['type'] == 'FaceDetailer' for n in nodes))
        self.assertIn(hand['name'], self.preset['description'])
        self.assertIn('hand-only', self.preset['description'])
        self.assertNotIn('edit node 13 in the original ComfyUI graph', self.preset['description'])
        for path in ('docs/ANIME-FANTASY-ATELIER.md', 'docs/reconciliation/2026-09-14-detail-denoise.md'):
            text = (ROOT/path).read_text(encoding='utf-8')
            self.assertIn('27%20-%20WAI%20Auto%20Hand%20Detail.json', text)
            self.assertIn('hand-only', text)
