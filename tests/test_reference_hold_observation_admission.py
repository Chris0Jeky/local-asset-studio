from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import tempfile
import threading
import unittest

from test_server import server


class Worker:
    def __init__(self, alive: bool):
        self.ident = 1
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


class HeldReferenceJobs:
    def __init__(self):
        self.calls = 0

    def require_available(self) -> None:
        self.calls += 1
        raise ValueError(
            "Reference analysis may still own resources. Inspect its operation and release the hold before starting work."
        )


class AvailableReferenceJobs:
    def __init__(self):
        self.calls = 0

    def require_available(self) -> None:
        self.calls += 1


class ObservationStudio:
    def __init__(self, root: Path, *, alive: bool = True, held: bool = True):
        self.lock = threading.RLock()
        self.worker = Worker(alive)
        self.reference_jobs = HeldReferenceJobs() if held else AvailableReferenceJobs()
        self.backends = SimpleNamespace(busy=False)
        self.jobs: dict[str, dict[str, object]] = {}
        self.queue = Queue()
        self.runs = root / "runs"
        self.runs.mkdir(parents=True)

    def require_worker(self) -> None:
        server.Studio.require_worker(self)

    def require_worker_observation(self) -> None:
        server.Studio.require_worker_observation(self)

    def _write_json_atomic(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def public(job: dict[str, object]) -> dict[str, object]:
        return copy.deepcopy(job)


def mixed_job() -> dict[str, object]:
    return {
        "id": "mixed-observation-job",
        "status": "uncertain",
        "message": "The second POST outcome is unknown.",
        "batch_count": 2,
        "prompt_ids": ["known-prompt"],
        "submissions": [
            {
                "index": 0,
                "prompt_id": "known-prompt",
                "status": "observing",
                "graph": {"1": {"class_type": "Sampler", "inputs": {}}},
            }
        ],
        "pending_submission": {
            "index": 1,
            "graph": {"2": {"class_type": "Sampler", "inputs": {}}},
        },
        "outputs": [],
    }


class ReferenceHoldObservationAdmissionTests(unittest.TestCase):
    def test_hold_blocks_new_work_but_not_worker_observation_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            studio = ObservationStudio(Path(temporary), held=True)
            with self.assertRaisesRegex(ValueError, "Reference analysis may still own resources"):
                studio.require_worker()
            self.assertEqual(studio.reference_jobs.calls, 1)

            studio.require_worker_observation()
            self.assertEqual(
                studio.reference_jobs.calls,
                1,
                "Observation must not ask the reference resource owner for new-work admission",
            )

    def test_dead_worker_blocks_both_start_and_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            studio = ObservationStudio(Path(temporary), alive=False, held=False)
            for guard in (studio.require_worker, studio.require_worker_observation):
                with self.subTest(guard=guard.__name__), self.assertRaisesRegex(
                    server.StudioError,
                    "Studio worker is unavailable",
                ):
                    guard()

    def test_mixed_batch_known_receipt_observation_ignores_reference_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            studio = ObservationStudio(Path(temporary), held=True)
            job = mixed_job()
            studio.jobs[job["id"]] = job
            revision = server.mixed_batch.snapshot(job)["revision"]

            result = server.mixed_batch.command(
                studio,
                job["id"],
                "observe",
                {
                    "request_id": "observe-known-0001",
                    "expected_revision": revision,
                },
            )

            self.assertEqual(result["status"], "queued")
            self.assertEqual(studio.reference_jobs.calls, 0)
            self.assertEqual(
                studio.queue.get_nowait(),
                ("observe-mixed", (job["id"], "observe-known-0001")),
            )
            self.assertEqual(job["pending_submission"]["index"], 1)
            self.assertNotIn("abandonment", job)

    def test_only_known_observation_paths_use_the_liveness_only_guard(self) -> None:
        resume_tracking = inspect.getsource(server.Studio._resume_tracking)
        mixed_command = inspect.getsource(server.mixed_batch.command)
        production_resume = inspect.getsource(server.Production.resume)
        production_start = inspect.getsource(server.Production._start)

        self.assertIn("self.require_worker_observation()", resume_tracking)
        self.assertNotIn("self.require_worker()", resume_tracking)
        self.assertIn("studio.require_worker_observation()", mixed_command)
        self.assertNotIn("studio.require_worker()", mixed_command)

        batch_reconcile = production_resume.index("_reconcile_batch_disposition")
        tracking_reconcile = production_resume.index("_reconcile_tracking_terminal")
        new_work_admission = production_resume.index("self.studio.require_worker()")
        self.assertLess(batch_reconcile, new_work_admission)
        self.assertLess(tracking_reconcile, new_work_admission)
        self.assertIn("self.studio.require_worker()", production_start)


if __name__ == "__main__":
    unittest.main()
