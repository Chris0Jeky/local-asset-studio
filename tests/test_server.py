import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

SPEC = importlib.util.spec_from_file_location("asset_server", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)

GRAPH = {"1":{"inputs":{"text":"native positive","width":512,"height":512,"seed":1,"steps":20,"cfg":7,"lora":1,"strength_clip":1,"reference":"default.png"}}, "2":{"inputs":{"width":512,"height":512}}}
PRESET = {"id":"demo","name":"Demo","category":"Test","graph":"workflows/api/demo-api.json","positive":["1","text"],"width":["1","width"],"height":["1","height"],"seed":["1","seed"],"steps":["1","steps"],"cfg":["1","cfg"],"lora":["1","lora"],"reference":["1","reference"],"bindings_extra":{"width":[["2","width"]],"height":[["2","height"]],"lora":[["1","strength_clip"]]}}

class FakeStudio(server.Studio):
    def __init__(self, root, replies): self.replies=iter(replies); self.requests=[]; super().__init__(root)
    def _request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        response=next(self.replies)
        if isinstance(response, Exception): raise response
        return response

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        (self.root/"presets").mkdir(); (self.root/"workflows/api").mkdir(parents=True)
        (self.root/"config").mkdir(); (self.root/"fake-comfy/input").mkdir(parents=True)
        (self.root/"config/local.json").write_text(json.dumps({"comfy_root":str(self.root/"fake-comfy")}))
        (self.root/"presets/catalog.json").write_text(json.dumps({"presets":[PRESET]}))
        (self.root/"workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start=patch.object(threading.Thread,"start",lambda *_:None); self.start.start()
    def tearDown(self): self.start.stop(); self.tmp.cleanup()
    def studio(self): return server.Studio(self.root)
    def test_validation_and_companion_bindings(self):
        s=self.studio(); _, graph, _, _, _=s.prepare({"preset_id":"demo","controls":{"width":640,"height":768,"lora":"0.5"}})
        self.assertEqual(graph["1"]["inputs"]["width"],640); self.assertEqual(graph["2"]["inputs"]["width"],640)
        self.assertEqual(graph["1"]["inputs"]["strength_clip"],0.5)
        with self.assertRaisesRegex(server.StudioError,"multiple of 8"): s.prepare({"preset_id":"demo","controls":{"width":641}})
        with self.assertRaisesRegex(server.StudioError,"Unsupported"): s.prepare({"preset_id":"demo","controls":{"negative":"no"}})
    def test_path_traversal_and_upload_magic(self):
        with self.assertRaises(server.StudioError): server.inside(self.root, self.root/"../outside")
        s=self.studio()
        with self.assertRaises(server.StudioError): s.upload("../x.png","image/png",b"wrong")
        self.assertIn("file",s.upload("../x.png","image/png",b"\x89PNG\r\n\x1a\nbody"))
        uploads=self.root/"experiments/uploads"; uploads.mkdir(parents=True,exist_ok=True); (uploads/"plain.png").write_bytes(b"x")
        with self.assertRaisesRegex(server.StudioError,"Reference upload is invalid"):
            s.prepare({"preset_id":"demo","controls":{"reference":"../plain.png"}})
        with self.assertRaisesRegex(server.StudioError,"Reference upload is invalid"):
            s.prepare({"preset_id":"demo","controls":{"reference":"plain.png"}})

    def test_loopback_host_and_origin_are_required_for_mutation(self):
        handler=server.Handler.__new__(server.Handler)
        handler.headers={"Host":"127.0.0.1:8191","Origin":"http://127.0.0.1:8191"}
        self.assertTrue(handler._safe_mutation())
        handler.headers={"Host":"localhost:8191","Origin":"https://localhost:8191"}
        self.assertFalse(handler._safe_mutation())
        handler.headers={"Host":"evil.example:8191","Origin":"http://evil.example:8191"}
        self.assertFalse(handler._safe_host())

    def test_numbers_reject_bool_nan_and_fractional_integers(self):
        for bad in (True, float("nan"), float("inf"), 1.5, "3.2"):
            with self.assertRaises(server.StudioError): server.number(bad, "seed", 0, 99, integer=True)
        self.assertEqual(server.number("4.0", "seed", 0, 99, integer=True), 4)
    def test_job_persistence_and_restart_marks_uncertain(self):
        s=self.studio(); job=s.create_job({"preset_id":"demo","controls":{}}); live=s.jobs[job["id"]]; live["status"]="running"; s._save(live)
        recovered=self.studio().jobs[job["id"]]
        self.assertEqual(recovered["status"],"uncertain"); self.assertIn("not resubmitted",recovered["message"])
    def test_mock_comfy_success_failure_and_uncertain_post(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"p1"},{"p1":{"status":{"status_str":"success"},"outputs":{"9":{"images":[{"filename":"ok.png","subfolder":"","type":"output"}]}}}}]
        s=FakeStudio(self.root,replies); job=s.create_job({"preset_id":"demo","controls":{}}); s._run(s.jobs[job["id"]]); self.assertEqual(s.jobs[job["id"]]["status"],"completed")
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"p1"},{"p1":{"status":{"status_str":"error"}}}]
        s=FakeStudio(self.root,replies); job=s.create_job({"preset_id":"demo","controls":{}})
        with self.assertRaises(server.StudioError): s._run(s.jobs[job["id"]])
        replies=[{"queue_running":[],"queue_pending":[]},URLError("timeout")]
        s=FakeStudio(self.root,replies); job=s.create_job({"preset_id":"demo","controls":{}}); s._run(s.jobs[job["id"]]); self.assertEqual(s.jobs[job["id"]]["status"],"uncertain")

    def test_batches_get_distinct_seed_and_durable_exact_graph(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"one"},{"one":{"status":{"status_str":"success"},"outputs":{}}},{"prompt_id":"two"},{"two":{"status":{"status_str":"success"},"outputs":{}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{"seed":40},"batch_count":2}); job=s.jobs[created["id"]]; s._run(job)
        posts=[call[0][2]["prompt"] for call in s.requests if call[0][0]=="/prompt"]
        self.assertEqual([p["1"]["inputs"]["seed"] for p in posts],[40,41])
        self.assertEqual([x["seed"] for x in job["submissions"]],[40,41]); self.assertEqual(job["submissions"][1]["graph"],posts[1])
        self.assertFalse(list((self.root/"experiments/runs"/job["id"]).glob("*.tmp")))

    def test_history_failure_stops_batch_and_known_prompt_can_resume(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"one"},URLError("connection lost")]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{},"batch_count":2}); job=s.jobs[created["id"]]; s._run(job)
        self.assertEqual(job["status"],"uncertain"); self.assertEqual(len([x for x in s.requests if x[0][0]=="/prompt"]),1)
        s.replies=iter([{"one":{"status":{"status_str":"success"},"outputs":{}}}]); s._resume(job)
        self.assertEqual(job["status"],"partial"); self.assertEqual(len(job["prompt_ids"]),1)
        self.assertIn("1 of 2",job["message"])
        self.assertEqual(len([x for x in s.requests if x[0][0]=="/prompt"]),1)
        self.assertEqual(self.studio().jobs[job["id"]]["status"],"partial")

    def test_health_identifies_offline_and_missing_node_class(self):
        offline=FakeStudio(self.root,[URLError("offline")]).health()
        self.assertEqual(offline["app"],"local-asset-studio"); self.assertFalse(offline["online"])
        live=FakeStudio(self.root,[{},{}]).health()
        self.assertIn("demo",live["missing_models"])

if __name__ == "__main__": unittest.main()
