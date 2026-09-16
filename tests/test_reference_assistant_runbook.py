"""Operator documentation stays portable and avoids stale measured counts."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / 'docs/prompt-studio/REFERENCE-ASSISTANT.md'
AGENT_GUIDE = ROOT / 'CLAUDE.md'


class ReferenceAssistantRunbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RUNBOOK.read_text(encoding='utf-8')

    def test_examples_do_not_embed_one_machine_absolute_path(self):
        self.assertNotIn('C:/AI/', self.text)
        self.assertIn("$Workspace = Join-Path (Get-Location) 'reference-session'", self.text)
        self.assertIn("workspace = Path('reference-session')", self.text)

    def test_default_cache_location_and_opt_out_are_explicit(self):
        self.assertIn('<workspace>/.runtime/prompt-cache/', self.text)
        self.assertIn('--no-cache', self.text)
        self.assertIn('derived local data', self.text)

    def test_agent_test_guidance_uses_live_query_not_stale_module_count(self):
        guide = AGENT_GUIDE.read_text(encoding='utf-8')
        self.assertNotIn('49 of 130 modules', guide)
        self.assertIn('rg "^(from|import) (test_|review_fixture)" tests', guide)
        self.assertIn('stored module count', guide)


if __name__ == '__main__':
    unittest.main()
