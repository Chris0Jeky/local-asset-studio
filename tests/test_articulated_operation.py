import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("articulated_operation", ROOT / "app/articulated.py")
operation = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(operation)


class Assets:
    def __init__(self):
        self.calls = []
    def register(self, job, index, source):
        self.calls.append((job["id"], index, Path(source).name))
        return f"asset-{index}"


class Studio:
    def __init__(self, root, blender):
        self.experiments = root / "experiments"
        self.config = {"blender": str(blender)}
        self.assets = Assets()


def runtime(path):
    return {"path": str(path), "sha256": "a" * 64, "start_command_not_run": True}


class ArticulatedOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.blender = self.root / "blender.exe"; self.blender.write_bytes(b"configured blender")
        self.studio = Studio(self.root, self.blender)
        self.preflight = mock.patch.object(operation.articulated_prop, "preflight", side_effect=lambda _: runtime(self.blender))
        self.preflight.start()

    def tearDown(self):
        self.preflight.stop(); self.temp.cleanup()

    def plan(self):
        return operation.prepare(self.studio, {"name": "Chest study", "options": {"render_size": 128, "samples": 4}})

    def test_prepare_pins_json_safe_runtime_and_refuses_code_fields(self):
        plan = self.plan()
        self.assertEqual(plan["operation"], operation.OPERATION)
        self.assertEqual(plan["blender"]["sha256"], "a" * 64)
        self.assertTrue(plan["no_comfy_submission"])
        with self.assertRaises(operation.ArticulatedOperationError):
            operation.prepare(self.studio, {"name": "bad", "script": "x"})

    def test_run_registers_glb_and_renders_without_comfy_prompt(self):
        def fake_execute(target, options, blender_path):
            target.mkdir(parents=True)
            (target / "views").mkdir()
            for path in [target / "chest.blend", target / "chest.glb", target / "metadata.json",
                         *(target / "views" / f"{name}.png" for name in operation.RENDER_NAMES)]:
                path.write_bytes(path.name.encode())
            return {"metadata": {"render": {"device": "CPU", "threads": 4}, "limitations": ["authored only"]}}
        with mock.patch.object(operation.articulated_prop, "execute", side_effect=fake_execute) as execute:
            result = operation.run(self.studio, "a" * 32, self.plan())
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(result["job"]["prompt_ids"], [])
        self.assertEqual(result["job"]["status"], "completed")
        self.assertEqual(len(self.studio.assets.calls), 5)
        project = self.studio.experiments / "projects" / ("a" * 32)
        self.assertTrue((project / "export.zip").is_file())
        self.assertIn("export.zip", [item["path"] for item in result["artifacts"]])
        with self.assertRaises(operation.ArticulatedOperationError):
            operation.run(self.studio, "a" * 32, self.plan())

    def test_invalid_project_or_plan_never_starts_adapter(self):
        with mock.patch.object(operation.articulated_prop, "execute") as execute:
            with self.assertRaises(operation.ArticulatedOperationError):
                operation.run(self.studio, "bad", self.plan())
            altered = self.plan(); altered["options"]["width"] = 9
            with self.assertRaises(operation.ArticulatedOperationError):
                operation.run(self.studio, "b" * 32, altered)
        execute.assert_not_called()

    def test_failed_adapter_retains_owned_attempt_files(self):
        def failing_execute(target, options, blender_path):
            target.mkdir(parents=True)
            (target / "failure.txt").write_text("kept for diagnosis", encoding="utf-8")
            raise RuntimeError("Blender did not finish")

        with mock.patch.object(operation.articulated_prop, "execute", side_effect=failing_execute):
            result = operation.run(self.studio, "c" * 32, self.plan())
        project = self.studio.experiments / "projects" / ("c" * 32)
        receipt = json.loads((project / "articulated-job.json").read_text(encoding="utf-8"))
        self.assertEqual(result["job"]["status"], "failed")
        self.assertTrue(receipt["failure_files"])
        self.assertEqual((project / "articulated" / "failure.txt").read_text(encoding="utf-8"), "kept for diagnosis")


if __name__ == "__main__":
    unittest.main()
