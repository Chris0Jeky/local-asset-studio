from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from studio_prompt import adult_illustration_research as research
from tests.test_adult_illustration_research import write_fixture


class AdultIllustrationResearchReviewRegressions(unittest.TestCase):
    def make_root(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        write_fixture(root)
        return root

    def test_oversized_manifest_is_refused_before_read_bytes(self) -> None:
        root = self.make_root()
        path = root / "research" / "adult-illustration" / "route-candidates.json"
        with path.open("wb") as stream:
            stream.seek(research.MAX_MANIFEST_BYTES)
            stream.write(b"\0")

        with mock.patch.object(
            Path,
            "read_bytes",
            side_effect=AssertionError("oversized manifest was read"),
        ):
            with self.assertRaisesRegex(ValueError, "exceeds.*bytes"):
                research.list_records(root, "routes")

    def test_comparison_plan_surfaces_moving_technique_revision(self) -> None:
        root = self.make_root()
        plan = research.comparison_plan(
            root,
            case_ids=["case-a"],
            route_ids=["route-a"],
            technique_ids=["technique-a"],
        )

        self.assertIn(
            "technique technique-a: immutable source revision is unresolved",
            plan["compatibility_gaps"],
        )


if __name__ == "__main__":
    unittest.main()
