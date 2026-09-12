import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from test_server import FakeStudio, GRAPH, PRESET, server


class FailedJobTimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        for name in ("presets", "workflows/api", "config", "fake-comfy/input"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start = patch.object(threading.Thread, "start", lambda *_: None); self.start.start()

    def tearDown(self):
        self.start.stop(); self.tmp.cleanup()

    def test_worker_persists_confirmed_failure_timing(self):
        replies = [{"queue_running": [], "queue_pending": []}, {"prompt_id": "worker-failed"},
                   {"worker-failed": {"status": {"status_str": "error"}}}]
        studio = FakeStudio(self.root, replies); created = studio.create_job({"preset_id": "demo", "controls": {}})
        with patch.object(studio.queue, "get", side_effect=[("generate", created["id"]), KeyboardInterrupt]), \
             patch.object(server.time, "time", side_effect=[100.0, 135.0, 160.0]):
            with self.assertRaises(KeyboardInterrupt): studio._work()
        job = studio.jobs[created["id"]]
        self.assertEqual(job["status"], "failed"); self.assertEqual(job["finished_at"], 160.0); self.assertEqual(job["elapsed_seconds"], 60.0)

    def test_repeated_history_failure_keeps_first_terminal_timestamp(self):
        error = {"prompt": {"status": {"status_str": "error"}}}
        studio = FakeStudio(self.root, [error]); created = studio.create_job({"preset_id": "demo", "controls": {}})
        job = studio.jobs[created["id"]]; job.update(started_at=100.0, submissions=[{"prompt_id": "prompt", "status": "observing"}]); studio._save(job)
        with patch.object(server.time, "time", return_value=160.0), self.assertRaises(Exception): studio._resume(job)
        first = (job["finished_at"], job["elapsed_seconds"])
        studio.replies = iter([{"prompt": {"status": {"status_str": "error"}}}])
        with patch.object(server.time, "time", return_value=170.0), self.assertRaises(Exception): studio._resume(job)
        self.assertEqual((job["finished_at"], job["elapsed_seconds"]), first)
        self.assertEqual(job["submissions"][0]["status"], "failed")

    def test_legacy_or_uncertain_observation_keeps_timing_unknown(self):
        for started in (None, True, float("nan"), float("inf"), 200.0):
            with self.subTest(started=started):
                error = {"prompt": {"status": {"status_str": "error"}}}
                studio = FakeStudio(self.root, [error]); created = studio.create_job({"preset_id": "demo", "controls": {}})
                job = studio.jobs[created["id"]]; job.update(started_at=started, submissions=[{"prompt_id": "prompt", "status": "observing"}]); studio._save(job)
                with patch.object(server.time, "time", return_value=160.0), self.assertRaises(Exception): studio._resume(job)
                self.assertEqual(studio.public(job)["finished_at"], 160.0); self.assertIsNone(studio.public(job)["elapsed_seconds"])

        uncertain = FakeStudio(self.root, [{"queue_running": [], "queue_pending": []}, URLError("lost")])
        unknown = uncertain.create_job({"preset_id": "demo", "controls": {}}); uncertain._run(uncertain.jobs[unknown["id"]])
        self.assertEqual(uncertain.jobs[unknown["id"]]["status"], "uncertain")
        self.assertIsNone(uncertain.public(uncertain.jobs[unknown["id"]])["finished_at"])
        self.assertIsNone(uncertain.public(uncertain.jobs[unknown["id"]])["elapsed_seconds"])

    def test_production_failure_records_job_timing_and_resume_does_not_post(self):
        replies = [{"queue_running": [], "queue_pending": []}, {"prompt_id": "production-failed"},
                   {"production-failed": {"status": {"status_str": "error"}}}]
        studio = FakeStudio(self.root, replies)
        with patch.object(server.Studio, "production_preflight", lambda s, *a: {"test_bundle": True, "comfy_url": s.comfy_url}), \
             patch.object(server.Studio, "check_production_bundle", lambda *a: None), \
             patch.object(server.Studio, "validate_graph", lambda *a: None):
            intent = {"name": "Failure timing", "recipe": {"preset_id": "demo", "controls": {}}, "axis": "seed", "values": [1], "max_generations": 1}
            project = studio.production.create(intent); studio.production.start(project["id"])
            with patch.object(server.time, "time", side_effect=[90.0, 95.0, 100.0, 135.0, 100.0, 125.0, 160.0, 170.0]): studio.production.run(project["id"])
            state = studio.production.get(project["id"])
            job = next(iter(studio.jobs.values()))
            self.assertEqual(state["state"]["status"], "failed"); self.assertEqual(job["elapsed_seconds"], 60.0)
            self.assertEqual(state["stages"][0]["job"]["finished_at"], 160.0)
            self.assertEqual(len([x for x in studio.requests if x[0][0] == "/prompt"]), 1)
            studio.replies = iter([{ "production-failed": {"status": {"status_str": "error"}}}])
            with self.assertRaises(Exception): studio._resume(job)
            self.assertEqual(len([x for x in studio.requests if x[0][0] == "/prompt"]), 1)


if __name__ == "__main__":
    unittest.main()
