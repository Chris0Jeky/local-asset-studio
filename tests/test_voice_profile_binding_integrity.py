"""Qualification plans must retain an internally valid narration-profile binding."""
from __future__ import annotations

import copy
import unittest

from test_voice_profile_qualification import accepted_report, qualification


def rehash_binding_and_plan(plan):
    profile = plan["profile"]
    profile["binding_sha256"] = qualification.canonical_digest(
        {key: value for key, value in profile.items() if key != "binding_sha256"}
    )
    plan["plan_sha256"] = qualification.canonical_digest(
        {key: value for key, value in plan.items() if key != "plan_sha256"}
    )
    return plan


class VoiceProfileBindingIntegrityTests(unittest.TestCase):
    def test_rehashed_plan_cannot_rewrite_profile_binding_contents(self):
        plan = qualification.build_plan("ember-brief-v1")
        mutated = copy.deepcopy(plan)
        mutated["profile"]["delivery"]["instruction"] = (
            "Locally rewritten delivery instructions that were never resolved."
        )
        mutated["plan_sha256"] = qualification.canonical_digest(
            {key: value for key, value in mutated.items() if key != "plan_sha256"}
        )
        report = accepted_report(mutated)

        with self.assertRaisesRegex(
            qualification.QualificationError,
            "profile binding SHA-256",
        ):
            qualification.validate_report(mutated, report)

    def test_rehashed_binding_cannot_hide_a_stale_delivery_identity(self):
        plan = qualification.build_plan("ember-brief-v1")
        mutated = copy.deepcopy(plan)
        mutated["profile"]["delivery"]["instruction"] = (
            "Rewritten after profile resolution while retaining the old delivery digest."
        )
        rehash_binding_and_plan(mutated)
        report = accepted_report(mutated)

        with self.assertRaisesRegex(
            qualification.QualificationError,
            "delivery SHA-256",
        ):
            qualification.validate_report(mutated, report)

    def test_rehashed_binding_cannot_hide_a_stale_mix_identity(self):
        plan = qualification.build_plan("ember-brief-v1")
        mutated = copy.deepcopy(plan)
        mutated["profile"]["mix"]["recipe"] = "dry-remixed"
        rehash_binding_and_plan(mutated)
        report = accepted_report(mutated)

        with self.assertRaisesRegex(
            qualification.QualificationError,
            "mix SHA-256",
        ):
            qualification.validate_report(mutated, report)

    def test_rehashed_binding_keeps_status_and_acceptance_consistent(self):
        plan = qualification.build_plan("ember-brief-v1")
        mutated = copy.deepcopy(plan)
        mutated["profile"]["status"] = "accepted"
        rehash_binding_and_plan(mutated)
        report = accepted_report(mutated)

        with self.assertRaisesRegex(
            qualification.QualificationError,
            "accepted profile binding",
        ):
            qualification.validate_report(mutated, report)

    def test_rehashed_plan_requires_the_complete_profile_binding_shape(self):
        plan = qualification.build_plan("ember-brief-v1")
        mutated = copy.deepcopy(plan)
        del mutated["profile"]["binding_sha256"]
        mutated["plan_sha256"] = qualification.canonical_digest(
            {key: value for key, value in mutated.items() if key != "plan_sha256"}
        )
        report = accepted_report(mutated)

        with self.assertRaisesRegex(
            qualification.QualificationError,
            "profile binding",
        ):
            qualification.validate_report(mutated, report)


if __name__ == "__main__":
    unittest.main()
