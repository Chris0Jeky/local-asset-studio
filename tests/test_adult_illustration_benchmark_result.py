"""Offline contract tests for Adult Illustration benchmark results."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_adult_illustration.py"
AUTHORITY_FIELDS = (
    "download_authorized",
    "install_authorized",
    "execution_authorized",
    "generation_submitted",
    "training_authorized",
    "promotion_authorized",
)
CASE_ID = "adult-character-plus-pose"
ROUTE_ID = "qwen-image-edit-2511-source-review"
MEASURES = {
    "hard_constraints",
    "accepted_distinct_task",
    "failure_class",
}


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_adult_illustration", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load validator from {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def rehash(value: dict[str, object]) -> None:
    unsigned = copy.deepcopy(value)
    unsigned.pop("result_id", None)
    value["result_id"] = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()


def measurement(measure_id: str) -> dict[str, object]:
    return {
        "id": measure_id,
        "state": "unobserved",
        "value": None,
        "numerator": None,
        "denominator": None,
        "unit": None,
        "uncertainty": None,
        "evidence_refs": [],
    }


def valid_result() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "studio.adult-illustration-benchmark-result/v1",
        "kind": "synthetic-benchmark-result-example",
        "executable": False,
        "authority": "none",
        "research_date": "2026-09-18",
        "source_baseline": "b29205cfc95ca4e64d72ae38d53df30c83968997",
        "issue": 409,
        "synthetic": True,
        "corpus": {
            "path": "research/adult-illustration/benchmark-corpus.json",
            "git_blob_sha": "1c75c9e46f78da1d17ad0427a14647d49dbfe4ee",
            "case_ids": [CASE_ID],
        },
        "study": {
            "id": "synthetic-character-pose-smoke",
            "phase": "smoke",
            "route_id": ROUTE_ID,
            "prompt_variant": "unchanged_brief",
            "declared_candidate_cap": 2,
            "external_campaign_id": None,
            "external_authorization_ref": None,
        },
        "candidates": [
            {
                "id": "candidate-001",
                "ordinal": 1,
                "case_id": CASE_ID,
                "seed": 101,
                "status": "completed",
                "failure_class": None,
                "output_ref": "synthetic:candidate-001",
                "accepted": False,
                "human_reviewed": False,
                "adult_envelope": "unreviewed",
                "artistic_accepted": False,
                "rights_reviewed": False,
                "evidence_refs": ["synthetic:evidence-001"],
            },
            {
                "id": "candidate-002",
                "ordinal": 2,
                "case_id": CASE_ID,
                "seed": 102,
                "status": "oom",
                "failure_class": "oom",
                "output_ref": None,
                "accepted": False,
                "human_reviewed": False,
                "adult_envelope": "unobserved",
                "artistic_accepted": False,
                "rights_reviewed": False,
                "evidence_refs": ["synthetic:failure-002"],
            },
        ],
        "accounting": {
            "attempted_candidates": 2,
            "retained_candidates": 2,
            "accepted_candidates": 0,
            "attempted_distinct_tasks": 1,
            "accepted_distinct_tasks": 0,
            "owner_interactions": 0,
            "wait_seconds": None,
            "cleanup_minutes": None,
        },
        "measurements": [measurement(item) for item in sorted(MEASURES)],
        "decision": {
            "outcome": "insufficient_evidence",
            "target_type": "route",
            "target_id": ROUTE_ID,
            "scope": [],
            "evidence_refs": [],
            "human_approved": False,
            "promotion_authorized": False,
        },
        "notes": [
            "Synthetic contract fixture only; it contains no real generation evidence."
        ],
        **{field: False for field in AUTHORITY_FIELDS},
    }
    rehash(value)
    return value


class AdultIllustrationBenchmarkResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def validate(self, value: dict[str, object]) -> list[str]:
        errors: list[str] = []
        self.validator._validate_benchmark_result(
            value,
            {CASE_ID},
            {ROUTE_ID},
            MEASURES,
            errors,
        )
        return errors

    def assert_error(self, errors: list[str], *needles: str) -> None:
        joined = "\n".join(errors).casefold()
        for needle in needles:
            self.assertIn(needle.casefold(), joined, joined)

    def test_valid_synthetic_result_contract(self) -> None:
        self.assertEqual(self.validate(valid_result()), [])

    def test_result_manifest_is_required_by_the_offline_gate(self) -> None:
        self.assertIn(
            "benchmark-result-example.json",
            self.validator.REQUIRED_MANIFESTS,
        )

    def test_candidate_accounting_must_retain_every_attempt(self) -> None:
        value = valid_result()
        value["accounting"]["retained_candidates"] = 1  # type: ignore[index]
        rehash(value)
        self.assert_error(self.validate(value), "retained", "candidate")

    def test_actual_candidates_cannot_exceed_declared_cap(self) -> None:
        value = valid_result()
        value["study"]["declared_candidate_cap"] = 1  # type: ignore[index]
        rehash(value)
        self.assert_error(self.validate(value), "cap", "candidate")

    def test_uncertain_submission_is_distinct_and_counts_against_cap(self) -> None:
        value = valid_result()
        candidate = value["candidates"][1]  # type: ignore[index]
        candidate["status"] = "uncertain_submission"
        candidate["failure_class"] = "uncertain_submission"
        rehash(value)
        self.assertEqual(self.validate(value), [])

    def test_accepted_candidate_requires_completed_human_reviewed_acceptance(self) -> None:
        value = valid_result()
        candidate = value["candidates"][0]  # type: ignore[index]
        candidate["accepted"] = True
        value["accounting"]["accepted_candidates"] = 1  # type: ignore[index]
        value["accounting"]["accepted_distinct_tasks"] = 1  # type: ignore[index]
        rehash(value)
        self.assert_error(self.validate(value), "accepted", "human", "review")

    def test_unobserved_measurement_cannot_encode_zero_as_observation(self) -> None:
        value = valid_result()
        value["measurements"][0]["value"] = 0  # type: ignore[index]
        rehash(value)
        self.assert_error(self.validate(value), "unobserved", "null")

    def test_observed_ratio_requires_bounded_numerator_denominator_and_evidence(self) -> None:
        value = valid_result()
        item = value["measurements"][0]  # type: ignore[index]
        item.update(
            state="observed",
            numerator=3,
            denominator=2,
            unit="candidates",
            evidence_refs=[],
        )
        rehash(value)
        errors = self.validate(value)
        self.assert_error(errors, "numerator", "denominator")
        self.assert_error(errors, "evidence")

    def test_non_finite_measurement_is_rejected(self) -> None:
        for number in (math.nan, math.inf, -math.inf):
            with self.subTest(number=number):
                value = valid_result()
                item = value["measurements"][0]  # type: ignore[index]
                item.update(
                    state="observed",
                    value=number,
                    unit="score",
                    evidence_refs=["synthetic:measurement"],
                )
                # Do not rehash: JSON canonicalization must also fail closed.
                errors = self.validate(value)
                self.assert_error(errors, "finite", "measurement")

    def test_unknown_case_route_or_measure_is_rejected(self) -> None:
        value = valid_result()
        value["corpus"]["case_ids"] = ["missing-case"]  # type: ignore[index]
        value["study"]["route_id"] = "missing-route"  # type: ignore[index]
        value["measurements"][0]["id"] = "invented_measure"  # type: ignore[index]
        rehash(value)
        errors = self.validate(value)
        self.assert_error(errors, "unknown", "case")
        self.assert_error(errors, "unknown", "route")
        self.assert_error(errors, "measure")

    def test_synthetic_fixture_cannot_approve_or_authorize_promotion(self) -> None:
        value = valid_result()
        value["decision"]["outcome"] = "promote_route"  # type: ignore[index]
        value["decision"]["human_approved"] = True  # type: ignore[index]
        value["decision"]["promotion_authorized"] = True  # type: ignore[index]
        value["promotion_authorized"] = True
        rehash(value)
        self.assert_error(self.validate(value), "synthetic", "promotion")

    def test_rehashed_tampering_still_fails_semantic_validation(self) -> None:
        value = valid_result()
        value["candidates"][1]["failure_class"] = "crash"  # type: ignore[index]
        rehash(value)
        self.assert_error(self.validate(value), "failure", "status")


if __name__ == "__main__":
    unittest.main()
