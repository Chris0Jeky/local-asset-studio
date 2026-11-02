import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import procgen_factory as factory
import procgen_level as level

SCHEMA = factory.load_schema()


class LevelChecks(unittest.TestCase):
    def test_ground_parts_without_factory_collision_get_engine_trimesh(self):
        self.assertEqual(level.trimesh_parts(SCHEMA["generators"]["coastal_path"]), ["path", "terrain"])
        self.assertEqual(level.trimesh_parts(SCHEMA["generators"]["pier"]), [])          # water is not walkable ground
        self.assertEqual(level.trimesh_parts(SCHEMA["generators"]["shrine"]), [])        # platform and steps carry boxes

    def test_level_validation_reports_every_problem(self):
        bad = {"pieces": [{"name": "Coast", "generator": "coastal_path"},
                          {"name": "pier", "generator": "nope", "position": [0, 0]},
                          {"name": "pier", "generator": "pier", "yaw_deg": float("inf")}]}
        errors = level.check_level(bad, SCHEMA)
        self.assertEqual(len(errors), 5, errors)
        self.assertTrue(any("duplicate name" in e for e in errors))
        self.assertTrue(any("unknown generator" in e for e in errors))
        self.assertEqual(level.check_level({"pieces": []}, SCHEMA), ['level needs a non-empty "pieces" list'])
        good = {"pieces": [{"name": "coast", "generator": "coastal_path", "position": [0, 0, 0], "yaw_deg": 0}]}
        self.assertEqual(level.check_level(good, SCHEMA), [])

    def test_invalid_level_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "level.json"; path.write_text(json.dumps({"pieces": []}), encoding="utf-8")
            with self.assertRaises(factory.EvidenceError):
                level.assemble(path, Path(directory) / "out", blender="unused")
            self.assertFalse((Path(directory) / "out").exists())


@unittest.skipUnless(os.environ.get("PROCGEN_LIVE_BLENDER"), "set PROCGEN_LIVE_BLENDER=<blender.exe> for the live assembly")
class LiveAssembly(unittest.TestCase):
    def test_coast_and_pier_assemble_into_a_loadable_level(self):
        config = json.loads(factory.LOCAL_CONFIG.read_text(encoding="utf-8")) if factory.LOCAL_CONFIG.is_file() else {}
        if not config.get("godot"): self.skipTest("no godot in config/local.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "level.json"
            path.write_text(json.dumps({"pieces": [
                {"name": "coast", "generator": "coastal_path", "params": {"fence": 0, "detail": 8}},
                {"name": "pier", "generator": "pier", "params": {"water_level": 0.3, "deck_height": 1.65}, "position": [0.8, 9.0, 0], "yaw_deg": -90}]}), encoding="utf-8")
            manifest = level.assemble(path, Path(directory) / "out", os.environ["PROCGEN_LIVE_BLENDER"], config["godot"], config.get("node"))
            self.assertEqual(manifest["godot"]["pieces"], 2)
            self.assertEqual(manifest["godot"]["engine_trimesh"], 2)                    # coast terrain + path
            self.assertGreater(manifest["godot"]["collision_shapes"], 2)                # plus the pier's factory boxes
            self.assertTrue((Path(directory) / "out" / "godot" / "level.tscn").is_file())


if __name__ == "__main__":
    unittest.main()
