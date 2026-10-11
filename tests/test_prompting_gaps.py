import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("asset_prompting_gaps", Path(__file__).parents[1] / "app/prompting.py")
prompting = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(prompting)


class PromptingGapsTests(unittest.TestCase):
    def test_expand_is_deterministic_with_seeded_rng(self):
        text = "a witch, {cool|warm} palette"
        first = prompting.expand(text, random.Random(1234))
        again = prompting.expand(text, random.Random(1234))
        self.assertEqual(first, again)
        self.assertIn(first, ["a witch, cool palette", "a witch, warm palette"])

    def test_expand_resolves_wildcard_nesting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cards = root / "presets/wildcards"
            cards.mkdir(parents=True)
            (cards / "mood.txt").write_text("{serene|stormy} mood\n", encoding="utf-8")
            result = prompting.expand("__mood__ at {dawn|dusk}", random.Random(7), root)
            self.assertNotIn("{", result)
            self.assertNotIn("}", result)
            self.assertNotIn("__", result)
            self.assertTrue(
                result in ("serene mood at dawn", "serene mood at dusk", "stormy mood at dawn", "stormy mood at dusk"),
                f"unexpected nested expansion: {result!r}",
            )

    def test_expand_limit_raises(self):
        with self.assertRaisesRegex(ValueError, "expand past 16000"):
            prompting.expand("x" * 17000, random.Random(0))


if __name__ == "__main__":
    unittest.main()
