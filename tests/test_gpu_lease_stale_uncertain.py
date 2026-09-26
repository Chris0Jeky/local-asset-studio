"""Issue #979 (owner decision 2026-09-25): a stale 'uncertain' job no longer blocks a GPU lease grant forever.

The real BackendManager work checks run over fake jobs; every seam that could observe or stop a real process, or reach a
ComfyUI endpoint, is replaced. No job record is changed by a grant or a refusal.
"""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_gpu_lease as fixtures
from backends import BackendManager
from gpu_lease import STALE_UNCERTAIN_SECONDS, GpuLease, GpuLeaseError, last_activity
from test_backend_safety import FixtureStudio

NOW = 2_000_000_000.0
OLD = NOW - STALE_UNCERTAIN_SECONDS - 3600
RECENT = NOW - 3600


def job(identifier, status="uncertain", created_at=OLD, **fields):
    return {"id": identifier, "status": status, "created_at": created_at, "prompt_ids": ["prompt-" + identifier], **fields}


class StaleUncertainLeaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        scan = patch("psutil.process_iter", return_value=[]); scan.start(); self.addCleanup(scan.stop)
        self.studio = FixtureStudio(Path(temporary.name))
        self.manager = BackendManager(self.studio); self.studio.backends = self.manager
        self.process = fixtures.FakeProcess(); self.history = {}; self.history_calls = []
        # Real _local_work and _stopped_results; inert startup, queue, process and history seams.
        self.manager._check_retained_startup = lambda: None; self.manager._check_startup_processes = lambda: {}
        self.manager._idle = lambda profile, allow_offline=False: True
        self.manager.process = lambda profile: self.process if profile["id"] == "primary" and not self.process.terminated else None
        def request(profile, route, timeout=2):
            self.history_calls.append((profile["id"], route))
            prompt = route.rsplit("/", 1)[-1]
            return {prompt: self.history[prompt]} if prompt in self.history else {}
        self.manager.request = request
        self.lease = GpuLease(self.studio, clock=lambda: NOW)
        self.payload = {"holder": "local-qwen", "ttl_seconds": 600}

    def jobs(self, *records):
        self.studio.jobs = {record["id"]: record for record in records}
        return copy.deepcopy(self.studio.jobs)

    def refused(self, code="studio_work_active"):
        with self.assertRaises(GpuLeaseError) as caught: self.lease.acquire(self.payload)
        self.assertEqual((caught.exception.status, caught.exception.code), (409, code))
        self.assertEqual(self.process.terminated, 0); self.assertFalse(self.lease.snapshot()["held"])
        return caught.exception

    def test_old_uncertain_job_is_ignored_and_reported_in_the_grant_and_log(self):
        before = self.jobs(job("aaaa1111"))
        result = self.lease.acquire(self.payload)
        self.assertTrue(result["granted"]); self.assertEqual(result["ignored_stale_uncertain"], ["aaaa1111"])
        self.assertEqual(self.process.terminated, 1)
        self.assertEqual(self.studio.jobs, before, "a grant never changes, resolves or abandons a job record")
        logged = [json.loads(line) for line in (self.studio.root / ".runtime/studio-gpu-lease.log").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(logged[-1]["ignored_stale_uncertain"], ["aaaa1111"])
        self.assertEqual(result["limits"]["stale_uncertain_seconds"], 24 * 3600)
        # The history probe still ran for the exempted prompt on the listener that was about to stop.
        self.assertIn(("primary", "/history/prompt-aaaa1111"), self.history_calls)

    def test_recent_uncertain_job_still_blocks(self):
        before = self.jobs(job("bbbb2222", created_at=RECENT))
        error = self.refused()
        self.assertEqual(error.details["ignored_stale_uncertain"], [])
        self.assertEqual(self.studio.jobs, before)

    def test_old_active_statuses_always_block(self):
        for status in ("queued", "waiting", "submitting", "running"):
            with self.subTest(status=status):
                self.jobs(job("cccc3333", status=status, created_at=NOW - 30 * 86400))
                self.assertEqual(self.refused().details["ignored_stale_uncertain"], [])

    def test_mixed_jobs_block_on_any_recent_uncertain_and_report_only_stale_uncertain_ids(self):
        settled = [job("done0000", status=status) for status in ("completed", "failed", "abandoned", "partial")]
        stopped = job("stop0000", tracking_disposition={"status": "stopped", "reason": "gone", "recorded_at": OLD})
        self.jobs(job("zzzz0002"), job("aaaa0001"), job("mmmm0003", created_at=RECENT), stopped, *settled)
        self.assertEqual(self.refused().details["ignored_stale_uncertain"], ["aaaa0001", "zzzz0002"])
        self.jobs(job("zzzz0002"), job("aaaa0001"), stopped, *settled)
        self.assertEqual(self.lease.acquire(self.payload)["ignored_stale_uncertain"], ["aaaa0001", "zzzz0002"])

    def test_old_uncertain_does_not_hide_other_active_work(self):
        self.jobs(job("aaaa0001"), job("qqqq0002", status="running"))
        self.assertEqual(self.refused().details["ignored_stale_uncertain"], ["aaaa0001"])
        self.jobs(job("aaaa0001")); self.studio.production.list = lambda: [{"state": {"status": "observing"}}]
        self.refused()

    def test_boundary_is_exactly_the_threshold(self):
        self.jobs(job("edge0001", created_at=NOW - STALE_UNCERTAIN_SECONDS + 1))
        self.refused()
        self.jobs(job("edge0001", created_at=NOW - STALE_UNCERTAIN_SECONDS))
        self.assertEqual(self.lease.acquire(self.payload)["ignored_stale_uncertain"], ["edge0001"])

    def test_age_counts_from_the_latest_recorded_activity_and_unknown_time_blocks(self):
        recent_activity = {
            "started_at": {"started_at": RECENT}, "finished_at": {"finished_at": RECENT},
            "pending_submission": {"pending_submission": {"index": 0, "marked_at": RECENT}},
            "tracking_resumed": {"tracking_disposition": {"status": "resumed", "recorded_at": OLD,
                                                          "history": [{"status": "stopped", "recorded_at": OLD}, {"status": "resumed", "recorded_at": RECENT}]}},
        }
        for name, fields in recent_activity.items():
            with self.subTest(activity=name):
                self.jobs(job("late0001", **fields)); self.refused()
        for created in (None, "2026-09-13", True, math.nan, math.inf, NOW + 60):
            with self.subTest(created_at=created):
                self.jobs(job("time0001", created_at=created)); self.refused()
        # The owner's put-away acknowledgement is not activity.
        self.jobs(job("seen0001", put_away_at=RECENT))
        self.assertEqual(self.lease.acquire(self.payload)["ignored_stale_uncertain"], ["seen0001"])

    def test_stale_uncertain_result_still_in_comfy_history_blocks_the_stop(self):
        self.jobs(job("hist0001")); self.history["prompt-hist0001"] = {"status": {"status_str": "success"}, "outputs": {}}
        error = self.refused("backend_not_idle")
        self.assertIn("resume its observation", str(error))

    def test_renewal_reports_an_empty_list_and_rechecks_nothing(self):
        self.jobs(job("aaaa0001"))
        self.lease.acquire(self.payload)
        self.jobs(job("aaaa0001"), job("bbbb0002", created_at=RECENT))
        renewed = self.lease.acquire(self.payload)
        self.assertTrue(renewed["renewed"]); self.assertEqual(renewed["ignored_stale_uncertain"], [])

    def test_backend_switch_and_other_callers_keep_blocking_on_old_uncertain_jobs(self):
        self.jobs(job("aaaa0001"))
        self.assertTrue(self.manager._local_work(), "the default (switch) check is unchanged")
        self.manager.available = lambda profile: True
        with self.assertRaisesRegex(ValueError, "reconcile"): self.manager.switch("hidream")
        # An exempted id that is no longer 'uncertain' when the manager reads it blocks again.
        self.jobs(job("aaaa0001", status="queued"))
        self.assertTrue(self.manager._local_work(ignore_job_ids=("aaaa0001",)))

    def test_last_activity_reads_only_finite_numbers(self):
        self.assertIsNone(last_activity({}))
        self.assertIsNone(last_activity({"created_at": True, "started_at": "x", "finished_at": math.nan}))
        self.assertEqual(last_activity({"created_at": 1, "finished_at": 5.5, "put_away_at": 99}), 5.5)
        self.assertIsNone(last_activity({"created_at": 10 ** 400}), "an int beyond float range is not a time")


if __name__ == "__main__":
    unittest.main()
