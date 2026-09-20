"""Ordinary known-prompt observation must not request new-work admission."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from test_reference_hold_observation_admission import ObservationStudio, stopped_job
from test_server import server


def ordinary_job() -> dict[str, object]:
    job = stopped_job()
    job.pop("tracking_disposition")
    job["id"] = "ordinary-observation-job"
    return job


def terminal_receipt_job() -> dict[str, object]:
    job = ordinary_job()
    job.update(
        status="partial",
        message="A later output was not submitted after a local admission refusal.",
        batch_count=2,
        submissions=[
            {
                "index": 0,
                "prompt_id": "known-prompt",
                "status": "failed",
                "graph": {},
            }
        ],
    )
    return job


class OrdinaryObservationAdmissionTests(unittest.TestCase):
    def test_unresolved_known_prompt_bypasses_retained_reference_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            studio = ObservationStudio(Path(temporary), held=True)
            job = ordinary_job()
            studio.jobs[job["id"]] = job

            result = studio.resume_job(job["id"])

            self.assertEqual(result["status"], "queued")
            self.assertEqual(studio.reference_jobs.calls, 0)
            self.assertEqual(studio.queue.get_nowait(), ("observe", job["id"]))
            self.assertNotIn("reconciliation", job)

    def test_terminal_receipt_reconciliation_bypasses_retained_reference_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            studio = ObservationStudio(Path(temporary), held=True)
            job = terminal_receipt_job()
            studio.jobs[job["id"]] = job

            result = studio.resume_job(job["id"])

            self.assertEqual(result["status"], "queued")
            self.assertEqual(studio.reference_jobs.calls, 0)
            self.assertEqual(studio.queue.get_nowait(), ("observe", job["id"]))
            self.assertEqual(
                job["reconciliation"],
                {
                    "status": "partial",
                    "message": "A later output was not submitted after a local admission refusal.",
                },
            )

    def test_dead_worker_still_blocks_ordinary_known_prompt_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            studio = ObservationStudio(Path(temporary), alive=False, held=False)
            job = ordinary_job()
            studio.jobs[job["id"]] = job

            with self.assertRaisesRegex(server.StudioError, "Studio worker is unavailable"):
                studio.resume_job(job["id"])

            self.assertTrue(studio.queue.empty())
            self.assertEqual(job["status"], "uncertain")


if __name__ == "__main__":
    unittest.main()
