"""Exercise the real evidence setup with API-shaped, frame-dependent scene data.

These fixtures inspect renderer inputs; they do not claim native Blender render parity.
"""
import copy
import itertools
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_lab_bpy as bpy_side


class Vector(tuple):
    def __sub__(self, other):
        return Vector(a - b for a, b in zip(self, other))

    @property
    def length(self):
        return math.sqrt(sum(value * value for value in self))


class EvidenceScene:
    def __init__(self):
        self.evaluated_frames, self.renders = [], []
        self.authored_camera = SimpleNamespace(
            name="AuthoredCamera", type="CAMERA", hide_render=False,
            data=SimpleNamespace(type="PERSP", lens=71.0, ortho_scale=42.0), location=(4, 5, 6))
        self.authored_light = SimpleNamespace(
            name="AuthoredLight", type="LIGHT", hide_render=False,
            data=SimpleNamespace(energy=321.0, color=(0.2, 0.4, 0.6)))
        self.scene = SimpleNamespace(
            frame_current=37, frame_start=3, camera=self.authored_camera,
            render=SimpleNamespace(use_border=True, use_crop_to_border=True, image_settings=SimpleNamespace()),
            cycles=SimpleNamespace(), display=SimpleNamespace(shading=SimpleNamespace()),
            view_settings=SimpleNamespace())
        self.scene.frame_set = lambda frame: setattr(self.scene, "frame_current", frame)
        scene = self.scene

        class AnimatedMatrix:
            def __matmul__(self, point):
                return Vector((point[0] + scene.frame_current * 10, point[1], point[2]))

        def evaluated_get(depsgraph):
            self.evaluated_frames.append(scene.frame_current)
            return SimpleNamespace(matrix_world=AnimatedMatrix(), bound_box=list(itertools.product((-1, 1), repeat=3)))

        self.mesh = SimpleNamespace(name="OwnedMesh", type="MESH", hide_render=False,
                                    visible_get=lambda **kwargs: True, evaluated_get=evaluated_get)
        self.scene.objects = [self.mesh, self.authored_camera, self.authored_light]
        self.bpy = SimpleNamespace(
            context=SimpleNamespace(scene=scene, view_layer=object(), evaluated_depsgraph_get=lambda: object()),
            data=SimpleNamespace(materials=[], worlds=SimpleNamespace(new=lambda name: SimpleNamespace(use_nodes=True))),
            ops=SimpleNamespace(render=SimpleNamespace(render=self.capture)))

    def rig(self, scene, spec):
        return {name: SimpleNamespace(name=name, target=copy.deepcopy(spec["target"])) for name in spec["views"]}

    def capture(self, write_still):
        self.renders.append({"frame": self.scene.frame_current, "target": self.scene.camera.target,
                             "border": self.scene.render.use_border, "crop": self.scene.render.use_crop_to_border})

    def render(self, spec=None):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(sys.modules, {"bpy": self.bpy, "mathutils": SimpleNamespace(Vector=Vector)}), \
                patch.object(bpy_side, "_rig", side_effect=self.rig):
            return bpy_side.render_evidence(tmp, spec=spec)


class EvidenceRendererTests(unittest.TestCase):
    def test_requested_native_render_failure_is_not_replaced_with_capability_success(self):
        fixture = EvidenceScene()
        def unavailable(write_still): raise RuntimeError('requested render device unavailable')
        fixture.bpy.ops.render.render = unavailable
        with self.assertRaisesRegex(RuntimeError, 'render device unavailable'): fixture.render()

    def test_bounds_use_the_evidence_frame_not_the_saved_frame(self):
        fixture = EvidenceScene()
        evidence = fixture.render()
        self.assertEqual(fixture.evaluated_frames, [3])
        self.assertEqual(evidence["camera_spec"]["target"], [30.0, 0.0, 0.0])
        self.assertEqual(len(fixture.renders), 16)
        self.assertTrue(all(item["frame"] == 3 and item["target"] == [30.0, 0.0, 0.0]
                            for item in fixture.renders))

    def test_authored_border_and_crop_are_disabled_for_every_evidence_pass(self):
        fixture = EvidenceScene()
        fixture.render()
        self.assertEqual(len(fixture.renders), 16)
        self.assertTrue(all(not item["border"] and not item["crop"] for item in fixture.renders))

    def test_roundtrip_reuses_supplied_frame_and_cameras_without_touching_authored_data(self):
        fixture = EvidenceScene()
        camera_before = copy.deepcopy(vars(fixture.authored_camera))
        light_data_before = copy.deepcopy(vars(fixture.authored_light.data))
        spec = {"target": [999, 1, 2], "ortho_scale": 8, "views": copy.deepcopy(bpy_side.VIEWS), "frame": 7}
        spec_before = copy.deepcopy(spec)
        with patch.object(bpy_side, "camera_spec", side_effect=AssertionError("roundtrip must reuse the source cameras")):
            evidence = fixture.render(spec)
        self.assertEqual(spec, spec_before)
        self.assertEqual(evidence["camera_spec"], spec_before)
        self.assertTrue(all(item["frame"] == 7 and item["target"] == [999, 1, 2] for item in fixture.renders))
        self.assertEqual(vars(fixture.authored_camera), camera_before)
        self.assertEqual(vars(fixture.authored_light.data), light_data_before)
        self.assertTrue(fixture.authored_light.hide_render)


if __name__ == "__main__":
    unittest.main()
