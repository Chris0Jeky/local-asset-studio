"""Bound input consumption before zero-authority research planning."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from studio_prompt import adult_illustration_research as research
from tests.test_adult_illustration_research import write_fixture

ROOT = Path(__file__).resolve().parents[1]


class ResearchConsumptionBoundsTests(unittest.TestCase):
    def make_root(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Match production resolution: Windows temp paths can use short aliases.
        root = Path(temporary.name).resolve()
        write_fixture(root)
        return root

    def test_selection_iterators_stop_at_first_excess_item_before_catalog_reads(self):
        limits = {
            "case_ids": research.MAX_CASES,
            "route_ids": research.MAX_ROUTES,
            "dialect_ids": research.MAX_OPTIONAL,
            "technique_ids": research.MAX_OPTIONAL,
        }
        for field, maximum in limits.items():
            with self.subTest(field=field):
                consumed = []

                def guarded_values():
                    for number in range(maximum + 1):
                        consumed.append(number)
                        yield f"candidate-{number}"
                    raise AssertionError("planner consumed beyond its input bound")

                arguments = {"case_ids": ["case-a"], "route_ids": ["route-a"]}
                arguments[field] = guarded_values()
                with mock.patch.object(research._base, "_selected", side_effect=AssertionError("catalog read")):
                    with self.assertRaisesRegex(ValueError, "at most"):
                        research.comparison_plan("unused-root", **arguments)
                self.assertEqual(len(consumed), maximum + 1)

    def test_finite_generators_preserve_exact_plan_identity_and_zero_authority(self):
        root = self.make_root()
        values = {"case_ids": ["case-b", "case-a"], "route_ids": ["route-a"], "technique_ids": ["technique-a"]}
        expected = research.comparison_plan(root, **values)
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            actual = research.comparison_plan(root, **{key: iter(value) for key, value in values.items()})
        self.assertEqual(actual, expected)
        self.assertEqual(actual["authority"], "none")
        self.assertEqual(actual["authorized_candidate_cap"], 0)
        for field in ("execution_authorized", "download_authorized", "install_authorized", "training_authorized", "generation_submitted"):
            self.assertIs(actual[field], False)

    def test_manifest_growth_cannot_turn_a_prechecked_file_into_an_unbounded_read(self):
        root = self.make_root()
        path = root / "research/adult-illustration/route-candidates.json"
        original_open = Path.open
        reads = []

        class Reader:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.handle.close()

            def read(self, size=-1):
                reads.append(size)
                return self.handle.read(size)

        def growing_open(candidate, mode="r", *args, **kwargs):
            if candidate == path and mode == "rb":
                # Real file growth after stat but before the read. No fake JSON
                # parser or mocked allocation limit can make this assertion pass.
                with original_open(candidate, "r+b") as writer:
                    writer.seek(research.MAX_MANIFEST_BYTES + 127)
                    writer.write(b"\0")
                return Reader(original_open(candidate, mode, *args, **kwargs))
            return original_open(candidate, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", growing_open):
            with self.assertRaises(ValueError):
                research.list_records(root, "routes")
        self.assertEqual(reads, [research.MAX_MANIFEST_BYTES + 1])
        self.assertEqual(path.stat().st_size, research.MAX_MANIFEST_BYTES + 128)

    def test_parser_recursion_failure_is_a_structured_validation_error(self):
        root = self.make_root()
        # The decoder's nesting capacity differs between Python versions. Test
        # the error boundary explicitly instead of assuming a fixed native limit.
        failure = RecursionError('fixture: decoder nesting exhausted')
        with mock.patch.object(research.json, 'loads', side_effect=failure):
            with self.assertRaisesRegex(ValueError, "Invalid research manifest") as caught:
                research.list_records(root, "routes")
        self.assertIs(caught.exception.__cause__, failure)

    def test_direct_private_import_enforces_bounds_without_facade(self):
        # The private implementation must be safe when imported alone: no
        # facade import may run first in this fresh process.
        root = self.make_root()
        child = textwrap.dedent("""\
            import sys

            sys.path.insert(0, sys.argv[1])
            fixture_root = sys.argv[2]
            if "studio_prompt.adult_illustration_research" in sys.modules:
                raise AssertionError("public facade was imported before the private impl")
            from studio_prompt import _adult_illustration_research_impl as impl
            if "studio_prompt.adult_illustration_research" in sys.modules:
                raise AssertionError("importing the private impl pulled in the public facade")

            import json
            from pathlib import Path

            failure = RecursionError("fixture: decoder nesting exhausted")
            original_loads = json.loads
            json.loads = lambda *args, **kwargs: (_ for _ in ()).throw(failure)
            try:
                try:
                    impl.list_records(fixture_root, "routes")
                except ValueError as exc:
                    if exc.__cause__ is not failure:
                        raise AssertionError("RecursionError was not preserved as __cause__")
                    if "Invalid research manifest" not in str(exc):
                        raise AssertionError("unexpected message: %r" % (exc,))
                else:
                    raise AssertionError("RecursionError escaped instead of ValueError")
            finally:
                json.loads = original_loads

            path = Path(fixture_root) / "research/adult-illustration/route-candidates.json"
            original_open = Path.open
            reads = []

            class Reader:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.handle.close()

                def read(self, size=-1):
                    reads.append(size)
                    return self.handle.read(size)

            def growing_open(candidate, mode="r", *args, **kwargs):
                if candidate == path and mode == "rb":
                    # Real file growth after stat but before the read.
                    with original_open(candidate, "r+b") as writer:
                        writer.seek(impl.MAX_MANIFEST_BYTES + 127)
                        writer.write(b"\\0")
                    return Reader(original_open(candidate, mode, *args, **kwargs))
                return original_open(candidate, mode, *args, **kwargs)

            Path.open = growing_open
            try:
                try:
                    impl.list_records(fixture_root, "routes")
                except ValueError:
                    pass
                else:
                    raise AssertionError("grown manifest was not refused")
            finally:
                Path.open = original_open
            if reads != [impl.MAX_MANIFEST_BYTES + 1]:
                raise AssertionError("unbounded manifest read: %r" % (reads,))
            print("private-impl bounds ok without facade")
            """)
        completed = subprocess.run(
            [sys.executable, "-", str(ROOT), str(root)],
            input=child,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr[-4000:])
        self.assertIn("private-impl bounds ok without facade", completed.stdout)


if __name__ == "__main__":
    unittest.main()
