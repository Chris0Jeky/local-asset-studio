"""Put away (#940): an owner-side, reversible hide flag for settled problem jobs.

Putting a job away records only `put_away_at`. It never changes status, reservations,
prompt IDs, outputs or tracking, and never queues, submits or resumes anything.
"""
import copy
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("asset_server_put_away", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)

GRAPH = {"1": {"inputs": {"text": "native positive", "seed": 1}}}
PRESET = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json",
          "positive": ["1", "text"], "seed": ["1", "seed"]}


class JobPutAwayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start = patch.object(threading.Thread, "start", lambda *_: None); self.start.start()

    def tearDown(self): self.start.stop(); self.tmp.cleanup()

    def studio(self): return server.Studio(self.root)

    def job(self, studio, **fields):
        job = studio.jobs[studio.create_job({"preset_id": "demo", "controls": {}}, enqueue=False)["id"]]
        job.update(fields); studio._save(job)
        return job

    def failed(self, studio):
        return self.job(studio, status="failed", message="Out of memory on the VAE decode", prompt_ids=["p-1"],
                        submissions=[{"index": 0, "prompt_id": "p-1", "seed": 1, "graph": GRAPH, "status": "failed"}],
                        failure={"exception_type": "OutOfMemoryError"}, host_commit_readings=[{"phase": "prepared"}])

    def uncertain(self, studio):
        return self.job(studio, status="uncertain", message="Known prompt observation was interrupted.", prompt_ids=["known"],
                        submissions=[{"index": 0, "prompt_id": "known", "seed": 1, "graph": GRAPH, "status": "observing"}],
                        outputs=[{"filename": "kept.png", "subfolder": "Studio", "type": "output", "prompt_id": "known"}])

    def state(self, studio, job):
        return json.loads((studio.runs / job["id"] / "state.json").read_text(encoding="utf-8"))

    def files(self, studio, job):
        directory = studio.runs / job["id"]
        return {name: (directory / name).read_bytes() for name in ("recipe.json", "workflow.json")}

    def test_put_away_records_only_a_timestamp_survives_restart_and_is_reversible(self):
        studio = self.studio(); job = self.failed(studio)
        before_state, before_files, before_job = self.state(studio, job), self.files(studio, job), json.dumps(job, sort_keys=True)
        queued = studio.queue.qsize()
        public = studio.public(job)
        self.assertTrue(public["can_put_away"]); self.assertFalse(public["put_away"]); self.assertIsNone(public["put_away_at"])
        with patch.object(server.time, "time", return_value=4321.5):
            public = studio.put_away_job(job["id"], True)
        self.assertEqual(public["put_away_at"], 4321.5); self.assertTrue(public["put_away"]); self.assertEqual(public["put_away_basis"], "owner")
        self.assertFalse(public["can_put_away"]); self.assertTrue(public["can_bring_back"])
        after = self.state(studio, job)
        self.assertEqual(after.pop("put_away_at"), 4321.5)
        self.assertEqual(after, before_state)  # status, message, prompt IDs, submissions, outputs, readings: untouched
        self.assertEqual(self.files(studio, job), before_files)
        self.assertEqual(studio.queue.qsize(), queued)
        live = dict(job); self.assertEqual(live.pop("put_away_at"), 4321.5)
        self.assertEqual(json.dumps(live, sort_keys=True), before_job)
        # Idempotent: a repeat keeps the first timestamp.
        self.assertEqual(studio.put_away_job(job["id"], True)["put_away_at"], 4321.5)
        restored = self.studio(); again = restored.jobs[job["id"]]
        self.assertEqual(again["status"], "failed"); self.assertEqual(again["put_away_at"], 4321.5)
        self.assertTrue(restored.public(again)["put_away"])
        brought = restored.put_away_job(job["id"], False)
        self.assertFalse(brought["put_away"]); self.assertIsNone(brought["put_away_at"]); self.assertTrue(brought["can_put_away"])
        self.assertEqual(self.state(restored, job), before_state); self.assertEqual(self.files(restored, job), before_files)
        self.assertEqual(restored.put_away_job(job["id"], False)["put_away_at"], None)
        self.assertNotIn("put_away_at", self.studio().jobs[job["id"]])

    def test_uncertain_job_still_tracking_is_refused_until_tracking_is_stopped(self):
        studio = self.studio(); job = self.uncertain(studio)
        state = (studio.runs / job["id"] / "state.json").read_bytes(); before = json.dumps(job, sort_keys=True)
        public = studio.public(job)
        self.assertTrue(public["can_stop_tracking"]); self.assertFalse(public["can_put_away"]); self.assertFalse(public["put_away"])
        with self.assertRaisesRegex(server.StudioError, "Stop tracking"):
            studio.put_away_job(job["id"], True)
        self.assertEqual((studio.runs / job["id"] / "state.json").read_bytes(), state); self.assertEqual(json.dumps(job, sort_keys=True), before)
        # Part 2: Stop tracking alone takes the job off the desk; nothing new is recorded for it.
        stopped = studio.stop_tracking(job["id"], "Owner inspected the retained prompt")
        self.assertTrue(stopped["put_away"]); self.assertEqual(stopped["put_away_basis"], "tracking_stopped")
        self.assertIsNone(stopped["put_away_at"]); self.assertFalse(stopped["can_bring_back"]); self.assertTrue(stopped["can_resume_tracking"])
        self.assertNotIn("put_away_at", self.state(studio, job))
        # Resuming observation brings it back; the resume path is not blocked by put-away.
        resumed = studio.resume_job(job["id"])
        self.assertEqual(resumed["status"], "queued"); self.assertFalse(resumed["put_away"])

    def test_owner_put_away_does_not_hide_a_job_that_became_active_again(self):
        studio = self.studio(); job = self.uncertain(studio)
        studio.stop_tracking(job["id"], "Stop for now")
        public = studio.put_away_job(job["id"], True)
        self.assertEqual(public["put_away_basis"], "owner"); self.assertIsNotNone(public["put_away_at"])
        # A successful explicit Resume clears the presentation marker: the
        # resumed observation is back on the desk while queued.
        resumed = studio.resume_job(job["id"])
        self.assertEqual(resumed["status"], "queued"); self.assertFalse(resumed["put_away"]); self.assertIsNone(resumed["put_away_basis"])
        self.assertIsNone(resumed["put_away_at"])
        # Bring back is now idempotent because Resume already removed the marker.
        brought_back = studio.put_away_job(job["id"], False)
        self.assertEqual(brought_back["status"], "queued"); self.assertIsNone(brought_back["put_away_at"])
        self.assertNotIn("put_away_at", job)
        self.assertNotIn("put_away_at", self.state(studio, job))

    def test_resume_clears_owner_marker_for_stopped_tracking_job(self):
        studio = self.studio(); job = self.uncertain(studio)
        studio.stop_tracking(job["id"], "Stop for now")
        studio.put_away_job(job["id"], True)
        self.assertIn("put_away_at", job)
        before = copy.deepcopy({k: v for k, v in job.items() if k != "put_away_at"})
        graph = job["graph"]
        history = studio._tracking_history(job)
        queued = studio.queue.qsize()
        published = []
        real_publish = studio._write_observation_state

        def capture(path, value):
            published.append(dict(value))
            return real_publish(path, value)

        with patch.object(studio, "_write_observation_state", side_effect=capture):
            resumed = studio.resume_job(job["id"])
        self.assertEqual(resumed["status"], "queued")
        self.assertIsNone(resumed["put_away_at"]); self.assertFalse(resumed["put_away"]); self.assertIsNone(resumed["put_away_basis"])
        self.assertNotIn("put_away_at", published[-1])  # removed from the prospective state before publication
        self.assertEqual(published[-1]["status"], "queued")
        self.assertNotIn("put_away_at", job)  # removed from the live job only after publication succeeded
        persisted = self.state(studio, job)
        self.assertNotIn("put_away_at", persisted); self.assertEqual(persisted["status"], "queued")
        self.assertEqual(studio.queue.qsize(), queued + 1)
        self.assertEqual(studio.queue.get_nowait(), ("observe", job["id"])); self.assertTrue(studio.queue.empty())
        # Status, prompt IDs, submissions, outputs and tracking history follow the existing Resume behavior only.
        self.assertEqual(job["prompt_ids"], before["prompt_ids"]); self.assertEqual(job["submissions"], before["submissions"])
        self.assertEqual(job["outputs"], before["outputs"]); self.assertIs(job["graph"], graph)
        self.assertEqual(job["tracking_disposition"]["history"][:-1], history)
        self.assertEqual(job["tracking_disposition"]["status"], "resumed")
        self.assertEqual(job["tracking_disposition"]["event_id"], before["tracking_disposition"]["event_id"])
        # A later failed/partial/uncertain outcome surfaces as an unacknowledged problem.
        for status in ("failed", "partial"):
            with self.subTest(status=status):
                job["status"] = status; job["message"] = "Resumed observation settled again"; studio._save(job)
                settled = studio.public(job)
                self.assertFalse(settled["put_away"]); self.assertIsNone(settled["put_away_at"]); self.assertTrue(settled["can_put_away"])
        job["status"] = "uncertain"; job["message"] = "Resumed observation was interrupted again"; studio._save(job)
        unsettled = studio.public(job)
        self.assertFalse(unsettled["put_away"]); self.assertIsNone(unsettled["put_away_at"])

    def test_resume_clears_owner_marker_for_ordinary_known_prompt_job(self):
        studio = self.studio(); job = self.failed(studio)
        studio.put_away_job(job["id"], True)
        self.assertIn("put_away_at", job)
        before = copy.deepcopy({k: v for k, v in job.items() if k != "put_away_at"})
        graph = job["graph"]
        queued = studio.queue.qsize()
        published = []
        real_publish = studio._write_observation_state

        def capture(path, value):
            published.append(dict(value))
            return real_publish(path, value)

        with patch.object(studio, "_write_observation_state", side_effect=capture):
            resumed = studio.resume_job(job["id"])
        self.assertEqual(resumed["status"], "queued")
        self.assertIsNone(resumed["put_away_at"]); self.assertFalse(resumed["put_away"]); self.assertIsNone(resumed["put_away_basis"])
        self.assertNotIn("put_away_at", published[-1])  # removed from the prospective state before publication
        self.assertEqual(published[-1]["status"], "queued")
        self.assertNotIn("put_away_at", job)  # removed from the live job only after publication succeeded
        persisted = self.state(studio, job)
        self.assertNotIn("put_away_at", persisted); self.assertEqual(persisted["status"], "queued")
        self.assertEqual(studio.queue.qsize(), queued + 1)
        self.assertEqual(studio.queue.get_nowait(), ("observe", job["id"])); self.assertTrue(studio.queue.empty())
        # Prompt IDs, submissions and outputs follow the existing Resume behavior only.
        self.assertEqual(job["prompt_ids"], before["prompt_ids"]); self.assertEqual(job["submissions"], before["submissions"])
        self.assertEqual(job["outputs"], before["outputs"]); self.assertIs(job["graph"], graph)
        # A later failed/partial outcome surfaces as an unacknowledged problem.
        for status in ("failed", "partial"):
            with self.subTest(status=status):
                job["status"] = status; job["message"] = "Resumed observation settled again"; studio._save(job)
                settled = studio.public(job)
                self.assertFalse(settled["put_away"]); self.assertIsNone(settled["put_away_at"]); self.assertTrue(settled["can_put_away"])

    def test_resume_publication_failure_retains_owner_marker(self):
        for path in ("stopped-tracking", "ordinary"):
            with self.subTest(path=path):
                studio = self.studio()
                if path == "stopped-tracking":
                    job = self.uncertain(studio); studio.stop_tracking(job["id"], "Stop for now")
                else:
                    job = self.failed(studio)
                studio.put_away_job(job["id"], True)
                marker = job["put_away_at"]
                before = copy.deepcopy(job)
                raw = (studio.runs / job["id"] / "state.json").read_bytes()
                queued = studio.queue.qsize()
                with patch.object(studio, "_write_observation_state", side_effect=OSError("disk full")):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        studio.resume_job(job["id"])
                self.assertEqual(job, before)  # marker and everything else retained in memory
                self.assertEqual(job["put_away_at"], marker)
                self.assertEqual((studio.runs / job["id"] / "state.json").read_bytes(), raw)  # and on disk
                self.assertEqual(studio.queue.qsize(), queued)  # nothing queued
                self.assertTrue(studio.public(job)["put_away"])

    def test_resume_validation_and_worker_failures_retain_owner_marker(self):
        studio = self.studio(); job = self.failed(studio)
        studio.put_away_job(job["id"], True)
        marker = job["put_away_at"]
        # An unknown submission cannot resume as a known prompt: validation fails before any publication.
        job["pending_submission"] = {"index": 0}; studio._save(job)
        raw = (studio.runs / job["id"] / "state.json").read_bytes()
        queued = studio.queue.qsize()
        with patch.object(studio, "_write_observation_state") as publish:
            with self.assertRaises(server.StudioError):
                studio.resume_job(job["id"])
        publish.assert_not_called()
        self.assertEqual(job["put_away_at"], marker)
        self.assertIn("pending_submission", job)
        self.assertEqual((studio.runs / job["id"] / "state.json").read_bytes(), raw)
        self.assertEqual(studio.queue.qsize(), queued)
        # A dead worker refuses admission before any publication.
        job.pop("pending_submission"); studio._save(job)
        raw = (studio.runs / job["id"] / "state.json").read_bytes()
        studio.worker = type("DeadWorker", (), {"ident": 1, "is_alive": lambda self: False})()
        with patch.object(studio, "_write_observation_state") as publish:
            with self.assertRaisesRegex(server.StudioError, "worker is unavailable"):
                studio.resume_job(job["id"])
        publish.assert_not_called()
        self.assertEqual(job["put_away_at"], marker)
        self.assertEqual((studio.runs / job["id"] / "state.json").read_bytes(), raw)
        self.assertEqual(studio.queue.qsize(), queued)
        self.assertTrue(studio.public(job)["put_away"])

    def test_active_completed_and_unknown_submission_jobs_are_refused_without_mutation(self):
        cases = {"queued": dict(status="queued"), "running": dict(status="running"), "completed": dict(status="completed"),
                 "not submitted": dict(status="not_submitted"),
                 "unknown submission": dict(status="partial", pending_submission={"index": 1})}
        for name, fields in cases.items():
            with self.subTest(name=name):
                studio = self.studio(); job = self.job(studio, **fields)
                state = (studio.runs / job["id"] / "state.json").read_bytes(); before = json.dumps(job, sort_keys=True)
                self.assertFalse(studio.public(job)["can_put_away"])
                with self.assertRaises(server.StudioError):
                    studio.put_away_job(job["id"], True)
                self.assertEqual((studio.runs / job["id"] / "state.json").read_bytes(), state)
                self.assertEqual(json.dumps(job, sort_keys=True), before)

    def test_partial_and_abandoned_jobs_can_be_put_away(self):
        studio = self.studio()
        for fields in (dict(status="partial"), dict(status="abandoned", abandonment={"reason": "Replacement ran", "basis": "outcome_unknown"},
                                                    pending_submission={"index": 0})):
            job = self.job(studio, **fields)
            self.assertTrue(studio.put_away_job(job["id"], True)["put_away"])
            self.assertEqual(job["status"], fields["status"])

    def test_invalid_commands_and_failed_publication_leave_memory_unchanged(self):
        studio = self.studio(); job = self.failed(studio)
        for value in (None, 1, "true", 0):
            with self.subTest(value=value), self.assertRaisesRegex(server.StudioError, "true or false"):
                studio.put_away_job(job["id"], value)
        with self.assertRaisesRegex(server.StudioError, "Unknown job"):
            studio.put_away_job("missing", True)
        with patch.object(studio, "_write_observation_state", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                studio.put_away_job(job["id"], True)
        self.assertNotIn("put_away_at", job)
        studio.put_away_job(job["id"], True)
        with patch.object(studio, "_write_observation_state", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                studio.put_away_job(job["id"], False)
        self.assertIn("put_away_at", job)

    def test_route_requires_same_origin_and_an_object_body(self):
        studio = self.studio(); job = self.failed(studio); sent = []

        def post(path, body, safe=True):
            handler = server.Handler.__new__(server.Handler); handler.studio = studio; handler.path = path
            handler._safe_mutation = lambda: safe; handler._body_json = lambda *a: body
            sent.clear(); handler._json = lambda status, obj: sent.append((status, obj))
            handler.do_POST(); return sent[0]

        self.assertEqual(post("/api/jobs/" + job["id"] + "/put-away", {"put_away": True}, safe=False)[0], 403)
        self.assertNotIn("put_away_at", job)
        for body in ([], "yes", {"put_away": "yes"}, {}):
            with self.subTest(body=repr(body)):
                self.assertEqual(post("/api/jobs/" + job["id"] + "/put-away", body)[0], 400)
        self.assertEqual(post("/api/jobs/x/y/put-away", {"put_away": True})[0], 400)
        status, public = post("/api/jobs/" + job["id"] + "/put-away", {"put_away": True})
        self.assertEqual(status, 200); self.assertTrue(public["put_away"]); self.assertEqual(job["status"], "failed")
        status, public = post("/api/jobs/" + job["id"] + "/put-away", {"put_away": False})
        self.assertEqual(status, 200); self.assertFalse(public["put_away"]); self.assertNotIn("put_away_at", job)


if __name__ == "__main__":
    unittest.main()
