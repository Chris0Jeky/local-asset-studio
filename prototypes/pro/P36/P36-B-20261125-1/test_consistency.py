from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from consistency import ConsistencyError, measure_regions, policy_digest, score_sheet
from fixture_helpers import REGIONS, feature, fixture


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.anchor_sha = "a" * 64
        self.media_sha = "b" * 64
        self.policy = {
            "version": 1,
            "features": {"iris": {"kind": "rgb", "tolerance": 0.02},
                         "ratio": {"kind": "ratio", "tolerance": 0.025},
                         "mark": {"kind": "trait"}},
            "required": {"turnaround": {"front": ["iris", "ratio", "mark"]}},
        }
        self.anchor = {"iris": feature([45, 120, 200], self.anchor_sha),
                       "ratio": feature(0.2, self.anchor_sha, "human_annotated"),
                       "mark": feature("left-cheek", self.anchor_sha, "human_annotated")}
        observations = copy.deepcopy(self.anchor)
        for record in observations.values():
            record["media_sha256"] = self.media_sha
        self.sheet = {"views": [{"id": "front", "media_sha256": self.media_sha, "features": observations}]}

    def score(self):
        return score_sheet(self.anchor, self.sheet, self.policy, "turnaround")

    def test_baseline_preserves_truth_boundaries(self):
        result = self.score()
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["annotation_checks"], 2)
        self.assertFalse(result["perceptual_identity_verified"])
        self.assertFalse(result["art_acceptance_implied"])
        self.assertFalse(result["generation_implied"])
        self.assertFalse(result["licence_clearance_implied"])
        self.assertFalse(result["provenance_verified"])
        self.assertTrue(result["review_required"])

    def test_critical_fail_cannot_be_averaged_away(self):
        names = ["f" + str(n) for n in range(20)]
        self.policy = {"version": 1, "features": {n: {"kind": "trait"} for n in names},
                       "required": {"turnaround": {"front": names}}}
        self.anchor = {n: feature("same", self.anchor_sha) for n in names}
        self.sheet["views"][0]["features"] = {n: feature("same", self.media_sha) for n in names}
        self.sheet["views"][0]["features"]["f19"]["value"] = "wrong"
        result = self.score()
        self.assertEqual(result["score"], 0.95)
        self.assertFalse(result["passed"])
        self.assertEqual(result["blockers"], ["critical_mismatch:front:f19"])

    def test_missing_view_blocks(self):
        self.policy["required"]["turnaround"]["back"] = ["mark"]
        result = self.score()
        self.assertIn("view_missing:back", result["blockers"])
        self.assertFalse(result["coverage_complete"])

    def test_duplicate_view_id_blocks(self):
        self.sheet["views"].append(copy.deepcopy(self.sheet["views"][0]))
        self.assertIn("view_duplicate:front", self.score()["blockers"])

    def test_same_media_cannot_fulfil_multiple_required_views(self):
        self.policy["required"]["turnaround"]["back"] = ["mark"]
        other = copy.deepcopy(self.sheet["views"][0])
        other["id"] = "back"
        self.sheet["views"].append(other)
        result = self.score()
        self.assertFalse(result["passed"])
        self.assertTrue(any(code.startswith("duplicate_required_media:") for code in result["blockers"]))

    def test_profile_and_back_require_only_policy_visible_features(self):
        self.policy["required"]["turnaround"] = {"front": ["iris"], "left": ["iris"], "back": ["mark"]}
        for view, sha, names in (("left", "c" * 64, ["iris"]), ("back", "d" * 64, ["mark"])):
            observations = {name: copy.deepcopy(self.anchor[name]) for name in names}
            for observation in observations.values():
                observation["media_sha256"] = sha
            self.sheet["views"].append({"id": view, "media_sha256": sha, "features": observations})
        result = self.score()
        self.assertTrue(result["passed"])
        self.assertEqual(result["required_observations"], 3)

    def test_missing_observation_cannot_declare_itself_not_applicable(self):
        self.sheet["views"][0]["features"]["iris"] = {"state": "not_applicable", "reason": "occluded"}
        result = self.score()
        self.assertFalse(result["passed"])
        self.assertFalse(result["coverage_complete"])

    def test_feature_hash_must_match_view(self):
        self.sheet["views"][0]["features"]["iris"]["media_sha256"] = "f" * 64
        self.assertIn("observation_hash_mismatch:front:iris", self.score()["blockers"])

    def test_missing_anchor_cannot_be_inferred_from_candidate(self):
        del self.anchor["iris"]
        self.assertIn("anchor_observation_shape_invalid:iris", self.score()["blockers"])

    def test_unsupported_stage_fails(self):
        result = score_sheet(self.anchor, self.sheet, self.policy, "engine")
        self.assertEqual(result["blockers"], ["stage_unsupported"])

    def test_diagnostics_do_not_increase_score_or_waive_failure(self):
        self.sheet["views"][0]["features"]["iris"]["value"] = [255, 0, 0]
        before = self.score()
        self.sheet["views"][0]["features"]["extra"] = {"value": "perfect"}
        self.sheet["views"].append({"id": "diagnostic", "accepted": True})
        self.sheet.update(score=1.0, passed=True, tolerance=99999, required=[])
        after = self.score()
        self.assertEqual(before["score"], after["score"])
        self.assertEqual(before["blockers"], after["blockers"])
        self.assertEqual(after["ignored_features"], ["front:extra"])
        self.assertEqual(after["ignored_views"], ["diagnostic"])

    def test_invalid_required_values_fail(self):
        for value in (True, float("nan"), float("inf"), -0.1, "0.2", None, 10 ** 400):
            with self.subTest(value=value):
                self.sheet["views"][0]["features"]["ratio"]["value"] = value
                self.assertIn("feature_value_invalid:front:ratio", self.score()["blockers"])
        for value in ([True, 2, 3], [0, 1, float("nan")], [0, 1, 256], [0, 1], (0, 1, 2)):
            with self.subTest(value=value):
                self.sheet["views"][0]["features"]["iris"]["value"] = value
                self.assertIn("feature_value_invalid:front:iris", self.score()["blockers"])

    def test_invalid_policy_tolerances_fail(self):
        for tolerance in (True, float("nan"), float("inf"), -1, 1.01, "0.1"):
            with self.subTest(tolerance=tolerance):
                self.policy["features"]["iris"]["tolerance"] = tolerance
                self.assertEqual(self.score()["blockers"], ["policy_tolerance_invalid"])

    def test_policy_digest_changes_with_threshold_and_requirements(self):
        first = policy_digest(self.policy)
        self.policy["features"]["iris"]["tolerance"] = 0.03
        second = policy_digest(self.policy)
        self.policy["required"]["turnaround"]["back"] = ["mark"]
        self.assertEqual(len({first, second, policy_digest(self.policy)}), 3)

    def test_policy_mapping_order_does_not_change_digest(self):
        reordered = dict(reversed(list(self.policy.items())))
        self.assertEqual(policy_digest(self.policy), policy_digest(reordered))

    def test_bad_policy_shapes_and_duplicate_requirements_fail(self):
        mutations = [
            lambda p: p.update(version=True),
            lambda p: p.update(version=2),
            lambda p: p.update(extra="waiver"),
            lambda p: p["features"]["iris"].update(critical=False),
            lambda p: p["required"]["turnaround"]["front"].append("iris"),
            lambda p: p["required"]["turnaround"]["front"].append("unknown"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                policy = copy.deepcopy(self.policy)
                mutation(policy)
                result = score_sheet(self.anchor, self.sheet, policy, "turnaround")
                self.assertFalse(result["passed"])
                self.assertTrue(result["blockers"])

    def test_ratio_boundary_uses_unrounded_distance(self):
        self.anchor["ratio"]["value"] = 0.25
        self.policy["features"]["ratio"]["tolerance"] = 0.125
        self.sheet["views"][0]["features"]["ratio"]["value"] = 0.375
        self.assertTrue(self.score()["passed"])
        self.sheet["views"][0]["features"]["ratio"]["value"] = math.nextafter(0.375, 1.0)
        self.assertFalse(self.score()["passed"])

    def test_unrecognized_provenance_cannot_claim_verified(self):
        self.sheet["views"][0]["features"]["iris"]["provenance"] = "identity_verified"
        self.assertIn("provenance_invalid:front:iris", self.score()["blockers"])

    def test_invalid_provenance_types_refuse_without_exception(self):
        for provenance in ([], {}, 1, None):
            with self.subTest(provenance=provenance):
                self.sheet["views"][0]["features"]["iris"]["provenance"] = provenance
                self.assertIn("provenance_invalid:front:iris", self.score()["blockers"])

    def test_occluded_or_uncertain_value_cannot_pass_even_when_value_matches(self):
        for state in ("not_visible", "uncertain", "occluded", "not_applicable"):
            with self.subTest(state=state):
                self.sheet["views"][0]["features"]["iris"]["state"] = state
                self.assertIn("observation_unavailable:front:iris", self.score()["blockers"])

    def test_non_string_diagnostic_key_does_not_crash(self):
        self.sheet["views"][0]["features"][123] = {"value": "ignored"}
        self.assertTrue(self.score()["passed"])

    def test_result_is_deterministic_and_json_safe(self):
        self.assertEqual(self.score(), self.score())
        json.dumps(self.score(), allow_nan=False)


class PixelTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parents[4] / '.runtime' / 'pro' / 'P36-B-20261125-1' / 'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=runtime)
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def save(self, name, **kwargs):
        path = self.root / name
        sha = fixture(path, **kwargs)
        return path, sha

    def test_reads_real_pixels_and_exact_hash(self):
        path, sha = self.save("anchor.png")
        values = measure_regions(path, sha, REGIONS)
        self.assertEqual(values["iris"]["value"], [45.0, 120.0, 200.0])
        self.assertEqual(values["hair"]["value"], [70.0, 40.0, 20.0])
        self.assertTrue(all(v["media_sha256"] == sha and v["provenance"] == "pixel_measured" for v in values.values()))

    def test_pixel_mutation_changes_measurement_and_hard_gate(self):
        anchor_path, anchor_sha = self.save("anchor.png")
        changed_path, changed_sha = self.save("changed.png", iris=(255, 20, 20))
        anchor = measure_regions(anchor_path, anchor_sha, REGIONS)
        changed = measure_regions(changed_path, changed_sha, REGIONS)
        policy = {"version": 1, "features": {name: {"kind": "rgb", "tolerance": 0.02} for name in REGIONS},
                  "required": {"turnaround": {"front": list(REGIONS)}}}
        result = score_sheet(anchor, {"views": [{"id": "front", "media_sha256": changed_sha, "features": changed}]}, policy, "turnaround")
        self.assertEqual(result["blockers"], ["critical_mismatch:front:iris"])

    def test_outfit_and_expression_changes_preserve_identity_proxy(self):
        anchor_path, anchor_sha = self.save("anchor.png")
        changed_path, changed_sha = self.save("changed.png", outfit=(180, 40, 200), expression="smile")
        anchor = measure_regions(anchor_path, anchor_sha, REGIONS)
        changed = measure_regions(changed_path, changed_sha, REGIONS)
        self.assertNotEqual(anchor_sha, changed_sha)
        self.assertEqual({n: f["value"] for n, f in anchor.items()}, {n: f["value"] for n, f in changed.items()})

    def test_known_limit_geometry_drift_outside_roi_does_not_establish_acceptance(self):
        anchor_path, anchor_sha = self.save("anchor.png")
        changed_path, changed_sha = self.save("changed.png", geometry="angular")
        anchor = measure_regions(anchor_path, anchor_sha, REGIONS)
        changed = measure_regions(changed_path, changed_sha, REGIONS)
        policy = {"version": 1, "features": {name: {"kind": "rgb", "tolerance": 0.02} for name in REGIONS},
                  "required": {"turnaround": {"front": list(REGIONS)}}}
        result = score_sheet(anchor, {"views": [{"id": "front", "media_sha256": changed_sha, "features": changed}]}, policy, "turnaround")
        self.assertNotEqual(anchor_sha, changed_sha)
        self.assertTrue(result["passed"])
        self.assertFalse(result["perceptual_identity_verified"])
        self.assertFalse(result["art_acceptance_implied"])
        self.assertTrue(result["review_required"])

    def test_file_replacement_cannot_reuse_old_hash(self):
        path, sha = self.save("image.png")
        fixture(path, iris=(255, 0, 0))
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, REGIONS)
        self.assertEqual(raised.exception.code, "media_hash_mismatch")

    def test_transparent_roi_blocks_and_threshold_cannot_be_weakened(self):
        path, _ = self.save("image.png")
        with Image.open(path) as source:
            image = source.convert("RGBA")
        image.paste((45, 120, 200, 0), (32, 32, 48, 48))
        image.save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, REGIONS)
        self.assertEqual(raised.exception.code, "region_alpha_insufficient:iris")
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, REGIONS, min_alpha=0)
        self.assertEqual(raised.exception.code, "alpha_threshold_invalid")

    def test_alpha_boundary_and_transparent_rgb_not_counted(self):
        path = self.root / "alpha.png"
        image = Image.new("RGBA", (10, 10), (20, 40, 60, 255))
        for x in range(5):
            image.putpixel((x, 0), (255, 0, 0, 0))
        image.save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        values = measure_regions(path, sha, {"all": [0, 0, 1, 1]})
        self.assertEqual(values["all"]["value"], [20.0, 40.0, 60.0])
        self.assertEqual(values["all"]["alpha_coverage"], 0.95)
        image.putpixel((5, 0), (255, 0, 0, 0))
        image.save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, {"all": [0, 0, 1, 1]})
        self.assertEqual(raised.exception.code, "region_alpha_insufficient:all")

    def test_regions_reject_bool_nan_empty_and_out_of_bounds(self):
        path, sha = self.save("image.png")
        for roi in ([True, 0, 1, 1], [0, 0, float("nan"), 1], [0.5, 0, 0.5, 1], [-0.1, 0, 1, 1], [0, 0, 2, 1]):
            with self.subTest(roi=roi), self.assertRaises(ConsistencyError):
                measure_regions(path, sha, {"iris": roi})

    def test_non_png_is_refused(self):
        path = self.root / "fake.png"
        Image.new("RGB", (10, 10)).save(path, format="JPEG")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, {"all": [0, 0, 1, 1]})
        self.assertEqual(raised.exception.code, "media_format_unsupported")

    def test_animated_png_is_refused(self):
        path = self.root / "animation.png"
        first = Image.new("RGBA", (10, 10), "red")
        second = Image.new("RGBA", (10, 10), "blue")
        first.save(path, save_all=True, append_images=[second], duration=100, loop=0)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, {"all": [0, 0, 1, 1]})
        self.assertEqual(raised.exception.code, "media_animated")

    def test_oversized_dimensions_refused_before_pixel_measurement(self):
        path = self.root / "wide.png"
        Image.new("RGB", (4097, 1)).save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, {"all": [0, 0, 1, 1]})
        self.assertEqual(raised.exception.code, "media_dimensions_exceeded")

    def test_corrupt_png_refused(self):
        path, _ = self.save("image.png")
        path.write_bytes(path.read_bytes()[:80])
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ConsistencyError) as raised:
            measure_regions(path, sha, REGIONS)
        self.assertEqual(raised.exception.code, "media_decode_failed")

    def test_measurement_is_repeatable_and_read_only(self):
        path, sha = self.save("image.png")
        before = set(self.root.iterdir()), path.read_bytes()
        first = measure_regions(path, sha, REGIONS)
        self.assertEqual(first, measure_regions(path, sha, REGIONS))
        self.assertEqual(before, (set(self.root.iterdir()), path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
