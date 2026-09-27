"""Owner cancel (#1138): targets only this job's prompt, records what ComfyUI showed, never resubmits.

A scripted ComfyUI answers each `_request` in order and fails the test on any call it did not expect, so every test
also proves which requests were (and were not) sent: no second /prompt, no interrupt of a prompt that is not ours.
"""
import copy
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

SPEC = importlib.util.spec_from_file_location("asset_server_job_cancel", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
import job_cancel  # noqa: E402  (app/ is on sys.path once server.py is loaded)

GRAPH = {"1": {"inputs": {"text": "native positive", "seed": 1}}}
PRESET = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json",
          "positive": ["1", "text"], "seed": ["1", "seed"]}
IDLE = {"queue_running": [], "queue_pending": []}


def queue(running=(), pending=()):
    return {"queue_running": [[0, p, {}, {}, []] for p in running], "queue_pending": [[1, p, {}, {}, []] for p in pending]}


def success(prompt_id, filename="ok.png"):
    return {prompt_id: {"status": {"status_str": "success", "completed": True},
                        "outputs": {"9": {"images": [{"filename": filename, "subfolder": "", "type": "output"}]}}}}


def interrupted(prompt_id):
    return {prompt_id: {"status": {"status_str": "error", "completed": False,
                                   "messages": [["execution_start", {}], ["execution_interrupted", {"node_id": "3"}]]}, "outputs": {}}}


class ScriptedStudio(server.Studio):
    """Each step is (method, path, reply); a callable reply runs first (to model the owner clicking) and returns the reply."""
    def __init__(self, root, script):
        self.script = list(script); self.requests = []; super().__init__(root)

    def _request(self, path, method="GET", data=None, **kwargs):
        self.requests.append((method, path, data))
        if not self.script: raise AssertionError(f"unexpected ComfyUI request {method} {path}")
        want_method, want_path, reply = self.script.pop(0)
        if (want_method, want_path) != (method, path): raise AssertionError(f"expected {want_method} {want_path}, got {method} {path}")
        if callable(reply): reply = reply()
        if isinstance(reply, Exception): raise reply
        return reply

    def posts(self, path): return [r for r in self.requests if r[0] == "POST" and r[1] == path]


class JobCancelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.real_start = threading.Thread.start
        for target in (patch.object(threading.Thread, "start", lambda *_: None), patch.object(server.time, "sleep", lambda *_: None)):
            target.start(); self.addCleanup(target.stop)
        self.addCleanup(self.tmp.cleanup)

    def studio(self, script=()): return ScriptedStudio(self.root, script)

    def job(self, studio, batch=1):
        return studio.jobs[studio.create_job({"preset_id": "demo", "controls": {}, "batch_count": batch})["id"]]

    def state(self, studio, job): return json.loads((studio.runs / job["id"] / "state.json").read_text(encoding="utf-8"))

    def click(self, studio, job, result):
        """The owner's Cancel click arriving while ComfyUI answers a request."""
        def reply():
            self.clicked = studio.cancel_job(job["id"]); return result
        return reply

    def assertNoResubmission(self, studio, submitted=1):
        self.assertEqual(studio.script, [], "every scripted ComfyUI answer is consumed")
        self.assertEqual(len(studio.posts("/prompt")), submitted)

    # -- not started -------------------------------------------------------------------------------------------
    def test_queued_job_is_settled_at_once_nothing_is_sent_and_the_worker_skips_it(self):
        studio = self.studio(); job = self.job(studio)
        self.assertTrue(studio.public(job)["can_cancel"]); self.assertFalse(studio.public(job)["cancel_needs_confirm"])
        public = studio.cancel_job(job["id"])
        self.assertEqual(public["status"], "cancelled"); self.assertEqual(public["message"], "Not started: cancelled by you. Nothing was sent to ComfyUI.")
        record = public["cancellation"]
        self.assertEqual((record["state"], record["requested_by"], record["status_at_request"]), ("cancelled", "owner", "queued"))
        self.assertEqual(self.state(studio, job)["status"], "cancelled")
        self.assertFalse(public["can_cancel"]); self.assertEqual(public["cancel_blocked_reason"], "Already cancelled")
        again = studio.cancel_job(job["id"])  # double click
        self.assertEqual(again["cancellation"]["event_id"], record["event_id"])
        studio._run(job)  # the worker dequeues it later
        self.assertEqual(job["status"], "cancelled"); self.assertEqual(studio.requests, [])
        with self.assertRaisesRegex(server.StudioError, "cancelled job is closed"): studio.resume_job(job["id"])

    def test_cancel_while_waiting_for_a_busy_comfyui_stops_before_the_post(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", self.click(studio, job, queue(running=["someone-else"])))]
        studio._run(job)
        self.assertEqual(self.clicked["cancellation"]["state"], "requested")
        self.assertEqual(job["status"], "cancelled"); self.assertEqual(job["prompt_ids"], []); self.assertNoResubmission(studio, 0)
        self.assertEqual(job["cancellation"]["status_at_request"], "waiting"); self.assertEqual(job["cancellation"]["state"], "cancelled")
        self.assertNotIn(job["id"], studio.cancel_requests); self.assertEqual(self.state(studio, job)["status"], "cancelled")

    # -- pending in ComfyUI ------------------------------------------------------------------------------------
    def test_pending_prompt_is_deleted_by_id_and_verified_gone_from_queue_and_history(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(running=["lab"], pending=["ours"])), ("POST", "/queue", None),
                         ("GET", "/queue", queue(running=["lab"])), ("GET", "/history/ours", {})]
        studio._run(job)
        self.assertEqual(self.clicked["cancellation"]["status_at_request"], "submitting")
        self.assertEqual(job["status"], "cancelled"); self.assertIn("removed the prompt before it started", job["message"])
        self.assertEqual(studio.posts("/queue"), [("POST", "/queue", {"delete": ["ours"]})]); self.assertEqual(studio.posts("/interrupt"), [])
        self.assertEqual(job["submissions"][0]["status"], "cancelled"); self.assertEqual(job["submissions"][0]["cancelled"]["basis"], "dequeued")
        record = job["cancellation"]
        self.assertEqual([a["action"] for a in record["actions"]], ["dequeue"]); self.assertEqual(record["actions"][0]["reply"], "ok")
        self.assertEqual([(o["queue"], o.get("history")) for o in record["observations"]], [("pending", None), ("absent", "absent")])
        self.assertEqual(job["prompt_ids"], ["ours"]); self.assertNoResubmission(studio)
        saved = self.state(studio, job); self.assertEqual(saved["status"], "cancelled"); self.assertEqual(saved["cancellation"]["state"], "cancelled")

    def test_prompt_that_started_before_the_delete_landed_is_interrupted_only_once_it_is_seen_running(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(pending=["ours"])), ("POST", "/queue", None), ("GET", "/queue", queue(running=["ours"])),
                         ("GET", "/history/ours", {}),                     # observer poll after the failed delete
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", None),
                         ("GET", "/history/ours", interrupted("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "cancelled"); self.assertEqual([a["action"] for a in job["cancellation"]["actions"]], ["dequeue", "interrupt"])
        self.assertEqual(studio.posts("/interrupt"), [("POST", "/interrupt", {"prompt_id": "ours"})]); self.assertNoResubmission(studio)

    def test_prompt_that_ran_and_finished_before_the_delete_is_not_claimed_cancelled(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(pending=["ours"])), ("POST", "/queue", None), ("GET", "/queue", IDLE),
                         ("GET", "/history/ours", success("ours")), ("GET", "/history/ours", success("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(job["submissions"][0]["status"], "completed")
        self.assertEqual(job["cancellation"]["observations"][-1]["history"], "present")
        self.assertEqual(job["cancellation"]["state"], "too_late"); self.assertIn("settled as completed", job["cancellation"]["note"])
        self.assertNoResubmission(studio)

    # -- running -----------------------------------------------------------------------------------------------
    def test_running_prompt_that_is_ours_is_interrupted_with_its_id_and_history_confirms_it(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "ours"}),
                         ("GET", "/history/ours", self.click(studio, job, {})),
                         ("GET", "/queue", queue(running=["ours"], pending=["lab-next"])), ("POST", "/interrupt", None),
                         ("GET", "/history/ours", interrupted("ours"))]
        studio._run(job)
        self.assertFalse(self.clicked["can_cancel"]); self.assertIn("Cancel requested", self.clicked["cancel_blocked_reason"])
        self.assertEqual(self.clicked["cancellation"]["status_at_request"], "running")
        self.assertEqual(job["status"], "cancelled"); self.assertIn("reported the render interrupted", job["message"])
        self.assertEqual(job["submissions"][0]["cancelled"], dict(job["submissions"][0]["cancelled"], basis="interrupted", interrupt_reply="ok"))
        self.assertEqual(studio.posts("/interrupt"), [("POST", "/interrupt", {"prompt_id": "ours"})])
        self.assertEqual(studio.posts("/queue"), []); self.assertNoResubmission(studio)
        self.assertIsNone(job.get("failure")); self.assertTrue(job["finished_at"] >= job["started_at"])

    def test_running_prompt_that_is_not_ours_is_refused_and_nothing_is_interrupted(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "ours"}),
                         ("GET", "/history/ours", self.click(studio, job, {})), ("GET", "/queue", queue(running=["lab"])),
                         ("GET", "/history/ours", success("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(studio.posts("/interrupt"), []); self.assertEqual(studio.posts("/queue"), [])
        record = job["cancellation"]; self.assertEqual(record["state"], "refused")
        self.assertIn("does not list this job's prompt", record["note"]); self.assertIn("another prompt", record["note"])
        self.assertEqual(record["observations"][0]["running"], ["lab"]); self.assertNoResubmission(studio)
        self.assertTrue(studio.public(job)["can_cancel"] is False)

    def test_two_running_prompts_or_an_unreadable_queue_are_refused_without_any_action(self):
        for answer, words in ((queue(running=["ours", "lab"]), "more than one running prompt"), (URLError("refused"), "Could not read ComfyUI's queue"),
                              ({"queue_running": "?"}, "Could not read ComfyUI's queue")):
            with self.subTest(words=words):
                studio = self.studio(); job = self.job(studio)
                studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                                 ("GET", "/queue", answer), ("GET", "/history/ours", success("ours"))]
                studio._run(job)
                self.assertEqual(job["status"], "completed"); self.assertEqual(job["cancellation"]["state"], "refused")
                self.assertIn(words, job["cancellation"]["note"]); self.assertEqual(studio.posts("/interrupt"), [])
                self.assertNotIn(job["id"], studio.cancel_requests); self.assertNoResubmission(studio)

    def test_a_refused_cancel_still_stops_the_rest_of_a_batch(self):
        # #1159 review: the in-flight output cannot be proven ours, but stopping before the next POST needs nothing from ComfyUI.
        for answer, words in ((queue(running=["lab"]), "does not list this job's prompt"), (URLError("refused"), "Could not read ComfyUI's queue")):
            with self.subTest(words=words):
                studio = self.studio(); job = self.job(studio, batch=3); second = ("POST", "/prompt", {"prompt_id": "two"})
                studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "one"})),
                                 ("GET", "/queue", answer), ("GET", "/history/one", success("one")), second]
                studio._run(job)
                self.assertEqual(studio.script, [second], "the second output is never submitted")
                self.assertEqual(len(studio.posts("/prompt")), 1); self.assertEqual(studio.posts("/interrupt"), [])
                self.assertEqual(job["status"], "cancelled"); self.assertEqual(job["prompt_ids"], ["one"]); self.assertEqual(len(job["outputs"]), 1)
                self.assertIn("1 of 3 outputs finished and are kept", job["message"])
                record = job["cancellation"]; self.assertEqual(record["state"], "cancelled"); self.assertNotIn("stop_submissions", record)
                self.assertIn(words, record["refusal"]); self.assertIn("No further outputs", record["refusal"])
                self.assertIn("in-flight output could not be stopped", record["note"])

    def test_a_single_output_refusal_stays_refused_and_carries_no_batch_stop(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(running=["lab"])), ("GET", "/history/ours", success("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(job["cancellation"]["state"], "refused")
        self.assertNotIn("stop_submissions", job["cancellation"]); self.assertNotIn("No further outputs", job["cancellation"]["note"])
        self.assertNoResubmission(studio)

    def test_a_delete_whose_read_back_was_lost_is_confirmed_by_history_not_refused(self):
        # #1159 review: the next pass finds the prompt absent; the earlier delete is noticed and /history decides.
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(pending=["ours"])), ("POST", "/queue", None), ("GET", "/queue", URLError("busy")),
                         ("GET", "/history/ours", {}),
                         ("GET", "/queue", IDLE), ("GET", "/history/ours", {})]
        studio._run(job)
        self.assertEqual(job["status"], "cancelled"); self.assertEqual(job["submissions"][0]["cancelled"]["basis"], "dequeued")
        record = job["cancellation"]; self.assertEqual(record["state"], "cancelled"); self.assertEqual([a["action"] for a in record["actions"]], ["dequeue"])
        self.assertEqual([(o["queue"], o.get("history")) for o in record["observations"]], [("pending", None), ("unreadable", None), ("absent", "absent")])
        self.assertNoResubmission(studio)
        # Same lost read-back, but history shows it ran: not claimed cancelled, never "refused... nothing was cancelled".
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(pending=["ours"])), ("POST", "/queue", None), ("GET", "/queue", URLError("busy")),
                         ("GET", "/history/ours", {}), ("GET", "/queue", IDLE), ("GET", "/history/ours", success("ours")),
                         ("GET", "/history/ours", success("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(job["cancellation"]["state"], "too_late"); self.assertNoResubmission(studio)

    def test_refused_cancel_can_be_asked_again_and_keeps_the_earlier_attempt(self):
        studio = self.studio(); job = self.job(studio)
        def second():
            self.second = studio.cancel_job(job["id"]); return {}
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", URLError("busy")), ("GET", "/history/ours", second),
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", None), ("GET", "/history/ours", interrupted("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "cancelled"); self.assertEqual(job["cancellation"]["previous"][-1]["state"], "refused")
        self.assertNotEqual(job["cancellation"]["event_id"], job["cancellation"]["previous"][-1]["event_id"]); self.assertNoResubmission(studio)

    # -- races -------------------------------------------------------------------------------------------------
    def test_interrupt_sent_but_render_completed_anyway_is_recorded_as_completed_too_late(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", None), ("GET", "/history/ours", success("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(len(job["outputs"]), 1)
        self.assertEqual(job["cancellation"]["state"], "too_late"); self.assertIn("finished the render before the interrupt", job["cancellation"]["note"])
        self.assertEqual(self.state(studio, job)["cancellation"]["state"], "too_late"); self.assertNoResubmission(studio)

    def test_cancel_that_lands_as_the_render_finishes_is_too_late_and_a_finished_job_refuses_it(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "ours"}), ("GET", "/history/ours", self.click(studio, job, success("ours")))]
        studio._run(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(job["cancellation"]["state"], "too_late")
        self.assertEqual(studio.posts("/interrupt"), []); self.assertNoResubmission(studio)
        with self.assertRaisesRegex(server.StudioError, "already finished"): studio.cancel_job(job["id"])

    def test_double_cancel_records_one_request_and_sends_one_action(self):
        studio = self.studio(); job = self.job(studio)
        def twice():
            first = studio.cancel_job(job["id"]); second = studio.cancel_job(job["id"])
            self.assertEqual(first["cancellation"]["event_id"], second["cancellation"]["event_id"]); return {"prompt_id": "ours"}
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", twice), ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", None),
                         ("GET", "/history/ours", {}), ("GET", "/history/ours", interrupted("ours"))]
        studio._run(job)
        self.assertEqual(len(studio.posts("/interrupt")), 1); self.assertEqual(job["status"], "cancelled"); self.assertNoResubmission(studio)

    def test_lost_interrupt_reply_is_resolved_only_by_history(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", URLError("reset")), ("GET", "/history/ours", interrupted("ours"))]
        studio._run(job)
        self.assertEqual(job["status"], "cancelled"); self.assertTrue(job["submissions"][0]["cancelled"]["interrupt_reply"].startswith("no reply"))
        # Same lost reply, then ComfyUI stays unreadable for every bounded history read (#1113): uncertain, cancel not confirmed.
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", URLError("reset"))] + [("GET", "/history/ours", URLError("down"))] * server.HISTORY_READ_STRIKES
        studio._run(job)
        self.assertEqual(job["status"], "uncertain"); self.assertEqual(job["cancellation"]["state"], "unresolved")
        self.assertIn("not confirmed", job["cancellation"]["note"]); self.assertNoResubmission(studio)

    def unresolved_after_interrupt(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", None)] + [("GET", "/history/ours", URLError("down"))] * server.HISTORY_READ_STRIKES
        studio._run(job)
        self.assertEqual((job["status"], job["cancellation"]["state"]), ("uncertain", "unresolved"))
        studio.resume_job(job["id"]); return studio, job

    def test_resume_observation_settles_an_unresolved_cancel_from_the_observed_outcome(self):
        # #1159 review (Codex): finish() used to ignore an `unresolved` cancel once Resume observation saw the outcome.
        studio, job = self.unresolved_after_interrupt()
        studio.script = [("GET", "/history/ours", success("ours"))]; studio._resume(job)
        self.assertEqual(job["status"], "completed"); self.assertEqual(job["cancellation"]["state"], "too_late")
        self.assertIn("before the interrupt took effect", job["cancellation"]["note"]); self.assertIn("not confirmed", job["cancellation"]["unresolved_note"])
        self.assertEqual(self.state(studio, job)["cancellation"]["state"], "too_late"); self.assertNoResubmission(studio)
        studio, job = self.unresolved_after_interrupt()
        studio.script = [("GET", "/history/ours", interrupted("ours"))]; studio._resume(job)
        self.assertEqual((job["status"], job["cancellation"]["state"]), ("cancelled", "cancelled")); self.assertNoResubmission(studio)
        self.assertIn("not confirmed", job["cancellation"].get("unresolved_note") or "", "the earlier note is kept on both legs")
        studio, job = self.unresolved_after_interrupt()
        studio.script = [("GET", "/history/ours", URLError("still down"))] * server.HISTORY_READ_STRIKES; studio._resume(job)
        self.assertEqual((job["status"], job["cancellation"]["state"]), ("uncertain", "unresolved"), "still unknown stays unresolved")

    def test_a_history_read_lost_while_verifying_a_delete_is_rechecked_on_the_next_pass(self):
        # #1159 review (Muse): a transient /history failure right after the delete leaves the request open, never refused.
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, {"prompt_id": "ours"})),
                         ("GET", "/queue", queue(pending=["ours"])), ("POST", "/queue", None), ("GET", "/queue", IDLE), ("GET", "/history/ours", URLError("blip")),
                         ("GET", "/history/ours", {}), ("GET", "/queue", IDLE), ("GET", "/history/ours", {})]
        studio._run(job)
        self.assertEqual((job["status"], job["cancellation"]["state"]), ("cancelled", "cancelled"))
        self.assertEqual([(o["queue"], o.get("history")) for o in job["cancellation"]["observations"]], [("pending", None), ("absent", "unreadable"), ("absent", "absent")])
        self.assertNoResubmission(studio)

    def test_a_cancel_from_another_thread_while_the_worker_waits_on_comfyui(self):
        # #1159 review (Muse): a real second thread. Events order the steps, so nothing depends on timing.
        studio = self.studio(); job = self.job(studio); inside, release = threading.Event(), threading.Event()
        def blocking_history():
            inside.set(); self.assertTrue(release.wait(10)); return {}
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "ours"}), ("GET", "/history/ours", blocking_history),
                         ("GET", "/queue", queue(running=["ours"])), ("POST", "/interrupt", None), ("GET", "/history/ours", interrupted("ours"))]
        worker = threading.Thread(target=studio._run, args=(job,), daemon=True); self.real_start(worker)
        self.assertTrue(inside.wait(10), "the worker reached its observation")
        asked = studio.cancel_job(job["id"])
        self.assertEqual((asked["status"], asked["cancellation"]["state"]), ("running", "requested"))
        self.assertEqual(json.loads((studio.runs / job["id"] / "cancel-request.json").read_text())["event_id"], asked["cancellation"]["event_id"])
        self.assertNotIn("cancellation", self.state(studio, job), "the request thread never writes the worker's state file")
        release.set(); worker.join(10); self.assertFalse(worker.is_alive())
        self.assertEqual((job["status"], job["cancellation"]["state"]), ("cancelled", "cancelled")); self.assertNoResubmission(studio)

    def test_interrupted_by_someone_else_before_our_interrupt_stays_a_failure(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "ours"}), ("GET", "/history/ours", interrupted("ours"))]
        with self.assertRaises(server.StudioError): studio._run(job)
        self.assertEqual(job["status"], "failed"); self.assertNotIn("cancellation", job); self.assertNoResubmission(studio)

    def test_uncertain_submission_leaves_the_cancel_unresolved_and_never_resubmits(self):
        studio = self.studio(); job = self.job(studio)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", self.click(studio, job, URLError("timeout")))]
        studio._run(job)
        self.assertEqual(job["status"], "uncertain"); self.assertEqual(job["cancellation"]["state"], "unresolved"); self.assertNoResubmission(studio)

    # -- batches -----------------------------------------------------------------------------------------------
    def test_batch_cancel_between_outputs_keeps_finished_outputs_and_submits_nothing_more(self):
        studio = self.studio(); job = self.job(studio, batch=3)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "one"}), ("GET", "/history/one", self.click(studio, job, success("one")))]
        studio._run(job)
        self.assertEqual(job["status"], "cancelled"); self.assertEqual(job["prompt_ids"], ["one"]); self.assertEqual(len(job["outputs"]), 1)
        self.assertIn("1 of 3 outputs finished and are kept", job["message"]); self.assertIn("remaining outputs were not submitted", job["message"])
        self.assertNoResubmission(studio)

    def test_batch_cancel_during_the_second_output_interrupts_it_and_keeps_the_first(self):
        studio = self.studio(); job = self.job(studio, batch=3)
        studio.script = [("GET", "/queue", IDLE), ("POST", "/prompt", {"prompt_id": "one"}), ("GET", "/history/one", success("one")),
                         ("POST", "/prompt", {"prompt_id": "two"}), ("GET", "/history/two", self.click(studio, job, {})),
                         ("GET", "/queue", queue(running=["two"])), ("POST", "/interrupt", None), ("GET", "/history/two", interrupted("two"))]
        studio._run(job)
        self.assertEqual(job["status"], "cancelled"); self.assertEqual([s["status"] for s in job["submissions"]], ["completed", "cancelled"])
        self.assertEqual(len(job["outputs"]), 1); self.assertIn("1 of 3 outputs finished", job["message"]); self.assertNoResubmission(studio, 2)

    # -- refusals, restart, route ------------------------------------------------------------------------------
    def test_blocked_reasons_name_the_safe_alternative(self):
        studio = self.studio(); job = self.job(studio)
        for fields, words in (({"status": "uncertain"}, "Stop tracking"), ({"status": "not_submitted"}, "abandon"), ({"status": "failed"}, "already finished"),
                              ({"status": "running", "project_id": "p" * 32}, "comparison"),
                              ({"status": "running", "pending_submission": {"index": 1}, "prompt_ids": ["a"]}, "submission outcome is unknown")):
            with self.subTest(words=words):
                trial = dict(job, **fields); public = studio.public(trial)
                self.assertFalse(public["can_cancel"]); self.assertIn(words, public["cancel_blocked_reason"])
        # Confirm only when something was sent and may be rendering.
        for fields, confirm in (({"status": "waiting"}, False), ({"status": "running", "prompt_ids": ["a"]}, True),
                                ({"status": "submitting", "pending_submission": {"index": 0}}, True)):
            with self.subTest(confirm=fields["status"]):
                public = studio.public(dict(job, **fields))
                self.assertTrue(public["can_cancel"]); self.assertIs(public["cancel_needs_confirm"], confirm); self.assertIsNone(public["cancel_blocked_reason"])

    def test_dead_worker_refuses_a_started_job_but_still_settles_a_queued_one(self):
        studio = self.studio(); job = self.job(studio)
        class Dead:
            ident = 1
            def is_alive(self): return False
        studio.worker = Dead()
        running = dict(job, status="running", prompt_ids=["ours"]); studio.jobs["r"] = dict(running, id="r")
        with self.assertRaisesRegex(server.StudioError, "worker is unavailable"): studio.cancel_job("r")
        self.assertEqual(studio.cancel_job(job["id"])["status"], "cancelled")

    def test_restart_with_an_open_request_cancels_a_never_sent_job_and_leaves_a_sent_one_unresolved(self):
        studio = self.studio(); waiting = self.job(studio); sent = self.job(studio)
        for job, extra in ((waiting, {"status": "waiting"}), (sent, {"status": "running", "prompt_ids": ["ours"],
                                                                      "submissions": [{"index": 0, "prompt_id": "ours", "seed": 1, "status": "observing"}]})):
            job.update(extra); studio._save(job); studio.cancel_job(job["id"])
        restarted = self.studio(); a, b = restarted.jobs[waiting["id"]], restarted.jobs[sent["id"]]
        self.assertEqual((a["status"], a["cancellation"]["state"]), ("cancelled", "cancelled"))
        self.assertEqual((b["status"], b["cancellation"]["state"]), ("uncertain", "unresolved")); self.assertIn("restarted", b["cancellation"]["note"])
        self.assertEqual(restarted.requests, []); self.assertEqual(self.state(restarted, b)["cancellation"]["state"], "unresolved")
        again = self.studio(); self.assertEqual(again.jobs[sent["id"]]["cancellation"]["resolved_at"], b["cancellation"]["resolved_at"])  # idempotent reload

    def test_a_confirmed_cancel_is_terminal_for_resource_reservations_and_an_open_one_is_not(self):
        import resource_admission
        done = {"status": "cancelled", "submissions": [{"status": "completed"}, {"status": "cancelled"}]}
        self.assertTrue(resource_admission._definitive_terminal(done))
        self.assertFalse(resource_admission._definitive_terminal(dict(done, submissions=[{"status": "observing"}])))
        self.assertFalse(resource_admission._definitive_terminal(dict(done, status="running")))

    def test_http_route_answers_202_and_refuses_bad_bodies_and_routes(self):
        studio = self.studio(); job = self.job(studio); sent = []
        def post(path, body):
            handler = server.Handler.__new__(server.Handler); handler.studio = studio; handler.path = path
            handler._safe_mutation = lambda: True; handler._body_json = lambda *a: body
            sent.clear(); handler._json = lambda status, obj: sent.append((status, obj)); handler.do_POST(); return sent[0]
        self.assertEqual(post("/api/jobs/%s/cancel" % job["id"], [])[0], 400)
        self.assertEqual(post("/api/jobs/x/y/cancel", {})[0], 400)
        self.assertEqual(post("/api/jobs/missing/cancel", {}), (400, {"error": "Unknown job"}))
        status, body = post("/api/jobs/%s/cancel" % job["id"], {})
        self.assertEqual((status, body["status"]), (202, "cancelled"))

    # -- job_cancel unit pins (current behaviour, not a spec) ------------------------------------------------------
    def test_act_refuses_a_still_pending_prompt_after_two_ignored_deletes_without_a_third_delete(self):
        studio = self.studio(); job = self.job(studio)
        job.update(status="running", prompt_ids=["ours"]); studio._save(job)
        studio.cancel_job(job["id"])
        submission = {"prompt_id": "ours"}; pending = queue(pending=["ours"])
        studio.script = [("GET", "/queue", pending), ("POST", "/queue", None), ("GET", "/queue", pending)]
        self.assertFalse(job_cancel.act(studio, job, submission))
        self.assertEqual(job["cancellation"]["state"], "requested", "one ignored delete stays open")
        studio.script = [("GET", "/queue", pending), ("POST", "/queue", None), ("GET", "/queue", pending)]
        self.assertFalse(job_cancel.act(studio, job, submission))
        self.assertEqual([a["action"] for a in job["cancellation"]["actions"]], ["dequeue", "dequeue"])
        self.assertEqual(len(studio.posts("/queue")), 2)
        studio.script = [("GET", "/queue", pending)]
        self.assertFalse(job_cancel.act(studio, job, submission))
        record = job["cancellation"]
        self.assertEqual(record["state"], "refused")
        self.assertEqual(record["note"], "ComfyUI kept this prompt queued after two delete requests; nothing more was sent.")
        self.assertEqual(len(studio.posts("/queue")), 2, "no third DELETE is sent")
        self.assertEqual(studio.script, [], "every scripted ComfyUI answer is consumed")
        self.assertEqual(studio.posts("/interrupt"), [])

    def test_queue_reports_unreadable_for_malformed_entries_but_reads_empty_queues(self):
        studio = self.studio()
        for reply, expected, label in (({"queue_running": [{"not": "a", "list": "entry"}], "queue_pending": []}, ("unreadable", []), "non-list entry of length 2"),
                                      ({"queue_running": [[0]], "queue_pending": []}, ("unreadable", []), "entry shorter than 2"),
                                      ({"queue_running": [], "queue_pending": []}, ("absent", []), "empty queues are absent, not unreadable"),
                                      (queue(pending=["ours"]), ("pending", []), "length-2 entries still parse")):
            with self.subTest(label=label):
                studio.script = [("GET", "/queue", reply)]
                self.assertEqual(job_cancel._queue(studio, None, "ours"), expected)
                self.assertEqual(studio.script, [], "the one scripted answer is consumed")

    def test_history_reports_unreadable_for_a_non_dict_entry_or_response(self):
        studio = self.studio()
        for reply, expected, label in ((["not", "a", "dict"], "unreadable", "non-dict response"),
                                      ({"ours": ["not", "a", "dict"]}, "unreadable", "non-dict entry"),
                                      ({}, "absent", "missing entry stays absent, not unreadable"),
                                      ({"ours": {"status": {}}}, "present", "dict entry is present")):
            with self.subTest(label=label):
                studio.script = [("GET", "/history/ours", reply)]
                self.assertEqual(job_cancel._history(studio, None, "ours"), expected)
                self.assertEqual(studio.script, [], "the one scripted answer is consumed")

    def test_resolve_keeps_a_newer_request_whose_event_id_differs(self):
        studio = self.studio()
        job = {"id": "j", "cancellation": {"event_id": "old", "state": "requested"}}
        studio.cancel_requests["j"] = {"event_id": "new", "state": "requested"}
        job_cancel._resolve(studio, job, "cancelled", "done")
        self.assertEqual(job["cancellation"]["state"], "cancelled")
        self.assertEqual(studio.cancel_requests["j"]["event_id"], "new", "a newer request is kept")
        studio.cancel_requests["j"] = {"event_id": "old", "state": "requested"}
        job_cancel._resolve(studio, job, "cancelled", "done")
        self.assertNotIn("j", studio.cancel_requests, "the request this record resolves is removed")

    def test_blocked_refuses_jobs_with_an_operation_key(self):
        studio = self.studio(); job = self.job(studio)
        trial = dict(job, status="running", prompt_ids=["ours"], operation="upscale")
        self.assertEqual(job_cancel.blocked(studio, trial), "This kind of job cannot be cancelled here")
        self.assertIsNone(job_cancel.blocked(studio, dict(job, status="running", prompt_ids=["ours"])),
                          "the same job without an operation key stays cancellable")

    def test_record_interrupted_without_a_prior_interrupt_action_records_no_reply(self):
        for actions, expected, label in (([], None, "no prior interrupt action"),
                                        ([{"action": "interrupt", "prompt_id": "ours", "at": 1.0, "reply": "ok"}], "ok", "prior reply is carried")):
            with self.subTest(label=label):
                studio = self.studio(); job = self.job(studio)
                job.update(status="running", prompt_ids=["ours"],
                           submissions=[{"index": 0, "prompt_id": "ours", "seed": 1, "status": "observing"}],
                           cancellation={"event_id": "e1", "requested_at": 1.0, "requested_by": "owner", "status_at_request": "running",
                                         "state": "requested", "actions": list(actions), "observations": []})
                studio._save(job)
                submission = job["submissions"][0]
                job_cancel.record_interrupted(studio, job, submission)
                self.assertEqual(submission["status"], "cancelled")
                self.assertEqual(set(submission["cancelled"]), {"basis", "at", "interrupt_reply"})
                self.assertEqual(submission["cancelled"]["basis"], "interrupted")
                self.assertEqual(submission["cancelled"]["interrupt_reply"], expected)
                self.assertEqual(job["status"], "cancelled"); self.assertIn("interrupted", job["message"])
                self.assertEqual(job["cancellation"]["state"], "cancelled")

    def test_reconcile_restart_ignores_a_missing_corrupt_or_non_dict_request_without_writing(self):
        for index, (body, label) in enumerate(((None, "missing file"), ("not json{{", "corrupt file"),
                                              ('["not", "a", "dict"]', "non-dict JSON"), ('{"event_id": 7}', "non-string event id"))):
            with self.subTest(label=label):
                directory = self.root / ("probe-%d" % index); directory.mkdir()
                if body is not None: (directory / job_cancel.REQUEST_FILE).write_text(body, encoding="utf-8")
                job = {"id": directory.name, "status": "running", "prompt_ids": ["ours"]}
                before = copy.deepcopy(job)
                self.assertFalse(job_cancel.reconcile_restart(job, directory))
                self.assertEqual(job, before, "an ignored request writes nothing to the job")
                self.assertFalse((directory / "state.json").exists(), "an ignored request writes no state file")
        directory = self.root / "probe-open"; directory.mkdir()
        (directory / job_cancel.REQUEST_FILE).write_text(
            json.dumps({"event_id": "e1", "requested_at": 1.0, "requested_by": "owner",
                        "status_at_request": "running", "state": "requested"}), encoding="utf-8")
        job = {"id": directory.name, "status": "running", "prompt_ids": ["ours"]}
        self.assertTrue(job_cancel.reconcile_restart(job, directory), "a well-formed request is still adopted")
        self.assertEqual(job["cancellation"]["state"], "unresolved"); self.assertIn("restarted", job["cancellation"]["note"])


if __name__ == "__main__":
    unittest.main()
