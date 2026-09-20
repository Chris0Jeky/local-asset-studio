"""Qualification plans must retain an internally valid narration-profile binding."""
from __future__ import annotations

import copy
import unittest

from test_voice_profile_qualification import accepted_report, qualification


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
