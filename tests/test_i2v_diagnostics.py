import importlib.util
import hashlib
import io
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("asset_server_i2v", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)
from i2v_diagnostics import _supported_wan_job, artifact_path, centered_crop_plan, graph_diff


def png(width=832, height=1248):
    stream = io.BytesIO()
    Image.new("RGB", (width, height), "purple").save(stream, "PNG")
    return stream.getvalue()


class I2VDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "presets").mkdir()
        (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir()
        (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "experiments/uploads").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}), encoding="utf-8")
        self.reference = "a" * 32 + "_source.png"
        self.reference_bytes = png()
        (self.root / "experiments/uploads" / self.reference).write_bytes(self.reference_bytes)
        self.graph = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "model.safetensors"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "text.safetensors", "type": "wan", "device": "default"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
            "4": {"class_type": "LoadImage", "inputs": {"image": "placeholder.png"}},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "positive"}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "negative"}},
            "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "start_image": ["4", 0], "width": 512, "height": 768, "length": 17, "batch_size": 1}},
            "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
            "9": {"class_type": "KSampler", "inputs": {"model": ["8", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "seed": 1, "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0}},
        }
        self.preset = {
            "id": "wan22-i2v",
            "name": "Wan I2V",
            "graph": "workflows/api/wan-api.json",
            "positive": ["5", "text"],
            "negative": ["6", "text"],
            "width": ["7", "width"],
            "height": ["7", "height"],
            "frames": ["7", "length"],
            "seed": ["9", "seed"],
            "steps": ["9", "steps"],
            "cfg": ["9", "cfg"],
            "sampler": ["9", "sampler_name"],
            "scheduler": ["9", "scheduler"],
            "reference": ["4", "image"],
            "modality": "video",
            "dimension_multiple": 32,
            "max_pixels": 983040,
            "frame_grid": 4,
            "frame_offset": 1,
            "dimension_limits": [64, 1536],
            "choices": {"sampler": ["uni_pc"], "scheduler": ["simple"]},
            "metadata_controls": ["mode"],
            "source_orientation": "auto-swap-authored-pairs",
            "orientation_pairs": [[512, 768], [768, 512], [1280, 704], [704, 1280]],
            "i2v_modes": [{"id": "canonical", "name": "Canonical upstream", "controls": {"width": 1280, "height": 704, "frames": 41, "steps": 30, "seed": 9, "sampler": "uni_pc", "scheduler": "simple"}, "required_reference": {"label": "official fixture", "sha256": hashlib.sha256(self.reference_bytes).hexdigest()}}],
        }
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [self.preset]}), encoding="utf-8")
        (self.root / "workflows/api/wan-api.json").write_text(json.dumps(self.graph), encoding="utf-8")
        self.thread_patch = patch.object(threading.Thread, "start", lambda *_: None)
        self.thread_patch.start()

    def tearDown(self):
        if self.thread_patch:
            self.thread_patch.stop()
        self.temporary.cleanup()

    def studio(self):
        return server.Studio(self.root)

    def test_wan_center_crop_matches_installed_common_upscale_geometry(self):
        plan = centered_crop_plan(832, 1248, 512, 512)
        self.assertEqual(plan["crop_box"], [0, 208, 832, 1040])
        self.assertEqual(plan["crop_dimensions"], [832, 832])
        self.assertEqual(plan["strategy"], "center crop then bilinear resample")
        self.assertFalse(plan["letterbox"])
        self.assertFalse(plan["stretches_full_source"])

    def test_i2v_mode_swaps_landscape_pair_for_portrait_source_before_binding(self):
        studio = self.studio()
        prepared, graph, _, controls, _ = studio.prepare({"preset_id": "wan22-i2v", "controls": {"mode": "canonical", "reference": self.reference}})
        self.assertEqual(controls["mode"], "canonical")
        self.assertEqual(graph["4"]["inputs"]["image"], self.reference)
        self.assertEqual(graph["7"]["inputs"]["width"], 704)
        self.assertEqual(graph["7"]["inputs"]["height"], 1280)
        self.assertEqual(graph["7"]["inputs"]["length"], 41)
        self.assertEqual(graph["9"]["inputs"]["steps"], 30)
        preparation = prepared.get("_prepared_source")
        self.assertEqual(preparation["orientation_action"], "swapped to match source")
        self.assertEqual(preparation["source"]["dimensions"], [832, 1248])

    def test_canonical_i2v_mode_rejects_missing_or_mismatched_source(self):
        studio = self.studio()
        with self.assertRaisesRegex(server.StudioError, "requires the official fixture upload"):
            studio.prepare({"preset_id": "wan22-i2v", "controls": {"mode": "canonical"}})
        other = studio.upload("other.png", "image/png", png(768, 512))["file"]
        with self.assertRaisesRegex(server.StudioError, "selected source does not match"):
            studio.prepare({"preset_id": "wan22-i2v", "controls": {"mode": "canonical", "reference": other}})
        self.assertEqual(studio.jobs, {})
        self.assertTrue(studio.queue.empty())

    def test_diagnostic_accepts_only_recorded_wan_i2v_jobs(self):
        studio = self.studio()
        self.assertEqual(_supported_wan_job(studio, {"preset_id": "wan22-i2v", "graph": self.graph})["id"], "wan22-i2v")
        for index, job in enumerate(({"preset_id": "av-preview", "graph": {}}, {"preset_id": "generic-video", "graph": {}})):
            job = dict(job, id=f"unsupported-{index}")
            studio.jobs[job["id"]] = job
            with self.subTest(preset_id=job["preset_id"]), self.assertRaisesRegex(server.StudioError, "supports recorded Wan I2V jobs only"):
                studio.i2v_diagnostic(job["id"])
        with self.assertRaisesRegex(ValueError, "requires a recorded Wan22ImageToVideoLatent graph"):
            _supported_wan_job(studio, {"preset_id": "wan22-i2v", "graph": {}})

    def test_graph_diff_normalizes_links_and_reports_literals(self):
        canonical = {"1": {"class_type": "A", "inputs": {"value": 1}}, "2": {"class_type": "B", "inputs": {"source": ["1", 0]}}}
        actual = {"9": {"class_type": "A", "inputs": {"value": 2}}, "4": {"class_type": "B", "inputs": {"source": ["9", 0]}}}
        changes = graph_diff(actual, canonical)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["field"], "value")

    def test_diagnostic_artifact_path_rejects_traversal(self):
        class Stub:
            experiments = self.root / "experiments"

        with self.assertRaises(ValueError):
            artifact_path(Stub(), "job", "../report.json")

    def test_diagnostic_http_routes_are_read_only_gets(self):
        class Stub:
            jobs = {"job": {"id": "job"}}

            @staticmethod
            def i2v_diagnostic(job_id):
                return {"job_id": job_id, "generation_submitted": False}

            @staticmethod
            def i2v_diagnostic_file(job_id, filename):
                return Path(__file__)

        self.thread_patch.stop()
        self.thread_patch = None
        handler_type = type("DiagnosticHandler", (server.Handler,), {"studio": Stub()})
        http = server.ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        try:
            connection = HTTPConnection("127.0.0.1", http.server_port, timeout=5)
            with patch.object(server.Handler, "_safe_host", return_value=True):
                connection.request("GET", "/api/jobs/job/i2v-diagnostic")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertFalse(json.loads(response.read())["generation_submitted"])
            connection.close()
        finally:
            http.shutdown()
            http.server_close()
            worker.join(2)


if __name__ == "__main__":
    unittest.main()
