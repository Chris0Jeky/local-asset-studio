"""Source-bound contracts for the real Chromium Step-ordering journey."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests" / "workflow_steps_browser.py"


class WorkflowStepOrderEvidenceTests(unittest.TestCase):
    def test_browser_fixture_exercises_a_non_terminal_down_move(self):
        source = BROWSER.read_text(encoding="utf-8")
        self.assertIn(
            "WorkflowStudio.snapshot().steps.length === 3",
            source,
            "The browser fixture must build three Steps so move-down can name a non-null before target",
        )
        self.assertRegex(
            source,
            re.compile(
                r"reordered\s*=\s*\[\s*before_order\[1\]\s*,\s*before_order\[0\]\s*,\s*before_order\[2\]\s*\]"
            ),
            "The journey must require an adjacent one-place reorder inside a three-Step list",
        )

    def test_saved_order_assertion_is_not_the_identity_order(self):
        source = BROWSER.read_text(encoding="utf-8")
        self.assertIn("arg=reordered", source)
        self.assertIn(
            "['id'] for step in studio._workflow_documents.get(original)['document']['steps']] == reordered",
            source,
            "The real SQLite assertion must persist the changed order, not the original fixture order",
        )


if __name__ == "__main__":
    unittest.main()
