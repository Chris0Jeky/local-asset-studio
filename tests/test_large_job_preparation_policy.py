from __future__ import annotations

import unittest

from large_job_prep_test_support import (
    GIB, LargeJobPreparationTestCase, PreparationError, Process, SimpleNamespace, Studio,
    observation, threading,
)


class LargeJobPreparationPolicyTests(LargeJobPreparationTestCase):
    def test_dry_run_is_provably_non_mutating_and_replays_same_receipt(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        result = self.controller(studio).run(self.request(dry_run=True, allow_restart=True))
        self.assertEqual(result["phase"], "dry_run")
        self.assertFalse(result["final"]["ready"])
        self.assertEqual(studio.free_calls, [])
        self.assertFalse(studio.backends.current.terminated)
        self.assertEqual(studio.backends.launches, 0)
        self.assertEqual(studio.created_jobs, 0)
        replay = self.controller(studio).run(self.request(dry_run=True, allow_restart=True))
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(studio.prepare_calls, 1)

    def test_missing_counter_is_unknown_and_never_calls_free(self):
        studio = Studio(self.root, [observation(commit=None)])
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "resource_unknown")
        self.assertEqual(result["final"]["decision"], "unknown")
        self.assertEqual(studio.free_calls, [])

    def test_free_http_success_without_measured_relief_is_not_ready(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "restart_not_authorized")
        # /free ran, so the top-level state can never read as a no-op refusal.
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["final"]["ready"])
        self.assertEqual(result["actions"][0]["state"], "measured")
        self.assertFalse(result["actions"][0]["measured_relief"])
        self.assertEqual(len(studio.free_calls), 1)

    def test_measured_release_can_make_exact_profile_ready(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=40 * GIB)])
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "ready_after_release")
        self.assertTrue(result["final"]["ready"])
        self.assertGreater(result["release_delta_bytes"]["windows_commit_bytes"], 0)
        self.assertEqual(len(studio.free_calls), 1)

    def test_lost_free_response_is_durable_unknown_and_never_replayed(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.free_error = TimeoutError("response lost")
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "release_response_unknown")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(len(studio.free_calls), 1)
        replay = self.controller(studio).run(self.request())
        self.assertTrue(replay["replayed"])
        self.assertEqual(len(studio.free_calls), 1)
        self.assertEqual(studio.backends.launches, 0)

    def test_release_holds_switch_gate_during_free_and_releases_afterward(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        seen = {}
        original = studio._request
        def capture(route, **kwargs):
            seen["busy_during_free"] = studio.backends.busy
            return original(route, **kwargs)
        studio._request = capture
        result = self.controller(studio).run(self.request())
        self.assertEqual(len(studio.free_calls), 1)
        self.assertTrue(seen["busy_during_free"])
        self.assertFalse(studio.backends.busy)
        self.assertEqual(result["actions"][0]["kind"], "release")
        self.assertEqual(result["actions"][0]["state"], "measured")

    def test_switch_gate_held_before_release_claim_refuses_without_post(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        controller = self.controller(studio)
        original = type(controller)._claim_release_gate
        def switch_then_claim(expected_identity, expected_profile_id):
            # The switch arrives after observation but before release takes the gate.
            with studio.lock:
                studio.backends.busy = True
            return original(controller, expected_identity, expected_profile_id)
        controller._claim_release_gate = switch_then_claim
        result = controller.run(self.request())
        self.assertEqual(studio.free_calls, [])
        self.assertTrue(studio.backends.busy)
        self.assertEqual(result["actions"], [])
        self.assertEqual(result["phase"], "refused")
        self.assertIn("switching", result["final"]["reason"])

    def test_lost_free_response_releases_own_gate_and_never_replays_or_restarts(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.free_error = TimeoutError("response lost")
        seen = {}
        original = studio._request
        def capture(route, **kwargs):
            seen["busy_during_free"] = studio.backends.busy
            return original(route, **kwargs)
        studio._request = capture
        controller = self.controller(studio)
        result = controller.run(self.request())
        self.assertEqual(result["phase"], "release_response_unknown")
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(len(studio.free_calls), 1)
        self.assertTrue(seen["busy_during_free"])
        self.assertFalse(studio.backends.busy)
        self.assertEqual(studio.backends.launches, 0)
        self.assertEqual([action["kind"] for action in result["actions"]], ["release"])
        replay = controller.run(self.request())
        self.assertTrue(replay["replayed"])
        self.assertEqual(len(studio.free_calls), 1)
        self.assertFalse(studio.backends.busy)
        self.assertEqual(studio.backends.launches, 0)

    def test_unresolved_work_at_rest_still_permits_free(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=40 * GIB)])
        studio.jobs["u"] = {"status": "uncertain", "prompt_ids": ["p-1"],
                            "submissions": [{"index": 0, "prompt_id": "p-1", "status": "observing"}]}
        result = self.controller(studio).run(self.request())
        self.assertEqual(len(studio.free_calls), 1)
        self.assertEqual(studio.backends.history_requests, [])
        self.assertEqual(result["phase"], "ready_after_release")
        self.assertTrue(result["final"]["ready"])
        self.assertFalse(studio.backends.busy)


    def test_unknown_production_state_fails_closed(self):
        # Interrupted plans block only a restart (test_large_job_preparation_classification).
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.production.items = [{"id": "project-1", "state": {"status": "unrecognized"}}]
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("In-flight", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])
        second = Studio(self.root / "malformed", [observation(commit=20 * GIB)])
        second.production.items = [{"id": "project-2"}]
        result = self.controller(second).run(self.request(request_id="prepare-2"))
        self.assertEqual(result["phase"], "refused")
        self.assertIn("invalid project", result["final"]["reason"])

    def test_uncertain_job_with_pending_submission_blocks_all_lifecycle_actions(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.jobs["unknown"] = {"status": "uncertain", "pending_submission": {"index": 0}, "submissions": []}
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("In-flight", result["final"]["reason"])
        self.assertEqual(result["blockers"]["items"][0]["blocks"], "all")
        self.assertEqual(studio.free_calls, [])

    def test_queue_change_immediately_before_free_invalidates_plan(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        checks = {"count": 0}
        def mutate(manager):
            checks["count"] += 1
            if checks["count"] == 3:
                manager.queue["queue_pending"] = [["external"]]
        studio.backends.on_queue = mutate
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(studio.free_calls, [])

    def test_pid_reuse_or_process_change_before_free_invalidates_plan(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        original_process = studio.backends.process
        calls = {"count": 0}
        def changed(profile):
            calls["count"] += 1
            if calls["count"] >= 3:
                replacement = Process(40, 999.0)
                studio.backends.current = replacement
                studio.backends.configured = [replacement]
            return original_process(profile) if calls["count"] < 3 else studio.backends.current
        studio.backends.process = changed
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("changed", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])

    def test_active_reservations_reduce_effective_capacity(self):
        studio = Studio(self.root, [observation(commit=50 * GIB), observation(commit=50 * GIB)])
        studio.jobs["held"] = {
            "status": "failed",
            "pending_submission": {"index": 0},
            "submissions": [],
            "resource_admission": [{
                "state": "retained",
                "reservation": {
                    "physical_ram_bytes": 0,
                    "windows_commit_bytes": 20 * GIB,
                    "vram_bytes": 0,
                },
            }],
        }
        # The uncertain job is itself a blocker, so model an in-memory reservation
        # belonging to a reconciled auxiliary owner instead.
        studio.jobs.clear()
        ledger = SimpleNamespace(
            lock=threading.RLock(),
            reservations={"aux": {"reservation": {
                "physical_ram_bytes": 0,
                "windows_commit_bytes": 20 * GIB,
                "vram_bytes": 0,
            }}},
        )
        studio._stage_resource_admission = SimpleNamespace(ledger=ledger)
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["before"]["evaluation"]["decision"], "observed_unsafe")
        self.assertEqual(result["before"]["reservations"]["owners"], ["aux"])

    def test_runtime_version_drift_leaves_the_exact_profile_unbound(self):
        studio = Studio(self.root, [observation(commit=20 * GIB, version="2")])
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "profile_unknown")
        self.assertNotEqual(result["before"]["workflow_identity"]["identity_sha256"], studio.exact_identity())
        self.assertEqual(studio.free_calls, [])

    def test_malformed_stored_profile_refuses_without_action(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        del studio.profile["stages"][0]["vram_bytes"]
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("every resource dimension", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])

    def test_workflow_for_another_backend_never_releases_the_selected_one(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.backends.profiles["hidream"] = {"id": "hidream", "url": "http://127.0.0.1:8192"}
        studio.backends.active = "hidream"
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("other than the selected", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])

    def test_refusal_without_any_action_keeps_refused_state(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        result = self.controller(studio).run(self.request(allow_release=False))
        self.assertEqual(result["phase"], "release_not_authorized")
        self.assertEqual(result["state"], "refused")
        self.assertEqual(result["actions"], [])

    def test_request_id_content_conflict_is_refused(self):
        studio = Studio(self.root, [observation(commit=40 * GIB)])
        controller = self.controller(studio)
        controller.run(self.request(allow_release=False))
        with self.assertRaisesRegex(PreparationError, "different content"):
            controller.run(self.request(allow_release=True))

    def test_saved_in_progress_intent_becomes_unknown_without_execution(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        controller = self.controller(studio)
        normalized = self.request()
        from large_job_preparation import _digest, _normalize_request, JOURNAL_SCHEMA
        normalized = _normalize_request(normalized)
        journal = {"schema": JOURNAL_SCHEMA, "records": [{
            "schema": "studio.large-job-preparation/v1",
            "request_id": normalized["request_id"],
            "request_sha256": _digest(normalized, 128 * 1024),
            "state": "in_progress",
            "phase": "release_intent_saved",
            "actions": [{"kind": "release", "state": "intent_saved"}],
        }]}
        studio._write_json_atomic(controller.path, journal)
        result = controller.run(self.request())
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["phase"], "interrupted")
        self.assertEqual(studio.free_calls, [])

    @staticmethod
    def _fake_receipt(request_id, state):
        return {
            "schema": "studio.large-job-preparation/v1",
            "request_id": request_id,
            "state": state,
            "phase": "probe",
            "marker": request_id,
        }

    def _fill_journal(self, controller, studio, states):
        from large_job_prep_common import JOURNAL_SCHEMA
        records = [
            self._fake_receipt("rotate-%02d" % index, state)
            for index, state in enumerate(states)
        ]
        studio._write_json_atomic(controller.path, {"schema": JOURNAL_SCHEMA, "records": records})
        return controller._load()

    def test_full_journal_evicts_oldest_terminal_first(self):
        from large_job_prep_common import MAX_RECORDS, _digest
        studio = Studio(self.root, [])
        controller = self.controller(studio)
        states = ["completed", "refused"] + [
            "in_progress" if index % 3 == 0 else ("unknown" if index % 3 == 1 else "completed")
            for index in range(2, MAX_RECORDS)
        ]
        journal = self._fill_journal(controller, studio, states)
        controller._persist(journal, self._fake_receipt("rotate-new", "in_progress"))
        reloaded = controller._load()
        ids = [record["request_id"] for record in reloaded["records"]]
        self.assertEqual(len(ids), MAX_RECORDS)
        self.assertNotIn("rotate-00", ids)
        self.assertIn("rotate-01", ids)
        self.assertIn("rotate-new", ids)
        self.assertEqual(ids[-1], "rotate-new")
        self.assertEqual(ids[0], "rotate-01")
        for record in reloaded["records"]:
            if record["request_id"] == "rotate-new":
                expected = {key: value for key, value in record.items() if key != "receipt_sha256"}
                self.assertEqual(record["receipt_sha256"], _digest(expected))

    def test_protected_states_are_never_evicted(self):
        from large_job_prep_common import MAX_RECORDS
        studio = Studio(self.root, [])
        controller = self.controller(studio)
        states = ["in_progress", "unknown", "started", "completed"] + ["completed"] * (MAX_RECORDS - 5) + ["refused"]
        journal = self._fill_journal(controller, studio, states)
        controller._persist(journal, self._fake_receipt("rotate-new", "in_progress"))
        reloaded = controller._load()
        ids = [record["request_id"] for record in reloaded["records"]]
        self.assertEqual(len(ids), MAX_RECORDS)
        self.assertEqual(ids[:3], ["rotate-00", "rotate-01", "rotate-02"])
        self.assertNotIn("rotate-03", ids)
        self.assertIn("rotate-new", ids)

    def test_terminal_action_receipt_is_not_evicted(self):
        from large_job_prep_common import MAX_RECORDS
        studio = Studio(self.root, [])
        controller = self.controller(studio)
        journal = self._fill_journal(controller, studio, ["completed"] * MAX_RECORDS)
        journal["records"][0]["actions"] = [{"kind": "free", "state": "measured"}]
        studio._write_json_atomic(controller.path, journal)
        controller._persist(journal, self._fake_receipt("rotate-new", "in_progress"))
        ids = [record["request_id"] for record in controller._load()["records"]]
        self.assertIn("rotate-00", ids)
        self.assertNotIn("rotate-01", ids)

    def test_full_action_journal_refuses_new_request(self):
        from large_job_prep_common import MAX_RECORDS
        studio = Studio(self.root, [])
        controller = self.controller(studio)
        journal = self._fill_journal(controller, studio, ["completed"] * MAX_RECORDS)
        for record in journal["records"]:
            record["actions"] = [{"kind": "free", "state": "measured"}]
        studio._write_json_atomic(controller.path, journal)
        before = controller.path.read_bytes()
        with self.assertRaisesRegex(PreparationError, "retention is full"):
            controller._persist(journal, self._fake_receipt("rotate-new", "in_progress"))
        self.assertEqual(controller.path.read_bytes(), before)

    def test_full_protected_journal_fails_closed_intact(self):
        from large_job_prep_common import MAX_RECORDS
        studio = Studio(self.root, [])
        controller = self.controller(studio)
        states = [
            ("in_progress" if index % 3 == 0 else ("unknown" if index % 3 == 1 else "started"))
            for index in range(MAX_RECORDS)
        ]
        journal = self._fill_journal(controller, studio, states)
        before = controller.path.read_bytes()
        with self.assertRaisesRegex(PreparationError, "retention is full"):
            controller._persist(journal, self._fake_receipt("rotate-new", "in_progress"))
        self.assertEqual(controller.path.read_bytes(), before)
        reloaded = controller._load()
        self.assertEqual([record["request_id"] for record in reloaded["records"]],
                         ["rotate-%02d" % index for index in range(MAX_RECORDS)])

    def test_existing_request_update_does_not_rotate(self):
        from large_job_prep_common import MAX_RECORDS
        studio = Studio(self.root, [])
        controller = self.controller(studio)
        states = ["completed"] + ["in_progress"] * (MAX_RECORDS - 1)
        journal = self._fill_journal(controller, studio, states)
        updated = self._fake_receipt("rotate-05", "in_progress")
        updated["phase"] = "updated"
        controller._persist(journal, updated)
        reloaded = controller._load()
        ids = [record["request_id"] for record in reloaded["records"]]
        self.assertEqual(len(ids), MAX_RECORDS)
        self.assertEqual(sorted(ids), sorted("rotate-%02d" % index for index in range(MAX_RECORDS)))
        self.assertEqual(reloaded["records"][ids.index("rotate-05")]["phase"], "updated")


if __name__ == "__main__":
    unittest.main()
