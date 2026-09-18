"""Contracts for workshop evidence fidelity from issue #599."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import workshop_browser_core as core  # noqa: E402


class WorkshopEvidenceHardeningTests(unittest.TestCase):
    def test_core_driver_resolves_the_production_css_without_wrapper_patch(self):
        css = core.immersive_css()
        self.assertNotIn("@import", css)
        self.assertIn(".wk-immersive-hero", css)
        self.assertEqual(css.count("data:image/svg+xml;base64,"), 2)

    def test_geometry_cases_cover_none_and_night_shift_for_every_layout(self):
        cases = core.presentation_geometry_cases(
            layouts=["focus", "studio", "immersive"],
            skins=["atelier"],
            widths=[(390, 844)],
        )
        observed = {(case["layout"], case["ambience"]) for case in cases}
        self.assertEqual(
            observed,
            {
                ("focus", "none"),
                ("focus", "night-shift"),
                ("studio", "none"),
                ("studio", "night-shift"),
                ("immersive", "none"),
                ("immersive", "night-shift"),
            },
        )

    def test_both_browser_drivers_use_shared_geometry_and_page_observers(self):
        core_source = (ROOT / "tests/workshop_browser_core.py").read_text(encoding="utf-8")
        application_source = (ROOT / "tests/workshop_application.py").read_text(encoding="utf-8")
        self.assertIn("attach_page_observers(", core_source)
        self.assertGreaterEqual(core_source.count("attach_page_observers("), 3)
        self.assertIn("presentation_geometry_cases(", core_source)
        self.assertIn("presentation_geometry_cases(", application_source)

    def test_docs_do_not_claim_zero_gap_or_classify_css_as_an_asset(self):
        design = (ROOT / "docs/workshop/DESIGN.md").read_text(encoding="utf-8")
        assets = (ROOT / "docs/workshop/ASSETS.md").read_text(encoding="utf-8")
        self.assertNotIn("without leaving a layout gap", design)
        self.assertNotIn(
            "| `app/static/workshop-immersive-core.css` | Production poster renditions |",
            assets,
        )


if __name__ == "__main__":
    unittest.main()
