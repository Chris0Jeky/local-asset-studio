import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/curated/style-pose-matrix/2026-09-14-combine/research-scripts/audition_night.py"


def load_script():
    spec = importlib.util.spec_from_file_location("test_audition_night_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # The merged script performs a catalog request while importing. Keep the
    # regression focused on receipt semantics rather than a live Studio.
    with patch.object(sys, "argv", ["audition_night.py", "no-groups"]), \
         patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"presets":[]}')):
        spec.loader.exec_module(module)
    return module


class AuditionNightReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = load_script()

    def test_new_job_is_receipted_before_waiting(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "audition_night.json"
            job_id = "new-job-id"
            bodies = []

            def post_job(endpoint, body):
                self.assertEqual(endpoint, "/api/jobs")
                bodies.append(body)
                return {"id": job_id}

            def wait_job(received_id):
                self.assertEqual(received_id, job_id)
                receipt = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(receipt, [{
                    "group": "depthcut", "id": job_id, "status": "submitted",
                    "seed": 2026091441, "depth_cut": 80,
                }])
                return {
                    "id": job_id, "status": "completed", "preset_id": "combine-klein-9b-depth",
                    "prompt_ids": ["prompt-1"], "outputs": [], "elapsed_seconds": 12.5, "error": None,
                }

            result = self.script.run_experiment(
                "depthcut", lambda: {"preset_id": "combine-klein-9b-depth"},
                {"seed": 2026091441, "depth_cut": 80},
                results_path=path, post_job=post_job, wait_job=wait_job,
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(bodies, [{"preset_id": "combine-klein-9b-depth"}])
            rows = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], job_id)
            self.assertEqual(rows[0]["prompt_ids"], ["prompt-1"])

    def test_submitted_job_resumes_without_building_or_posting_again(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "audition_night.json"
            job_id = "existing-job-id"
            path.write_text(json.dumps([{
                "group": "editor", "id": job_id, "status": "submitted",
                "seed": 2026091462, "guide": "guide.png",
            }]), encoding="utf-8")
            waited = []

            def forbidden(*_args, **_kwargs):
                raise AssertionError("a submitted receipt must resume without another body or POST")

            def wait_job(received_id):
                waited.append(received_id)
                return {
                    "id": received_id, "status": "completed", "preset_id": "combine-klein-9b-skeleton",
                    "prompt_ids": ["prompt-2"], "outputs": [], "elapsed_seconds": 7.0, "error": None,
                }

            result = self.script.run_experiment(
                "editor", forbidden, {"seed": 2026091462, "guide": "guide.png"},
                results_path=path, post_job=forbidden, wait_job=wait_job,
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(waited, [job_id])
            rows = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], job_id)

    def test_terminal_job_is_a_zero_side_effect_rerun(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "audition_night.json"
            row = {
                "group": "copypose", "id": "done-job", "status": "completed",
                "seed": 2026091472, "prompt_ids": ["prompt-3"],
            }
            path.write_text(json.dumps([row]), encoding="utf-8")

            def forbidden(*_args, **_kwargs):
                raise AssertionError("a terminal receipt must not perform work")

            result = self.script.run_experiment(
                "copypose", forbidden, {"seed": 2026091472},
                results_path=path, post_job=forbidden, wait_job=forbidden,
            )
            self.assertEqual(result, row)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [row])

    def test_failed_serialization_does_not_truncate_existing_receipts(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "audition_night.json"
            original = '[{"id":"safe"}]\n'
            path.write_text(original, encoding="utf-8")
            old_out = self.script.OUT
            self.script.OUT = str(root)
            try:
                with self.assertRaises(TypeError):
                    self.script.save([{"not_json": object()}])
            finally:
                self.script.OUT = old_out
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertFalse((root / "audition_night.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
