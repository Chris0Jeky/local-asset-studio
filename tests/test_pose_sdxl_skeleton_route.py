"""The SDXL drawn-skeleton route (#445 items 2-3, #761): a precomputed guide reaches Xinsir OpenPose and no detector runs.

Run through discovery (it imports sibling test modules): python -m unittest discover -s tests -p "test_pose_sdxl*.py"
"""
import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'app'))

from studio_workflow import pose_raster, pose_route_binding as binding  # noqa: E402
from test_pose_guide import NoComfyStudio, payload, pose_guide, server  # noqa: E402
import test_pose_route_binding as rb  # noqa: E402

PRESETS = ('wai-skeleton',)
# Every class the precomputed path may contain. A detector (OpenposePreprocessor, DWPreprocessor, AIO_Preprocessor,
# DepthAnything..., any controlnet_aux node) is not in it, so adding one anywhere in the graph fails the test.
ALLOWED = {'CheckpointLoaderSimple', 'CLIPTextEncode', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage',
           'ControlNetLoader', 'LoadImage', 'ControlNetApplyAdvanced', 'SetUnionControlNetType'}
DETECTOR_WORDS = ('preprocessor', 'estimator', 'detector', 'openpose', 'dwpose', 'depthanything', 'annotator')


def catalog_preset(preset_id):
    catalog = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))
    return next(p for p in catalog['presets'] if p['id'] == preset_id)


def links(graph):
    """(source node, output, consumer node, input) for every link in an API graph."""
    return [(value[0], value[1], node_id, field) for node_id, node in graph.items()
            for field, value in node['inputs'].items() if isinstance(value, list)]


def upstream(graph, starts):
    seen, todo = set(), list(starts)
    while todo:
        node = todo.pop()
        if node in seen: continue
        seen.add(node); todo.extend(source for source, _, consumer, _ in links(graph) if consumer == node)
    return seen


class RouteGraphTests(unittest.TestCase):
    def test_the_catalog_declares_one_pose_slot_drawn_with_the_openpose_renderer(self):
        for preset_id in PRESETS:
            with self.subTest(preset=preset_id):
                preset = catalog_preset(preset_id); graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
                self.assertEqual(preset['pose_guide_renderer'], pose_raster.OPENPOSE_RENDERER)
                self.assertEqual([slot['role'] for slot in preset['reference_slots']], ['pose'])
                self.assertEqual(preset['reference_board']['min'], 1, 'Generate waits for a guide; the authored example never runs')
                self.assertNotIn('reference', preset); self.assertNotIn('last_reference', preset)
                node, field = preset['reference_slots'][0]['binding']
                self.assertEqual((graph[node]['class_type'], field), ('LoadImage', 'image'))
                strength_node, strength_field = preset['pose_strength']
                self.assertEqual((graph[strength_node]['class_type'], strength_field), ('ControlNetApplyAdvanced', 'strength'))

    def test_no_detector_is_reachable_and_the_guide_feeds_the_controlnet_directly(self):
        for preset_id in PRESETS:
            with self.subTest(preset=preset_id):
                preset = catalog_preset(preset_id); graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
                classes = {node['class_type'] for node in graph.values()}
                self.assertLessEqual(classes, ALLOWED)
                self.assertFalse([c for c in classes if any(word in c.lower() for word in DETECTOR_WORDS)])
                saves = [n for n, node in graph.items() if node['class_type'] == 'SaveImage']
                self.assertEqual(upstream(graph, saves), set(graph), 'no node sits off the path to the saved picture')
                guide, _ = preset['reference_slots'][0]['binding']
                self.assertEqual([n for n, node in graph.items() if node['class_type'] == 'LoadImage'], [guide])
                consumers = [(consumer, field) for source, _, consumer, field in links(graph) if source == guide]
                self.assertEqual(len(consumers), 1)
                apply_node, field = consumers[0]
                self.assertEqual((graph[apply_node]['class_type'], field), ('ControlNetApplyAdvanced', 'image'))
                loader = graph[apply_node]['inputs']['control_net'][0]
                if graph[loader]['class_type'] == 'SetUnionControlNetType':
                    self.assertEqual(graph[loader]['inputs']['type'], 'openpose'); loader = graph[loader]['inputs']['control_net'][0]
                self.assertEqual(graph[loader]['class_type'], 'ControlNetLoader')
                self.assertIn(graph[loader]['inputs']['control_net_name'],
                              ('xinsir-openpose-sdxl.safetensors', 'xinsir-union-sdxl-1.0.safetensors'))
                samplers = [node for node in graph.values() if node['class_type'] == 'KSampler']
                self.assertEqual(len(samplers), 1)
                self.assertEqual((samplers[0]['inputs']['positive'], samplers[0]['inputs']['negative']), ([apply_node, 0], [apply_node, 1]))


class RouteStudioPathTests(unittest.TestCase):
    """The shipped preset and graph on a real Studio whose ComfyUI seam refuses to be called."""
    def studio_for(self, preset_id):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name)
        preset = catalog_preset(preset_id)
        (root / 'presets').mkdir(); (root / 'workflows/api').mkdir(parents=True)
        (root / 'config').mkdir(); (root / 'fake-comfy/input').mkdir(parents=True)
        (root / 'presets/catalog.json').write_text(json.dumps({'presets': [preset]}), encoding='utf-8')
        (root / 'workflows/api' / Path(preset['graph']).name).write_bytes((ROOT / preset['graph']).read_bytes())
        (root / 'config/local.json').write_text(json.dumps({'comfy_root': str(root / 'fake-comfy')}))
        with patch.object(threading.Thread, 'start', lambda *_: None): studio = NoComfyStudio(root)
        return preset, studio

    def test_the_drawn_guide_binds_to_the_control_image_and_nothing_is_submitted(self):
        for preset_id in PRESETS:
            with self.subTest(preset=preset_id):
                preset, studio = self.studio_for(preset_id)
                guide = pose_guide.render(studio, payload(renderer=preset['pose_guide_renderer']))
                result = studio.preview({'preset_id': preset_id, 'batch_count': 1,
                                         'controls': {'width': 256, 'height': 384, 'seed': 7, 'pose_strength': 0.8},
                                         'references': [{'file': guide['file'], 'role': 'pose', 'sha256': guide['sha256'],
                                                         'contribution': '', 'avoid': ''}]})
                node, field = preset['reference_slots'][0]['binding']
                self.assertEqual(result['workflow'][node]['inputs'][field], guide['file'])
                apply_node, strength = preset['pose_strength']
                self.assertEqual(result['workflow'][apply_node]['inputs'][strength], 0.8)
                self.assertEqual([(r['slot'], r['role'], r['file']) for r in result['references']], [(1, 'pose', guide['file'])])
                self.assertFalse(result['submitted']); self.assertFalse(studio.jobs); self.assertEqual(studio.requests, [])

    def test_without_a_guide_the_recipe_refuses_to_prepare(self):
        for preset_id in PRESETS:
            with self.subTest(preset=preset_id):
                _, studio = self.studio_for(preset_id)
                with self.assertRaisesRegex((ValueError, server.StudioError), 'Attach at least 1 picture'):
                    studio.preview({'preset_id': preset_id, 'batch_count': 1, 'controls': {}})
                self.assertEqual(studio.requests, [])


class RouteBindingTests(unittest.TestCase):
    """pose_route_binding's sdxl-corrected-skeleton contract, now with the renderer this route draws with."""
    def openpose_request(self, pose, data, **overrides):
        request = rb.skeleton_request(pose, data, renderer_id=pose_raster.OPENPOSE_RENDERER,
                                      renderer_pin=pose_raster.renderer_sha256(pose_raster.OPENPOSE_RENDERER))
        for key, value in overrides.items(): request['route'][key] = value
        return request

    def test_the_openpose_guide_is_recomputed_exactly_and_no_detector_runs(self):
        pose = rb.artifact(missing=('right_ear',)); data = pose_raster.render_png(pose, .3, pose_raster.OPENPOSE_RENDERER)
        result = binding.compile_binding(self.openpose_request(pose, data), data, artifact=pose)
        self.assertEqual(result['route']['native_slot'], 'control-image')
        self.assertEqual(result['route']['detector_behavior'], 'bypass-precomputed-guide')
        self.assertEqual(result['diagnostics']['detector_invocations'], 0)
        self.assertEqual(result['diagnostics']['renderer_validation'], 'recomputed-exact')
        self.assertEqual(result['diagnostics']['renderer_identity'], pose_raster.renderer_identity(pose_raster.OPENPOSE_RENDERER))
        self.assertFalse(result['ready_for_execution'])

    def test_refusals(self):
        pose = rb.artifact(); openpose = pose_raster.render_png(pose, .3, pose_raster.OPENPOSE_RENDERER)
        lines = pose_raster.render_png(pose, .3)
        blank = io.BytesIO(); Image.new('RGB', (256, 256), (0, 0, 0)).save(blank, 'PNG'); blank = blank.getvalue()
        cases = {
            'thin-line bytes declared as the OpenPose drawing': (self.openpose_request(pose, lines), lines),
            'a blank guide': (self.openpose_request(pose, blank), blank),
            'the Klein renderer pin on the OpenPose renderer': (rb.skeleton_request(pose, openpose, renderer_id=pose_raster.OPENPOSE_RENDERER), openpose),
            'the Klein geometry slot on the SDXL route': (self.openpose_request(pose, openpose, native_slot='geometry-reference'), openpose),
            'a detector route relabelled as a bypass': (self.openpose_request(pose, openpose, detector_behavior='not-applicable'), openpose),
            'a pose-donor source kind on the skeleton route': (self.openpose_request(pose, openpose, source_kind='rgb-pose-donor'), openpose),
        }
        for name, (request, data) in cases.items():
            with self.subTest(case=name), self.assertRaises(ValueError): binding.compile_binding(request, data, artifact=pose)
        self.assertNotEqual(hashlib.sha256(openpose).hexdigest(), hashlib.sha256(lines).hexdigest())


if __name__ == '__main__':
    unittest.main()
