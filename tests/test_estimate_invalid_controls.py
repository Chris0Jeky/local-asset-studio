import copy
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("asset_server", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)

GRAPH = {"1": {"inputs": {"text": "native positive", "width": 512, "height": 512, "seed": 1, "steps": 20, "cfg": 7, "lora": 1, "strength_clip": 1, "reference": "default.png"}}, "2": {"inputs": {"width": 512, "height": 512}}}
PRESET = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"], "width": ["1", "width"], "height": ["1", "height"], "seed": ["1", "seed"], "steps": ["1", "steps"], "cfg": ["1", "cfg"], "lora": ["1", "lora"], "reference": ["1", "reference"], "bindings_extra": {"width": [["2", "width"]], "height": [["2", "height"]], "lora": [["1", "strength_clip"]]}}


class EstimateInvalidControlsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))

    def studio(self):
        # Only construction suppresses the fixture worker. Later starts and
        # requests are failures, so an estimate cannot quietly begin real work.
        with patch.object(threading.Thread, "start", lambda *_: None):
            studio = server.Studio(self.root)
        for owner, name in ((studio, "_request"), (studio, "create_job"),
                            (server, "urlopen"), (threading.Thread, "start")):
            self.enterContext(patch.object(owner, name, side_effect=AssertionError(
                "Estimate must not submit, contact the network or start a thread")))
        return studio

    def test_invalid_string_steps_returns_unavailable(self):
        studio = self.studio()
        result = studio.estimate({"preset_id": "demo", "controls": {"steps": "not-a-number"}})
        self.assertFalse(result["available"])
        self.assertIn("steps", str(result.get("reason", "")).lower())

    def test_nan_infinity_out_of_range_steps_return_unavailable(self):
        studio = self.studio()
        for raw in (float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", 0, 1000):
            with self.subTest(raw=raw):
                result = studio.estimate({"preset_id": "demo", "controls": {"steps": raw}})
                self.assertFalse(result["available"], msg=f"steps={raw!r} should be unavailable")
                self.assertIn("steps", str(result.get("reason", "")).lower())

    def test_valid_controls_still_estimate(self):
        studio = self.studio()
        result = studio.estimate({"preset_id": "demo", "controls": {"steps": 20}})
        self.assertTrue(result["available"])
        self.assertIn("estimate_seconds", result)

    def test_fractional_and_boolean_steps_return_unavailable(self):
        studio = self.studio()
        for raw in (20.5, "20.5", True, False):
            with self.subTest(raw=raw):
                result = studio.estimate({"preset_id": "demo", "controls": {"steps": raw}})
                self.assertFalse(result["available"])
                self.assertIn("steps", str(result.get("reason", "")).lower())

    def test_numeric_lora_fraction_and_zero_reach_companion_binding(self):
        studio = self.studio()
        preset = studio.preset("demo")
        for raw, expected in (("0.5", 0.5), (0, 0.0)):
            with self.subTest(raw=raw):
                graph = studio._estimate_graph(preset, {"lora": raw})
                self.assertEqual(graph["1"]["inputs"]["lora"], expected)
                self.assertEqual(graph["1"]["inputs"]["strength_clip"], expected)
                self.assertTrue(studio.estimate({"preset_id": "demo", "controls": {"lora": raw}})["available"])

    def test_filename_bound_lora_remains_text(self):
        graph = copy.deepcopy(GRAPH)
        graph["1"]["inputs"]["lora"] = "authored.safetensors"
        preset = copy.deepcopy(PRESET)
        del preset["bindings_extra"]["lora"]
        (self.root / preset["graph"]).write_text(json.dumps(graph))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [preset]}))
        studio = self.studio()
        bound = studio._estimate_graph(studio.preset("demo"), {"lora": "chosen.safetensors"})
        self.assertEqual(bound["1"]["inputs"]["lora"], "chosen.safetensors")
        self.assertTrue(studio.estimate({"preset_id": "demo", "controls": {"lora": "chosen.safetensors"}})["available"])

    def test_valid_controls_change_only_estimate_graph(self):
        studio = self.studio()
        preset = studio.preset("demo")
        before_preset = copy.deepcopy(preset)
        source = self.root / preset["graph"]
        before_bytes = source.read_bytes()
        studio.jobs["retained"] = {"id": "retained", "status": "queued", "controls": {"steps": 7}}
        studio.queue.put(("generate", "retained"))
        before_jobs = copy.deepcopy(studio.jobs)
        before_queue = list(studio.queue.queue)
        controls = {"steps": 32, "width": 768}

        graph = studio._estimate_graph(preset, controls)
        self.assertEqual(graph["1"]["inputs"]["steps"], 32)
        self.assertEqual(graph["1"]["inputs"]["width"], 768)
        self.assertEqual(graph["2"]["inputs"]["width"], 768)
        result = studio.estimate({"preset_id": "demo", "controls": controls})
        self.assertTrue(result["available"])
        self.assertEqual(result["features"]["steps"], 32)
        self.assertEqual(result["features"]["resolution"], [768, 512])
        self.assertEqual(source.read_bytes(), before_bytes)
        self.assertEqual(preset, before_preset)
        self.assertEqual(studio.jobs, before_jobs)
        self.assertEqual(list(studio.queue.queue), before_queue)


if __name__ == "__main__":
    unittest.main()
