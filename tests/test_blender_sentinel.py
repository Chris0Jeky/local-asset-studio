import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_sentinel as sentinel

FIXTURES = ROOT / "tests" / "fixtures" / "blender_lab"
MANIFEST = json.loads((FIXTURES / "manifest-lab-asset-5.4.0-alpha-67c9bdddb88b.json").read_text(encoding="utf-8"))
SAMPLE = json.loads((FIXTURES / "sentinel-result-material-mismatch-5.4.0-alpha.json").read_text(encoding="utf-8"))
LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


def obj(manifest, name): return next(o for o in manifest["objects"] if o["name"] == name)


class StructuralTests(unittest.TestCase):
    def test_identical_manifests_have_no_failures(self):
        result = sentinel.compare_manifests(MANIFEST, copy.deepcopy(MANIFEST))
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["expected_exclusions"], [])

    def test_missing_mesh_material_swap_and_lost_texture_are_failures(self):
        roundtrip = copy.deepcopy(MANIFEST)
        roundtrip["objects"] = [o for o in roundtrip["objects"] if o["name"] != "Badge"]
        obj(roundtrip, "Head")["material_slots"][0]["material"] = "BodyTextured"
        next(m for m in roundtrip["materials"] if m["name"] == "BodyTextured")["images"] = []
        failures = sentinel.compare_manifests(MANIFEST, roundtrip)["failures"]
        self.assertIn("visible mesh Badge is missing after the roundtrip", failures)
        self.assertIn("Head: materials ['HeadRed'] -> ['BodyTextured']", failures)
        self.assertIn("material BodyTextured: textures ['lab-checker'] -> []", failures)

    def test_principled_value_drift_beyond_tolerance_fails(self):
        roundtrip = copy.deepcopy(MANIFEST)
        next(m for m in roundtrip["materials"] if m["name"] == "HeadRed")["principled"]["roughness"] = 0.6 + 1e-3
        self.assertEqual(sentinel.compare_manifests(MANIFEST, roundtrip)["failures"], [])
        next(m for m in roundtrip["materials"] if m["name"] == "HeadRed")["principled"]["roughness"] = 0.7
        self.assertEqual(sentinel.compare_manifests(MANIFEST, roundtrip)["failures"], ["material HeadRed: roughness 0.6 -> 0.7"])

    def test_hidden_source_mesh_is_an_expected_exclusion_and_modifiers_are_format_losses(self):
        source = copy.deepcopy(MANIFEST)
        obj(source, "Badge")["hide_render"] = True
        obj(source, "Head")["modifiers"].append({"name": "Smooth", "type": "SUBSURF", "show_render": True, "show_viewport": True, "object": None})
        roundtrip = copy.deepcopy(MANIFEST); roundtrip["objects"] = [o for o in roundtrip["objects"] if o["name"] != "Badge"]
        result = sentinel.compare_manifests(source, roundtrip)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["expected_exclusions"], ["Badge (MESH, hidden) is not exported by the LAS settings"])
        self.assertIn("Head: SUBSURF modifier 'Smooth' is not applied by the LAS export settings", result["format_losses"])

    def test_unexpected_mesh_and_missing_source_image(self):
        source, roundtrip = copy.deepcopy(MANIFEST), copy.deepcopy(MANIFEST)
        source["images"][0]["missing"] = True
        extra = copy.deepcopy(obj(roundtrip, "Badge")); extra["name"] = "Stray"; roundtrip["objects"].append(extra)
        failures = sentinel.compare_manifests(source, roundtrip)["failures"]
        self.assertIn("unexpected visible mesh Stray after the roundtrip", failures)
        self.assertIn("source image lab-checker is missing (lab-checker.png)", failures)


class VisualTests(unittest.TestCase):
    PALETTE = {"Red": [1.0, 0.0, 0.0], "Blue": [0.0, 0.0, 1.0]}

    def _pair(self, tmp, paint):
        a = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); a.paste((255, 0, 0, 255), (8, 8, 40, 40))
        b = a.copy(); paint(b)
        a.save(Path(tmp) / "a.png"); b.save(Path(tmp) / "b.png")
        return Path(tmp) / "a.png", Path(tmp) / "b.png", Path(tmp) / "d.png"

    def test_identical_images_do_not_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = sentinel.compare_image(*self._pair(tmp, lambda b: None), "object_id", self.PALETTE)
        self.assertEqual((record["changed_fraction"], record["boxes"], record["warn"], record["silhouette_iou"]), (0.0, [], False, 1.0))

    def test_changed_region_is_boxed_and_attributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = sentinel.compare_image(*self._pair(tmp, lambda b: b.paste((0, 0, 255, 255), (24, 24, 40, 40))), "object_id", self.PALETTE)
            self.assertTrue((Path(tmp) / "d.png").is_file())
        self.assertEqual(record["boxes"], [[24, 24, 40, 40]])
        self.assertEqual(record["attribution"], [{"box": [24, 24, 40, 40], "source": ["Red"], "roundtrip": ["Blue"]}])
        self.assertTrue(record["warn"])
        self.assertEqual(record["silhouette_iou"], 1.0)

    def test_missing_part_lowers_silhouette_iou(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = sentinel.compare_image(*self._pair(tmp, lambda b: b.paste((0, 0, 0, 0), (8, 8, 40, 24))), "object_id", self.PALETTE)
        self.assertEqual(record["silhouette_iou"], 0.5)
        self.assertEqual(record["attribution"][0]["roundtrip"], [])

    def test_lit_noise_below_pixel_threshold_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            noisy = lambda b: b.paste((235, 20, 20, 255), (8, 8, 40, 40))
            record = sentinel.compare_image(*self._pair(tmp, noisy), "lit")
        self.assertEqual((record["changed_fraction"], record["warn"]), (0.0, False))


class ContractTests(unittest.TestCase):
    def test_sample_result_has_the_brief_shape_and_caught_the_seeded_defect(self):
        self.assertLessEqual({"pass", "blender", "source", "export", "roundtrip", "structural_failures", "visual_warnings", "artifacts"}, set(SAMPLE))
        self.assertFalse(SAMPLE["pass"])
        self.assertEqual(SAMPLE["seeded_defect"]["kind"], "material-mismatch")
        self.assertEqual(SAMPLE["export"]["settings"], sentinel.lab.bpy_side.LAS_GLTF_SETTINGS)
        self.assertTrue(SAMPLE["source"]["unchanged"])

    def test_refuses_reused_output_and_unknown_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            blend = Path(tmp) / "a.blend"; blend.write_bytes(b"")
            with self.assertRaises(sentinel.lab.BlenderLabError): sentinel.sentinel(exe, blend, tmp)
            with self.assertRaises(sentinel.lab.BlenderLabError): sentinel.sentinel(exe, blend, Path(tmp) / "new", "bogus")


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live sentinel")
class LiveSentinelTests(unittest.TestCase):
    def test_control_passes_and_every_seeded_defect_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            blend = sentinel.lab.make_fixture(LIVE_BLENDER, Path(tmp) / "asset")
            control = sentinel.sentinel(LIVE_BLENDER, blend, Path(tmp) / "control")
            self.assertTrue(control["pass"], control["structural_failures"] + control["visual_warnings"])
            for defect in sentinel.lab.bpy_side.SEEDED_DEFECTS:
                result = sentinel.sentinel(LIVE_BLENDER, blend, Path(tmp) / defect, defect)
                self.assertFalse(result["pass"], defect)
                self.assertTrue(result["structural_failures"] and result["visual_warnings"], defect)


if __name__ == "__main__":
    unittest.main()
