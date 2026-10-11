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
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start = patch.object(threading.Thread, "start", lambda *_: None); self.start.start()
        self.addCleanup(self.start.stop); self.addCleanup(self.tmp.cleanup)

    def studio(self):
        return server.Studio(self.root)

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


if __name__ == "__main__":
    unittest.main()
