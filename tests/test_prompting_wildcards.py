import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "asset_prompting_wildcards", Path(__file__).parents[1] / "app/prompting.py"
)
prompting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prompting)


class PromptingWildcardsTests(unittest.TestCase):
    def test_unknown_wildcard_left_literal(self):
        rng = random.Random(1234)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "presets/wildcards").mkdir(parents=True)
            text = "a __typo_xq__ b"
            self.assertEqual(prompting.expand(text, rng, root), text)

    def test_known_wildcard_expands(self):
        rng = random.Random(1234)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cards = root / "presets/wildcards"
            cards.mkdir(parents=True)
            (cards / "known.txt").write_text("red\n", encoding="utf-8")
            self.assertEqual(prompting.expand("__known__", rng, root), "red")


if __name__ == "__main__":
    unittest.main()
