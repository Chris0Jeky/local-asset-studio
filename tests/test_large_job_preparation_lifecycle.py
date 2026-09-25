from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from large_job_prep_test_support import (
    GIB, LargeJobPreparationTestCase, PreparationError, Process, Studio, observation,
)


SPEC = importlib.util.spec_from_file_location("asset_server_prep", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)


class LargeJobPreparationLifecycleTests(LargeJobPreparationTestCase):
    def test_restart_holds_the_switch_gate_so_new_jobs_are_refused(self):
        studio = Studio(self.root, [
            observation(commit=20 * GIB),
            observation(commit=20 * GIB),
            observation(commit=40 * GIB),
        ])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        def wait(timeout):
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        original_launch = studio.backends.launch_recovery
        def launch(profile):
            pid = original_launch(profile)
            studio.backends.system_ready = False
            return pid
        studio.backends.launch_recovery = launch
        attempts = []
        def sleep(seconds):
            # A browser request lands while the relaunched backend is still loading.
            attempts.append(studio.backends.busy)
            with self.assertRaisesRegex(server.StudioError, "backend switch is running"):
                server.Studio.prepare(studio, {"preset_id": "demo", "controls": {}})
            studio.backends.system_ready = True
            self.clock.value += seconds
        self.clock.sleep = sleep
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "ready_after_restart")
        self.assertEqual(attempts, [True])
        self.assertFalse(studio.backends.busy)
        self.assertEqual(studio.jobs, {})
        self.assertEqual(studio.prepare_calls, 1)
        self.assertEqual(studio.backends.launches, 1)

    def test_switch_gate_already_held_refuses_restart_before_termination(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        original_recheck = type(self.controller(studio))._recheck
        controller = self.controller(studio)
        calls = {"count": 0}
        def recheck(expected_identity, expected_profile_id):
            calls["count"] += 1
            value = original_recheck(controller, expected_identity, expected_profile_id)
            if calls["count"] == 3:
                studio.backends.busy = True  # a switch claimed the gate first
            return value
        controller._recheck = recheck
        result = controller.run(self.request(allow_restart=True))
        self.assertEqual(result["state"], "unknown")
        self.assertIn("busy", result["final"]["reason"])
        self.assertFalse(studio.backends.current.terminated)
        self.assertEqual(studio.backends.launches, 0)
        self.assertTrue(studio.backends.busy)  # someone else's gate is never released by us

    def test_successful_verified_restart_uses_new_creation_identity(self):
        studio = Studio(self.root, [
            observation(commit=20 * GIB),
            observation(commit=20 * GIB),
            observation(commit=40 * GIB),
        ])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        original_wait = original.wait
        def wait(timeout):
            original_wait(timeout)
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "ready_after_restart")
        self.assertTrue(result["final"]["ready"])
        self.assertTrue(original.terminated)
        self.assertEqual(studio.backends.launches, 1)
        self.assertNotEqual(result["actions"][1]["old_process"], result["actions"][1]["new_process"])

    def test_late_studio_job_during_final_restart_snapshot_refuses_readiness(self):
        studio = Studio(self.root, [
            observation(commit=20 * GIB),
            observation(commit=20 * GIB),
            observation(commit=40 * GIB),
        ])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        original_wait = original.wait
        def wait(timeout):
            original_wait(timeout)
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        controller = self.controller(studio)
        original_snapshot = controller._backend_snapshot
        original_check = controller._check_work
        events: list[str] = []
        def check(message, **kwargs):
            events.append("check:" + message)
            return original_check(message, **kwargs)
        def snapshot(**kwargs):
            value = original_snapshot(**kwargs)
            if ("check:New Studio work arrived after restart; readiness was not granted" in events
                    and "injected" not in events):
                studio.jobs["late-arrival"] = {"status": "running"}
                events.append("injected")
            events.append("snapshot")
            return value
        controller._check_work = check
        controller._backend_snapshot = snapshot
        result = controller.run(self.request(allow_restart=True))
        self.assertFalse(result["final"]["ready"])
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(result["state"], "unknown")
        self.assertIn(
            "Studio work changed while post-restart resources were being measured",
            result["final"]["reason"],
        )
        self.assertIn("injected", events)
        self.assertLess(
            events.index("injected"),
            events.index("check:Studio work changed while post-restart resources were being measured"),
        )
        self.assertEqual(studio.backends.launches, 1)
        self.assertTrue(original.terminated)
        self.assertFalse(studio.backends.current.terminated)
        self.assertFalse(result["generation_submitted"])
        self.assertFalse(result["final"]["generation_submitted"])
        self.assertEqual(len(result["actions"]), 2)
        self.assertNotIn("after_restart", result)
        self.assertFalse(studio.backends.busy)

    def test_launch_return_loss_is_reconciled_without_second_launch(self):
        studio = Studio(self.root, [
            observation(commit=20 * GIB),
            observation(commit=20 * GIB),
            observation(commit=40 * GIB),
        ])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        def wait(timeout):
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        studio.backends.launch_error = TimeoutError("return lost")
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "ready_after_restart")
        self.assertEqual(studio.backends.launches, 1)
        self.assertEqual(result["actions"][1]["launch_transport"], "lost_but_process_reconciled")

    def test_new_unrelated_listener_after_stop_prevents_launch(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        foreign = Process(77, 700.0)
        def wait(timeout):
            studio.backends.current = foreign
            studio.backends.configured = [foreign, Process(78, 701.0)]
        original.wait = wait
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(studio.backends.launches, 0)
        self.assertFalse(result["final"]["ready"])



    def test_external_queue_arrival_after_free_blocks_readiness_and_restart(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        checks = {"count": 0}
        def mutate(manager):
            checks["count"] += 1
            if checks["count"] == 4:
                manager.queue["queue_running"] = [["external"]]
        studio.backends.on_queue = mutate
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(len(studio.free_calls), 1)
        self.assertEqual(studio.backends.launches, 0)
        self.assertFalse(result["final"]["ready"])

    def test_missing_exact_profile_refuses_before_any_action(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.profile_identity = "different-runtime-identity"
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "profile_unknown")
        self.assertEqual(studio.free_calls, [])
        self.assertFalse(result["final"]["ready"])

    def test_disabled_cleanup_still_allows_non_mutating_dry_run(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.config["enable_large_job_resource_cleanup"] = False
        result = self.controller(studio).run(self.request(dry_run=True))
        self.assertEqual(result["phase"], "dry_run")
        self.assertFalse(result["local_authorization"]["cleanup_enabled"])
        self.assertEqual(studio.free_calls, [])
        self.assertFalse(studio.backends.current.terminated)

    def test_process_inspection_permission_failure_preserves_everything(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        studio.backends.process = lambda profile: (_ for _ in ()).throw(PermissionError("denied"))
        result = self.controller(studio).run(self.request())
        self.assertEqual(result["phase"], "refused")
        self.assertIn("ownership is unknown", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])

    def test_restart_startup_failure_is_recorded_without_second_launch(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        def wait(timeout):
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        original_launch = studio.backends.launch_recovery
        def launch(profile):
            pid = original_launch(profile)
            studio.backends.system_ready = False
            return pid
        studio.backends.launch_recovery = launch
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(studio.backends.launches, 1)
        self.assertEqual(result["actions"][1]["state"], "startup_failed")
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["final"]["ready"])
        self.assertFalse(studio.backends.busy)

    def test_termination_wait_failure_preserves_backend_and_releases_own_gate(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        original.wait_error = TimeoutError("stop timed out")
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["final"]["ready"])
        self.assertIn("did not stop", result["final"]["reason"])
        self.assertFalse(result["generation_submitted"])
        self.assertEqual(len(result["actions"]), 2)
        restart_action = result["actions"][1]
        self.assertEqual(restart_action["kind"], "restart")
        self.assertEqual(restart_action["state"], "termination_failed_or_alive")
        self.assertEqual(restart_action["error"], "TimeoutError")
        self.assertIs(studio.backends.current, original)
        self.assertEqual(len(studio.backends.configured), 1)
        self.assertIs(studio.backends.configured[0], original)
        self.assertTrue(original.terminated)
        self.assertEqual(studio.backends.launches, 0)
        self.assertFalse(studio.backends.busy)

    def test_launch_transport_loss_without_reconciled_process_is_unknown_and_releases_gate(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=20 * GIB)])
        studio.config["enable_large_job_backend_restart"] = True
        original = studio.backends.current
        def wait(timeout):
            studio.backends.current = None
            studio.backends.configured = []
        original.wait = wait
        attempts = {"count": 0}
        def failing_launch(profile):
            attempts["count"] += 1
            raise ConnectionError("transport lost")
        studio.backends.launch_recovery = failing_launch
        result = self.controller(studio).run(self.request(allow_restart=True))
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["final"]["ready"])
        self.assertIn("retry is prohibited", result["final"]["reason"])
        self.assertFalse(result["generation_submitted"])
        self.assertEqual(len(result["actions"]), 2)
        restart_action = result["actions"][1]
        self.assertEqual(restart_action["kind"], "restart")
        self.assertEqual(restart_action["state"], "launch_unknown")
        self.assertEqual(restart_action["error"], "ConnectionError")
        self.assertEqual(attempts["count"], 1)
        self.assertEqual(studio.backends.launches, 0)
        self.assertIsNone(studio.backends.current)
        self.assertEqual(studio.backends.configured, [])
        self.assertFalse(studio.backends.busy)

    def test_idle_policy_requires_separate_opt_in_and_cannot_restart(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        result = self.controller(studio).run(self.request(mode="idle_policy"))
        self.assertEqual(result["phase"], "idle_policy_disabled")
        self.assertEqual(studio.free_calls, [])
        with self.assertRaisesRegex(PreparationError, "cannot authorize"):
            self.controller(Studio(self.root / "other", [observation(commit=20 * GIB)])).run(
                self.request(request_id="idle-2", mode="idle_policy", allow_restart=True)
            )


if __name__ == "__main__":
    unittest.main()
