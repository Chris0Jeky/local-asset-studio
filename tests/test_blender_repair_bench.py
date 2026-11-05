import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_repair_bench as bench
import blender_worker as bw

MANIFEST = json.loads((ROOT / "tests" / "fixtures" / "blender_lab" / "manifest-lab-asset-5.4.0-alpha-67c9bdddb88b.json").read_text(encoding="utf-8"))
OTHER_MANIFEST = json.loads((ROOT / "tests" / "fixtures" / "blender_lab" / "manifest-articulated-chest.json").read_text(encoding="utf-8"))
LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


def obj(manifest, name): return next(o for o in manifest["objects"] if o["name"] == name)


def report_file(directory, rows=(), *, manifest=MANIFEST, agent="codex-sol", legacy=False, adjacent=False):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    report = {"schema": "las.blender-repair-bench.v1", "agent": agent, "rows": list(rows)}
    if not legacy: report["asset_identity"] = manifest["semantic_checksum"]
    path = directory / "repair-bench.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    if adjacent: (directory / "control-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


class RunIdentityTests(unittest.TestCase):
    def test_run_persists_the_control_identity(self):
        def manifest(exe, blend, out):
            Path(out).write_text(json.dumps(MANIFEST), encoding="utf-8")
            return copy.deepcopy(MANIFEST)
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"; corpus.mkdir()
            (corpus / "corpus.json").write_text(json.dumps({"entries": [{"id": "control", "blend": "control.blend"}]}))
            with mock.patch.object(bench.lab, "executable", return_value=Path("blender")), \
                 mock.patch.object(bench.lab, "manifest", side_effect=manifest), \
                 mock.patch.object(bench, "run_codex", return_value={"text": '{"repaired": false}', "returncode": 0}):
                report = bench.run("blender", corpus, Path(tmp) / "run", "codex-sol")
            saved = json.loads((Path(tmp) / "run" / "repair-bench.json").read_text())
        self.assertEqual(report["asset_identity"], MANIFEST["semantic_checksum"])
        self.assertEqual(saved["asset_identity"], MANIFEST["semantic_checksum"])


class VerdictAndOutcomeTests(unittest.TestCase):
    def test_final_json_line_is_parsed_even_in_a_code_fence(self):
        self.assertEqual(bench.verdict('done\n`{"repaired": true, "edits": 1, "reason": "x"}`'), {"repaired": True, "edits": 1, "reason": "x"})
        self.assertIsNone(bench.verdict("no json here"))

    def test_outcomes_separate_honest_declines_from_misses_and_harm(self):
        base = {"saved": False, "exact": False, "remaining": ["x"], "collateral": []}
        self.assertEqual(bench.outcome("mesh-hole", base), "declined (correct)")
        self.assertEqual(bench.outcome("omitted-mesh", base), "declined (repairable)")
        self.assertEqual(bench.outcome("omitted-mesh", {**base, "saved": True, "exact": True, "remaining": []}), "exact repair")
        self.assertEqual(bench.outcome("duplicate-overlap", {**base, "saved": True, "remaining": []}), "structurally clean (checksum differs)")
        self.assertEqual(bench.outcome("transform-offset", {**base, "saved": True, "collateral": ["new"]}), "harmful (collateral change)")
        self.assertEqual(bench.outcome("control", {**base, "remaining": []}), "no-op (correct)")


class InfraAndCombineTests(unittest.TestCase):
    def test_an_outage_is_not_a_decline(self):
        result = {"saved": False, "exact": False, "remaining": ["x"], "collateral": [], "infrastructure_failure": True}
        self.assertTrue(bench.outcome("omitted-mesh", result).startswith("infrastructure failure"))
        self.assertIsNotNone(bench.INFRA.search("API Error: Can't reach the API server (ENOTFOUND)"))

    def test_combine_keeps_the_latest_real_attempt_and_counts_outages(self):
        def row(case, outcome, infra=False):
            return {"case": case, "outcome": outcome, "infrastructure_failure": infra, "exact": outcome == "exact repair",
                    "repairable_by_vocabulary": case == "omitted-mesh", "collateral": []}
        with tempfile.TemporaryDirectory() as tmp:
            for name, rows in (("first", [row("omitted-mesh", "infrastructure failure (x)", True), row("mesh-hole", "declined (correct)")]),
                               ("rerun", [row("omitted-mesh", "exact repair")])):
                report_file(Path(tmp) / name, rows)
            report = bench.combine([Path(tmp) / "first", Path(tmp) / "rerun"], Path(tmp) / "out.json")
            saved = json.loads((Path(tmp) / "out.json").read_text())
        self.assertEqual(report["outcomes"], {"exact repair": 1, "declined (correct)": 1})
        self.assertEqual((report["repairable_exact"], report["infrastructure_failures_retried"]), (1, 1))
        self.assertEqual(report["asset_identity"], MANIFEST["semantic_checksum"])
        self.assertEqual(saved["asset_identity"], MANIFEST["semantic_checksum"])

    def test_combine_refuses_runs_of_different_assets_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = report_file(Path(tmp) / "first")
            second = report_file(Path(tmp) / "second", manifest=OTHER_MANIFEST)
            out = Path(tmp) / "combined.json"
            with self.assertRaisesRegex(ValueError, "different assets"):
                bench.combine([first.parent, second.parent], out)
            self.assertFalse(out.exists())

    def test_combine_migrates_only_verified_adjacent_legacy_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = report_file(Path(tmp) / "first", legacy=True, adjacent=True)
            second = report_file(Path(tmp) / "second", legacy=True, adjacent=True)
            out = Path(tmp) / "combined.json"
            report = bench.combine([first.parent, second.parent], out)
            self.assertEqual(report["asset_identity"], MANIFEST["semantic_checksum"])
            self.assertEqual(json.loads(out.read_text())["asset_identity"], MANIFEST["semantic_checksum"])

    def test_combine_refuses_unidentified_legacy_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = report_file(Path(tmp) / "run", legacy=True)
            with self.assertRaisesRegex(ValueError, "asset identity.*control-manifest.json"):
                bench.combine([report.parent], Path(tmp) / "combined.json")


class FailureAndTreeTests(unittest.TestCase):
    def test_a_crashed_or_garbled_agent_is_not_a_decline(self):
        base = {"saved": False, "exact": False, "remaining": ["x"], "collateral": []}
        self.assertEqual(bench.outcome("mesh-hole", {**base, "returncode": 1, "verdict_ok": True}), "agent failure (no valid verdict)")
        self.assertEqual(bench.outcome("mesh-hole", {**base, "returncode": 0, "verdict_ok": False}), "agent failure (no valid verdict)")
        self.assertEqual(bench.outcome("mesh-hole", {**base, "returncode": 0, "verdict_ok": True}), "declined (correct)")

    def test_timeout_kills_the_whole_process_tree(self):
        import selectors, signal, subprocess, time
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            pid_file = Path(tmp) / "child.pid"
            spawn = ("import subprocess, sys, time; from pathlib import Path; "
                     "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(12)']); "
                     f"p = Path({str(pid_file)!r}); p.with_suffix('.tmp').write_text(str(c.pid)); p.with_suffix('.tmp').replace(p); "
                     "print('child started', flush=True); time.sleep(12)")
            started = time.monotonic()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(bench.run_tree, [sys.executable, "-c", spawn], input="", cwd=tmp, env=None, timeout=3)
                child, pidfd = None, None
                try:
                    while not pid_file.exists():
                        self.assertLess(time.monotonic() - started, 8, "agent did not start its child")
                        time.sleep(0.01)
                    child_pid = int(pid_file.read_text())
                    if hasattr(os, "pidfd_open"):
                        pidfd = os.pidfd_open(child_pid)  # exact child identity; /proc may expose a different PID namespace
                    else:
                        child = psutil.Process(child_pid)
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        future.result(timeout=8)
                    self.assertLess(time.monotonic() - started, 8, "timeout waited for the inherited child stdout pipe")
                    self.assertIn("child started", caught.exception.output)
                    if pidfd is not None:
                        with selectors.DefaultSelector() as watcher:
                            watcher.register(pidfd, selectors.EVENT_READ)
                            self.assertTrue(watcher.select(2), "agent child survived timeout cleanup")
                    else:
                        deadline = time.monotonic() + 2
                        while child.is_running():
                            try:
                                if child.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD): break
                            except psutil.NoSuchProcess: break
                            self.assertLess(time.monotonic(), deadline, "agent child survived timeout cleanup")
                            time.sleep(0.05)
                finally:
                    if pidfd is not None:
                        try: signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        except ProcessLookupError: pass
                        finally: os.close(pidfd)
                    elif child is not None:
                        try:
                            if child.is_running() and child.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD): child.kill()
                        except psutil.NoSuchProcess: pass


class AggregateTests(unittest.TestCase):
    def test_aggregate_totals_across_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            for asset, rows in (("a", [{"case": "omitted-mesh", "outcome": "exact repair", "exact": True, "repairable_by_vocabulary": True,
                                        "collateral": [], "seconds": 10}]),
                                ("b", [{"case": "mesh-hole", "outcome": "declined (correct)", "exact": False, "repairable_by_vocabulary": False,
                                        "collateral": [], "seconds": 20}])):
                report_file(Path(tmp) / asset, rows, manifest=MANIFEST if asset == "a" else OTHER_MANIFEST)
            a, b = Path(tmp) / "a" / "repair-bench.json", Path(tmp) / "b" / "repair-bench.json"
            totals = bench.aggregate([a, b])
            with self.assertRaises(ValueError): bench.aggregate([a, a])  # the same asset twice
            report_file(Path(tmp) / "c", manifest=OTHER_MANIFEST, agent="claude-haiku")
            with self.assertRaises(ValueError): bench.aggregate([a, Path(tmp) / "c" / "repair-bench.json"])  # mixed agents
        self.assertEqual((totals["cases"], totals["repairable_exact"], totals["repairable_total"]), (2, 1, 1))
        self.assertEqual(totals["outcomes"], {"exact repair": 1, "declined (correct)": 1})
        self.assertEqual(totals["median_seconds"], 15)

    def test_aggregate_refuses_the_same_asset_under_different_directory_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = report_file(Path(tmp) / "original")
            copied = report_file(Path(tmp) / "renamed-copy")
            with self.assertRaisesRegex(ValueError, "duplicate asset"):
                bench.aggregate([original, copied])

    def test_aggregate_distinguishes_different_assets_with_the_same_directory_name(self):
        row = {"case": "transform-offset", "outcome": "harmful (collateral change)", "exact": False,
               "repairable_by_vocabulary": True, "collateral": ["changed"], "seconds": 10}
        with tempfile.TemporaryDirectory() as tmp:
            first = report_file(Path(tmp) / "a" / "same", [row])
            second = report_file(Path(tmp) / "b" / "same", [row], manifest=OTHER_MANIFEST)
            totals = bench.aggregate([first, second])
        self.assertEqual(totals["cases"], 2)
        self.assertEqual(len(set(totals["collateral_cases"])), 2)
        for manifest in (MANIFEST, OTHER_MANIFEST):
            self.assertIn(f"same@{manifest['semantic_checksum']}/transform-offset", totals["collateral_cases"])

    def test_aggregate_refuses_missing_or_invalid_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = report_file(Path(tmp), legacy=True)
            report = json.loads(path.read_text())
            for value in (None, "", "not-a-checksum", "g" * 64, 7, {}, []):
                with self.subTest(value=value):
                    path.write_text(json.dumps({**report, "asset_identity": value}))
                    with self.assertRaisesRegex(ValueError, "invalid asset identity"):
                        bench.aggregate([path])
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "asset identity.*control-manifest.json"):
                bench.aggregate([path])

    def test_aggregate_normalizes_checksum_case_before_detecting_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = report_file(Path(tmp) / "first")
            second = report_file(Path(tmp) / "second")
            report = json.loads(second.read_text()); report["asset_identity"] = report["asset_identity"].upper()
            second.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "duplicate asset"):
                bench.aggregate([first, second])

    def test_aggregate_legacy_fallback_uses_content_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = report_file(Path(tmp) / "first", legacy=True, adjacent=True)
            second = report_file(Path(tmp) / "second", legacy=True, adjacent=True)
            with self.assertRaisesRegex(ValueError, "duplicate asset"):
                bench.aggregate([first, second])

    def test_legacy_report_paths_are_not_followed_to_infer_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = report_file(Path(tmp) / "original", adjacent=True)
            copied = report_file(Path(tmp) / "copied", legacy=True)
            report = json.loads(copied.read_text())
            report.update(corpus=str(original.parent), runs=[str(original.parent)])
            copied.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "asset identity.*control-manifest.json"):
                bench.aggregate([copied])

    def test_legacy_manifest_with_a_broken_checksum_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = report_file(Path(tmp), legacy=True, adjacent=True)
            damaged = copy.deepcopy(MANIFEST); damaged["scene"]["name"] = "Changed after capture"
            (Path(tmp) / "control-manifest.json").write_text(json.dumps(damaged))
            with self.assertRaisesRegex(ValueError, "control manifest.*checksum"):
                bench.aggregate([path])

    def test_report_identity_must_match_an_adjacent_control_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = report_file(Path(tmp), adjacent=True)
            (Path(tmp) / "control-manifest.json").write_text(json.dumps(OTHER_MANIFEST))
            with self.assertRaisesRegex(ValueError, "asset identity.*control manifest"):
                bench.aggregate([path])


class ScoreTests(unittest.TestCase):
    def test_new_damage_hidden_behind_an_existing_difference_is_collateral(self):
        damaged = copy.deepcopy(MANIFEST); obj(damaged, "Head")["matrix_world"][2][3] += 0.12
        repaired = copy.deepcopy(damaged); obj(repaired, "Head")["matrix_world"][0][1] = 0.5  # a rotation added on top
        collateral, imprecise = bench.property_changes(MANIFEST, damaged, repaired)
        self.assertEqual(collateral, ["/objects[Head]/matrix_world[0][1]"])
        self.assertEqual(imprecise, [])
        nearly = copy.deepcopy(damaged); obj(nearly, "Head")["matrix_world"][2][3] = MANIFEST["objects"][2]["matrix_world"][2][3] + 0.01
        self.assertEqual(bench.property_changes(MANIFEST, damaged, nearly)[1], ["/objects[Head]/matrix_world[2][3]"])


    def test_collateral_is_a_new_difference_not_one_the_defect_already_had(self):
        defective = copy.deepcopy(MANIFEST); obj(defective, "Badge")["material_slots"][0]["material"] = "BodyTextured"
        repaired = copy.deepcopy(MANIFEST); obj(repaired, "Head")["material_slots"][0]["material"] = "BadgeGreen"
        repaired["semantic_checksum"] = "0" * 64  # a real manifest carries its own checksum
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "repaired.blend").write_bytes(b"")
            with mock.patch.object(bench.lab, "manifest", return_value=repaired):
                result = bench.score("exe", "material-mismatch", MANIFEST, defective, Path(tmp), Path(tmp))
        self.assertTrue(result["saved"]); self.assertFalse(result["exact"])
        self.assertIn("/objects[Head]/material_slots[0]/material", result["collateral"])

    def test_unsaved_repair_keeps_the_defect_as_remaining(self):
        defective = copy.deepcopy(MANIFEST); obj(defective, "Body")["hide_render"] = True
        with tempfile.TemporaryDirectory() as tmp:
            result = bench.score("exe", "omitted-mesh", MANIFEST, defective, Path(tmp), Path(tmp))
        self.assertEqual((result["saved"], result["collateral"]), (False, []))
        self.assertIn("visible mesh Body is missing after the roundtrip", result["remaining"])


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live compare_to check")
class LiveCompareToTests(unittest.TestCase):
    def test_delete_fully_repairs_a_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = bw.lab.make_fixture(LIVE_BLENDER, Path(tmp) / "assets")
            damaged = clean.parent / "duplicate-overlap.blend"
            bw.lab.run(bw.lab.executable(LIVE_BLENDER), ["corpus-variant", "--blend", clean, "--kind", "duplicate-overlap",
                       "--out-blend", damaged, "--out", Path(tmp) / "v.json"], Path(tmp) / "v.log.json")
            (Path(tmp) / "root").mkdir()
            with bw.BlenderWorker(LIVE_BLENDER, Path(tmp) / "root") as worker:
                worker.call("open", blend=str(damaged), allow_edit=["BadgeDuplicate"])
                before = worker.compare_to(str(clean))
                worker.call("apply_edit", object="BadgeDuplicate", op="delete", value=True, expect_checksum=before["current_checksum"])
                after = worker.compare_to(str(clean))
                with self.assertRaises(bw.WorkerFailed):  # the deleted object is no longer editable
                    worker.call("apply_edit", object="BadgeDuplicate", op="hide_render", value=True, expect_checksum=after["current_checksum"])
        self.assertFalse(before["matches_reference"])
        self.assertTrue(after["matches_reference"])

    def test_compare_to_localises_and_confirms_a_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = bw.lab.make_fixture(LIVE_BLENDER, Path(tmp) / "assets")
            damaged = clean.parent / "material-mismatch.blend"
            bw.lab.run(bw.lab.executable(LIVE_BLENDER), ["corpus-variant", "--blend", clean, "--kind", "material-mismatch",
                       "--out-blend", damaged, "--out", Path(tmp) / "v.json"], Path(tmp) / "v.log.json")
            (Path(tmp) / "root").mkdir()
            with bw.BlenderWorker(LIVE_BLENDER, Path(tmp) / "root") as worker:
                worker.call("open", blend=str(damaged), allow_edit=["Badge"])
                before = worker.compare_to(str(clean))
                worker.call("apply_edit", object="Badge", op="material", value={"slot": 0, "material": "BadgeGreen"},
                            expect_checksum=before["current_checksum"])
                after = worker.compare_to(str(clean))
        self.assertFalse(before["matches_reference"])
        self.assertIn("Badge: materials ['BadgeGreen'] -> ['BodyTextured']", before["structural_differences"])
        self.assertIn("material BadgeGreen -> BodyTextured on Badge", before["localisation"])
        self.assertTrue(after["matches_reference"])
        self.assertEqual((after["structural_differences"], after["localisation"]), ([], []))


if __name__ == "__main__":
    unittest.main()
