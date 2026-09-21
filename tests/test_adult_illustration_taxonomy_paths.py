"""Implication emission requires a path of compilation-eligible reviewed entries."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from studio_prompt.adult_illustration_prompt_projection import (
    compile_prompt, validate_prompt_projection,
)
from studio_prompt.adult_illustration_prompt_membership import inspect_prompt_membership
from studio_prompt.adult_illustration_taxonomy import build_taxonomy_index
from studio_prompt.adult_illustration_taxonomy_contracts import canonical_bytes, sha256
from tests.test_adult_illustration_taxonomy import csv_bytes, review_entry, write_contracts
from tests.test_adult_illustration_taxonomy_prompt_integration import projection_with_terms

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "animagine-xl4-ordered-v1"
HYBRID = "anima-aesthetic-hybrid-v1"


class TaxonomyImplicationPathTests(unittest.TestCase):
    def make_root(self, *, blocked=True, deprecated=False, alternate=False, unordered=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        names = ["pose_seed", "blocked_bridge", "target_leaf", "alternate_path"]
        rows = [(i + 1, name, 0, 20 - i) for i, name in enumerate(names)]
        source = csv_bytes(rows)
        entries = [review_entry(name, profiles=[PROFILE, HYBRID]) for name in names]
        entries[0]["aliases"] = ["seed alias"]
        entries[0]["implications"] = ["blocked_bridge"] + (["alternate_path"] if alternate else [])
        entries[1]["accepted_for_compilation"] = not blocked
        entries[1]["deprecated_by"] = "alternate_path" if deprecated else None
        entries[1]["implications"] = ["target_leaf"]
        entries[3]["implications"] = ["target_leaf"]
        if unordered is not None:
            entries[unordered]["semantic_facets"] = ["pose"]
        write_contracts(root, source, rows, entries)
        path = root / "research/adult-illustration/prompt-profile-vocabulary.json"
        shutil.copyfile(ROOT / "research/adult-illustration/prompt-profile-vocabulary.json", path)
        if unordered is not None:
            catalog = json.loads(path.read_bytes())
            for profile in catalog["profiles"]:
                profile["facet_order"] = [f for f in profile["facet_order"] if f != "pose"]
                profile["facet_sources"] = {k: v for k, v in profile["facet_sources"].items() if v != "pose"}
            path.write_bytes(canonical_bytes(catalog))
        return root, source

    def compile(self, root, terms=None, profile=PROFILE):
        projection = projection_with_terms(terms or ["pose_seed"])
        original = copy.deepcopy(projection)
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            result = compile_prompt(projection, profile, root)
        self.assertEqual(projection, original)
        self.assertTrue(all(value is False for value in result["authority"].values()))
        return projection, result

    def test_rejected_bridge_cannot_emit_descendants_through_canonical_or_alias(self):
        for term in ("pose_seed", "seed alias"):
            for profile in (PROFILE, HYBRID):
                with self.subTest(term=term, profile=profile):
                    root, _ = self.make_root()
                    _, result = self.compile(root, [term], profile)
                    trace = result["vocabulary_resolutions"][0]
                    self.assertEqual(trace["entry_ids"], ["pose_seed", "blocked_bridge"])
                    self.assertEqual(trace["emitted"], ["pose_seed" if profile == PROFILE else "pose seed"])
                    self.assertEqual(trace["status"], "partially_emitted")
                    self.assertNotIn("target", result["channels"]["positive"])
                    self.assertIn("TAXONOMY_IMPLICATION_NOT_ACCEPTED", {d["code"] for d in result["diagnostics"]})

    def test_deprecated_bridge_does_not_reactivate_its_descendants_or_replacement(self):
        root, _ = self.make_root(deprecated=True)
        _, result = self.compile(root)
        trace = result["vocabulary_resolutions"][0]
        self.assertEqual(trace["entry_ids"], ["pose_seed", "blocked_bridge"])
        self.assertEqual(trace["emitted"], ["pose_seed"])
        self.assertNotIn("alternate_path", trace["entry_ids"])

    def test_unordered_entry_stops_traversal_even_when_accepted(self):
        for index in (0, 1):
            with self.subTest(index=index):
                root, _ = self.make_root(blocked=False, unordered=index)
                _, result = self.compile(root)
                trace = result["vocabulary_resolutions"][0]
                self.assertEqual(trace["entry_ids"], ["pose_seed"] if index == 0 else ["pose_seed", "blocked_bridge"])
                self.assertEqual(trace["emitted"], [] if index == 0 else ["pose_seed"])
                self.assertIn("TAXONOMY_UNORDERED_FOR_PROFILE", {d["code"] for d in result["diagnostics"]})

    def test_eligible_alternate_path_reaches_a_shared_descendant_in_its_own_order(self):
        root, _ = self.make_root(alternate=True)
        projection, result = self.compile(root)
        trace = result["vocabulary_resolutions"][0]
        self.assertEqual(trace["entry_ids"], ["pose_seed", "blocked_bridge", "alternate_path", "target_leaf"])
        self.assertEqual(trace["emitted"], ["pose_seed", "alternate_path", "target_leaf"])
        self.assertEqual(validate_prompt_projection(result, projection, root), result)

    def test_separate_direct_input_can_still_select_an_eligible_descendant(self):
        root, _ = self.make_root()
        _, result = self.compile(root, ["seed alias", "target_leaf"])
        first, second = result["vocabulary_resolutions"][:2]
        self.assertEqual(first["entry_ids"], ["pose_seed", "blocked_bridge"])
        self.assertEqual(first["emitted"], ["pose_seed"])
        self.assertEqual(second["entry_ids"], ["target_leaf"])
        self.assertEqual(second["emitted"], ["target_leaf"])

    def test_eligible_diamond_keeps_original_depth_first_order_and_shared_tail_once(self):
        root, _ = self.make_root(blocked=False, alternate=True)
        _, result = self.compile(root)
        trace = result["vocabulary_resolutions"][0]
        self.assertEqual(trace["entry_ids"], ["pose_seed", "blocked_bridge", "target_leaf", "alternate_path"])
        self.assertEqual(trace["emitted"], trace["entry_ids"])
        self.assertEqual(trace["status"], "emitted")

    def test_source_authenticated_membership_preserves_the_pruned_compiler_trace(self):
        root, source = self.make_root()
        projection, compiled = self.compile(root)
        index = build_taxonomy_index(source, root)
        report = inspect_prompt_membership(compiled, projection, index, source, root)
        self.assertTrue(report["taxonomy"]["source_revalidated"])
        self.assertEqual(report["inspections"][0]["compiler"]["entry_ids"], ["pose_seed", "blocked_bridge"])
        changed = copy.deepcopy(compiled)
        changed["vocabulary_resolutions"][0]["emitted"].append("target_leaf")
        changed.pop("compiled_sha256")
        changed["compiled_sha256"] = sha256(canonical_bytes(changed))
        with self.assertRaisesRegex(ValueError, "Changed or invalid"):
            inspect_prompt_membership(changed, projection, index, source, root)


if __name__ == "__main__":
    unittest.main()
