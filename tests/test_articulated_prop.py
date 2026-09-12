from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import articulated_prop as prop


class ArticulatedPropContractTests(unittest.TestCase):
    def test_describe_and_generated_script_keep_fixed_safety_contract(self):
        self.assertEqual(prop.describe()["fixed_argv"][:3], ["--background", "--factory-startup", "--disable-autoexec"])
        script = prop._script()
        self.assertIn('scene.cycles.device = "CPU"', script)
        self.assertIn('scene.render.threads = 4', script)
        self.assertIn('lid["hinge_axis"] = "X"', script)
        self.assertIn('action.name = "ChestLidOpenHoldClose"', script)
        self.assertIn('bpy.ops.import_scene.gltf(filepath=str(output / "chest.glb"))', script)
        self.assertTrue(all(f'"{name}":' in script for name in ("closed", "open", "front", "side")))

    def test_options_are_bounded_and_command_is_fixed(self):
        options = prop.normalize_options({"width": 3, "render_size": 128, "samples": 4})
        self.assertEqual(options["open_degrees"], 70)
        self.assertEqual(options["keyframes"]["hold"], 40)
        with self.assertRaises(prop.ArticulatedPropError):
            prop.normalize_options({"script": "anything"})
        with self.assertRaises(prop.ArticulatedPropError):
            prop.normalize_options({"render_size": 4096})
        command = prop.command_for("blender.exe", "owned.py", "config.json")
        self.assertEqual(command, ["blender.exe", "--background", "--factory-startup", "--disable-autoexec", "--python", "owned.py", "--", "--config", "config.json"])

    def test_execute_rejects_invalid_request_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new-output"
            with self.assertRaises(prop.ArticulatedPropError):
                prop.execute(target, {"width": 999}, blender_path=ROOT / "missing.exe")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
