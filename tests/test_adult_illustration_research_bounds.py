"""Bound input consumption before zero-authority research planning."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from studio_prompt import adult_illustration_research as research
from tests.test_adult_illustration_research import write_fixture


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

    def test_deep_json_refuses_as_a_structured_validation_error(self):
        root = self.make_root()
        path = root / "research/adult-illustration/route-candidates.json"
        path.write_text('{"nested":' + '[' * 10000 + '0' + ']' * 10000 + '}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid research manifest"):
            research.list_records(root, "routes")


if __name__ == "__main__":
    unittest.main()
