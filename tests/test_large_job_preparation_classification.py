"""#306 live proof (25 Sep 2026): classify Studio work by what each action can harm.

In-flight work refuses everything. Unresolved work at rest refuses only the backend
restart, and only while the selected backend may still hold the /history of one of its
open prompt IDs (a restart discards it; Resume observation needs it, #864). Records at
rest never block.
"""
from __future__ import annotations

import unittest

from large_job_prep_test_support import GIB, LargeJobPreparationTestCase, Studio, observation
from large_job_prep_common import WorkBlockedError


def observing_job(status="uncertain", prompt="p-1"):
    return {"status": status, "prompt_ids": [prompt],
            "message": "Restarted while remote job state was unknown; use Resume observation for known prompt IDs.",
            "submissions": [{"index": 0, "prompt_id": prompt, "status": "observing"}]}


def plan(identifier, status, **extra):
    return {"id": identifier, "state": dict({"status": status}, **extra)}


AT_REST_PLANS = ["planned", "awaiting_review", "reviewed", "published", "stopped",
                 "completed", "failed", "abandoned", "not_submitted", "cancelled"]


class LargeJobPreparationClassificationTests(LargeJobPreparationTestCase):
    def live_library(self, studio, *, history_present=True):
        # The shape that refused everything on the owner's PC.
        for index in range(5):
            studio.jobs[f"uncertain-{index}"] = observing_job(prompt=f"p-{index}")
            if history_present:
                studio.backends.history.add(f"p-{index}")
        studio.jobs["done"] = {"status": "completed", "submissions": [{"status": "completed"}]}
        studio.production.items = [
            plan("p-planned", "planned"), plan("p-review", "awaiting_review"),
            # No attempt ever reached ComfyUI, so there is no history to lose.
            plan("p-interrupted", "interrupted", attempts={}),
            plan("p-uncertain", "uncertain", attempts={"0": {"job_id": "uncertain-0"}}),
        ]

    def restartable(self, studio):
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        def wait(timeout):
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        return original

    def test_dry_run_observes_and_lists_blockers_when_only_work_at_rest_exists(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        self.live_library(studio)
        result = self.controller(studio).run(self.request(dry_run=True, allow_restart=True))
        self.assertEqual(result["phase"], "dry_run")
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["before"]["evaluation"]["decision"], "observed_unsafe")
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache"])
        self.assertTrue(result["restart_blocked_by_unresolved_work"])
        blockers = result["blockers"]
        self.assertEqual((blockers["count"], blockers["blocks_all"], blockers["blocks_restart"]), (6, 0, 6))
        self.assertTrue(blockers["history_checked"])
        listed = {(item["kind"], item["id"]): item for item in blockers["items"]}
        self.assertEqual(listed[("studio_job", "uncertain-0")],
                         {"kind": "studio_job", "id": "uncertain-0", "status": "uncertain", "blocks": "restart"})
        self.assertEqual(listed[("production", "p-uncertain")]["blocks"], "restart")
        for absent in (("production", "p-interrupted"), ("production", "p-planned"),
                       ("production", "p-review"), ("studio_job", "done")):
            self.assertNotIn(absent, listed)
        checks = {(item["kind"], item["id"]): item for item in blockers["history_checks"]}
        self.assertEqual(checks[("studio_job", "uncertain-3")],
                         {"kind": "studio_job", "id": "uncertain-3", "prompt_ids": 1, "result": "history_present"})
        # The plan shares its job's prompt; each prompt ID is fetched once.
        self.assertEqual(sorted(studio.backends.history_requests), [f"p-{index}" for index in range(5)])
        self.assertEqual(studio.free_calls, [])
        self.assertFalse(studio.backends.current.terminated)

    def test_dry_run_without_restart_keeps_the_release_plan_and_skips_history(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        self.live_library(studio)
        result = self.controller(studio).run(self.request(dry_run=True))
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache"])
        self.assertFalse(result["restart_blocked_by_unresolved_work"])
        self.assertFalse(result["blockers"]["history_checked"])
        self.assertEqual(studio.backends.history_requests, [])

    def test_at_rest_records_never_block(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.production.items = [plan("p-" + status, status) for status in AT_REST_PLANS]
        for status in ("completed", "failed", "not_submitted", "cancelled"):
            studio.jobs[status] = {"status": status, "submissions": [{"status": "completed"}]}
        # Abandonment is a terminal local disposition even when it keeps the pending marker.
        studio.jobs["abandoned"] = {"status": "abandoned", "pending_submission": {"index": 0}, "submissions": []}
        # Unresolved records that never retained a prompt ID have no history to lose.
        studio.jobs["uncertain-unsent"] = {"status": "uncertain", "prompt_ids": [], "submissions": []}
        studio.production.items.append(plan("voice", "interrupted", attempts={"0": {"status": "interrupted"}}))
        result = self.controller(studio).run(self.request(dry_run=True, allow_restart=True))
        self.assertEqual(result["phase"], "dry_run")
        self.assertEqual(result["blockers"], {"count": 0, "blocks_all": 0, "blocks_restart": 0, "items": [],
                                              "history_checked": True, "history_checks": []})
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache", "restart_verified_owned_backend"])
        self.assertEqual(studio.backends.history_requests, [])

    def test_unrecognized_job_status_blocks_everything(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.jobs["odd"] = {"status": "mystery", "submissions": []}
        studio.jobs["missing"] = {"submissions": []}
        result = self.controller(studio).run(self.request(dry_run=True))
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(result["blockers"]["blocks_all"], 2)
        self.assertEqual({item["status"] for item in result["blockers"]["items"]}, {"mystery", "unknown"})
        self.assertEqual(studio.prepare_calls, 0)

    def test_release_runs_with_uncertain_observing_jobs_present(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=40 * GIB)])
        self.live_library(studio)
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "ready_after_release")
        self.assertTrue(result["final"]["ready"])
        self.assertEqual(len(studio.free_calls), 1)
        self.assertEqual(result["blockers"]["blocks_restart"], 6)
        self.assertEqual(studio.backends.history_requests, [])

    def test_restart_proceeds_when_the_selected_backend_no_longer_holds_the_history(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB),
                                    observation(commit=40 * GIB)])
        self.live_library(studio, history_present=False)
        original = self.restartable(studio)
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "ready_after_restart")
        self.assertTrue(original.terminated)
        self.assertEqual(studio.backends.launches, 1)
        self.assertEqual(result["blockers"]["blocks_restart"], 0)
        self.assertEqual({item["result"] for item in result["blockers"]["history_checks"]}, {"history_absent"})
        self.assertEqual(len(result["blockers"]["history_checks"]), 6)

    def test_restart_is_refused_while_the_history_may_still_be_needed(self):
        cases = {
            "uncertain job, history present": lambda s: (s.jobs.__setitem__("u", observing_job()),
                                                         s.backends.history.add("p-1")),
            "partial job, history present": lambda s: (s.jobs.__setitem__("u", observing_job("partial")),
                                                       s.backends.history.add("p-1")),
            "interrupted plan, history present": lambda s: (
                setattr(s.production, "items", [plan("u", "interrupted", attempts={"0": {"prompt_ids": ["p-1"]}})]),
                s.backends.history.add("p-1")),
            "history request error": lambda s: (s.jobs.__setitem__("u", observing_job()),
                                                setattr(s.backends, "history_error", TimeoutError("slow"))),
            "unparseable history": lambda s: (s.jobs.__setitem__("u", observing_job()),
                                              setattr(s.backends, "history_value", ["not", "a", "mapping"])),
            "unreadable prompt IDs": lambda s: s.jobs.__setitem__("u", dict(observing_job(), prompt_ids="p-1")),
        }
        for label, setup in cases.items():
            with self.subTest(label):
                studio = Studio(self.root / label.replace(" ", "-").replace(",", ""),
                                [observation(commit=20 * GIB), observation(commit=20 * GIB)])
                studio.config["enable_large_job_backend_restart"] = True
                setup(studio)
                result = self.controller(studio).run(self.request(allow_restart=True))
                self.assertEqual(result["phase"], "restart_blocked_by_unresolved_work")
                # /free was attempted, so the top-level state never reads as a no-op (M2).
                self.assertEqual(result["state"], "unknown")
                self.assertEqual(result["final"]["decision"], "observed_unsafe")
                self.assertIn("Resume observation", result["final"]["reason"])
                self.assertEqual(len(studio.free_calls), 1)
                self.assertEqual([action["kind"] for action in result["actions"]], ["release"])
                self.assertFalse(studio.backends.current.terminated)
                self.assertEqual(studio.backends.launches, 0)
                self.assertFalse(studio.backends.busy)
                self.assertEqual(result["blockers"]["items"][0]["id"], "u")
                self.assertEqual(result["blockers"]["items"][0]["blocks"], "restart")
                expected = "history_present" if "present" in label else "unknown"
                self.assertEqual(result["blockers"]["history_checks"][0]["result"], expected)

    def test_history_checks_are_bounded_and_fail_closed_beyond_the_bound(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        for index in range(25):
            studio.jobs[f"u-{index:02d}"] = observing_job(prompt=f"p-{index:02d}")
        result = self.controller(studio).run(self.request(dry_run=True, allow_restart=True))
        self.assertTrue(result["restart_blocked_by_unresolved_work"])
        self.assertEqual(len(studio.backends.history_requests), 20)
        self.assertEqual(result["blockers"]["blocks_restart"], 5)
        self.assertEqual(len(result["blockers"]["history_checks"]), 20)
        second = Studio(self.root / "prompts", [observation(commit=20 * GIB)])
        for index in range(3):
            second.jobs[f"big-{index}"] = {"status": "uncertain", "submissions": [],
                                           "prompt_ids": [f"b{index}-{n:02d}" for n in range(30)]}
        result = self.controller(second).run(self.request(request_id="prepare-2", dry_run=True, allow_restart=True))
        self.assertEqual(len(second.backends.history_requests), 30)
        self.assertEqual([item["result"] for item in result["blockers"]["history_checks"]],
                         ["history_absent", "unknown", "unknown"])
        self.assertEqual(result["blockers"]["blocks_restart"], 2)

    def test_a_terminal_job_with_a_stale_observing_receipt_blocks_only_the_restart(self):
        # Live proof, 25 Sep 2026: three jobs from 11 Sep failed with a ComfyUI execution error but kept an
        # observing receipt. The queue check covers a prompt that is really still running; history covers the rest.
        for status in ("failed", "completed"):
            with self.subTest(status):
                studio = Studio(self.root / ("stale-" + status), [observation(commit=20 * GIB), observation(commit=40 * GIB)])
                studio.jobs["stale"] = observing_job(status=status, prompt="p-stale")
                result = self.controller(studio).run(self.request())
                self.assertEqual(result["phase"], "ready_after_release")
                self.assertEqual(len(studio.free_calls), 1)
                self.assertEqual(result["blockers"]["blocks_all"], 0)
                self.assertEqual(result["blockers"]["blocks_restart"], 1)
        studio = Studio(self.root / "stale-restart", [observation(commit=20 * GIB), observation(commit=20 * GIB),
                                                      observation(commit=40 * GIB)])
        studio.jobs["stale"] = observing_job(status="failed", prompt="p-stale")
        studio.backends.history.add("p-stale")
        self.restartable(studio)
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(studio.backends.launches, 0, "History still held: the restart is refused")
        self.assertEqual(result["phase"], "restart_blocked_by_unresolved_work")
        # History gone: the restart proceeds.
        studio = Studio(self.root / "stale-gone", [observation(commit=20 * GIB), observation(commit=20 * GIB),
                                                   observation(commit=40 * GIB)])
        studio.jobs["stale"] = observing_job(status="abandoned", prompt="p-stale")
        original = self.restartable(studio)
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "ready_after_restart")
        self.assertTrue(original.terminated)
        # A prompt really still in the selected backend's queue refuses /free whatever the job record says.
        for status in ("failed", "completed", "abandoned", "not_submitted", "cancelled"):
            with self.subTest(queue=status):
                studio = Studio(self.root / ("stale-busy-" + status), [observation(commit=20 * GIB), observation(commit=40 * GIB)])
                studio.jobs["stale"] = observing_job(status=status, prompt="p-stale")
                studio.backends.queue["queue_running"] = [[0, "p-stale", {}, {}, []]]
                result = self.controller(studio).run(self.request())
                self.assertEqual(studio.free_calls, [])
                self.assertFalse(result["final"]["ready"])

    def test_in_flight_work_refuses_everything_including_dry_run(self):
        cases = {
            "running job": lambda s: s.jobs.__setitem__("x", {"status": "running", "submissions": []}),
            "queued resume": lambda s: s.jobs.__setitem__("x", dict(observing_job(), status="queued")),
            "pending submission": lambda s: s.jobs.__setitem__(
                "x", dict(observing_job(), pending_submission={"index": 1})),
            "submitting receipt": lambda s: s.jobs.__setitem__(
                "x", {"status": "uncertain", "submissions": [{"status": "submitting"}]}),
            "submitting receipt on a failed job": lambda s: s.jobs.__setitem__(
                "x", {"status": "failed", "submissions": [{"status": "submitting"}]}),
            "malformed receipt": lambda s: s.jobs.__setitem__("x", {"status": "uncertain", "submissions": ["bad"]}),
            "running plan": lambda s: setattr(s.production, "items", [plan("x", "running")]),
            "observing plan": lambda s: setattr(s.production, "items", [plan("x", "observing")]),
            "plan pending submission": lambda s: setattr(
                s.production, "items", [plan("x", "planned", pending_submission={"index": 0})]),
            "unrecognized plan status": lambda s: setattr(s.production, "items", [plan("x", "mystery")]),
            "busy reference job": lambda s: setattr(s.reference_jobs, "active", True),
        }
        for label, setup in cases.items():
            for dry_run in (True, False):
                with self.subTest(label, dry_run=dry_run):
                    studio = Studio(self.root / (label.replace(" ", "-") + str(dry_run)),
                                    [observation(commit=20 * GIB), observation(commit=40 * GIB)])
                    self.live_library(studio)
                    setup(studio)
                    result = self.controller(studio).run(self.request(dry_run=dry_run))
                    self.assertEqual(result["phase"], "refused")
                    self.assertEqual(result["state"], "refused")
                    self.assertIn("In-flight", result["final"]["reason"])
                    self.assertEqual(studio.prepare_calls, 0)
                    self.assertEqual(studio.free_calls, [])
                    self.assertEqual(result["actions"], [])
                    self.assertNotIn("before", result)
                    first = result["blockers"]["items"][0]
                    self.assertEqual((first["id"], first["blocks"]), ("x" if "reference" not in label else "active", "all"))
                    self.assertEqual(result["blockers"]["blocks_all"], 1)

    def test_live_library_with_a_busy_queue_refuses_without_free(self):
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run):
                studio = Studio(self.root / str(dry_run), [observation(commit=20 * GIB)])
                self.live_library(studio)
                studio.backends.queue["queue_running"] = [[0, "external-prompt"]]
                result = self.controller(studio).run(self.request(dry_run=dry_run, allow_restart=True))
                self.assertEqual(result["phase"], "refused")
                self.assertIn("queue", result["final"]["reason"])
                self.assertEqual(studio.free_calls, [])
                self.assertEqual(studio.backends.launches, 0)

    def test_recheck_catches_work_that_starts_between_observation_and_free(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        self.live_library(studio)
        controller = self.controller(studio)
        original = type(controller)._recheck
        def recheck(expected_identity, expected_profile_id):
            studio.jobs["late"] = {"status": "running", "submissions": []}
            return original(controller, expected_identity, expected_profile_id)
        controller._recheck = recheck
        result = controller.run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("New Studio work arrived", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])
        self.assertEqual(result["actions"], [])
        self.assertEqual(result["blockers"]["items"][0], {"kind": "studio_job", "id": "late", "status": "running", "blocks": "all"})

    def test_uncertain_work_arriving_after_free_blocks_the_restart(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        studio.backends.history.add("p-1")
        original = studio._request
        def free(route, **kwargs):
            value = original(route, **kwargs)
            studio.jobs["late"] = observing_job()
            return value
        studio._request = free
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "restart_blocked_by_unresolved_work")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(len(studio.free_calls), 1)
        self.assertFalse(studio.backends.current.terminated)
        self.assertEqual(studio.backends.launches, 0)

    def test_new_unresolved_work_under_the_switch_lock_blocks_without_network(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        self.live_library(studio, history_present=False)
        self.restartable(studio)
        controller = self.controller(studio)
        original = type(controller)._claim_backend
        requests = {}
        def claim(expected_identity, expected_profile_id, verified_absent=frozenset()):
            # The pre-check proved the history absent; this job lands before the lock is taken.
            studio.jobs["late"] = observing_job(prompt="p-late")
            requests["before"] = list(studio.backends.history_requests)
            return original(controller, expected_identity, expected_profile_id, verified_absent)
        controller._claim_backend = claim
        result = controller.run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "restart_blocked_by_unresolved_work")
        self.assertEqual(studio.backends.history_requests, requests["before"])
        self.assertFalse(studio.backends.current.terminated)
        self.assertEqual(studio.backends.launches, 0)
        self.assertFalse(studio.backends.busy)

    def test_claiming_the_switch_gate_rechecks_unresolved_work_and_leaves_the_gate_free(self):
        studio = Studio(self.root, [])
        studio.jobs["u"] = observing_job()
        controller = self.controller(studio)
        identity = {"pid": studio.backends.current.pid, "created_at": studio.backends.current.created}
        with self.assertRaises(WorkBlockedError) as caught:
            controller._claim_backend(identity, "primary")
        self.assertEqual(caught.exception.phase, "restart_blocked_by_unresolved_work")
        self.assertFalse(studio.backends.busy)
        self.assertEqual(studio.backends.history_requests, [])
        controller._claim_backend(identity, "primary", frozenset({("studio_job", "u", ("p-1",))}))
        self.assertTrue(studio.backends.busy)
        controller._release_backend()

    def test_work_after_the_restart_refuses_readiness_without_the_restart_phase(self):
        for label, late, phase in (
            ("in-flight", {"status": "running", "submissions": []}, "refused"),
            # The history is already gone once the restart happened; nothing is left to protect.
            ("unresolved", observing_job(prompt="p-late"), "ready_after_restart"),
        ):
            with self.subTest(label):
                studio = Studio(self.root / label, [observation(commit=20 * GIB), observation(commit=20 * GIB),
                                                    observation(commit=40 * GIB)])
                studio.backends.history.add("p-late")
                original = self.restartable(studio)
                launch = studio.backends.launch_recovery
                def launched(profile, studio=studio, launch=launch, late=late):
                    pid = launch(profile)
                    studio.jobs["late"] = late
                    return pid
                studio.backends.launch_recovery = launched
                result = self.controller(studio).run(self.request(allow_restart=True))
                self.assertTrue(original.terminated)
                self.assertEqual(result["phase"], phase)
                if phase == "refused":
                    self.assertEqual(result["state"], "unknown")
                    self.assertIn("after restart", result["final"]["reason"])

    def test_blocker_list_is_bounded_and_keeps_in_flight_work_first(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        for index in range(30):
            studio.jobs[f"u-{index:02d}"] = observing_job(prompt=f"p-{index:02d}")
        studio.jobs["zz-running"] = {"status": "running", "submissions": []}
        result = self.controller(studio).run(self.request(dry_run=True))
        blockers = result["blockers"]
        self.assertEqual((blockers["count"], blockers["blocks_all"], blockers["blocks_restart"]), (31, 1, 30))
        self.assertEqual(len(blockers["items"]), 20)
        self.assertEqual(blockers["items"][0]["id"], "zz-running")


if __name__ == "__main__":
    unittest.main()
