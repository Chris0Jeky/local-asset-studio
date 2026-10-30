"""#1765: a job records model/environment identity at creation; export_recipe only copies it and import ignores it."""
import copy
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("asset_server_provenance", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)

GRAPH = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "m.safetensors"}},
         "2": {"class_type": "LoraLoader", "inputs": {"lora_name": "free.safetensors", "model": ["1", 0]}},
         "3": {"class_type": "Text", "inputs": {"text": "native positive", "seed": 1}}}
PRESET = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json", "positive": ["3", "text"], "seed": ["3", "seed"]}
ZERO, ONE = "0" * 64, "1" * 64


def pin(sha): return {"id": "m-pin", "file": "checkpoints/m.safetensors", "bytes": 10, "sha256": sha}


class RecipeProvenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)
        for sub in ("presets", "workflows/api", "config", "models", "fake-comfy/input"): (self.root / sub).mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        start = patch.object(threading.Thread, "start", lambda *_: None); start.start(); self.addCleanup(start.stop)

    def library(self, *assets): (self.root / "models/library.json").write_text(json.dumps({"assets": list(assets), "collections": []}))

    def job(self, *assets):
        self.library(*assets); s = server.Studio(self.root)
        return s, s.jobs[s.create_job({"preset_id": "demo", "controls": {"positive": "x"}})["id"]]

    def test_same_filename_with_different_pins_differs(self):
        a = self.job(pin(ZERO))[1]["provenance"]; b = self.job(pin(ONE))[1]["provenance"]
        self.assertNotEqual(a, b)
        self.assertEqual(next(m for m in a["models"] if m["file"] == "checkpoints/m.safetensors")["sha256"], ZERO)
        self.assertEqual(next(m for m in b["models"] if m["file"] == "checkpoints/m.safetensors")["sha256"], ONE)

    def test_unpinned_model_is_explicitly_unknown(self):
        _, job = self.job(pin(ZERO)); models = {m["file"]: m for m in job["provenance"]["models"]}
        self.assertIsNone(models["loras/free.safetensors"]["sha256"]); self.assertIn("unknown", models["loras/free.safetensors"]["basis"])
        self.assertEqual(job["provenance"]["unknown"], ["loras/free.safetensors"])
        _, bare = self.job(); self.assertEqual(sorted(bare["provenance"]["unknown"]), ["checkpoints/m.safetensors", "loras/free.safetensors"])
        self.assertEqual(job["provenance"]["backend_id"], "primary")

    def test_no_model_is_hashed_and_record_survives_restart(self):
        with patch.object(server, "digest_file", side_effect=AssertionError("hashed a model")): s, job = self.job(pin(ZERO))
        self.assertEqual(server.Studio(self.root).jobs[job["id"]]["provenance"], job["provenance"])

    def test_a_provenance_fault_never_blocks_job_creation(self):
        self.library(pin(ZERO)); s = server.Studio(self.root)
        with patch.object(server.recipe_provenance, "build", side_effect=AttributeError("malformed node")):
            job = s.jobs[s.create_job({"preset_id": "demo", "controls": {"positive": "x"}})["id"]]
        self.assertEqual(job["status"], "queued"); self.assertIn("AttributeError", job["provenance"]["unavailable"])

    def test_export_copies_provenance_and_old_jobs_export_unchanged(self):
        s, job = self.job(pin(ZERO)); exported = s.export_recipe(job)
        self.assertEqual(exported["provenance"], job["provenance"])
        old = dict(job); del old["provenance"]; legacy = s.export_recipe(old)
        self.assertNotIn("provenance", legacy)
        self.assertEqual(json.dumps({k: v for k, v in exported.items() if k != "provenance"}, indent=2), json.dumps(legacy, indent=2))

    def test_export_is_stable_across_a_studio_build_change(self):
        s, job = self.job(pin(ZERO)); before = json.dumps(s.export_recipe(job)); s.build = {"sha": "f" * 40}
        self.assertEqual(json.dumps(s.export_recipe(job)), before)

    def test_import_accepts_and_ignores_provenance(self):
        s, job = self.job(pin(ZERO)); exported = s.export_recipe(job); self.assertTrue(s.check_recipe(exported)["matches"])
        plain = {k: v for k, v in exported.items() if k != "provenance"}
        hostile = copy.deepcopy(exported); hostile["provenance"] = {"controls": {"positive": "hijack"}, "workflow": {"9": {}}, "models": "x"}
        for recipe in (exported, hostile):
            self.assertTrue(s.check_recipe(recipe)["matches"])
            self.assertEqual(s.prepare(recipe)[1:4:2], s.prepare(plain)[1:4:2])
        self.assertEqual(s.prepare(hostile)[1], s.prepare(plain)[1])


if __name__ == "__main__": unittest.main()
