"""Independent regression for an observed cross-stage anchor-measurement bypass.

The concept's scalp measures [80, 20, 90], while its anchor falsely claims
[110, 20, 90]. That small discrepancy is within the diagnostic scoring tolerance.
A later view reuses the same image, sampling a body patch that really is
[110, 20, 90]. A global (media SHA, feature name) cache previously let that later
measurement satisfy the false concept annotation. Only the concept's own pinned
measurement may establish its pixel anchor. These are synthetic test records.
"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

import fixtures
import pack_export
import pipeline
from consistency import measure_regions


class IndependentReviewRegressions(unittest.TestCase):
    @staticmethod
    def attest_fixture_payload(receipt):
        for dimension, state, actor in (
            ("generation", "completed", "fixture"),
            ("inspection", "inspected", "fixture"),
            ("acceptance", "accepted", "owner"),
        ):
            receipt = pipeline.attest(
                receipt, dimension, state, actor, "fixture:anchor-cache-counterexample")
        return receipt

    def test_later_stage_roi_cannot_satisfy_a_false_concept_anchor(self):
        runtime = pipeline.REPO_ROOT / ".runtime" / "pro" / "P36-B-20261125-1" / "tests"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="p36-anchor-cache-regression-", dir=runtime) as temporary:
            root = Path(temporary)
            policy = fixtures.policy()
            # This region is fixed before the family is created. It covers the
            # body swatch, while concept/front/hair still covers the scalp swatch.
            policy["regions"]["unreal"]["front"]["hair"] = [0.3125, 0.625, 0.6875, 0.8125]
            family = pipeline.create_family(
                "p36-fixture", "a" * 32, "p36-fixture", policy, mode="synthetic")

            concept = fixtures.stage_receipt(
                family, "concept", root, mutation={"outfit": (110, 20, 90)})
            front = concept["payload"]["identity"]["sheet"]["views"][0]
            self.assertEqual(front["features"]["hair"]["value"], [80.0, 20.0, 90.0])
            # Rebind the synthetic state evidence to this deliberately wrong
            # annotation so stale-attestation detection is not the tested gate.
            concept["payload"]["identity"]["anchor_features"]["hair"]["value"] = [110.0, 20.0, 90.0]
            concept = self.attest_fixture_payload(concept)
            family = pipeline.record_receipt(family, concept)
            source_artifact = concept["payload"]["artifacts"][0]
            alternate = measure_regions(
                root / source_artifact["path"], source_artifact["sha256"],
                policy["regions"]["unreal"]["front"])
            self.assertEqual(alternate["hair"]["value"], [110.0, 20.0, 90.0])

            for stage in pipeline.STAGES[1:]:
                receipt = fixtures.stage_receipt(family, stage, root)
                if stage == "unreal":
                    receipt["payload"]["artifacts"][0] = copy.deepcopy(source_artifact)
                    view = receipt["payload"]["identity"]["sheet"]["views"][0]
                    view["media_sha256"] = source_artifact["sha256"]
                    view["features"] = copy.deepcopy(front["features"])
                    view["features"].update(copy.deepcopy(alternate))
                    receipt = self.attest_fixture_payload(receipt)
                family = pipeline.record_receipt(family, receipt)

            # The diagnostic tolerance may pass; exact concept measurement
            # reproduction must independently block the actual export.
            self.assertTrue(pipeline.assess(family, "unreal")["passed"])
            with self.assertRaisesRegex(
                pipeline.PipelineError, "Anchor pixel measurement was not reproduced"):
                pack_export.build_manifest(family, root, fixtures.metadata())


if __name__ == "__main__":
    unittest.main()
