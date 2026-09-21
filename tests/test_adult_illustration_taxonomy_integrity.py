"""Cross-layer namespace and bounded-relationship regression tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_prompt_membership import inspect_prompt_membership
from studio_prompt.adult_illustration_prompt_projection import compile_prompt
from studio_prompt.adult_illustration_taxonomy import (
    _acyclic, build_taxonomy_index, lookup_taxonomy,
)
from studio_prompt.adult_illustration_taxonomy_prompt import _validate_graph
from studio_prompt.adult_illustration_taxonomy_contracts import (
    canonical_bytes, load_taxonomy_contracts, sha256,
)
from tests.test_adult_illustration_prompt_membership import write_fixture
from tests.test_adult_illustration_taxonomy import csv_bytes, review_entry, write_contracts


def _rehash(index):
    unsigned = copy.deepcopy(index)
    unsigned.pop("index_id", None)
    index["index_id"] = sha256(canonical_bytes(unsigned))


class TaxonomyNamespaceIntegrityTests(unittest.TestCase):
    def test_reviewed_display_cannot_shadow_an_unreviewed_source_name(self):
        rows = [(1, "solo", 0, 10), (2, "mystery_tag", 0, 9)]
        source = csv_bytes(rows)
        reviewed = review_entry("solo")
        reviewed["display"] = "mystery tag"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_contracts(root, source, rows, [reviewed])
            with self.assertRaisesRegex(ValueError, "display.*colli"):
                build_taxonomy_index(source, root)

    def test_reviewed_display_namespace_is_unique_and_disjoint_from_aliases(self):
        rows = [(1, "solo", 0, 10), (2, "sitting", 0, 9)]
        source = csv_bytes(rows)
        for alias_collision in (False, True):
            with self.subTest(alias_collision=alias_collision), tempfile.TemporaryDirectory() as directory:
                entries = [review_entry("solo"), review_entry("sitting")]
                entries[0]["display"] = "one person"
                if alias_collision:
                    entries[1]["aliases"] = ["one_person"]
                else:
                    entries[1]["display"] = "one_person"
                root = Path(directory)
                write_contracts(root, source, rows, entries)
                with self.assertRaisesRegex(ValueError, "colli"):
                    build_taxonomy_index(source, root)

    def test_rehashed_saved_index_cannot_introduce_a_display_collision(self):
        rows = [(1, "solo", 0, 10), (2, "mystery_tag", 0, 9)]
        source = csv_bytes(rows)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_contracts(root, source, rows, [review_entry("solo")])
            index = build_taxonomy_index(source, root)
        next(entry for entry in index["entries"] if entry["reviewed"])["display"] = "mystery tag"
        _rehash(index)
        with self.assertRaisesRegex(ValueError, "display.*colli"):
            lookup_taxonomy(index, "solo")

    def test_authenticated_report_refuses_compiler_membership_identity_disagreement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, _, index, source = write_fixture(root)
            path = root / "research/adult-illustration/taxonomy-review.json"
            review = json.loads(path.read_text(encoding="utf-8"))
            next(entry for entry in review["entries"] if entry["source_name"] == "solo")["display"] = "mystery tag"
            path.write_text(json.dumps(review), encoding="utf-8")
            next(entry for entry in index["entries"] if entry["source_name"] == "solo")["display"] = "mystery tag"
            index["contracts"]["review_manifest_sha256"] = load_taxonomy_contracts(root)["review"]["manifest_sha256"]
            _rehash(index)
            compiled = compile_prompt(projection, "animagine-xl4-ordered-v1", root)
            # The compiler only loads reviewed terms. It cannot see the source-only
            # canonical occupying this display name; source-backed inspection must.
            resolution = next(item for item in compiled["vocabulary_resolutions"] if item["input"] == "mystery_tag")
            self.assertEqual(resolution["entry_ids"], ["solo"])
            with self.assertRaisesRegex(ValueError, "display.*colli"):
                inspect_prompt_membership(compiled, projection, index, source, root)

    def test_unique_display_and_own_normalised_canonical_remain_valid(self):
        rows = [(1, "solo", 0, 10), (2, "sitting", 0, 9)]
        source = csv_bytes(rows)
        entries = [review_entry("solo"), review_entry("sitting")]
        entries[0]["display"] = "single figure"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_contracts(root, source, rows, entries)
            index = build_taxonomy_index(source, root)
        self.assertEqual(lookup_taxonomy(index, "SOLO")["source_name"], "solo")
        self.assertEqual(index["counts"]["accepted"], 2)


class TaxonomyRelationshipBudgetTests(unittest.TestCase):
    def test_long_chains_refuse_at_contract_depth_before_python_recursion_limit(self):
        graph = {f"n{i:05}": [f"n{i + 1:05}"] for i in range(2000)}
        for validator in (_acyclic, _validate_graph):
            with self.subTest(validator=validator.__name__):
                with self.assertRaisesRegex(ValueError, "exceeds depth 8"):
                    validator(graph, "implication", 8)

    def test_cached_subtree_does_not_hide_the_longest_relationship_path(self):
        graph = {"a": [], "b": ["a"], "c": ["b"], "z": ["c"]}
        for validator in (_acyclic, _validate_graph):
            with self.subTest(validator=validator.__name__):
                with self.assertRaisesRegex(ValueError, "exceeds depth 3"):
                    validator(graph, "deprecation", 3)
                validator(graph, "deprecation", 4)

    def test_shared_tail_and_short_cycles_have_stable_outcomes(self):
        for validator in (_acyclic, _validate_graph):
            with self.subTest(validator=validator.__name__):
                validator({"a": ["b", "c"], "b": ["d"], "c": ["d"]}, "implication", 3)
                with self.assertRaisesRegex(ValueError, "cycle"):
                    validator({"a": ["b"], "b": ["a"]}, "implication", 8)


if __name__ == "__main__":
    unittest.main()
