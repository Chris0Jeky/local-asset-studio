"""Independent synthetic adversaries for the P36 semantic veto.

These fixtures contain annotations, not character images or owner judgements.
The mean-only baseline is deliberately weak and separate from both scorers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import unittest

from consistency import score_sheet

try:
    import sheet_identity
except ModuleNotFoundError as error:
    if error.name != "sheet_identity":
        raise
    sheet_identity = None


def digest(value):
    """Independent documented canonical JSON, not a scorer helper."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def fixture_inputs(stage="turnaround"):
    """Reusable annotation-only fixture for the root's evidence command."""
    concept = {"asset_id": "synthetic-concept", "media_sha256": "a" * 64,
               "receipt_digest": "b" * 64}
    proxy_policy = {
        "version": 1,
        "features": {"proportion": {"kind": "ratio", "tolerance": 0.05},
                     "hair": {"kind": "rgb", "tolerance": 0.05}},
        "required": {
            "turnaround": {view: ["proportion", "hair"] for view in ("front", "left", "right", "back")},
            "outfits": {view: ["proportion", "hair"] for view in ("festival-front", "festival-back")},
        },
    }
    anchors = {
        "left-iris": {"kind": "identity", "value": "amber", "vocabulary": ["amber", "blue"]},
        "right-iris": {"kind": "identity", "value": "blue", "vocabulary": ["amber", "blue"]},
        "braid-side": {"kind": "identity", "value": "subject-left",
                       "vocabulary": ["subject-left", "subject-right"]},
        "coat": {"kind": "costume", "value": "blue-coat", "vocabulary": ["blue-coat", "red-coat"]},
    }
    semantic_policy = {
        "version": 1, "side_basis": "subject_anatomical", "concept": copy.deepcopy(concept),
        "proxy_policy_digest": digest(proxy_policy), "anchors": anchors,
        "contexts": {"base": {}, "festival": {"coat": "red-coat"}},
        "required": {
            "turnaround": {
                "front": {"context": "base", "anchors": ["left-iris", "right-iris", "braid-side", "coat"]},
                "left": {"context": "base", "anchors": ["left-iris", "braid-side", "coat"]},
                "right": {"context": "base", "anchors": ["right-iris", "coat"]},
                "back": {"context": "base", "anchors": ["braid-side", "coat"]},
            },
            "outfits": {
                "festival-front": {"context": "festival", "anchors": ["left-iris", "right-iris", "coat"]},
                "festival-back": {"context": "festival", "anchors": ["braid-side", "coat"]},
            },
        },
    }
    anchor_features = {
        "proportion": {"value": 1.0, "provenance": "fixture_truth", "media_sha256": concept["media_sha256"]},
        "hair": {"value": [40, 80, 120], "provenance": "fixture_truth", "media_sha256": concept["media_sha256"]},
    }
    sheet = {"views": []}
    annotations = {"version": 1, "method": "manual_descriptor_v1", "side_basis": "subject_anatomical",
                   "concept": copy.deepcopy(concept), "policy_digest": digest(semantic_policy), "views": []}
    for index, (view, requirement) in enumerate(semantic_policy["required"][stage].items()):
        media = hashlib.sha256((stage + "/" + view).encode("ascii")).hexdigest()
        features = copy.deepcopy(anchor_features)
        for record in features.values():
            record["media_sha256"] = media
        sheet["views"].append({"id": view, "media_sha256": media, "features": features})
        observed = {}
        for name in requirement["anchors"]:
            expected = semantic_policy["contexts"][requirement["context"]].get(name, anchors[name]["value"])
            observed[name] = {"state": "observed", "value": expected, "provenance": "fixture_truth"}
        annotations["views"].append({"id": view, "media_sha256": media, "compared_to": copy.deepcopy(concept),
                                     "context": requirement["context"], "anchors": observed})
    return {"anchor_features": anchor_features, "sheet": sheet, "proxy_policy": proxy_policy,
            "stage": stage, "semantic_policy": semantic_policy, "annotations": annotations, "concept": concept}


def challenge_cases():
    """Literal challenge labels and independent mean-only baseline inputs.

    Each baseline list is an authored prior similarity observation. The baseline
    ignores semantic bindings and coverage; this intentional weakness is declared.
    """
    cases = []
    def add(name, data, expected, baseline_scores):
        cases.append({"name": name, "inputs": data, "expected_pass": expected,
                      "baseline_scores": baseline_scores})
    add("matching", fixture_inputs(), True, [1.0, 1.0, 1.0, 1.0])
    add("permitted-costume", fixture_inputs("outfits"), True, [1.0, 1.0])
    case = fixture_inputs()
    front = case["annotations"]["views"][0]["anchors"]
    front["left-iris"]["value"], front["right-iris"]["value"] = "blue", "amber"
    add("mirrored-heterochromia", case, False, [1.0, 1.0, 1.0, 1.0])
    case = fixture_inputs()
    case["annotations"]["views"][3]["anchors"]["braid-side"]["value"] = "subject-right"
    add("one-back-mark-drift", case, False, [1.0, 1.0, 1.0, 1.0])
    case = fixture_inputs()
    case["sheet"]["views"][3]["features"]["proportion"]["value"] = 0.8
    add("one-numeric-drift", case, False, [1.0, 1.0, 1.0, 0.8])
    case = fixture_inputs()
    case["annotations"]["views"][0]["anchors"]["left-iris"] = {
        "state": "not_visible", "value": None, "provenance": "fixture_truth"}
    add("occluded-required-eye", case, False, [1.0, 1.0, 1.0, 1.0])
    case = fixture_inputs()
    case["annotations"]["views"].pop()
    add("missing-back-annotation", case, False, [1.0, 1.0, 1.0])
    case = fixture_inputs()
    case["annotations"]["views"][0]["compared_to"]["receipt_digest"] = "c" * 64
    add("stale-root-comparison", case, False, [1.0, 1.0, 1.0, 1.0])
    case = fixture_inputs()
    case["annotations"]["views"][0]["anchors"]["invented"] = {
        "state": "observed", "value": "perfect", "provenance": "fixture_truth"}
    add("invented-descriptor", case, False, [1.0, 1.0, 1.0, 1.0])
    case = fixture_inputs()
    case["annotations"]["views"][0]["context"] = "festival"
    case["annotations"]["views"][0]["anchors"]["coat"]["value"] = "red-coat"
    add("unauthorized-costume-context", case, False, [1.0, 1.0, 1.0, 1.0])
    return cases


class IdentityTests(unittest.TestCase):
    def score(self, data=None):
        self.assertIsNotNone(sheet_identity, "The requested semantic veto has not been implemented")
        return sheet_identity.score_sheet_identity(**(data or fixture_inputs()))

    def test_matching_annotations_pass_without_promoting_evidence(self):
        result = self.score()
        self.assertTrue(result["passed"])
        self.assertEqual(result["worst_view_score"], 1.0)
        self.assertEqual(result["mean_score"], 1.0)
        self.assertEqual(result["evidence_state"], "implemented")
        for field in ("perceptual_identity_verified", "art_acceptance_implied", "generation_implied",
                      "licence_clearance_implied", "provenance_verified"):
            self.assertIs(result[field], False)
        self.assertIs(result["review_required"], True)

    def test_side_swap_is_rejected_when_prior_numeric_score_is_perfect(self):
        case = challenge_cases()[2]["inputs"]
        prior = score_sheet(case["anchor_features"], case["sheet"], case["proxy_policy"], case["stage"])
        self.assertTrue(prior["passed"])
        self.assertEqual(prior["score"], 1.0)
        result = self.score(case)
        self.assertFalse(result["passed"])
        self.assertIn("semantic_mismatch:front:left-iris", result["blockers"])
        self.assertIn("semantic_mismatch:front:right-iris", result["blockers"])
        self.assertEqual(result["worst_view_score"], 0.0)

    def test_one_bad_view_cannot_be_diluted_by_good_views(self):
        case = challenge_cases()[3]["inputs"]
        result = self.score(case)
        self.assertFalse(result["passed"])
        self.assertEqual(result["worst_view_score"], 0.0)
        self.assertEqual(result["mean_score"], 0.75)
        self.assertEqual(next(v for v in result["per_view"] if v["view"] == "back")["passed"], False)

    def test_prior_failure_is_never_elevated_by_semantic_agreement(self):
        case = challenge_cases()[4]["inputs"]
        result = self.score(case)
        self.assertFalse(result["passed"])
        self.assertFalse(result["proxy_report"]["passed"])
        self.assertEqual(result["worst_view_score"], 0.8)
        self.assertEqual(result["mean_score"], 0.95)

    def test_frozen_costume_context_changes_only_costume(self):
        case = fixture_inputs("outfits")
        self.assertTrue(self.score(case)["passed"])
        case["annotations"]["views"][0]["anchors"]["left-iris"]["value"] = "blue"
        self.assertFalse(self.score(case)["passed"])

    def test_candidate_cannot_select_easier_context(self):
        result = self.score(challenge_cases()[-1]["inputs"])
        self.assertFalse(result["passed"])
        self.assertIn("annotation_context_mismatch:front", result["blockers"])

    def test_identity_override_is_invalid_even_in_an_unused_policy_context(self):
        case = fixture_inputs()
        case["semantic_policy"]["contexts"]["unused"] = {"left-iris": "blue"}
        case["annotations"]["policy_digest"] = digest(case["semantic_policy"])
        result = self.score(case)
        self.assertFalse(result["passed"])
        self.assertIn("policy_identity_override", result["blockers"])

    def test_unobservable_states_never_pass_or_get_renamed_to_not_applicable(self):
        for state in ("uncertain", "not_visible", "occluded", "unknown", "not_applicable"):
            with self.subTest(state=state):
                case = fixture_inputs()
                record = case["annotations"]["views"][0]["anchors"]["left-iris"]
                record.update(state=state, value=None)
                self.assertFalse(self.score(case)["passed"])

    def test_view_specific_applicability_does_not_require_hidden_far_eye(self):
        case = fixture_inputs()
        self.assertNotIn("right-iris", case["annotations"]["views"][1]["anchors"])
        self.assertTrue(self.score(case)["passed"])
        del case["annotations"]["views"][1]["anchors"]["left-iris"]
        self.assertFalse(self.score(case)["passed"])

    def test_missing_duplicate_and_extra_annotation_views_fail_closed(self):
        for alteration in ("missing", "duplicate", "extra"):
            with self.subTest(alteration=alteration):
                case = fixture_inputs()
                views = case["annotations"]["views"]
                if alteration == "missing":
                    views.pop()
                else:
                    other = copy.deepcopy(views[0])
                    if alteration == "extra":
                        other["id"] = "unrequested"
                    views.append(other)
                self.assertFalse(self.score(case)["passed"])

    def test_invented_anchor_and_out_of_vocabulary_value_cannot_help(self):
        self.assertFalse(self.score(challenge_cases()[8]["inputs"])["passed"])
        case = fixture_inputs()
        case["annotations"]["views"][0]["anchors"]["left-iris"]["value"] = "close-enough"
        self.assertIn("semantic_value_unknown:front:left-iris", self.score(case)["blockers"])

    def test_root_binding_covers_asset_media_and_receipt_per_view(self):
        for field, replacement in (("asset_id", "another-concept"), ("media_sha256", "c" * 64),
                                   ("receipt_digest", "d" * 64)):
            for location in ("concept", "annotation", "view"):
                with self.subTest(field=field, location=location):
                    case = fixture_inputs()
                    target = case["concept"] if location == "concept" else (
                        case["annotations"]["concept"] if location == "annotation" else
                        case["annotations"]["views"][0]["compared_to"])
                    target[field] = replacement
                    self.assertFalse(self.score(case)["passed"])

    def test_missing_root_receipt_digest_fails_even_if_every_annotation_agrees(self):
        case = fixture_inputs()
        del case["concept"]["receipt_digest"]
        self.assertFalse(self.score(case)["passed"])

    def test_swapped_annotation_media_cannot_qualify_a_different_sheet(self):
        case = fixture_inputs()
        case["annotations"]["views"][0]["media_sha256"] = case["sheet"]["views"][1]["media_sha256"]
        self.assertIn("annotation_media_mismatch:front", self.score(case)["blockers"])

    def test_proxy_anchors_must_also_name_the_accepted_root_media(self):
        case = fixture_inputs()
        case["anchor_features"]["hair"]["media_sha256"] = "c" * 64
        self.assertFalse(self.score(case)["passed"])

    def test_candidate_cannot_supply_policy_or_passing_cached_report(self):
        for key, value in (("policy", {}), ("passed", True), ("score", 1.0)):
            with self.subTest(key=key):
                case = fixture_inputs()
                case["annotations"][key] = value
                self.assertFalse(self.score(case)["passed"])

    def test_candidate_cannot_rebind_annotation_hash_to_a_changed_proxy_policy(self):
        case = fixture_inputs()
        case["proxy_policy"]["features"]["proportion"]["tolerance"] = 10.0
        result = self.score(case)
        self.assertFalse(result["passed"])
        self.assertIn("proxy_policy_binding_mismatch", result["blockers"])

    def test_dropped_view_in_semantic_policy_cannot_weaken_numeric_view_coverage(self):
        case = fixture_inputs()
        del case["semantic_policy"]["required"]["turnaround"]["back"]
        case["annotations"]["policy_digest"] = digest(case["semantic_policy"])
        self.assertFalse(self.score(case)["passed"])

    def test_no_required_view_can_consist_only_of_costume(self):
        case = fixture_inputs()
        case["semantic_policy"]["required"]["turnaround"]["back"]["anchors"] = ["coat"]
        self.assertIn("policy_identity_coverage_missing", self.score(case)["blockers"])

    def test_nonfinite_numeric_and_type_alias_values_fail_without_exception(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "1", 10 ** 1000):
            with self.subTest(value=str(value)[:20]):
                case = fixture_inputs()
                case["sheet"]["views"][0]["features"]["proportion"]["value"] = value
                self.assertFalse(self.score(case)["passed"])
        for value in (True, 1.0, "1", None):
            case = fixture_inputs()
            case["annotations"]["version"] = value
            self.assertFalse(self.score(case)["passed"])

    def test_malformed_shapes_and_unserializable_input_fail_closed(self):
        for field in ("concept", "semantic_policy", "annotations", "anchor_features", "sheet", "proxy_policy"):
            for bad in (None, [], "bad", 42):
                with self.subTest(field=field, bad=bad):
                    case = fixture_inputs()
                    case[field] = bad
                    self.assertFalse(self.score(case)["passed"])
        case = fixture_inputs()
        case["annotations"]["views"][0]["anchors"]["left-iris"]["value"] = {1, 2}
        self.assertFalse(self.score(case)["passed"])

    def test_nonfinite_values_in_unused_fields_are_not_silently_ignored(self):
        case = fixture_inputs()
        case["sheet"]["untrusted_metric"] = float("nan")
        self.assertFalse(self.score(case)["passed"])

    def test_policy_digest_validates_every_unused_branch_and_rejects_bool_version(self):
        self.assertIsNotNone(sheet_identity)
        for mutate in (lambda p: p.update(version=True),
                       lambda p: p["contexts"].update(unused={"invented": "anything"}),
                       lambda p: p["anchors"]["left-iris"].update(vocabulary=["amber", "amber"]),
                       lambda p: p["required"]["outfits"]["festival-back"].update(anchors=[])):
            case = fixture_inputs()
            mutate(case["semantic_policy"])
            with self.assertRaises(ValueError):
                sheet_identity.semantic_policy_digest(case["semantic_policy"])

    def test_deterministic_report_hash_binds_input_policy_and_each_view(self):
        case = fixture_inputs()
        before = copy.deepcopy(case)
        result = self.score(case)
        self.assertEqual(case, before)
        self.assertEqual(result, self.score(copy.deepcopy(case)))
        self.assertEqual(result["input_digest"], digest(case))
        self.assertEqual(result["policy_digest"], digest(case["semantic_policy"]))
        self.assertEqual(result["report_digest"], digest({k: v for k, v in result.items() if k != "report_digest"}))
        case["annotations"]["views"][3]["anchors"]["braid-side"]["value"] = "subject-right"
        other = self.score(case)
        self.assertNotEqual(other["input_digest"], result["input_digest"])
        self.assertNotEqual(other["report_digest"], result["report_digest"])

    def test_key_order_does_not_change_hashes_or_report(self):
        case = fixture_inputs()
        reordered = {key: value for key, value in reversed(list(case.items()))}
        self.assertEqual(self.score(case), self.score(reordered))

    def test_challenge_set_beats_weak_mean_baseline_without_claiming_accuracy(self):
        baseline_false_accepts = strong_false_accepts = strong_false_rejects = 0
        for case in challenge_cases():
            with self.subTest(case=case["name"]):
                scores = case["baseline_scores"]
                baseline_pass = sum(scores) / len(scores) >= 0.90
                strong_pass = self.score(case["inputs"])["passed"]
                self.assertEqual(strong_pass, case["expected_pass"])
                baseline_false_accepts += baseline_pass and not case["expected_pass"]
                strong_false_accepts += strong_pass and not case["expected_pass"]
                strong_false_rejects += not strong_pass and case["expected_pass"]
        self.assertEqual((baseline_false_accepts, strong_false_accepts, strong_false_rejects), (8, 0, 0))


if __name__ == "__main__":
    unittest.main()
