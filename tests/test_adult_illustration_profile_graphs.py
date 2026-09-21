"""Bounded profile vocabulary graphs must not depend on Python recursion depth."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt.adult_illustration_prompt_catalog import load_catalog
from studio_prompt.adult_illustration_prompt_projection import compile_prompt, validate_prompt_projection
from tests.test_adult_illustration_taxonomy_prompt_integration import (
    projection_with_terms, write_contract_root,
)

PROFILE = "animagine-xl4-ordered-v1"
CHAIN_LENGTH = 1200  # Below MAX_ENTRIES and the serialized manifest/output caps.


def entry(number: int, targets: list[int]) -> dict:
    return {
        "id": f"entry-{number:04}", "canonical": f"term{number:04}",
        "aliases": [], "implications": [f"entry-{n:04}" for n in targets],
        "facet": "style", "polarity": "positive", "profile_ids": [PROFILE],
    }


def chain(length: int) -> list[dict]:
    return [entry(n, [n + 1] if n + 1 < length else []) for n in range(length)]


class ProfileVocabularyGraphTests(unittest.TestCase):
    def make_root(self, entries: list[dict]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = write_contract_root(Path(directory.name))
        path = root / "research/adult-illustration/prompt-profile-vocabulary.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["entries"] = entries
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertLess(path.stat().st_size, 1_048_576)
        return root

    def compile_chain(self, reverse: bool) -> None:
        entries = chain(CHAIN_LENGTH)
        root = self.make_root(list(reversed(entries)) if reverse else entries)
        projection = projection_with_terms(["term0000"])
        original = copy.deepcopy(projection)
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            result = compile_prompt(projection, PROFILE, root)
        trace = result["vocabulary_resolutions"][0]
        self.assertEqual(trace["entry_ids"], [e["id"] for e in entries])
        self.assertEqual(trace["emitted"], [e["canonical"] for e in entries])
        self.assertEqual(trace["status"], "emitted")
        actual_terms = result["channels"]["positive"].split(", ")
        self.assertEqual(actual_terms[:CHAIN_LENGTH], [e["canonical"] for e in entries])
        self.assertEqual(projection, original)
        self.assertTrue(all(value is False for value in result["authority"].values()))
        self.assertEqual(validate_prompt_projection(result, projection, root), result)

    def test_forward_chain_loads_and_compiles_without_call_stack_limit(self):
        self.compile_chain(reverse=False)

    def test_reverse_order_chain_also_compiles_without_call_stack_limit(self):
        # Parent validation can reuse visited tails in this order; its compiler
        # still recursively expands the chain and independently overflows.
        self.compile_chain(reverse=True)

    def test_long_cycle_is_a_validation_error_not_a_recursion_crash(self):
        entries = chain(CHAIN_LENGTH)
        entries[-1]["implications"] = [entries[0]["id"]]
        with self.assertRaisesRegex(ValueError, "implication cycle"):
            load_catalog(self.make_root(entries))

    def test_diamond_preserves_depth_first_order_and_deduplicates_shared_tail(self):
        entries = [entry(0, [1, 2]), entry(1, [3]), entry(2, [3]), entry(3, [])]
        result = compile_prompt(projection_with_terms(["term0000"]), PROFILE, self.make_root(entries))
        trace = result["vocabulary_resolutions"][0]
        self.assertEqual(trace["entry_ids"], ["entry-0000", "entry-0001", "entry-0003", "entry-0002"])
        self.assertEqual(trace["emitted"], ["term0000", "term0001", "term0003", "term0002"])

    def test_disconnected_cycle_is_not_hidden_by_an_acyclic_component(self):
        entries = [entry(0, [1]), entry(1, []), entry(2, [3]), entry(3, [2])]
        with self.assertRaisesRegex(ValueError, "implication cycle"):
            load_catalog(self.make_root(entries))

    def test_relationship_semantic_guards_remain_strict(self):
        for mutation, expected in (("missing", "unknown vocabulary"), ("polarity", "polarity mismatch"), ("profile", "profile mismatch")):
            with self.subTest(mutation=mutation):
                entries = chain(2)
                if mutation == "missing":
                    entries[0]["implications"] = ["absent"]
                elif mutation == "polarity":
                    entries[1]["polarity"] = "negative"
                else:
                    entries[1]["profile_ids"] = ["anima-aesthetic-hybrid-v1"]
                with self.assertRaisesRegex(ValueError, expected):
                    load_catalog(self.make_root(entries))


if __name__ == "__main__":
    unittest.main()
