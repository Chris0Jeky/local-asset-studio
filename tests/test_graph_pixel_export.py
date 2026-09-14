"""Prepared pixel-preset geometry and visual parity, not native inference proof."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import threading
import unittest
from unittest.mock import patch

from test_server import server
from test_graph_validation import pipeline

ROOT = Path(__file__).resolve().parents[1]
# Sibling fixtures prepend scripts; the actual package root must still win.
sys.path.insert(0, str(ROOT))
OLD_GRAPH = '8be86165d9326422a45886f0972c2313d9921c0f7272d18e22917f39e0933d01'
# Authored generation, decoder, LoRA and raw-save nodes before the export fix.
GENERATION_NODES = 'a84ac31ba10e24ba667cd777801611d4c4ec61f6b90a6af22f530d0ce552c086'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


class PixelExportTests(unittest.TestCase):
    def setUp(self):
        self.preset = next(p for p in read(ROOT/'presets/catalog.json')['presets'] if p['id'] == 'pixel-lora')
        self.graph = read(ROOT/self.preset['graph'])
        self.visual = read(ROOT/self.preset['visual'])
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root/'presets').mkdir(); (self.root/'workflows/api').mkdir(parents=True)
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[self.preset]}), encoding='utf-8')
        (self.root/self.preset['graph']).write_bytes((ROOT/self.preset['graph']).read_bytes())
        (self.root/'config').mkdir(); (self.root/'fake-comfy/input').mkdir(parents=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}), encoding='utf-8')
        with patch.object(threading.Thread, 'start', lambda *_: None): self.studio = server.Studio(self.root)
        self.no_http = patch.object(self.studio, '_request', side_effect=AssertionError('No backend request allowed'))
        self.no_http.start(); self.addCleanup(self.no_http.stop)

    def test_prepared_exports_follow_requested_canvas_at_one_eighth_scale(self):
        cases = [(1024,1024,128,128), (832,1216,104,152), (1216,832,152,104),
                 (64,1536,8,192), (1536,64,192,8), (1000,744,125,93)]
        original = copy.deepcopy(self.graph)
        for width, height, out_width, out_height in cases:
            with self.subTest(canvas=(width,height)):
                _, graph, _, _, _ = self.studio.prepare({'preset_id':'pixel-lora',
                    'controls':{'width':str(width),'height':str(height),'seed':str(2**63-1)}})
                node = graph['9']; inputs = node['inputs']
                # Project the documented native geometry for the two relevant
                # built-in nodes; no model/tensor execution is claimed here.
                if node['class_type'] == 'ImageScaleBy':
                    observed = (round(width*inputs['scale_by']), round(height*inputs['scale_by']))
                else:
                    self.assertEqual(node['class_type'], 'ImageScale')
                    observed = (inputs['width'], inputs['height'])
                self.assertEqual(observed, (out_width,out_height))
                self.assertEqual(observed[0]*height, observed[1]*width)
                self.assertEqual(inputs['image'], ['6',0])
                self.assertEqual(inputs['upscale_method'], 'nearest-exact')
                self.assertEqual(graph['5']['inputs']['seed'], 2**63-1)
                self.assertEqual(graph['4']['inputs'], {'width':width,'height':height,'batch_size':1})
        self.assertEqual(self.graph, original)
        self.assertEqual(read(self.root/self.preset['graph']), original)
        self.assertFalse(self.studio.jobs)

    def test_generation_and_raw_output_are_unchanged(self):
        nodes = {key:value for key,value in self.graph.items() if key not in ('9','10')}
        self.assertEqual(hashlib.sha256(json.dumps(nodes,sort_keys=True,separators=(',',':')).encode()).hexdigest(), GENERATION_NODES)
        self.assertEqual(self.graph['7']['inputs']['filename_prefix'], 'Studio/Pixel-LoRA-Raw')
        self.assertEqual(self.graph['10']['inputs'], {'images':['9',0], 'filename_prefix':'Studio/Pixel-LoRA-Export'})
        _, graph, _, controls, count = self.studio.prepare({'preset_id':'pixel-lora','controls':{}})
        self.assertEqual(graph, self.graph); self.assertEqual((controls,count), ({},1))

    def test_visual_and_api_scaler_widgets_and_links_match(self):
        scale = next(node for node in self.visual['nodes'] if node['id'] == 9)
        save = next(node for node in self.visual['nodes'] if node['id'] == 10)
        self.assertEqual(scale['type'], 'ImageScaleBy')
        self.assertEqual(self.graph['9']['class_type'], scale['type'])
        self.assertEqual(scale['properties']['Node name for S&R'], scale['type'])
        self.assertEqual(scale['widgets_values'], ['nearest-exact',0.125])
        self.assertEqual(scale['widgets_values'], [self.graph['9']['inputs'][key] for key in ('upscale_method','scale_by')])
        self.assertEqual(save['widgets_values'], [self.graph['10']['inputs']['filename_prefix']])
        self.assertEqual([link[1:5] for link in self.visual['links'] if link[0] in (12,13)], [[6,0,9,0],[9,0,10,0]])

    def test_scaler_accepts_source_derived_native_contract(self):
        # Reduced ComfyUI v0.35.0 ImageScaleBy INPUT_TYPES, not an installed schema.
        info = {'FixtureImage':{'input':{},'output':['IMAGE']},
                'ImageScaleBy':{'input':{'required':{'image':['IMAGE'],
                    'upscale_method':[['nearest-exact','bilinear','area','bicubic','lanczos']],
                    'scale_by':['FLOAT',{'min':0.01,'max':8.0}]}},'output':['IMAGE']}}
        graph = {'6':{'class_type':'FixtureImage','inputs':{}},'9':copy.deepcopy(self.graph['9'])}
        self.assertIn(graph['9']['class_type'], info, 'Export must use the scale-by contract')
        verdict = pipeline.graph_check(graph, info)
        self.assertFalse(verdict['inference_verified'])
        self.assertEqual(set(graph['9']['inputs']), {'image','upscale_method','scale_by'})

    def test_picker_explains_scale_and_does_not_inherit_execution_verification(self):
        preset = self.studio.catalog()['presets'][0]
        self.assertIn('1/8', preset['description'])
        self.assertIn('128', preset['description'])
        self.assertNotIn('128px prop', preset['name'])
        self.assertFalse(preset['verified'])
        self.assertIn('20.173', preset['execution_note'])
        self.assertIn('unexecuted', preset['execution_note'])
        self.assertEqual((preset['defaults']['width'],preset['defaults']['height']), (1024,1024))

    def test_old_template_ticket_is_rejected_instead_of_silently_rebased(self):
        with self.assertRaisesRegex(server.StudioError, 'preset changed'):
            self.studio.prepare({'preset_id':'pixel-lora','controls':{},'expected_template_sha256':OLD_GRAPH})
        current = hashlib.sha256((self.root/self.preset['graph']).read_bytes()).hexdigest()
        self.studio.prepare({'preset_id':'pixel-lora','controls':{},'expected_template_sha256':current})
        self.assertFalse(self.studio.jobs)


if __name__ == '__main__': unittest.main()
