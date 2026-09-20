"""Keep planning diagnostics bound to the manifest bytes that were hashed."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt import adult_illustration_research as research
from tests.test_adult_illustration_research import write_fixture

TECHNIQUES = "technique-candidates.json"
GAP = "technique technique-a: immutable source revision is unresolved"


class ResearchCapturedEvidenceTests(unittest.TestCase):
    def make_root(self, revision="a" * 40):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        write_fixture(root)
        # Golden identities bind bytes: keep synthetic fixtures LF on every OS.
        for path in (root / "research/adult-illustration").glob("*.json"):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        self.set_revision(root, revision)
        return root

    def set_revision(self, root, revision):
        path = root / "research/adult-illustration" / TECHNIQUES
        value = json.loads(path.read_text(encoding="utf-8"))
        value["candidates"][0]["source_revision"] = revision
        path.write_text(json.dumps(value), encoding="utf-8")

    def plan(self, root):
        return research.comparison_plan(
            root, case_ids=["case-a"], route_ids=["route-a"],
            technique_ids=["technique-a"],
        )

    def test_changed_revision_cannot_change_gaps_under_an_older_manifest_hash(self):
        for initial, replacement in (("a" * 40, "main"), ("main", "a" * 40)):
            with self.subTest(initial=initial):
                root = self.make_root(initial)
                expected = self.plan(root)
                original = research._base._read_manifest
                captures = []

                def change_after_capture(directory, filename):
                    document, digest = original(directory, filename)
                    if filename == TECHNIQUES:
                        captures.append(digest)
                        if len(captures) == 1:
                            self.set_revision(root, replacement)
                    return document, digest

                with mock.patch.object(research._base, "_read_manifest", change_after_capture):
                    actual = self.plan(root)
                self.assertEqual(actual, expected)
                self.assertEqual(captures, [expected["input_manifests"]["techniques"]])
                newer = self.plan(root)
                self.assertNotEqual(newer["plan_id"], actual["plan_id"])
                self.assertNotEqual(newer["input_manifests"], actual["input_manifests"])
                self.assertEqual(GAP in newer["compatibility_gaps"], replacement == "main")
                self.assertIs(actual["stale_when_any_input_manifest_changes"], True)

    def test_each_catalog_is_captured_once_even_with_no_optional_selection(self):
        root = self.make_root()
        for selected in ([], ["technique-a"]):
            with self.subTest(selected=selected):
                with mock.patch.object(research._base, "_read_manifest", wraps=research._base._read_manifest) as read:
                    result = research.comparison_plan(
                        root, case_ids=["case-a"], route_ids=["route-a"],
                        technique_ids=selected,
                    )
                self.assertEqual(Counter(call.args[1] for call in read.call_args_list), {
                    "benchmark-corpus.json": 1, "route-candidates.json": 1,
                    "prompt-dialects.json": 1, TECHNIQUES: 1, "control-ontology.json": 1,
                })
                self.assertEqual(result["techniques"], selected)

    def test_deletion_after_capture_does_not_trigger_a_second_evidence_read(self):
        root = self.make_root()
        expected = self.plan(root)
        original = research._base._read_manifest

        def delete_after_capture(directory, filename):
            captured = original(directory, filename)
            if filename == TECHNIQUES:
                (root / "research/adult-illustration" / filename).unlink()
            return captured

        with mock.patch.object(research._base, "_read_manifest", delete_after_capture):
            actual = self.plan(root)
        self.assertEqual(actual, expected)
        with self.assertRaises(FileNotFoundError):
            self.plan(root)

    def test_nested_plans_do_not_share_a_mutable_capture(self):
        root = self.make_root()
        expected = self.plan(root)
        original = research._base._read_manifest
        nested = []
        started = False

        def nested_after_capture(directory, filename):
            nonlocal started
            captured = original(directory, filename)
            if filename == TECHNIQUES and not started:
                started = True
                self.set_revision(root, "main")
                nested.append(self.plan(root))
            return captured

        with mock.patch.object(research._base, "_read_manifest", nested_after_capture):
            actual = self.plan(root)
        self.assertEqual(actual, expected)
        self.assertEqual(len(nested), 1)
        self.assertIn(GAP, nested[0]["compatibility_gaps"])
        self.assertNotEqual(nested[0]["input_manifests"], actual["input_manifests"])

    def test_unchanged_manifests_preserve_existing_plan_identities(self):
        expected = {
            "a" * 40: "2f5b827de1be84140649963b5575cbb3dac8766beb4b79994fa8538e4c6c53f3",
            "main": "8255b17587531aa252ca60e0df8cca20ae6d0a69fef0ce59c21dfb96d4b156e3",
            None: "6990ec66425c2ed47fdb9d2c8f29ed762b04484cbda5fad6a9f01e583e94ebab",
            "": "d4f9b19914721c574e4e34b235ce2359414315bb8b612c37f77bb6a2beeb7cb2",
        }
        for revision, digest in expected.items():
            with self.subTest(revision=revision):
                self.assertEqual(self.plan(self.make_root(revision))["plan_id"], digest)

    def test_revision_gaps_keep_the_existing_zero_authority_contract(self):
        for revision in (None, "", "  ", "main", "latest", "a" * 40):
            with self.subTest(revision=revision):
                root = self.make_root(revision)
                with mock.patch("socket.create_connection", side_effect=AssertionError("network")), mock.patch("subprocess.Popen", side_effect=AssertionError("process")):
                    result = self.plan(root)
                self.assertEqual(GAP in result["compatibility_gaps"], revision != "a" * 40)
                unsigned = copy.deepcopy(result)
                unsigned.pop("plan_id")
                self.assertEqual(result["plan_id"], hashlib.sha256(json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest())
                self.assertEqual(result["authorized_candidate_cap"], 0)
                self.assertEqual(result["authority"], "none")
                for field in ("download_authorized", "install_authorized", "execution_authorized", "generation_submitted", "training_authorized"):
                    self.assertIs(result[field], False)


if __name__ == "__main__":
    unittest.main()
