"""#306 live proof (25 Sep 2026): classify Studio work by what each action can harm.

In-flight work refuses everything; unresolved work at rest refuses only the backend
restart (it discards ComfyUI history that Resume observation needs, #864); at-rest
records never block.
"""
from __future__ import annotations

import unittest

from large_job_prep_test_support import GIB, LargeJobPreparationTestCase, Studio, observation
from large_job_prep_common import WorkBlockedError


def observing_job(status="uncertain"):
    return {"status": status, "prompt_ids": ["p-1"],
            "message": "Restarted while remote job state was unknown; use Resume observation for known prompt IDs.",
            "submissions": [{"index": 0, "prompt_id": "p-1", "status": "observing"}]}


def plan(identifier, status, **extra):
    return {"id": identifier, "state": dict({"status": status}, **extra)}


AT_REST_PLANS = ["planned", "awaiting_review", "reviewed", "published", "stopped",
                 "completed", "failed", "abandoned", "not_submitted"]


class LargeJobPreparationClassificationTests(LargeJobPreparationTestCase):
    def live_library(self, studio):
        # The shape that refused everything on the owner's PC.
        for index in range(5):
            studio.jobs[f"uncertain-{index}"] = observing_job()
        studio.jobs["done"] = {"status": "completed", "submissions": [{"status": "completed"}]}
        studio.production.items = [plan("p-planned", "planned"), plan("p-review", "awaiting_review"),
                                    plan("p-interrupted", "interrupted"), plan("p-uncertain", "uncertain")]

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
        self.assertEqual((blockers["count"], blockers["blocks_all"], blockers["blocks_restart"]), (7, 0, 7))
        listed = {(item["kind"], item["id"]): item for item in blockers["items"]}
        self.assertEqual(listed[("studio_job", "uncertain-0")],
                         {"kind": "studio_job", "id": "uncertain-0", "status": "uncertain", "blocks": "restart"})
        self.assertEqual(listed[("production", "p-interrupted")]["blocks"], "restart")
        self.assertEqual(listed[("production", "p-uncertain")]["blocks"], "restart")
        self.assertNotIn(("production", "p-planned"), listed)
        self.assertNotIn(("production", "p-review"), listed)
        self.assertNotIn(("studio_job", "done"), listed)
        self.assertEqual(studio.free_calls, [])
        self.assertFalse(studio.backends.current.terminated)

    def test_dry_run_without_restart_keeps_the_release_plan(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        self.live_library(studio)
        result = self.controller(studio).run(self.request(dry_run=True))
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache"])
        self.assertFalse(result["restart_blocked_by_unresolved_work"])

    def test_at_rest_records_never_block(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.production.items = [plan("p-" + status, status) for status in AT_REST_PLANS]
        for status in ("completed", "failed", "not_submitted"):
            studio.jobs[status] = {"status": status, "submissions": [{"status": "completed"}]}
        # Abandonment is a terminal local disposition even when it keeps the pending marker.
        studio.jobs["abandoned"] = {"status": "abandoned", "pending_submission": {"index": 0}, "submissions": []}
        result = self.controller(studio).run(self.request(dry_run=True, allow_restart=True))
        self.assertEqual(result["phase"], "dry_run")
        self.assertEqual(result["blockers"], {"count": 0, "blocks_all": 0, "blocks_restart": 0, "items": []})
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache", "restart_verified_owned_backend"])

    def test_release_runs_with_uncertain_observing_jobs_present(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=40 * GIB)])
        self.live_library(studio)
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "ready_after_release")
        self.assertTrue(result["final"]["ready"])
        self.assertEqual(len(studio.free_calls), 1)
        self.assertEqual(result["blockers"]["blocks_restart"], 7)

    def test_restart_is_refused_while_an_uncertain_job_is_present(self):
        for label, setup in (
            ("uncertain job", lambda studio: studio.jobs.__setitem__("u", observing_job())),
            ("partial job", lambda studio: studio.jobs.__setitem__("u", observing_job("partial"))),
            ("interrupted plan", lambda studio: setattr(studio.production, "items", [plan("u", "interrupted")])),
        ):
            with self.subTest(label):
                studio = Studio(self.root / label.replace(" ", "-"),
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

    def test_in_flight_work_refuses_everything_including_dry_run(self):
        cases = {
            "running job": lambda s: s.jobs.__setitem__("x", {"status": "running", "submissions": []}),
            "queued resume": lambda s: s.jobs.__setitem__("x", dict(observing_job(), status="queued")),
            "pending submission": lambda s: s.jobs.__setitem__(
                "x", dict(observing_job(), pending_submission={"index": 1})),
            "submitting receipt": lambda s: s.jobs.__setitem__(
                "x", {"status": "uncertain", "submissions": [{"status": "submitting"}]}),
            "observing receipt on a failed job": lambda s: s.jobs.__setitem__(
                "x", {"status": "failed", "submissions": [{"status": "observing"}]}),
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

    def test_claiming_the_switch_gate_rechecks_unresolved_work_and_leaves_the_gate_free(self):
        studio = Studio(self.root, [])
        studio.jobs["u"] = observing_job()
        controller = self.controller(studio)
        identity = {"pid": studio.backends.current.pid, "created_at": studio.backends.current.created}
        with self.assertRaises(WorkBlockedError) as caught:
            controller._claim_backend(identity, "primary")
        self.assertEqual(caught.exception.phase, "restart_blocked_by_unresolved_work")
        self.assertFalse(studio.backends.busy)
        del studio.jobs["u"]
        controller._claim_backend(identity, "primary")
        self.assertTrue(studio.backends.busy)
        controller._release_backend()

    def test_blocker_list_is_bounded_and_keeps_in_flight_work_first(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        for index in range(30):
            studio.jobs[f"u-{index:02d}"] = observing_job()
        studio.jobs["zz-running"] = {"status": "running", "submissions": []}
        result = self.controller(studio).run(self.request(dry_run=True))
        blockers = result["blockers"]
        self.assertEqual((blockers["count"], blockers["blocks_all"], blockers["blocks_restart"]), (31, 1, 30))
        self.assertEqual(len(blockers["items"]), 20)
        self.assertEqual(blockers["items"][0]["id"], "zz-running")


if __name__ == "__main__":
    unittest.main()
