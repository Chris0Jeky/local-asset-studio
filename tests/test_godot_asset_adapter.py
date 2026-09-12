import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import godot_asset_adapter as adapter


class GodotAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / "atlas").mkdir()
        atlas = self.root / "atlas" / "atlas.png"
        atlas.write_bytes(b"not-decoded-by-package-test")
        manifest = {
            "schema_version": 1, "kind": "sprite_atlas", "clip": "idle-qa", "loop": True,
            "logical_canvas": [48, 64], "anchor": [24, 60], "atlas": "atlas.png",
            "atlas_sha256": hashlib.sha256(atlas.read_bytes()).hexdigest(), "filter": "nearest",
            "frames": [{"id": f"frame-{index}", "region": [index * 48, 0, 48, 64], "duration_ms": duration}
                       for index, duration in enumerate([120, 80, 120, 160])],
        }
        (self.root / "atlas" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.root / "model.glb").write_bytes(b"glTF")

    def tearDown(self):
        self.temp.cleanup()

    def test_package_preserves_timing_anchor_filter_and_sources(self):
        output = self.root / "output project"
        result = adapter.package_project(self.root, "atlas/manifest.json", output, "model.glb")
        self.assertEqual(result["frame_count"], 4)
        scene = (output / "main.tscn").read_text(encoding="utf-8")
        self.assertIn('"speed": 60.0', scene)
        self.assertIn('"duration": 7.2', scene)  # 120 / 1000 * 60
        self.assertIn('"duration": 4.8', scene)  # 80 / 1000 * 60
        self.assertIn("offset = Vector2(0, -28)", scene)
        self.assertIn("texture_filter = 1", scene)
        self.assertEqual((output / "assets" / "atlas.png").read_bytes(), b"not-decoded-by-package-test")
        self.assertEqual((output / "assets" / "ember.glb").read_bytes(), b"glTF")

    def test_package_without_glb_does_not_add_an_invalid_placeholder(self):
        output = self.root / "sprite-only"
        adapter.package_project(self.root, "atlas/manifest.json", output)
        self.assertFalse((output / "assets" / "ember.glb").exists())
        self.assertIn('const GLB_PATH := ""', (output / "verify.gd").read_text(encoding="utf-8"))

    def test_output_must_be_new_and_inputs_cannot_escape_root(self):
        output = self.root / "output"
        output.mkdir()
        with self.assertRaises(adapter.GodotAdapterError):
            adapter.package_project(self.root, "atlas/manifest.json", output)
        with self.assertRaises(adapter.GodotAdapterError):
            adapter.package_project(self.root, "../atlas/manifest.json", self.root / "new-output")


if __name__ == "__main__":
    unittest.main()
