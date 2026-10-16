"""A sharded lifetime run covers every discovered module exactly once."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wrapper = load("lifetime_wrapper_shard", HERE / "check_full_suite_lifetime.py")
worker = load("lifetime_worker_shard", HERE / "full_suite_lifetime_worker.py")


class Case(unittest.TestCase):
    """A weight-one placeholder; no test method, so discovery collects nothing here."""


def module_suite(tests):
    return unittest.TestSuite([unittest.TestSuite(Case() for _ in range(tests))])


class ShardSelectionTests(unittest.TestCase):
    def test_parse_accepts_only_an_index_within_the_count(self):
        self.assertEqual(worker.parse_shard("2/3"), (2, 3))
        for bad in ("0/3", "4/3", "3", "a/b", "1/0", "-1/2"):
            with self.subTest(bad=bad), self.assertRaises(argparse.ArgumentTypeError):
                worker.parse_shard(bad)

    def test_shards_are_disjoint_complete_whole_modules_and_balanced(self):
        sizes = [40, 3, 17, 17, 1, 0, 25, 9, 9, 12, 30, 2]
        modules = [module_suite(size) for size in sizes]
        for count in (1, 2, 3, 5):
            with self.subTest(count=count):
                picked = []
                for index in range(1, count + 1):
                    first = list(worker.select_shard(unittest.TestSuite(modules), index, count))
                    again = list(worker.select_shard(unittest.TestSuite(modules), index, count))
                    self.assertEqual([id(m) for m in first], [id(m) for m in again])
                    # Discovery order is kept inside a shard.
                    self.assertEqual(first, sorted(first, key=modules.index))
                    picked.append(first)
                flat = [id(module) for shard in picked for module in shard]
                self.assertCountEqual(flat, [id(module) for module in modules])
                loads = [sum(module.countTestCases() for module in shard) for shard in picked]
                self.assertLessEqual(max(loads) - min(loads), max(sizes))

    def test_shards_balance_recorded_seconds_not_test_count(self):
        def named(module, tests):
            return unittest.TestSuite([unittest.TestSuite(type("C", (Case,), {"__module__": module})() for _ in range(tests))])
        # Weights: many 10 s, few 0.2 s, each slow module 100 s, and the unrecorded module
        # 60 x the recorded mean (210.2 s / 104 tests) = 121.3 s. Count balancing would give
        # [many] and [the rest]; a flat 1 s for unrecorded tests would give [slow_a, unrecorded].
        modules = [named("test_many", 100), named("test_few", 2), named("test_slow_a", 1), named("test_slow_b", 1),
                   named("test_unrecorded", 60)]
        seconds = {"test_many": 0.1, "test_few": 0.1, "test_slow_a": 100.0, "test_slow_b": 100.0}
        shards = [list(worker.select_shard(unittest.TestSuite(modules), index, 2, seconds)) for index in (1, 2)]
        self.assertEqual([modules.index(m) for m in shards[0]], [0, 1, 4])
        self.assertEqual([modules.index(m) for m in shards[1]], [2, 3])
        # The committed table is the worker's default and names real modules.
        table = worker.load_shard_seconds()
        self.assertGreater(len(table), 100)
        self.assertTrue(all(name.startswith("test_") and value >= 0 for name, value in table.items()))

    def test_parent_passes_an_explicit_shard_and_scrubs_it_from_the_suite(self):
        self.assertIsNone(wrapper.shard({}))
        self.assertEqual(wrapper.shard({wrapper.SHARD_VARIABLE: " 2/3 "}), "2/3")
        for bad in ("0/3", "4/3", "2", "x/3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                wrapper.shard({wrapper.SHARD_VARIABLE: bad})
        command = wrapper.suite_command(traceback_after=12.5, shard="2/3")
        self.assertEqual(command[command.index("--shard") + 1], "2/3")
        self.assertNotIn("--shard", wrapper.suite_command())
        self.assertNotIn(wrapper.SHARD_VARIABLE, wrapper.child_environment({wrapper.SHARD_VARIABLE: "1/2", "KEEP": "1"}))

    def test_worker_runs_only_its_shard_and_times_each_test(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, tests in (("test_big", 3), ("test_small_a", 1), ("test_small_b", 1)):
                body = "".join(f"    def test_{n}(self):\n        pass\n" for n in range(tests))
                (Path(directory) / f"{name}.py").write_text(
                    "import unittest\n\nclass T(unittest.TestCase):\n" + body, encoding="utf-8")
            outputs = []
            for shard in ("1/2", "2/2"):
                result = subprocess.run(
                    [sys.executable, str(HERE / "full_suite_lifetime_worker.py"), "--start-dir", directory,
                     "--traceback-after", "60", "--shutdown-traceback-after", "5", "--shard", shard],
                    capture_output=True, text=True, timeout=120, cwd=HERE.parent,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outputs.append(result.stderr)
        self.assertIn("LIFETIME SHARD 1/2: 1 modules, 3 tests", outputs[0])
        self.assertIn("LIFETIME SHARD 2/2: 2 modules, 2 tests", outputs[1])
        self.assertIn("START test_big.T.test_0", outputs[0])
        self.assertNotIn("test_big", outputs[1])
        self.assertRegex(outputs[1], r"END test_small_a\.T\.test_0 \d+\.\d{3}s")


if __name__ == "__main__":
    unittest.main()
