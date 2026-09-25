"""Offline contract tests for Adult Illustration benchmark results."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import unittest

from studio_prompt.adult_illustration_benchmark_result import (
    canonical_bytes,
    validate_benchmark_result,
)


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
CORPUS_BLOB_SHA = "1c75c9e46f78da1d17ad0427a14647d49dbfe4ee"
ROUTE_BLOB_SHA = "d68be781d9d5e5c88555ee522dd6fd147c1cccc5"
MEASURES = [
    "accepted_distinct_task",
    "failure_class",
    "hard_constraints",
]


def valid_corpus() -> dict[str, object]:
    return {
        "schema": "studio.adult-illustration-benchmark-corpus/v0",
        "kind": "non-executing-corpus",
        "executable": False,
        "authority": "none",
        "research_date": "2026-09-15",
        "source_baseline": "b29205cfc95ca4e64d72ae38d53df30c83968997",
        "issue": 409,
        "cases": [{"id": CASE_ID}],
        "measures": list(MEASURES),
    }


def valid_routes() -> dict[str, object]:
    return {
        "schema": "studio.adult-illustration-route-candidates/v0",
        "kind": "research-candidates",
        "executable": False,
        "authority": "none",
        "research_date": "2026-09-15",
        "source_baseline": "b29205cfc95ca4e64d72ae38d53df30c83968997",
        "issue": 405,
        "candidates": [{"id": ROUTE_ID}],
    }


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
            "git_blob_sha": CORPUS_BLOB_SHA,
            "case_ids": [CASE_ID],
        },
        "study": {
            "id": "synthetic-character-pose-smoke",
            "phase": "smoke",
            "route_id": ROUTE_ID,
            "route_manifest_git_blob_sha": ROUTE_BLOB_SHA,
            "prompt_variant": "unchanged_brief",
            "declared_candidate_cap": 2,
            "route_config_sha256": None,
            "graph_sha256": None,
            "source_set_sha256": None,
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
        "measurements": [measurement(item) for item in MEASURES],
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
    def validate(self, value: dict[str, object]) -> dict[str, object]:
        return validate_benchmark_result(
            value,
            valid_corpus(),
            valid_routes(),
            corpus_blob_sha=CORPUS_BLOB_SHA,
            route_blob_sha=ROUTE_BLOB_SHA,
        )

    def test_valid_synthetic_result_contract(self) -> None:
        value = valid_result()
        self.assertEqual(self.validate(value), value)

    def test_candidate_accounting_must_retain_every_attempt(self) -> None:
        value = valid_result()
        value["accounting"]["retained_candidates"] = 1  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "retained.*candidate"):
            self.validate(value)

    def test_actual_candidates_cannot_exceed_declared_cap(self) -> None:
        value = valid_result()
        value["study"]["declared_candidate_cap"] = 1  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "cap"):
            self.validate(value)

    def test_uncertain_submission_is_distinct_and_counts_against_cap(self) -> None:
        value = valid_result()
        candidate = value["candidates"][1]  # type: ignore[index]
        candidate["status"] = "uncertain_submission"
        candidate["failure_class"] = "uncertain_submission"
        rehash(value)
        self.assertEqual(self.validate(value), value)

    def test_accepted_candidate_requires_completed_human_reviewed_acceptance(self) -> None:
        value = valid_result()
        candidate = value["candidates"][0]  # type: ignore[index]
        candidate["accepted"] = True
        value["accounting"]["accepted_candidates"] = 1  # type: ignore[index]
        value["accounting"]["accepted_distinct_tasks"] = 1  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "accepted.*human-reviewed"):
            self.validate(value)

    def test_unobserved_measurement_cannot_encode_zero_as_observation(self) -> None:
        value = valid_result()
        value["measurements"][0]["value"] = 0  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "unobserved.*null"):
            self.validate(value)

    def test_observed_ratio_requires_bounded_numerator_denominator(self) -> None:
        value = valid_result()
        item = value["measurements"][0]  # type: ignore[index]
        item.update(
            state="observed",
            numerator=3,
            denominator=2,
            unit="candidates",
            evidence_refs=["synthetic:measurement"],
        )
        rehash(value)
        with self.assertRaisesRegex(ValueError, "numerator.*denominator"):
            self.validate(value)

    def test_observed_measurement_requires_evidence(self) -> None:
        value = valid_result()
        item = value["measurements"][0]  # type: ignore[index]
        item.update(state="observed", value=1, unit="score")
        rehash(value)
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            self.validate(value)

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
                with self.assertRaisesRegex(ValueError, "finite"):
                    self.validate(value)

    def test_unknown_case_route_or_measure_is_rejected(self) -> None:
        value = valid_result()
        value["corpus"]["case_ids"] = ["missing-case"]  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "unknown cases"):
            self.validate(value)

        value = valid_result()
        value["study"]["route_id"] = "missing-route"  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "unknown route"):
            self.validate(value)

        value = valid_result()
        value["measurements"][0]["id"] = "invented_measure"  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "unknown benchmark measure"):
            self.validate(value)

    def test_exact_corpus_and_route_manifest_identities_are_required(self) -> None:
        value = valid_result()
        value["corpus"]["git_blob_sha"] = "0" * 40  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "corpus identity"):
            self.validate(value)

        value = valid_result()
        value["study"]["route_manifest_git_blob_sha"] = "0" * 40  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "route manifest identity"):
            self.validate(value)

    def test_synthetic_fixture_cannot_approve_or_authorize_promotion(self) -> None:
        value = valid_result()
        value["decision"]["outcome"] = "promote_route"  # type: ignore[index]
        value["decision"]["human_approved"] = True  # type: ignore[index]
        value["decision"]["promotion_authorized"] = True  # type: ignore[index]
        value["promotion_authorized"] = True
        rehash(value)
        with self.assertRaisesRegex(ValueError, "promotion"):
            self.validate(value)

    def test_boolean_candidate_ordinal_is_rejected(self) -> None:
        value = valid_result()
        value["candidates"][0]["ordinal"] = True  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "ordinals"):
            self.validate(value)

    def test_decision_promotion_authorized_alone_is_refused(self) -> None:
        value = valid_result()
        value["decision"]["promotion_authorized"] = True  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "promotion"):
            self.validate(value)

    def test_rehashed_tampering_still_fails_semantic_validation(self) -> None:
        value = valid_result()
        value["candidates"][1]["failure_class"] = "crash"  # type: ignore[index]
        rehash(value)
        with self.assertRaisesRegex(ValueError, "failure class.*status"):
            self.validate(value)

    def test_non_synthetic_result_requires_frozen_external_evidence(self) -> None:
        value = valid_result()
        value["synthetic"] = False
        value["kind"] = "benchmark-result"
        rehash(value)
        with self.assertRaisesRegex(ValueError, "requires frozen route"):
            self.validate(value)


if __name__ == "__main__":
    unittest.main()
