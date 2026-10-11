import importlib.util
import random
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("asset_prompting_wildcards", Path(__file__).parents[1] / "app/prompting.py")
prompting = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(prompting)


class PromptingWildcardRunawayTests(unittest.TestCase):
    def test_expand_rejects_runaway(self):
        """A choice input whose expansion stays past LIMIT must raise, not return a runaway string."""
        text = "x" * 16000 + "{a|b}"
        with self.assertRaisesRegex(ValueError, "past 16000"):
            prompting.expand(text, random.Random(0))

    def test_normal_choice_expansion_still_passes(self):
        result = prompting.expand("{a|b|c}", random.Random(0))
        self.assertIn(result, ("a", "b", "c"))


if __name__ == "__main__":
    unittest.main()
