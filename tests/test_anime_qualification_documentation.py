"""Operator-facing anime qualification documentation must match shipped contracts."""
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AnimeQualificationDocumentationTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_anima_family_page_names_non_commercial_weight_terms(self) -> None:
        text = self.read("docs/SETTINGS-KNOWLEDGE.md")
        self.assertIn("CircleStone Labs Non-Commercial weights", text)
        self.assertIn("generated-output conditions", text)

    def test_scoped_guidance_schema_includes_source_scope(self) -> None:
        text = self.read("docs/bundle-studio/SCOPED-GUIDANCE.md")
        source = re.search(r'"source": \{(?P<body>.*?)\n  \},', text, re.S)
        self.assertIsNotNone(source)
        self.assertIn('"scope": "unrecorded"', source.group("body"))

    def test_delivered_slices_are_marked_complete(self) -> None:
        text = self.read("docs/strategy/anime-qualification/IMPLEMENTATION.md")
        delivered = text.split("## Slice 0:", 1)[1].split("## Subsequent slices", 1)[0]
        self.assertNotIn("- [ ]", delivered)
        self.assertGreaterEqual(delivered.count("- [x]"), 10)

    def test_architecture_names_the_validated_revision_field(self) -> None:
        text = self.read("docs/strategy/anime-qualification/ARCHITECTURE.md")
        self.assertIn("Specific declarations require a pinned `source.revision` identity", text)
        self.assertNotIn("Specific declarations require a pinned locator identity", text)


if __name__ == "__main__":
    unittest.main()
