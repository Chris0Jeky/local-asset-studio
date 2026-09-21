from __future__ import annotations

import copy
import unittest

from studio_prompt.adult_illustration_benchmark_result import validate_benchmark_result
from tests.test_adult_illustration_benchmark_result import (
    CORPUS_BLOB_SHA,
    ROUTE_BLOB_SHA,
    rehash,
    valid_corpus,
    valid_result,
    valid_routes,
)


class AdultIllustrationBenchmarkResultIntegrityTests(unittest.TestCase):
    def validate(
        self,
        value: dict[str, object],
        *,
        corpus: dict[str, object] | None = None,
        routes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return validate_benchmark_result(
            value,
            corpus or valid_corpus(),
            routes or valid_routes(),
            corpus_blob_sha=CORPUS_BLOB_SHA,
            route_blob_sha=ROUTE_BLOB_SHA,
        )

    def test_result_source_baseline_must_match_frozen_manifests(self) -> None:
        value = valid_result()
        value["source_baseline"] = "0" * 40
        rehash(value)

        with self.assertRaisesRegex(ValueError, "baseline"):
            self.validate(value)

    def test_corpus_and_route_manifests_must_share_one_source_baseline(self) -> None:
        routes = valid_routes()
        routes["source_baseline"] = "0" * 40

        with self.assertRaisesRegex(ValueError, "baseline"):
            self.validate(valid_result(), routes=routes)

    def test_research_date_must_be_an_iso_calendar_date(self) -> None:
        value = valid_result()
        value["research_date"] = "2026-99-99"
        rehash(value)

        with self.assertRaisesRegex(ValueError, "research date"):
            self.validate(value)

    def test_route_decisions_cannot_target_controls(self) -> None:
        value = copy.deepcopy(valid_result())
        value["synthetic"] = False
        value["kind"] = "benchmark-result"
        study = value["study"]
        assert isinstance(study, dict)
        study["route_config_sha256"] = "1" * 64
        study["graph_sha256"] = "2" * 64
        study["source_set_sha256"] = "3" * 64
        study["external_campaign_id"] = "campaign-001"
        study["external_authorization_ref"] = "authorization:001"
        decision = value["decision"]
        assert isinstance(decision, dict)
        decision["outcome"] = "promote_route"
        decision["target_type"] = "control"
        decision["target_id"] = "subject.identity"
        decision["scope"] = ["adult-character-plus-pose"]
        decision["evidence_refs"] = ["review:decision-001"]
        decision["human_approved"] = True
        rehash(value)

        with self.assertRaisesRegex(ValueError, "decision.*target|target.*decision"):
            self.validate(value)


if __name__ == "__main__":
    unittest.main()
