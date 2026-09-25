from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_projection import project
from studio_prompt.adult_illustration_prompt_projection import (
    compile_prompt,
    validate_prompt_projection,
)
from studio_prompt.adult_illustration_taxonomy_prompt import load_prompt_taxonomy
from tests.test_adult_illustration_prompt_profiles import sample_projection


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_NAMES = (
    "prompt-profile-vocabulary.json",
    "taxonomy-source.json",
    "taxonomy-review.json",
)
SOURCE_SHA256 = "298633d94d0031d2081c0893f29c82eab7f0df00b08483ba8f29d1e979441217"


def projection_with_terms(
    tags: list[str], avoid: list[str] | None = None
) -> dict[str, object]:
    intent = copy.deepcopy(sample_projection()["intent"])
    intent["tags"] = list(tags)
    intent["avoid"] = list(avoid or [])
    return project(intent)


def write_contract_root(
    root: Path,
    mutate_review=None,
) -> Path:
    source_dir = ROOT / "research" / "adult-illustration"
    target_dir = root / "research" / "adult-illustration"
    target_dir.mkdir(parents=True)
    for name in CONTRACT_NAMES:
        source = source_dir / name
        target = target_dir / name
        if name == "taxonomy-review.json" and mutate_review is not None:
            value = json.loads(source.read_text(encoding="utf-8"))
            mutate_review(value)
            target.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            target.write_bytes(source.read_bytes())
    return root


def positive_resolutions(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        item["input"]: item
        for item in result["vocabulary_resolutions"]
        if item["channel"] == "positive"
    }


class ReviewedTaxonomyPromptIntegrationTests(unittest.TestCase):
    def test_tag_profile_prefers_reviewed_taxonomy_then_uses_catalog_fallback(self) -> None:
        projection = projection_with_terms(["hot spring", "closed eyes", "rim light"])
        result = compile_prompt(projection, "animagine-xl4-ordered-v1", ROOT)
        positive = result["channels"]["positive"]

        self.assertEqual(
            result["format"], "studio.adult-illustration.prompt-projection/v2"
        )
        self.assertIn("onsen", positive)
        self.assertIn("closed_eyes", positive)
        self.assertIn("rim lighting", positive)
        self.assertNotIn("hot spring", positive)

        resolutions = positive_resolutions(result)
        self.assertEqual(resolutions["hot spring"]["source"], "reviewed_taxonomy")
        self.assertEqual(resolutions["hot spring"]["match_kind"], "alias")
        self.assertEqual(resolutions["hot spring"]["entry_ids"], ["onsen"])
        self.assertEqual(resolutions["hot spring"]["emitted"], ["onsen"])
        self.assertEqual(resolutions["closed eyes"]["emitted"], ["closed_eyes"])
        self.assertEqual(resolutions["rim light"]["source"], "profile_catalog")
        self.assertEqual(resolutions["rim light"]["emitted"], ["rim lighting"])

        taxonomy = result["taxonomy"]
        self.assertTrue(taxonomy["used_for_emission"])
        self.assertEqual(taxonomy["source_sha256"], SOURCE_SHA256)
        self.assertRegex(taxonomy["source_manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(taxonomy["review_manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(taxonomy["reviewed_entries"], 39)

    def test_hybrid_profile_uses_reviewed_display_forms(self) -> None:
        projection = projection_with_terms(
            ["twisted torso", "anime colouring", "closed eyes", "rim light"]
        )
        result = compile_prompt(projection, "anima-aesthetic-hybrid-v1", ROOT)
        positive = result["channels"]["positive"]

        self.assertIn("twisted torso", positive)
        self.assertIn("anime coloring", positive)
        self.assertIn("closed eyes", positive)
        self.assertIn("rim lighting", positive)
        self.assertNotIn("twisted_torso", positive)
        self.assertNotIn("closed_eyes", positive)

        resolutions = positive_resolutions(result)
        self.assertEqual(
            resolutions["anime colouring"]["source"], "reviewed_taxonomy"
        )
        self.assertEqual(
            resolutions["anime colouring"]["emitted"], ["anime coloring"]
        )

    def test_taxonomy_profile_rejection_cannot_fall_back_to_catalog(self) -> None:
        def restrict_onsen(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            entries["onsen"]["profile_ids"] = ["anima-aesthetic-hybrid-v1"]

        projection = projection_with_terms(["hot spring"])
        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), restrict_onsen)
            result = compile_prompt(projection, "animagine-xl4-ordered-v1", root)

        positive = result["channels"]["positive"]
        self.assertNotIn("onsen", positive)
        self.assertNotIn("hot spring", positive)
        self.assertIn(
            "TAXONOMY_UNSUPPORTED_FOR_PROFILE",
            {item["code"] for item in result["diagnostics"]},
        )
        resolution = positive_resolutions(result)["hot spring"]
        self.assertEqual(resolution["source"], "reviewed_taxonomy")
        self.assertEqual(resolution["status"], "unsupported_profile")
        self.assertEqual(resolution["emitted"], [])

    def test_reviewed_term_not_accepted_emits_nothing_without_catalog_fallback(
        self,
    ) -> None:
        def reject_onsen(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            entries["onsen"]["accepted_for_compilation"] = False

        projection = projection_with_terms(["hot spring"])
        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), reject_onsen)
            result = compile_prompt(projection, "animagine-xl4-ordered-v1", root)

        positive = result["channels"]["positive"]
        self.assertNotIn("onsen", positive)
        self.assertNotIn("hot spring", positive)
        self.assertIn(
            "TAXONOMY_TERM_NOT_ACCEPTED",
            {item["code"] for item in result["diagnostics"]},
        )
        resolution = positive_resolutions(result)["hot spring"]
        self.assertEqual(resolution["source"], "reviewed_taxonomy")
        self.assertEqual(resolution["status"], "not_accepted")
        self.assertEqual(resolution["entry_ids"], ["onsen"])
        self.assertEqual(resolution["emitted"], [])
        self.assertFalse(result["taxonomy"]["used_for_emission"])

    def test_reviewed_deprecated_term_emits_nothing(self) -> None:
        def deprecate_onsen(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            # A deprecated entry cannot remain accepted under the review contract.
            entries["onsen"]["accepted_for_compilation"] = False
            entries["onsen"]["deprecated_by"] = "sitting"

        projection = projection_with_terms(["hot spring"])
        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), deprecate_onsen)
            result = compile_prompt(projection, "animagine-xl4-ordered-v1", root)

        positive = result["channels"]["positive"]
        self.assertNotIn("onsen", positive)
        self.assertNotIn("hot spring", positive)
        self.assertIn(
            "TAXONOMY_DEPRECATED_TERM",
            {item["code"] for item in result["diagnostics"]},
        )
        resolution = positive_resolutions(result)["hot spring"]
        self.assertEqual(resolution["source"], "reviewed_taxonomy")
        self.assertEqual(resolution["status"], "deprecated")
        self.assertEqual(resolution["entry_ids"], ["onsen"])
        self.assertEqual(resolution["emitted"], [])
        self.assertFalse(result["taxonomy"]["used_for_emission"])

    def test_implication_target_not_accepted_is_not_emitted(self) -> None:
        def imply_rejected(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            entries["sitting"]["implications"] = ["solo"]
            entries["solo"]["accepted_for_compilation"] = False

        projection = projection_with_terms(["sitting"])
        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), imply_rejected)
            result = compile_prompt(projection, "animagine-xl4-ordered-v1", root)

        positive = result["channels"]["positive"]
        self.assertIn("sitting", positive)
        self.assertNotIn("solo", positive)
        self.assertIn(
            "TAXONOMY_IMPLICATION_NOT_ACCEPTED",
            {item["code"] for item in result["diagnostics"]},
        )
        resolution = positive_resolutions(result)["sitting"]
        self.assertEqual(resolution["source"], "reviewed_taxonomy")
        self.assertEqual(resolution["status"], "partially_emitted")
        self.assertEqual(resolution["entry_ids"], ["sitting", "solo"])
        self.assertEqual(resolution["emitted"], ["sitting"])
        self.assertTrue(result["taxonomy"]["used_for_emission"])

    def test_reviewed_implications_are_emitted_and_profile_ordered(self) -> None:
        def imply_solo(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            entries["sitting"]["implications"] = ["solo"]

        projection = projection_with_terms(["sitting"])
        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), imply_solo)
            result = compile_prompt(projection, "animagine-xl4-ordered-v1", root)

        positive = result["channels"]["positive"]
        self.assertLess(positive.index("solo"), positive.index("sitting"))
        resolution = positive_resolutions(result)["sitting"]
        self.assertEqual(resolution["entry_ids"], ["sitting", "solo"])
        self.assertEqual(resolution["emitted"], ["sitting", "solo"])

    def test_taxonomy_relationship_cycles_fail_closed(self) -> None:
        def add_cycle(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            entries["sitting"]["implications"] = ["solo"]
            entries["solo"]["implications"] = ["sitting"]

        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), add_cycle)
            with self.assertRaisesRegex(ValueError, "contains a cycle"):
                load_prompt_taxonomy(root)

    def test_taxonomy_relationship_depth_is_enforced(self) -> None:
        chain = [
            "solo",
            "sitting",
            "standing",
            "kneeling",
            "twisted_torso",
            "holding",
            "looking_at_viewer",
            "looking_back",
            "smile",
        ]

        def exceed_depth(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            for source, target in zip(chain, chain[1:]):
                entries[source]["implications"] = [target]

        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), exceed_depth)
            with self.assertRaisesRegex(ValueError, "exceeds depth 8"):
                load_prompt_taxonomy(root)

    def test_normalized_taxonomy_alias_collision_fails_closed(self) -> None:
        def collide_alias(value: dict[str, object]) -> None:
            entries = {entry["source_name"]: entry for entry in value["entries"]}
            entries["closed_eyes"]["aliases"].append("hot spring")

        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), collide_alias)
            with self.assertRaisesRegex(ValueError, "alias collision"):
                load_prompt_taxonomy(root)

    def test_changed_review_manifest_invalidates_retained_prompt(self) -> None:
        projection = projection_with_terms(["closed eyes"])
        compiled = compile_prompt(projection, "animagine-xl4-ordered-v1", ROOT)

        def revise_notes(value: dict[str, object]) -> None:
            value["notes"].append("Fixture-only review revision.")

        with tempfile.TemporaryDirectory() as tmp:
            root = write_contract_root(Path(tmp), revise_notes)
            with self.assertRaisesRegex(
                ValueError, "Changed or invalid prompt projection"
            ):
                validate_prompt_projection(compiled, projection, root)

    def test_version_one_prompt_artifact_is_not_reinterpreted_as_version_two(self) -> None:
        projection = projection_with_terms(["closed eyes"])
        compiled = compile_prompt(projection, "animagine-xl4-ordered-v1", ROOT)
        compiled["format"] = "studio.adult-illustration.prompt-projection/v1"

        with self.assertRaisesRegex(
            ValueError, "Changed or invalid prompt projection"
        ):
            validate_prompt_projection(compiled, projection, ROOT)

    def test_instruction_profile_records_tags_without_dumping_them(self) -> None:
        projection = projection_with_terms(["closed eyes"], ["watermark"])
        result = compile_prompt(projection, "qwen-edit-2511-instruction-v1", ROOT)
        instruction = result["channels"]["instruction"]

        self.assertNotIn("closed eyes", instruction)
        self.assertIn("Exclude: watermark.", instruction)
        self.assertFalse(result["taxonomy"]["used_for_emission"])
        resolutions = {
            (item["channel"], item["input"]): item
            for item in result["vocabulary_resolutions"]
        }
        self.assertEqual(
            resolutions[("positive", "closed eyes")]["status"],
            "not_emitted_instruction_profile",
        )
        self.assertEqual(
            resolutions[("negative", "watermark")]["status"],
            "instruction_exclusion",
        )
        self.assertEqual(
            resolutions[("positive", "closed eyes")]["emitted"], []
        )
        self.assertEqual(
            resolutions[("negative", "watermark")]["emitted"], ["watermark"]
        )


if __name__ == "__main__":
    unittest.main()
