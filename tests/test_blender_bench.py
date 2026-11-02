import contextlib, io, json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import blender_bench as bb


class TableTest(unittest.TestCase):
    def test_table_reports_success_and_failure_rows(self):
        ok = {"blender_exe": "C:/b/blender.exe", "blender": "5.4.0 Alpha", "engine": "cycles", "device": "HIPRT",
              "gpu_backend": None, "times": [6.1, 5.6, 5.5, 5.5, 5.6, 5.4, 5.5, 5.6], "hashes": ["ab" * 32] * 8,
              "cold_s": 6.1, "warm_median_s": 5.5, "warm_min_s": 5.4, "warm_max_s": 5.6, "setup_s": 0.1,
              "peak_private_mb": 1883, "vram_peak_over_baseline_mb": 3271, "timed_hashes_identical": False,
              "repeat_max_abs_diff": 1, "info": {}}
        bad = {"blender_exe": "C:/old/blender.exe", "engine": "eevee", "device": None, "gpu_backend": "vulkan",
               "exit_code": "no result"}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bench.jsonl"; p.write_text(json.dumps(ok) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out): bb.table(p)
        lines = out.getvalue().splitlines()
        self.assertIn("| 5.4.0 Alpha | cycles | HIPRT | 6.1 | 5.5 (5.4-5.6) |", lines[2])
        self.assertTrue(lines[2].rstrip().endswith("| 1 | abababababab |"))
        self.assertIn("| old | eevee | vulkan | failed (exit no result) |", lines[3])
        lines[0].encode("cp1252")  # the header must print on a default Windows console


class SummariseTest(unittest.TestCase):
    def frames(self, d, values):
        from PIL import Image
        for i, v in enumerate(values): Image.new("RGB", (4, 4), (v, v, v)).save(Path(d) / f"r{i:02d}.png")

    def test_result_counts_only_with_exit_code_zero(self):
        res = {"times": [2.0, 1.0, 1.0, 1.0, 1.0], "setup_s": 0.1, "info": {}}
        with tempfile.TemporaryDirectory() as d:
            self.frames(d, [10, 10, 10, 10, 13])
            ok = bb.summarise(res, 0, [], d, warmup=1)
            crashed = bb.summarise(res, 3221225477, ["BENCH_RESULT ...\n", "access violation\n"], d, warmup=1)
        self.assertEqual((ok["cold_s"], ok["warm_median_s"], ok["repeat_max_abs_diff"]), (2.0, 1.0, 3))
        self.assertFalse(ok["timed_hashes_identical"])
        self.assertNotIn("times", crashed); self.assertEqual(crashed["exit_code"], 3221225477)
        self.assertIn("access violation", crashed["log_tail"])
        self.assertEqual(bb.summarise(None, 0, ["Traceback\n"], ".", warmup=2)["exit_code"], "no result")


if __name__ == "__main__":
    unittest.main()
