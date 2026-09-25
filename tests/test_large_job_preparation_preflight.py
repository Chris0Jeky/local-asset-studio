from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

from large_job_prep_test_support import GIB, LargeJobPreparationTestCase, Studio, observation


SPEC = importlib.util.spec_from_file_location("asset_server_prep", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class LargeJobPreparationPreflightTests(LargeJobPreparationTestCase):
    def test_ready_receipt_respects_submission_commit_floor(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        for stage in studio.profile["stages"]:
            stage["windows_commit_bytes"] = 10 * GIB
        studio.required_host_commit_bytes = lambda preset, graph: 32 * GIB
        result = self.controller(studio).run(self.request(dry_run=True))
        self.assertEqual(result["before"]["evaluation"]["decision"], "observed_unsafe")
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache"])
        self.assertFalse(result["final"]["ready"])

    def test_release_still_below_submission_floor_is_not_ready(self):
        studio = Studio(self.root, [observation(commit=20 * GIB), observation(commit=25 * GIB)])
        for stage in studio.profile["stages"]:
            stage["windows_commit_bytes"] = 10 * GIB
        studio.required_host_commit_bytes = lambda preset, graph: 32 * GIB
        result = self.controller(studio).run(self.request())
        self.assertEqual(len(studio.free_calls), 1)
        self.assertEqual(result["after_release"]["evaluation"]["decision"], "observed_unsafe")
        self.assertFalse(result["final"]["ready"])

    def test_low_commit_preparation_defers_only_the_host_commit_gate(self):
        studio = Studio(self.root, [observation(commit=20 * GIB)])
        low_bytes = 5 * GIB
        studio._config["enforce_host_commit_headroom"] = True
        studio.host_commit_required = lambda preset, graph: True
        studio.required_host_commit_bytes = lambda preset, graph: server.Studio.required_host_commit_bytes(studio, preset, graph)

        def enforcing_preflight(preset, graph, refresh=False):
            if low_bytes < 32 * GIB:
                raise server.StudioError(
                    f"Host commit headroom {low_bytes / GIB:.1f} GiB is below the required 32 GiB "
                    "for this Qwen/FLUX.2 submission"
                )
            return {"available_bytes": low_bytes, "unknown_reason": None}

        studio.host_commit_preflight = enforcing_preflight

        def enforcing_prepare(recipe, *, _defer_host_commit_preflight=False):
            studio.prepare_calls += 1
            preset, graph = studio._prepared(recipe)
            if not _defer_host_commit_preflight:
                studio.host_commit_preflight(preset, graph)
            return preset, graph, Path("demo.json"), {}, 1

        studio.prepare = enforcing_prepare
        studio.prepare_for_large_job_preparation = lambda recipe: server.Studio.prepare_for_large_job_preparation(studio, recipe)

        with self.assertRaises(server.StudioError) as ctx:
            studio.prepare({"preset_id": "demo", "controls": {}})
        self.assertIn("32 GiB", str(ctx.exception))
        studio.prepare_calls = 0

        result = self.controller(studio).run(self.request(dry_run=True))
        self.assertEqual(result["phase"], "dry_run")
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["before"]["evaluation"]["decision"], "observed_unsafe")
        self.assertEqual(result["before"]["evaluation"]["host_commit_preflight"]["state"], "unsafe")
        self.assertEqual(result["planned_actions"], ["release_owned_backend_cache"])
        self.assertEqual(studio.free_calls, [])
        self.assertEqual(studio.backends.launches, 0)
        self.assertFalse(studio.backends.current.terminated)
        self.assertFalse(result["final"]["generation_submitted"])
        self.assertEqual(studio.prepare_calls, 1)

        stub = SimpleNamespace(
            config={"enforce_host_commit_headroom": True},
            host_commit_required=lambda preset, graph: True,
            required_host_commit_bytes=lambda preset, graph: server.Studio.required_host_commit_bytes(stub, preset, graph),
            host_commit_reading=lambda refresh=False: {"available_bytes": low_bytes, "unknown_reason": None},
        )
        with self.assertRaises(server.StudioError):
            server.Studio.host_commit_preflight(
                stub,
                {"host_commit_heavy": True},
                {"1": {"inputs": {"width": 2048, "height": 2048}}},
            )

    def test_invalid_recipe_studio_error_is_a_refused_receipt(self):
        studio = Studio(self.root, [observation(commit=40 * GIB)])

        def bad_prepare(recipe, *, _defer_host_commit_preflight=False):
            studio.prepare_calls += 1
            raise server.StudioError("Unknown preset")

        studio.prepare = bad_prepare
        studio.prepare_for_large_job_preparation = lambda recipe: server.Studio.prepare_for_large_job_preparation(studio, recipe)

        result = self.controller(studio).run(self.request())
        self.assertEqual(result["state"], "refused")
        self.assertEqual(result["phase"], "refused")
        self.assertEqual(result["final"]["decision"], "unknown")
        self.assertFalse(result["final"]["ready"])
        self.assertIn("Unknown preset", result["final"]["reason"])
        self.assertEqual(result["actions"], [])
        self.assertEqual(studio.free_calls, [])
        self.assertEqual(studio.backends.launches, 0)
        self.assertFalse(studio.backends.current.terminated)
        self.assertFalse(result["final"]["generation_submitted"])

    def test_arbitrary_preparation_error_stays_unknown(self):
        studio = Studio(self.root, [observation(commit=40 * GIB)])

        def boom_prepare(recipe):
            studio.prepare_calls += 1
            raise RuntimeError("boom")

        def boom_deferred(recipe):
            studio.prepare_calls += 1
            raise RuntimeError("boom")

        studio.prepare = boom_prepare
        studio.prepare_for_large_job_preparation = boom_deferred

        result = self.controller(studio).run(self.request())
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["phase"], "unexpected_failure")
        self.assertIn("RuntimeError", result["final"]["reason"])
        self.assertEqual(studio.free_calls, [])
        self.assertEqual(studio.backends.launches, 0)


if __name__ == "__main__":
    unittest.main()
