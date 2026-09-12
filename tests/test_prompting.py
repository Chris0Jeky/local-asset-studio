import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("asset_prompting", Path(__file__).parents[1] / "app/prompting.py")
prompting = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(prompting)

class PromptingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        cards = self.root / "presets/wildcards"; cards.mkdir(parents=True)
        (cards / "lighting.txt").write_text("# comment line\nbacklighting\n\n  rim lighting  \ndappled sunlight\n", encoding="utf-8")
        (cards / "mood.txt").write_text("{serene|stormy} mood\n", encoding="utf-8")
    def tearDown(self): self.tmp.cleanup()

    def test_comments_and_blank_lines_are_not_options(self):
        self.assertEqual(prompting.options(self.root, "lighting"), ["backlighting", "rim lighting", "dappled sunlight"])
        self.assertEqual(prompting.options(self.root, "missing"), [])

    def test_wildcard_name_cannot_escape_the_wildcard_folder(self):
        self.assertEqual(prompting.options(self.root, "../catalog"), [])
        self.assertEqual(prompting.options(self.root, "a/b"), [])
        self.assertEqual(prompting.expand("__../catalog__", random.Random("s"), self.root), "__../catalog__")

    def test_expansion_is_deterministic_for_the_same_seed_and_index(self):
        text = "a witch, __lighting__, {cool|warm} palette"
        first = prompting.expand(text, random.Random("281715418:0"), self.root)
        again = prompting.expand(text, random.Random("281715418:0"), self.root)
        batch = [prompting.expand(text, random.Random(f"281715418:{i}"), self.root) for i in range(8)]
        self.assertEqual(first, again)
        self.assertIn(first.split(", ")[1], ["backlighting", "rim lighting", "dappled sunlight"])
        self.assertNotIn("__", first); self.assertNotIn("{", first)
        self.assertGreater(len(set(batch)), 1, "batch members must not all collapse to one expansion")

    def test_nested_alternatives_and_wildcard_bodies_resolve(self):
        result = prompting.expand("{a {red|blue} cloak|plain cloak}, __mood__", random.Random("7:0"), self.root)
        self.assertNotIn("{", result); self.assertNotIn("|", result); self.assertNotIn("__", result)
        self.assertTrue(result.endswith("serene mood") or result.endswith("stormy mood"))

    def test_unknown_wildcard_stays_literal_and_non_text_passes_through(self):
        self.assertEqual(prompting.expand("keep __nosuch__ here", random.Random("1:0"), self.root), "keep __nosuch__ here")
        self.assertEqual(prompting.expand(7, random.Random("1:0"), self.root), 7)
        self.assertFalse(prompting.has_wildcards("plain prompt")); self.assertTrue(prompting.has_wildcards("{a|b}"))

    def test_depth_is_bounded(self):
        cards = self.root / "presets/wildcards"; (cards / "loop.txt").write_text("__loop__\n", encoding="utf-8")
        self.assertEqual(prompting.expand("__loop__", random.Random("1:0"), self.root), "__loop__")

if __name__ == "__main__": unittest.main()
