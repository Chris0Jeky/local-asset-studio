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

GIB = 1024 ** 3
GRAPH = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "model.gguf"}},
    "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "3": {"class_type": "KSampler", "inputs": {"steps": 20, "seed": 1, "model": ["1", 0], "latent_image": ["2", 0]}},
}
PRESET = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json", "seed": ["3", "seed"], "backend_id": "primary"}


class FakeStudio(server.Studio):
    def __init__(self, root, vram, prompt_reply=None):
        self.vram = vram; self.prompt_reply = prompt_reply or {"prompt_id": "accepted"}; self.requests = []
        super().__init__(root)

    def _request(self, path, *args, **kwargs):
        self.requests.append(path)
        if path == "/queue": return {"queue_running": [], "queue_pending": []}
        if path == "/system_stats":
            return {"system": {"comfyui_version": "test", "pytorch_version": "test"},
                    "devices": [{"vram_total": 16 * GIB, "vram_free": self.vram,
                                 "torch_vram_total": 16 * GIB, "torch_vram_free": self.vram}]}
        if path == "/prompt":
            if isinstance(self.prompt_reply, Exception): raise self.prompt_reply
            return copy.deepcopy(self.prompt_reply)
        if path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[-1]
            return {prompt_id: {"status": {"status_str": "success"}, "outputs": {}}}
        raise AssertionError(path)


class ObservedVramTests(unittest.TestCase):
    def test_available_vram_is_comfyui_total_free_not_the_torch_pool(self):
        # Live #306 proof: an empty 16 GB card reports vram_free ~15.7 GiB and torch_vram_free 0 (nothing loaded).
        import resource_admission
        studio = FakeStudio.__new__(FakeStudio); studio.config = {}; studio.comfy_url = "http://127.0.0.1:8188"
        stats = {"system": {"comfyui_version": "test", "pytorch_version": "test"},
                 "devices": [{"vram_total": 16 * GIB, "vram_free": 15 * GIB, "torch_vram_total": 0, "torch_vram_free": 0}]}
        studio._request = lambda path, *a, **k: stats
        observed = resource_admission.observe(studio)
        self.assertEqual(observed["vram"]["available_bytes"], 15 * GIB)
        self.assertIsNone(observed["vram"]["unknown_reason"])


class ResourceAdmissionServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy"),
                                                                  "enforce_stage_resource_admission": True}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.thread = patch.object(threading.Thread, "start", lambda *_: None); self.thread.start()
        resource_admission = server.continuation.resource_admission
        self.memory = patch.object(resource_admission.resource_probe, "physical_memory",
                                   return_value={"total_bytes": 128 * GIB, "available_bytes": 100 * GIB, "unknown_reason": None})
        self.commit = patch.object(resource_admission.host_memory, "read",
                                   return_value={"available_bytes": 100 * GIB, "limit_bytes": 128 * GIB,
                                                 "committed_bytes": 28 * GIB, "unknown_reason": None})
        self.memory.start(); self.commit.start()

    def tearDown(self):
        self.commit.stop(); self.memory.stop(); self.thread.stop(); self.tmp.cleanup()

    def _job(self, vram, required=12 * GIB):
        resource_admission = server.continuation.resource_admission
        studio = FakeStudio(self.root, vram)
        job = studio.jobs[studio.create_job({"preset_id": "demo", "controls": {}}, enqueue=False)["id"]]
        runtime = {"versions": {"comfyui_version": "test", "pytorch_version": "test"}}
        identity = resource_admission.workflow_identity(studio, studio.preset("demo"), job["graph"], runtime)
        studio.config["resource_admission_profiles"] = {identity["identity_sha256"]: {
            "schema": resource_admission.PROFILE_SCHEMA,
            "identity_sha256": identity["identity_sha256"], "basis": "observed",
            "source": {"receipt_sha256": "a" * 64, "kind": "test-observation"},
            "stages": [{"name": "sample", "physical_ram_bytes": GIB,
                        "windows_commit_bytes": GIB, "vram_bytes": required}],
        }}
        return studio, job

    def test_low_capacity_is_refused_after_queue_wait_before_prompt(self):
        studio, job = self._job(10 * GIB)
        studio._run(job)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(studio.requests, ["/queue", "/system_stats"])
        self.assertNotIn("/prompt", studio.requests)
        self.assertIn("No prompt was submitted", job["message"])
        self.assertEqual(job["resource_admission"][-1]["decision"], "observed_unsafe")

    def test_profiled_job_that_fits_still_runs(self):
        studio, job = self._job(14 * GIB)
        studio._run(job)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(studio.requests, ["/queue", "/system_stats", "/prompt", "/history/accepted"])
        self.assertEqual(job["resource_admission"][-1]["decision"], "observed_safe")


if __name__ == "__main__": unittest.main()
