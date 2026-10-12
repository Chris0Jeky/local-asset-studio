import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("asset_prompting_wildcards", Path(__file__).parents[1] / "app/prompting.py")
prompting = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(prompting)


class _StubRng:
    def choice(self, seq):
        return seq[0]


class PromptingWildcardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        cards = self.root / "presets/wildcards"; cards.mkdir(parents=True)
        (cards / "known.txt").write_text("red\n", encoding="utf-8")

    def tearDown(self): self.tmp.cleanup()

    def test_unknown_wildcard_stays_literal(self):
        result = prompting.expand("__typo__ __known__", _StubRng(), self.root)
        self.assertIn("__typo__", result)
        self.assertTrue(result.strip() != "")

    def test_unknown_wildcard_left_literal(self):
        empty = Path(self.tmp.name) / "empty-root"
        (empty / "presets/wildcards").mkdir(parents=True)
        self.assertEqual(prompting.expand("__nosuch__ hello", _StubRng(), empty), "__nosuch__ hello")

    def test_over_limit_expansion_raises(self):
        big = "y" * (prompting.LIMIT + 1)
        text = "{" + big + "|" + big + "}"
        with self.assertRaises(ValueError):
            prompting.expand(text, _StubRng(), self.root)


if __name__ == "__main__": unittest.main()
