import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_repair_bench as bench
import blender_worker as bw

MANIFEST = json.loads((ROOT / "tests" / "fixtures" / "blender_lab" / "manifest-lab-asset-5.4.0-alpha-67c9bdddb88b.json").read_text(encoding="utf-8"))
LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


def obj(manifest, name): return next(o for o in manifest["objects"] if o["name"] == name)


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
                (Path(tmp) / name).mkdir()
                (Path(tmp) / name / "repair-bench.json").write_text(json.dumps({"agent": "a", "rows": rows}))
            report = bench.combine([Path(tmp) / "first", Path(tmp) / "rerun"], Path(tmp) / "out.json")
        self.assertEqual(report["outcomes"], {"exact repair": 1, "declined (correct)": 1})
        self.assertEqual((report["repairable_exact"], report["infrastructure_failures_retried"]), (1, 1))


class FailureAndTreeTests(unittest.TestCase):
    def test_a_crashed_or_garbled_agent_is_not_a_decline(self):
        base = {"saved": False, "exact": False, "remaining": ["x"], "collateral": []}
        self.assertEqual(bench.outcome("mesh-hole", {**base, "returncode": 1, "verdict_ok": True}), "agent failure (no valid verdict)")
        self.assertEqual(bench.outcome("mesh-hole", {**base, "returncode": 0, "verdict_ok": False}), "agent failure (no valid verdict)")
        self.assertEqual(bench.outcome("mesh-hole", {**base, "returncode": 0, "verdict_ok": True}), "declined (correct)")

    def test_timeout_kills_the_whole_process_tree(self):
        import subprocess, time
        with tempfile.TemporaryDirectory() as tmp:
            pid_file = Path(tmp) / "child.pid"
            spawn = (f"import subprocess, sys, time; c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                     f"open(r'{pid_file}', 'w').write(str(c.pid)); time.sleep(60)")
            with self.assertRaises(subprocess.TimeoutExpired):
                bench.run_tree([sys.executable, "-c", spawn], input="", cwd=tmp, env=None, timeout=3)
            child = int(pid_file.read_text())
            time.sleep(1)
            alive = subprocess.run(["tasklist", "/FI", f"PID eq {child}"], capture_output=True, text=True).stdout if os.name == "nt" else ""
            self.assertNotIn(str(child), alive)


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
