"""Reject amplified resolution traces before expanding the remaining inputs."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt import _adult_illustration_prompt_projection_impl as compiler
from tests.test_adult_illustration_profile_graphs import chain, PROFILE
from tests.test_adult_illustration_taxonomy_prompt_integration import (
    projection_with_terms, write_contract_root,
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class PromptExpansionBudgetTests(unittest.TestCase):
    def make_root(self, length=1200, *, negative=False, unicode_terms=False):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = write_contract_root(Path(directory.name))
        entries = chain(length)
        if unicode_terms:
            for number, entry in enumerate(entries):
                entry["canonical"] = "幻想世界" * 5 + f"{number:04}"
        names = [entry["canonical"] for entry in entries]
        if negative:
            negatives = copy.deepcopy(entries)
            for entry in negatives:
                entry["id"] = "negative-" + entry["id"]
                entry["canonical"] = "avoid-" + entry["canonical"]
                entry["implications"] = ["negative-" + target for target in entry["implications"]]
                entry["polarity"] = "negative"
            entries.extend(negatives)
        path = root / "research/adult-illustration/prompt-profile-vocabulary.json"
        document = json.loads(path.read_bytes())
        document["entries"] = entries
        path.write_bytes(encoded(document))
        return root, names

    def first_excess(self, root, tags, avoid=()):
        # A resolution list is a literal subtree of the final JSON artifact.
        # Even ignoring every other field, it cannot exceed the whole budget.
        traces = []
        for negative, terms in ((False, tags), (True, avoid)):
            for term in terms:
                projection = projection_with_terms([] if negative else [term], [term] if negative else [])
                single = compiler.compile_prompt(projection, PROFILE, root)
                traces.extend(single["vocabulary_resolutions"])
                if len(encoded(traces)) > compiler.MAX_OUTPUT_BYTES:
                    return len(traces)
        self.fail("fixture does not exceed the resolution byte budget")

    def test_many_overlapping_chains_stop_at_first_over_budget_trace(self):
        root, names = self.make_root()
        tags = names[:32]
        expected_calls = self.first_excess(root, tags)
        projection = projection_with_terms(tags)
        original = copy.deepcopy(projection)
        with mock.patch.object(compiler, "_entry_closure", wraps=compiler._entry_closure) as expand:
            with self.assertRaisesRegex(ValueError, "128 KiB"):
                compiler.compile_prompt(projection, PROFILE, root)
        self.assertEqual(expand.call_count, expected_calls)
        self.assertLess(expected_calls, len(tags))
        self.assertEqual(projection, original)

    def test_positive_and_negative_inputs_share_one_trace_budget(self):
        root, names = self.make_root(negative=True)
        tags, avoid = names[:3], ["avoid-" + name for name in names[:3]]
        expected_calls = self.first_excess(root, tags, avoid)
        with mock.patch.object(compiler, "_entry_closure", wraps=compiler._entry_closure) as expand:
            with self.assertRaisesRegex(ValueError, "128 KiB"):
                compiler.compile_prompt(projection_with_terms(tags, avoid), PROFILE, root)
        self.assertEqual(expand.call_count, expected_calls)
        self.assertLess(expected_calls, len(tags) + len(avoid))

    def test_trace_budget_counts_utf8_bytes_not_python_characters(self):
        root, names = self.make_root(600, unicode_terms=True)
        tags = names[:12]
        expected_calls = self.first_excess(root, tags)
        with mock.patch.object(compiler, "_entry_closure", wraps=compiler._entry_closure) as expand:
            with self.assertRaisesRegex(ValueError, "128 KiB"):
                compiler.compile_prompt(projection_with_terms(tags), PROFILE, root)
        self.assertEqual(expand.call_count, expected_calls)
        self.assertLess(expected_calls, len(tags))

    def test_complete_artifact_guard_accepts_exact_limit_and_refuses_one_less(self):
        root, names = self.make_root(40)
        projection = projection_with_terms(names[:3])
        expected = compiler.compile_prompt(projection, PROFILE, root)
        size = len(encoded(expected))
        with mock.patch.object(compiler, "MAX_OUTPUT_BYTES", size):
            self.assertEqual(compiler.compile_prompt(projection, PROFILE, root), expected)
        with mock.patch.object(compiler, "MAX_OUTPUT_BYTES", size - 1):
            with self.assertRaisesRegex(ValueError, "128 KiB"):
                compiler.compile_prompt(projection, PROFILE, root)

    def test_refused_expansion_does_not_poison_the_next_plan(self):
        root, names = self.make_root()
        projection = projection_with_terms(names[:1])
        expected = compiler.compile_prompt(projection, PROFILE, root)
        with self.assertRaises(ValueError):
            compiler.compile_prompt(projection_with_terms(names[:32]), PROFILE, root)
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")), mock.patch("subprocess.Popen", side_effect=AssertionError("process")):
            actual = compiler.compile_prompt(projection, PROFILE, root)
        self.assertEqual(actual, expected)
        self.assertTrue(all(value is False for value in actual["authority"].values()))
        self.assertEqual(compiler.validate_prompt_projection(actual, projection, root), actual)


if __name__ == "__main__":
    unittest.main()
