from __future__ import annotations

import inspect
from pathlib import Path
import tempfile
import unittest

from tests import studio_use_cases as runner


class LiveValueSelectionTests(unittest.TestCase):
    def test_preferred_fixture_value_wins_when_live_dom_contains_it(self) -> None:
        self.assertEqual(
            runner.choose_live_value(["newest", "asset-1", "older"], "asset-1"),
            "asset-1",
        )

    def test_first_rendered_value_is_used_when_fixture_id_is_absent(self) -> None:
        self.assertEqual(
            runner.choose_live_value(["newest-live", "older-live"], "asset-1"),
            "newest-live",
        )

    def test_blank_duplicate_and_non_text_values_are_ignored(self) -> None:
        self.assertEqual(
            runner.choose_live_value(["", "  ", None, "newest", "newest", "older"]),
            "newest",
        )

    def test_no_rendered_value_returns_none(self) -> None:
        self.assertIsNone(runner.choose_live_value(["", None, "   "]))


class LiveSkipAccountingTests(unittest.TestCase):
    def test_named_live_skip_is_not_a_failure_or_dead_end(self) -> None:
        case_id = "live-prerequisite-test"
        previous = runner.DRIVERS.get(case_id)

        def skip_driver(case):
            case.skip("no Workspace image asset")

        runner.DRIVERS[case_id] = skip_driver
        spec = {
            "id": case_id,
            "goal": "Exercise one synthetic live prerequisite.",
            "starting_view": "assets",
            "success_condition": "The unavailable prerequisite is named without a false UI failure.",
            "steps": [],
        }
        try:
            with tempfile.TemporaryDirectory() as temporary:
                row = runner.run_case(
                    spec,
                    object(),
                    "http://127.0.0.1:8191",
                    True,
                    Path(temporary),
                )
        finally:
            if previous is None:
                runner.DRIVERS.pop(case_id, None)
            else:
                runner.DRIVERS[case_id] = previous

        self.assertFalse(row["passed"])
        self.assertTrue(row["skipped"])
        self.assertEqual(row["skip_reason"], "no Workspace image asset")
        self.assertEqual(row["failure"], "")
        self.assertEqual(row["dead_ends"], 0)
        self.assertEqual(row["steps_taken"], 0)
        self.assertEqual(runner.case_result(row), "SKIP")
        self.assertIn("SKIP", runner.table([row]))

    def test_skip_exception_requires_bounded_non_empty_reason(self) -> None:
        with self.assertRaises(ValueError):
            runner.LiveCaseSkip("")
        with self.assertRaises(ValueError):
            runner.LiveCaseSkip("x" * 501)
        self.assertEqual(str(runner.LiveCaseSkip("no reviewable study")), "no reviewable study")


class DriverBoundaryTests(unittest.TestCase):
    def test_data_backed_drivers_resolve_current_live_values(self) -> None:
        for driver in (
            runner._one_reference,
            runner._three_references,
            runner._review,
            runner._reuse,
            runner._native_export,
        ):
            with self.subTest(driver=driver.__name__):
                self.assertIn("live_data_selector", inspect.getsource(driver))

    def test_output_and_capability_drivers_guard_live_prerequisites(self) -> None:
        for driver in (
            runner._compare,
            runner._restyle,
            runner._combine,
            runner._draw_pose,
            runner._workflow,
        ):
            with self.subTest(driver=driver.__name__):
                source = inspect.getsource(driver)
                self.assertTrue(
                    "require_live" in source or "c.skip(" in source,
                    f"{driver.__name__} must stop with a named live prerequisite",
                )

    def test_live_drivers_do_not_compare_lineage_to_fixture_asset_id(self) -> None:
        source = inspect.getsource(runner._reuse)
        self.assertNotIn("lineage == 'asset-1'", source)
        self.assertIn("selected_asset", source)


if __name__ == "__main__":
    unittest.main()
