"""Opt-in headless Godot material policy; no Blender run, GPU render or visual-parity claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from engine_fixture import glb_bytes, model

ROOT = Path(__file__).resolve().parents[1]
GODOT = os.environ.get("STUDIO_TEST_GODOT")
if os.environ.get("STUDIO_REQUIRE_ENGINE_TESTS") == "1" and not GODOT:
    raise RuntimeError("Required toon material policy test lacks an explicit Godot executable")


@unittest.skipUnless(GODOT, "Explicit STUDIO_TEST_GODOT required; no native policy check was run")
class NativeMaterialPolicy(unittest.TestCase):
    def test_production_guard_preserves_rejected_materials_and_applies_only_ok(self):
        if os.environ.get("STUDIO_ENGINE_EVIDENCE"):
            root = Path(os.environ["STUDIO_ENGINE_EVIDENCE"]) / "toon-material-policy"
            root.mkdir(parents=True, exist_ok=False)
        else:
            tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
            root = Path(tmp.name)
        project = root / "project"; project.mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="toon policy probe"\n', encoding="utf-8")
        renderer = ROOT / "tools" / "toon-compiler" / "render.gd"
        probe = ROOT / "tests" / "toon_material_policy_probe.gd"
        shutil.copyfile(renderer, project / "render.gd")
        shutil.copyfile(probe, project / "probe.gd")
        fixture = root / "fixture.glb"
        fixture.write_bytes(glb_bytes(*model()))
        shader = "shader_type spatial;\nvoid fragment() { ALBEDO = vec3(0.2, 0.6, 0.8); }\n"
        for name in ("ready", "inspect", "stale"):
            (project / (name + ".gdshader")).write_text(shader, encoding="utf-8")
        (project / "empty.gdshader").write_text("", encoding="utf-8")
        (project / "blank.gdshader").write_text(" \n\t\n", encoding="utf-8")
        out = root / "result.json"
        command = [str(Path(GODOT).resolve()), "--headless", "--path", str(project.resolve()),
                   "--script", "res://probe.gd", "--", str(fixture.resolve()), str(out.resolve())]
        plan = {"command": command, "renderer_sha256": hashlib.sha256(renderer.read_bytes()).hexdigest(),
                "probe_sha256": hashlib.sha256(probe.read_bytes()).hexdigest(),
                "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()}
        (root / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        try:
            reply = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except subprocess.TimeoutExpired as exc:
            for name, value in (("stdout", exc.stdout), ("stderr", exc.stderr)):
                text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
                (root / (name + ".log")).write_text(text, encoding="utf-8")
            (root / "execution.json").write_text(json.dumps({"returncode": None, "timed_out": True}) + "\n", encoding="utf-8")
            self.fail("Headless Godot policy probe timed out; retained logs identify the failure")
        (root / "stdout.log").write_text(reply.stdout, encoding="utf-8")
        (root / "stderr.log").write_text(reply.stderr, encoding="utf-8")
        (root / "execution.json").write_text(json.dumps({"returncode": reply.returncode, "timed_out": False}) + "\n", encoding="utf-8")
        self.assertEqual(reply.returncode, 0, reply.stderr[-4000:] + reply.stdout[-4000:])
        receipt = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(receipt["failures"], [])
        self.assertEqual(receipt["imported"], {"mesh_count": 1, "surface_count": 1,
                                             "material_name": "FixturePaint", "material_class": "StandardMaterial3D"})
        cases = {row["name"]: row for row in receipt["cases"]}
        expected = {"ok", "partial", "unsupported", "unknown", "missing-status", "missing-record", "missing-file", "empty-file",
                    "invalid-file", "partial-with-override", "ok-with-override", "unavailable-material",
                    "absent-shader", "empty-shader", "blank-shader"}
        self.assertEqual(set(cases), expected)
        for name, row in cases.items():
            with self.subTest(case=name):
                self.assertTrue(row["base_material_unchanged"])
                self.assertTrue(row["active_material_correct"])
                self.assertEqual(row["result"]["applied"], name in ("ok", "ok-with-override"))
                self.assertEqual(row["loads"], int(name in ("ok", "ok-with-override", "unavailable-material",
                                                          "absent-shader", "empty-shader", "blank-shader")))


if __name__ == "__main__": unittest.main()
