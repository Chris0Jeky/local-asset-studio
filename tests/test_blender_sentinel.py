import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_damaged_shape_key_deformation_fails(self):
        roundtrip = copy.deepcopy(MANIFEST)
        head = next(m for m in roundtrip["meshes"] if m["name"] == "Head")
        head["shape_keys"]["keys"][1]["delta_max"] /= 2
        self.assertEqual(sentinel.compare_manifests(MANIFEST, roundtrip)["failures"],
                         ["Head: shape key Squash deformation changed (max delta 0.096 -> 0.048)"])

    def test_truncated_or_altered_animation_fails(self):
        truncated = copy.deepcopy(MANIFEST)
        truncated["pose_samples"]["Rig"]["frames"] = [1, 4, 6, 9, 12]
        self.assertIn("armature Rig: sampled frames", sentinel.compare_manifests(MANIFEST, truncated)["failures"][0])
        moved = copy.deepcopy(MANIFEST)
        moved["pose_samples"]["Rig"]["bones"]["Neck"][2][0] += 0.01
        self.assertEqual(sentinel.compare_manifests(MANIFEST, moved)["failures"], ["armature Rig: bone Neck moved at frame 12"])

    def test_lost_twist_shows_in_deformed_moments_even_when_bone_heads_stay(self):
        roundtrip = copy.deepcopy(MANIFEST)
        roundtrip["deform_samples"]["Body"]["moments"][2] = copy.deepcopy(MANIFEST["deform_samples"]["Body"]["moments"][0])
        self.assertEqual(sentinel.compare_manifests(MANIFEST, roundtrip)["failures"], ["Body: deformed shape differs at frame 12"])

    def test_one_interior_shape_key_vertex_changes_the_sums(self):
        roundtrip = copy.deepcopy(MANIFEST)
        key = next(m for m in roundtrip["meshes"] if m["name"] == "Head")["shape_keys"]["keys"][1]
        key["moments"]["sum"][5] += 0.01  # one vertex's z delta moved by 1 cm; extrema unchanged
        self.assertEqual(len(sentinel.compare_manifests(MANIFEST, roundtrip)["failures"]), 1)

    def test_moment_tolerance_absorbs_float32_noise(self):
        a = {"count": 10000, "sum": [100.0, 0.0, 1.0], "products": [5.0]}
        noisy = {"count": 10000, "sum": [100.00005, 0.00005, 1.00005], "products": [5.00005]}
        self.assertFalse(sentinel._moments_differ(a, noisy))
        self.assertTrue(sentinel._moments_differ(a, {**noisy, "count": 9999}))
        self.assertTrue(sentinel._moments_differ(a, {**noisy, "sum": [100.01, 0.0, 1.0]}))

    def test_systematic_rounding_at_a_baked_offset_is_not_damage(self):
        # Terra's case: 10,000 deltas of 0.1 recovered next to a 100-unit offset drift by ~1.5e-6 each.
        a = {"count": 10000, "scale": 101.1, "sum": [1000.0], "products": [100.0]}
        drifted = {**a, "sum": [1000.0 - 0.0155], "products": [100.0 - 0.0031]}
        self.assertFalse(sentinel._moments_differ(a, drifted))
        self.assertTrue(sentinel._moments_differ({**a, "scale": 1.0}, {**drifted, "scale": 1.0}))

    def test_object_level_animation_loss_or_truncation_fails(self):
        chest = json.loads((FIXTURES / "manifest-articulated-chest.json").read_text(encoding="utf-8"))
        self.assertEqual(sentinel.compare_manifests(chest, copy.deepcopy(chest))["failures"], [])
        flattened = copy.deepcopy(chest)
        lid = flattened["object_samples"]["ChestLid"]
        lid["matrices"] = [lid["matrices"][0]] * len(lid["matrices"])
        failures = sentinel.compare_manifests(chest, flattened)["failures"]
        self.assertEqual(len(failures), 1); self.assertTrue(failures[0].startswith("ChestLid: object transform differs at frame"))
        brief = copy.deepcopy(chest)  # one mid-range frame flattened: dense sampling still sees it
        lid = brief["object_samples"]["ChestLid"]; lid["matrices"][7] = lid["matrices"][0]
        self.assertEqual(sentinel.compare_manifests(chest, brief)["failures"], [f"ChestLid: object transform differs at frame {lid['frames'][7]}"])
        truncated = copy.deepcopy(chest); truncated["object_samples"]["ChestLid"]["frames"] = list(range(1, 31))
        self.assertIn("ChestLid: object animation frames", sentinel.compare_manifests(chest, truncated)["failures"][0])

    def test_hidden_helper_animation_carries_no_export_obligation(self):
        chest = json.loads((FIXTURES / "manifest-articulated-chest.json").read_text(encoding="utf-8"))
        source = copy.deepcopy(chest)
        source["object_samples"]["CollisionProxy"] = copy.deepcopy(chest["object_samples"]["ChestLid"])
        self.assertEqual(sentinel.compare_manifests(source, chest)["failures"], [])

    def test_flipped_normals_show_as_a_signed_volume_sign_change(self):
        roundtrip = copy.deepcopy(MANIFEST)
        head = next(m for m in roundtrip["meshes"] if m["name"] == "Head")
        original = head["signed_volume"]; head["signed_volume"] = -original
        self.assertGreater(original, 0)
        self.assertEqual(sentinel.compare_manifests(MANIFEST, roundtrip)["failures"],
                         [f"Head: signed volume {original} -> {-original} (normals flipped)"])

    def test_small_closed_meshes_flip_and_open_meshes_skip_volume(self):
        source, roundtrip = copy.deepcopy(MANIFEST), copy.deepcopy(MANIFEST)
        for manifest, volume in ((source, 0.0004), (roundtrip, -0.0004)):
            next(m for m in manifest["meshes"] if m["name"] == "Badge")["signed_volume"] = volume
        self.assertEqual(sentinel.compare_manifests(source, roundtrip)["failures"], ["Badge: signed volume 0.0004 -> -0.0004 (normals flipped)"])
        for manifest in (source, roundtrip): next(m for m in manifest["meshes"] if m["name"] == "Badge")["closed"] = False
        next(m for m in roundtrip["meshes"] if m["name"] == "Badge")["signed_volume"] = 0.1667  # translated open surface
        self.assertEqual(sentinel.compare_manifests(source, roundtrip)["failures"], [])
        next(m for m in source["meshes"] if m["name"] == "Badge")["closed"] = True
        self.assertIn("Badge: closed surface became open", sentinel.compare_manifests(source, roundtrip)["failures"])

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


class LocaliseTests(unittest.TestCase):
    OBJECTS = {"Body": [0.2, 0.5, 0.8], "Badge": [0.8, 0.3, 0.2]}
    MATERIALS = {"Wood": [0.3, 0.7, 0.3], "Brass": [0.7, 0.6, 0.2]}

    def paint(self, folder, view, pass_name, boxes):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        palette = self.OBJECTS if pass_name == "object_id" else self.MATERIALS if pass_name == "material_id" else None
        for name, box in boxes:
            colour = tuple(sentinel._srgb(c) for c in palette[name]) + (255,) if palette else name
            image.paste(colour, box)
        image.save(Path(folder) / f"{view}.{pass_name}.png")

    def scene(self, folder, objects, materials, lit):
        self.paint(folder, "front", "object_id", objects); self.paint(folder, "front", "material_id", materials)
        self.paint(folder, "front", "lit", lit); self.paint(folder, "front", "clay", [((90, 90, 90, 255), (0, 0, 64, 64))])

    def run_case(self, candidate, warn):
        with tempfile.TemporaryDirectory() as ref, tempfile.TemporaryDirectory() as cand:
            self.scene(ref, [("Body", (0, 0, 40, 64)), ("Badge", (40, 20, 60, 40))], [("Wood", (0, 0, 40, 64)), ("Brass", (40, 20, 60, 40))],
                       [((120, 60, 20, 255), (0, 0, 40, 64)), ((200, 160, 40, 255), (40, 20, 60, 40))])
            self.scene(cand, *candidate)
            views = {"front": {p: {"warn": p in warn} for p in ("lit", "clay", "object_id", "material_id")}}
            evidence = {"palette": {"object": self.OBJECTS, "material": self.MATERIALS}}
            return [e["statement"] for e in sentinel.localise(views, Path(ref), Path(cand), evidence)]

    def test_material_swap_names_material_and_mesh(self):
        statements = self.run_case(([("Body", (0, 0, 40, 64)), ("Badge", (40, 20, 60, 40))], [("Wood", (0, 0, 40, 64)), ("Wood", (40, 20, 60, 40))],
                                    [((120, 60, 20, 255), (0, 0, 40, 64)), ((120, 60, 20, 255), (40, 20, 60, 40))]), {"lit", "material_id"})
        self.assertEqual(statements, ["material Brass -> Wood on Badge"])

    def test_missing_object_and_lit_only_change(self):
        missing = self.run_case(([("Body", (0, 0, 40, 64))], [("Wood", (0, 0, 40, 64))], [((120, 60, 20, 255), (0, 0, 40, 64))]),
                                {"lit", "object_id", "material_id"})
        self.assertIn("object Badge is missing or hidden here", missing)
        shading = self.run_case(([("Body", (0, 0, 40, 64)), ("Badge", (40, 20, 60, 40))], [("Wood", (0, 0, 40, 64)), ("Brass", (40, 20, 60, 40))],
                                 [((255, 255, 255, 255), (0, 0, 40, 64)), ((200, 160, 40, 255), (40, 20, 60, 40))]), {"lit"})
        self.assertEqual(shading, ["shading changed on Body (lit pass; IDs unchanged)"])


class SecondSignalTests(unittest.TestCase):
    def test_absent_critic_is_reported_unavailable(self):
        with mock.patch.dict(sys.modules, {"render_critic": None}):
            self.assertEqual(sentinel.critic_signal(Path("a"), Path("b")), {"available": False})
        self.assertIsNone(sentinel.second_opinion({"available": False}, []))

    def test_critic_runs_on_lit_views_in_reference_mode(self):
        calls = []
        def check(images, reference=(), diff_only=False, **kwargs):
            calls.append((images, reference, diff_only))
            return {"changed": True, "pixel_diff": {"front.lit": {"changed_px": 40}, "back.lit": {"changed_px": 2}}, "defects": []}
        with mock.patch.dict(sys.modules, {"render_critic": mock.Mock(check=check)}):
            result = sentinel.critic_signal(Path("ref"), Path("cand"))
        images, reference, diff_only = calls[0]
        self.assertTrue(diff_only)
        self.assertEqual([Path(p).name for p in images], [f"{v}.lit.png" for v in sentinel.lab.bpy_side.VIEWS])
        self.assertEqual(Path(reference[0]).parent, Path("ref"))
        self.assertEqual((result["changed"], result["changed_px"], result["mode"]), (True, 42, "pixel gate"))

    def test_a_failing_critic_is_reported_not_raised(self):
        def check(*args, **kwargs): raise OSError("model server unreachable")
        with mock.patch.dict(sys.modules, {"render_critic": mock.Mock(check=check)}):
            result = sentinel.critic_signal(Path("ref"), Path("cand"), server="http://127.0.0.1:8290")
        self.assertEqual(result["available"], False); self.assertIn("unreachable", result["error"])

    def test_a_change_only_the_critic_sees_becomes_a_warning(self):
        warnings = []
        self.assertFalse(sentinel.second_opinion({"available": True, "changed": True, "changed_px": 99}, warnings))
        self.assertIn("independent render critic", warnings[0])
        self.assertTrue(sentinel.second_opinion({"available": True, "changed": False, "changed_px": 0}, []))


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
                self.assertTrue(result["structural_failures"], defect)
                # Animation and shape-key damage are invisible at the evidence frame; only the manifest catches them.
                self.assertEqual(bool(result["visual_warnings"]), defect in ("missing-texture", "omitted-mesh", "material-mismatch"), defect)
            self.assertEqual(len(sentinel.lab.bpy_side.SEEDED_DEFECTS), 7)


if __name__ == "__main__":
    unittest.main()
