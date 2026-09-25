"""Receipt preservation when the SFW lighting runner loses its recipe fetch."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


RUNNER = (Path(__file__).resolve().parents[1] / "experiments" / "curated"
          / "sfw-lighting-qualification" / "run.py")


class LightingRunnerReceiptTests(unittest.TestCase):
    def test_terminal_job_keeps_reconciliation_marker_if_recipe_fetch_fails(self):
        spec = importlib.util.spec_from_file_location("sfw_lighting_runner", RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)

        def request(url, payload=None):
            if url.endswith("/api/health"):
                return {"online": True, "worker_alive": True, "degraded": False}
            if url.endswith("/api/backends"):
                return {"active": "primary", "busy": False, "gpu_lease": {"held": False}}
            if url.endswith("/queue"):
                return {"queue_running": [], "queue_pending": []}
            if url.endswith("/api/jobs"):
                return {"id": "job-1"} if payload is not None else []
            if url.endswith("/api/jobs/job-1/recipe"):
                raise OSError("temporary recipe fetch failure")
            if url.endswith("/api/jobs/job-1"):
                return {"status": "completed", "prompt_ids": ["prompt-1"]}
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as directory:
            runner.HERE = Path(directory)
            with patch.object(runner, "request", side_effect=request), \
                    patch.object(runner.time, "sleep"):
                self.assertEqual(runner.main("baseline"), 1)
            marker = runner.HERE / "baseline.submission-started.json"
            result = runner.HERE / "baseline.result.json"
            self.assertTrue(marker.exists())
            self.assertTrue(result.exists())
            self.assertFalse((runner.HERE / "baseline.recipe.json").exists())
            self.assertIn("recipe_capture_error", result.read_text(encoding="utf-8"))
            with patch.object(runner, "request", side_effect=AssertionError("resubmitted")):
                with self.assertRaises(SystemExit):
                    runner.main("baseline")


if __name__ == "__main__":
    unittest.main()
