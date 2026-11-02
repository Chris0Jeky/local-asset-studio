import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import parity_check

PROJECT = "a" * 32
RESULT = {"pass": False, "structural_failures": ["Badge: materials ['A'] -> ['B']"], "visual_warnings": ["front/material_id: 1%"],
          "format_losses": [], "expected_exclusions": ["CollisionProxy (MESH, hidden) is not exported by the LAS settings"],
          "localisation": [{"statement": "material A -> B on Badge", "views": ["front"]}],
          "second_signal": {"available": True, "changed": True, "agrees_with_primary": True},
          "gpu_cost": {"class": "light"}, "blender": {"version_string": "5.4.0 Alpha"}}
PROBE = {"features": {"action_api": {"ok": True}, "gpu_backend": {"ok": False}}}


class FakeStudio:
    def __init__(self, root):
        self.experiments = Path(root) / "experiments"
        exe = Path(root) / "blender.exe"; exe.write_bytes(b"fake blender")
        self.config = {"blender": str(exe)}


def completed_build(studio):
    directory = studio.experiments / "projects" / PROJECT / "articulated"
    directory.mkdir(parents=True)
    (directory / "chest.blend").write_bytes(b"blend")
    (directory.parent / "articulated-job.json").write_text(json.dumps({"status": "completed"}))
    return directory.parent


class ParityCheckTests(unittest.TestCase):
    def test_refuses_without_a_completed_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = FakeStudio(tmp)
            with self.assertRaises(parity_check.ParityCheckError): parity_check.run_check(studio, PROJECT)
            directory = completed_build(studio)
            (directory / "articulated-job.json").write_text(json.dumps({"status": "failed"}))
            with self.assertRaises(parity_check.ParityCheckError): parity_check.run_check(studio, PROJECT)
            self.assertFalse((directory / parity_check.RECEIPT).exists())

    def test_runs_once_records_localised_findings_and_recovers_without_blender(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = FakeStudio(tmp); directory = completed_build(studio)
            with mock.patch.object(parity_check.blender_lab, "probe", return_value=PROBE) as probe, \
                 mock.patch.object(parity_check.blender_sentinel, "sentinel", return_value=RESULT) as sentinel:
                job = parity_check.run_check(studio, PROJECT)
                again = parity_check.run_check(studio, PROJECT)
            self.assertEqual((probe.call_count, sentinel.call_count), (1, 1))
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["summary"]["localisation"], ["material A -> B on Badge"])
            self.assertEqual(job["summary"]["capabilities"], ["action_api"])
            self.assertEqual(job["summary"]["visual_warnings"], ["front/material_id: 1%"])  # shown when nothing was localised
            self.assertEqual(again["summary"], job["summary"])
            receipt = json.loads((directory / parity_check.RECEIPT).read_text())
            self.assertEqual(receipt["source"]["path"], "articulated/chest.blend")

    def test_failure_keeps_a_failed_receipt_and_is_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = FakeStudio(tmp); directory = completed_build(studio)
            with mock.patch.object(parity_check.blender_lab, "probe", side_effect=parity_check.blender_lab.BlenderLabError("Blender exited 1")), \
                 mock.patch.object(parity_check.blender_sentinel, "sentinel") as sentinel:
                first = parity_check.run_check(studio, PROJECT)
                second = parity_check.run_check(studio, PROJECT)
            self.assertEqual((first["status"], second["status"]), ("failed", "failed"))
            self.assertIn("Blender exited 1", first["message"])
            sentinel.assert_not_called()
            self.assertTrue((directory / parity_check.FOLDER).is_dir())

    def test_interrupted_check_recovers_from_retained_result_or_reports_uncertain(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = FakeStudio(tmp); directory = completed_build(studio)
            (directory / parity_check.RECEIPT).write_text(json.dumps({"operation": parity_check.OPERATION, "status": "running"}))
            self.assertEqual(parity_check.recover(studio, PROJECT)["status"], "uncertain")
            (directory / parity_check.FOLDER / "sentinel").mkdir(parents=True)
            (directory / parity_check.FOLDER / "sentinel" / "result.json").write_text(json.dumps(RESULT))
            recovered = parity_check.recover(studio, PROJECT)
            self.assertEqual(recovered["status"], "completed")
            self.assertFalse(recovered["summary"]["pass"])

    def test_concurrent_requests_start_blender_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = FakeStudio(tmp); completed_build(studio)
            started = threading.Event(); release = threading.Event(); calls = []
            def slow_probe(*args, **kwargs):
                calls.append(1); started.set(); release.wait(5); return PROBE
            with mock.patch.object(parity_check.blender_lab, "probe", side_effect=slow_probe), \
                 mock.patch.object(parity_check.blender_sentinel, "sentinel", return_value=RESULT):
                first = threading.Thread(target=parity_check.run_check, args=(studio, PROJECT)); first.start()
                started.wait(5)
                second = parity_check.run_check(studio, PROJECT)  # receipt exists: recovers instead of starting Blender
                release.set(); first.join(10)
            self.assertEqual(len(calls), 1)
            self.assertEqual(second["status"], "uncertain")


if __name__ == "__main__":
    unittest.main()
