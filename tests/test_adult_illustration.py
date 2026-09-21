"""Offline contract tests for the controlled adult illustration research manifests.

These tests exercise static JSON only. They must not import application/runtime modules,
open the network, inspect model files, or submit generation.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_adult_illustration.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_adult_illustration", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load validator from {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdultIllustrationManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def validate_mutation(self, filename, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "research" / "adult-illustration"
            target.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "research" / "adult-illustration", target)
            path = target / filename
            payload = json.loads(path.read_text(encoding="utf-8"))
            mutate(payload)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return self.validator.validate_paths(root)

    def assert_has_error(self, errors, *needles):
        joined = "\n".join(errors).lower()
        for needle in needles:
            self.assertIn(needle.lower(), joined, joined)

    def test_checked_in_manifests_are_valid(self):
        self.assertEqual(self.validator.validate_paths(ROOT), [])

    def test_missing_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "research" / "adult-illustration"
            target.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "research" / "adult-illustration", target)
            (target / "genre-packs.json").unlink()
            errors = self.validator.validate_paths(root)
        self.assert_has_error(errors, "missing required manifest", "genre-packs.json")

    def test_executable_or_authoritative_research_is_rejected(self):
        errors = self.validate_mutation(
            "route-candidates.json",
            lambda payload: payload.update(executable=True, authority="execute"),
        )
        self.assert_has_error(errors, "executable", "authority")

    def test_duplicate_control_ids_are_rejected(self):
        def mutate(payload):
            payload["controls"].append(dict(payload["controls"][0]))
        errors = self.validate_mutation("control-ontology.json", mutate)
        self.assert_has_error(errors, "duplicate", "control")

    def test_unknown_required_control_is_rejected(self):
        def mutate(payload):
            payload["cases"][0]["required_controls"].append("unknown.control")
        errors = self.validate_mutation("benchmark-corpus.json", mutate)
        self.assert_has_error(errors, "unknown control", "unknown.control")

    def test_missing_adult_assertion_is_rejected(self):
        def mutate(payload):
            del payload["cases"][0]["subjects"][0]["adult_assertion"]
        errors = self.validate_mutation("benchmark-corpus.json", mutate)
        self.assert_has_error(errors, "adult assertion", "adult-original-text")

    def test_multi_subject_case_requires_consent_context(self):
        def mutate(payload):
            case = next(item for item in payload["cases"] if item["id"] == "two-adult-shared-prop")
            case["consent_context"] = "not_applicable"
        errors = self.validate_mutation("benchmark-corpus.json", mutate)
        self.assert_has_error(errors, "consent", "two-adult-shared-prop")

    def test_nonzero_authorized_candidate_cap_is_rejected(self):
        def mutate(payload):
            payload["cases"][0]["authorized_candidate_cap"] = 1
        errors = self.validate_mutation("benchmark-corpus.json", mutate)
        self.assert_has_error(errors, "authorized_candidate_cap", "zero")

    def test_invalid_route_evidence_state_is_rejected(self):
        def mutate(payload):
            payload["candidates"][0]["evidence_state"] = "popular"
        errors = self.validate_mutation("route-candidates.json", mutate)
        self.assert_has_error(errors, "evidence state", "popular")

    def test_route_source_requires_https(self):
        def mutate(payload):
            payload["candidates"][0]["source_url"] = "http://example.invalid/model"
        errors = self.validate_mutation("route-candidates.json", mutate)
        self.assert_has_error(errors, "https", "source_url")

    def test_adapter_sweep_weights_must_be_ordered_and_bounded(self):
        def mutate(payload):
            payload["adapter"]["tested_weights"] = [0.0, 0.5, 0.25, 8.0]
        errors = self.validate_mutation("lora-qualification-example.json", mutate)
        self.assert_has_error(errors, "tested_weights", "increasing", "bounded")

    def test_synthetic_adapter_cannot_be_promoted_even_with_interval(self):
        def mutate(payload):
            payload["adapter"]["promoted"] = True
            payload["adapter"]["promoted_interval"] = [0.1, 0.9]
        errors = self.validate_mutation("lora-qualification-example.json", mutate)
        self.assert_has_error(errors, "promoted", "remain false")

    def test_non_finite_adapter_sweep_weights_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                def mutate(payload, value=value):
                    payload["adapter"]["tested_weights"] = [0.0, value, 1.0]
                errors = self.validate_mutation("lora-qualification-example.json", mutate)
                self.assert_has_error(errors, "tested_weights", "finite")

    def test_programme_issue_owners_are_pinned(self):
        def mutate(payload):
            payload["issues"]["routes"] = 999
        errors = self.validate_mutation("programme.json", mutate)
        self.assert_has_error(errors, "routes", "405")

    def test_pack_must_reference_known_benchmark_cases(self):
        def mutate(payload):
            payload["packs"][0]["benchmark_cases"].append("missing-case")
        errors = self.validate_mutation("genre-packs.json", mutate)
        self.assert_has_error(errors, "unknown benchmark", "missing-case")

    def test_duplicate_case_pack_route_and_adapter_ids_are_rejected(self):
        def duplicate_case(payload):
            payload["cases"].append(dict(payload["cases"][0]))
        self.assert_has_error(
            self.validate_mutation("benchmark-corpus.json", duplicate_case),
            "duplicate", "case",
        )

        def duplicate_pack(payload):
            payload["packs"].append(dict(payload["packs"][0]))
        self.assert_has_error(
            self.validate_mutation("genre-packs.json", duplicate_pack),
            "duplicate", "pack",
        )

        def duplicate_route(payload):
            payload["candidates"].append(dict(payload["candidates"][0]))
        self.assert_has_error(
            self.validate_mutation("route-candidates.json", duplicate_route),
            "duplicate", "route",
        )


if __name__ == "__main__":
    unittest.main()
