import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_lab as lab

FIXTURES = ROOT / "tests" / "fixtures" / "blender_lab"
PROBE_45 = FIXTURES / "probe-blender-4.5.13.json"
PROBE_54 = FIXTURES / "probe-blender-5.4.0-alpha-67c9bdddb88b.json"
LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


def load(path): return json.loads(path.read_text(encoding="utf-8"))


class CommandTests(unittest.TestCase):
    def test_fixed_argv_never_loads_user_startup_or_autoexec(self):
        command = lab.command_for("C:/blender.exe", "probe", "--out", "x.json")
        self.assertEqual(command[:6], ["C:/blender.exe", "--background", "--factory-startup", "--disable-autoexec",
                                       "--python", str(lab.BPY_SCRIPT)])
        self.assertEqual(command[6:], ["--", "probe", "--out", "x.json"])

    def test_executable_must_be_absolute_existing_blender(self):
        with self.assertRaises(lab.BlenderLabError): lab.executable("blender.exe")
        with self.assertRaises(lab.BlenderLabError): lab.executable(ROOT / "missing" / "blender.exe")
        with self.assertRaises(lab.BlenderLabError): lab.executable(Path(__file__))

    def test_probe_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe.json"; out.write_text("{}")
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            with self.assertRaises(lab.BlenderLabError): lab.probe(exe, out)

    def test_run_never_replaces_an_existing_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "probe.log.json"; log.write_text("earlier receipt")
            with self.assertRaises(FileExistsError): lab.run(sys.executable, ["probe"], log)
            self.assertEqual(log.read_text(), "earlier receipt")

    def test_timeout_still_writes_a_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "slow.log.json"
            with mock.patch.object(lab, "command_for", return_value=[sys.executable, "-c", "import time; time.sleep(5)"]):
                with self.assertRaises(lab.BlenderLabError): lab.run(sys.executable, [], log, timeout=0.5)
            self.assertEqual(json.loads(log.read_text(encoding="utf-8"))["returncode"], "timeout")

    def test_blender_side_script_compiles(self):
        compile(lab.BPY_SCRIPT.read_text(encoding="utf-8"), str(lab.BPY_SCRIPT), "exec")


class ProbeFixtureTests(unittest.TestCase):
    """The committed probes are the measured capability record for the two configured Blenders."""

    def test_every_feature_test_ran(self):
        for path in (PROBE_45, PROBE_54):
            probe = load(path)
            self.assertEqual(probe["schema"], "las.blender-lab.v1")
            self.assertEqual({k for k, v in probe["features"].items() if not v["ok"]}, set(), path.name)
            self.assertRegex(probe["runtime"]["sha256"], r"^[0-9a-f]{64}$")

    def test_identity(self):
        self.assertEqual(load(PROBE_45)["blender"]["version"], [4, 5, 13])
        self.assertEqual(load(PROBE_54)["blender"]["build_hash"], "67c9bdddb88b")

    def test_legacy_fcurves_removed_in_alpha_but_layered_actions_in_both(self):
        old, new = (load(p)["features"]["action_api"]["detail"] for p in (PROBE_45, PROBE_54))
        self.assertTrue(old["legacy_fcurves_property"]); self.assertFalse(new["legacy_fcurves_property"])
        self.assertTrue(old["layered"] and new["layered"])

    def test_alpha_only_capabilities(self):
        old, new = load(PROBE_45)["features"], load(PROBE_54)["features"]
        lighting = {"ShaderNodeLightAccumulation", "ShaderNodeLightEvaluation", "ShaderNodeLightInfo"}
        self.assertTrue(lighting <= set(new["shader_nodes"]["detail"]["lighting_or_npr_candidates"]))
        self.assertFalse(lighting & set(old["shader_nodes"]["detail"]["lighting_or_npr_candidates"]))
        self.assertIn("BlenderProject", new["blender_projects"]["detail"]["types"])
        self.assertNotIn("BlenderProject", old["blender_projects"]["detail"]["types"])
        self.assertIn("spz_import", new["point_cloud_and_splat_import"]["detail"]["splat_like"])
        self.assertNotIn("spz_import", old["point_cloud_and_splat_import"]["detail"]["splat_like"])

    def test_engines_backend_and_gpu_visibility(self):
        old, new = load(PROBE_45), load(PROBE_54)
        self.assertIn("BLENDER_EEVEE_NEXT", old["render_engines"]); self.assertIn("BLENDER_EEVEE", new["render_engines"])
        self.assertEqual(new["features"]["gpu_backend"]["detail"]["active_backend"], "VULKAN")
        self.assertIn("not available in background", old["features"]["gpu_backend"]["detail"]["active_backend_error"])
        for probe in (old, new): self.assertIn("HIP", probe["features"]["cycles_devices"]["detail"]["gpu_visible"])

    def test_gltf_exporter_keeps_the_options_las_uses(self):
        las_options = {"export_format", "export_materials", "export_cameras", "export_lights", "export_animations",
                       "export_frame_range", "export_force_sampling", "use_renderable"}
        for path in (PROBE_45, PROBE_54):
            self.assertLessEqual(las_options, set(load(path)["features"]["gltf_export"]["detail"]["options"]), path.name)


MANIFEST_45 = FIXTURES / "manifest-lab-asset-4.5.13.json"
MANIFEST_54 = FIXTURES / "manifest-lab-asset-5.4.0-alpha-67c9bdddb88b.json"


class ManifestTests(unittest.TestCase):
    def test_rounding_folds_negative_zero_and_canonical_json_is_order_free(self):
        self.assertEqual(json.dumps(lab.bpy_side.rnd(-0.000001)), "0.0")
        self.assertEqual(lab.bpy_side.canonical({"b": 1, "a": [2.5]}), lab.bpy_side.canonical({"a": [2.5], "b": 1}))

    def test_checksum_ignores_identity_and_location_but_not_content(self):
        manifest = load(MANIFEST_45)
        base = lab.bpy_side.semantic_checksum(manifest)
        moved = {**manifest, "blender": {"version_string": "other"}, "source": {"file": "elsewhere.blend"}, "runtime": {}}
        self.assertEqual(lab.bpy_side.semantic_checksum(moved), base)
        edited = json.loads(json.dumps(manifest)); edited["materials"][0]["principled"]["roughness"] = 0.61
        self.assertNotEqual(lab.bpy_side.semantic_checksum(edited), base)

    def test_fixtures_verify_and_agree_across_builds(self):
        old, new = load(MANIFEST_45), load(MANIFEST_54)
        for manifest in (old, new):
            stripped = {k: v for k, v in manifest.items() if k != "runtime"}
            self.assertEqual(lab.bpy_side.semantic_checksum(stripped), manifest["semantic_checksum"])
        self.assertEqual(old["semantic_checksum"], new["semantic_checksum"])
        self.assertNotEqual(old["blender"]["build_hash"], new["blender"]["build_hash"])

    def test_lab_asset_manifest_content(self):
        manifest = load(MANIFEST_54)
        self.assertEqual(manifest["counts"], {"actions": 1, "armatures": 1, "images": 1, "materials": 3, "meshes": 3,
                                              "missing_images": 0, "objects": 4, "triangles": 600})
        rig = manifest["armatures"][0]
        self.assertEqual(([b["name"] for b in rig["bones"]], rig["roots"], rig["max_depth"]), (["Neck", "Root", "Spine"], ["Root"], 2))
        body = next(o for o in manifest["objects"] if o["name"] == "Body")
        self.assertEqual((body["parent"], body["vertex_weights"]["unnormalised_vertices"], body["modifiers"][0]["object"]), ("Rig", 0, "Rig"))
        action = manifest["actions"][0]
        self.assertEqual((action["name"], action["slots"][0]["identifier"], len(action["fcurves"])), ("LabSway", "OBRig", 3))
        self.assertEqual(next(m for m in manifest["materials"] if m["name"] == "BodyTextured")["images"], ["lab-checker"])
        head = next(m for m in manifest["meshes"] if m["name"] == "Head")
        self.assertEqual([k["name"] for k in head["shape_keys"]["keys"]], ["Basis", "Squash"])

    def test_manifest_requires_a_blend_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            with self.assertRaises(lab.BlenderLabError): lab.manifest(exe, Path(tmp) / "missing.blend", Path(tmp) / "m.json")
            with self.assertRaises(lab.BlenderLabError): lab.manifest(exe, exe, Path(tmp) / "m.json")


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live probe")
class LiveProbeTests(unittest.TestCase):
    def test_live_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = lab.probe(LIVE_BLENDER, Path(tmp) / "probe.json")
        self.assertEqual({k for k, v in result["features"].items() if not v["ok"]}, set())
        self.assertTrue(result["blender"]["background"])

    def test_live_fixture_manifest_is_deterministic_and_leaves_source_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            blend = lab.make_fixture(LIVE_BLENDER, Path(tmp) / "asset")
            before = lab.file_sha(blend)
            result = lab.manifest(LIVE_BLENDER, blend, Path(tmp) / "manifest.json")
            self.assertEqual(lab.file_sha(blend), before)
        self.assertEqual(result["semantic_checksum"], load(MANIFEST_45)["semantic_checksum"])


if __name__ == "__main__":
    unittest.main()
