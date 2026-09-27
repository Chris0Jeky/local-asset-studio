"""Owner backlog parsing counts explicit open items, not unrelated checklists."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import repository_snapshot as snapshot


ROOT = Path(__file__).resolve().parents[1]


class OwnerDecisionFactsTests(unittest.TestCase):
    def facts(self, text):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "HUMAN_TODO.md").write_text(text, encoding="utf-8")
            return snapshot.human_todo_facts(root)

    def test_open_headings_accept_dash_and_current_status_variants(self):
        for separator in ("-", "\u2013", "\u2014"):
            for status in (" (open).", " (open)", " (open; reworded at the owner's request).",
                           ": open.", ": open (kept open by the owner)."):
                with self.subTest(separator=separator, status=status):
                    text = f"**q-25 {separator} Review the pack{status}** Details.\n"
                    result = self.facts(text)
                    self.assertEqual(result["items"], [{"id": "q-25", "text": "Review the pack"}])
                    self.assertEqual(result["open_count"], 1)
                    self.assertEqual(result["blob_sha"], snapshot._git_blob_sha(text.encode("utf-8")))

    def test_only_explicit_named_owner_checkboxes_count(self):
        text = ("**q-6 - Review: answered by the owner.** Historical text.\n"
                "- [ ] Follow-up within the answered item\n"
                "- [ ] A generic release checklist item\n"
                "- [ ] **release-build**: Not labelled as owner work\n"
                "- [ ] **asset-wave-1** (owner action): Save candidate files\n"
                "- [ ] **asset-plan** (owner decisions; agents do not tick this): Choose a world\n"
                "- [x] **finished** (owner decision): Already answered\n")
        result = self.facts(text)
        self.assertEqual(result["open_count"], 2)
        self.assertEqual(result["items"], [
            {"id": "asset-wave-1", "text": "Save candidate files"},
            {"id": "asset-plan", "text": "Choose a world"},
        ])

    def test_examples_nested_checklists_and_answered_headings_do_not_count(self):
        for fence in ("```", "~~~~"):
            with self.subTest(fence=fence):
                text = (f"{fence}markdown\n**q-90 - Example (open).**\n"
                        "- [ ] **example** (owner action): Not a live item\n"
                        f"{fence}\n"
                        "**q-91 - Review: answered.** Previously (open).\n"
                        "  - [ ] **nested** (owner action): Part of the answered item\n"
                        "**q-92 - Real choice (open).**\n")
                self.assertEqual(self.facts(text)["items"], [{"id": "q-92", "text": "Real choice"}])

    def test_repeated_open_identity_is_counted_once_in_document_order(self):
        text = ("**q-25 - Review (open).**\n"
                "- [ ] **q-25** (owner decision): Same item repeated\n"
                "**q-25 - Review (open).**\n"
                "**q-26 - Next choice (open).**\n")
        self.assertEqual(self.facts(text)["items"], [
            {"id": "q-25", "text": "Review"}, {"id": "q-26", "text": "Next choice"},
        ])

    def test_issue_form_omits_an_empty_default_title(self):
        form = (ROOT / ".github/ISSUE_TEMPLATE/work-item.yml").read_text(encoding="utf-8")
        self.assertNotRegex(form, r'(?m)^title:\s*(?:""|\'\')\s*$')


if __name__ == "__main__":
    unittest.main()
