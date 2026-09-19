from __future__ import annotations

import unittest

from large_job_prep_test_support import (
    GIB, LargeJobPreparationTestCase, PreparationError, Process, Studio, observation,
)


class LargeJobPreparationLifecycleTests(LargeJobPreparationTestCase):
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
        self.assertFalse(result["final"]["ready"])

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
