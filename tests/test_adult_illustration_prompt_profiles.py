from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from studio_prompt.adult_illustration_projection import project
from studio_prompt.adult_illustration_prompt_catalog import load_catalog
from studio_prompt.adult_illustration_prompt_projection import (
    compile_prompt,
    validate_prompt_projection,
)


ROOT = Path(__file__).resolve().parents[1]


def sample_projection(reference_count: int = 3) -> dict:
    intent = json.loads(
        (ROOT / "examples/adult-illustration/hot-spring-study.json").read_text(
            encoding="utf-8"
        )
    )
    intent["tags"] = [
        "solo",
        "sitting",
        "torso_twist",
        "looking_at_viewer",
        "steam",
        "mystery_token",
    ]
    intent["avoid"] = ["text", "watermark", "copied background"]
    references = [
        {
            "id": "character-canon",
            "roles": ["identity"],
            "kind": "image",
            "path": "references/character.png",
            "sha256": "a" * 64,
            "take": ["face design", "hair construction", "body design"],
            "ignore": ["source outfit", "source pose", "source background"],
            "subject_id": "adult-a",
            "region_id": None,
        },
        {
            "id": "robe-study",
            "roles": ["outfit"],
            "kind": "image",
            "path": "references/robe.png",
            "sha256": "b" * 64,
            "take": ["robe construction", "silk drape"],
            "ignore": ["source person", "source pose", "source background"],
            "subject_id": "adult-a",
            "region_id": "wardrobe",
        },
        {
            "id": "pose-study",
            "roles": ["pose"],
            "kind": "image",
            "path": "references/pose.png",
            "sha256": "c" * 64,
            "take": ["weight distribution", "torso turn", "camera elevation"],
            "ignore": ["source identity", "source clothing", "source background"],
            "subject_id": "adult-a",
            "region_id": "full-body",
        },
        {
            "id": "palette-study",
            "roles": ["palette"],
            "kind": "image",
            "path": "references/palette.png",
            "sha256": "d" * 64,
            "take": ["charcoal amber and cool blue palette"],
            "ignore": ["source person", "source pose", "source clothing"],
            "subject_id": None,
            "region_id": None,
        },
    ]
    intent["references"] = references[:reference_count]
    return project(intent)


class PromptProfileCatalogTests(unittest.TestCase):
    def test_catalog_is_pinned_non_executing_and_has_three_profiles(self) -> None:
        catalog = load_catalog(ROOT)
        self.assertEqual(
            set(catalog["profiles"]),
            {
                "anima-aesthetic-hybrid-v1",
                "animagine-xl4-ordered-v1",
                "qwen-edit-2511-instruction-v1",
            },
        )
        self.assertTrue(all(value is False for value in catalog["authority"].values()))
        for profile in catalog["profiles"].values():
            self.assertRegex(profile["source_revision"], r"^[0-9a-f]{40}$")
            self.assertRegex(profile["documentation_revision"], r"^[0-9a-f]{40}$")

    def test_catalog_rejects_alias_collision(self) -> None:
        source = ROOT / "research/adult-illustration/prompt-profile-vocabulary.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["entries"][1]["aliases"].append(
            data["entries"][0]["canonical"].replace(" ", "_")
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "research/adult-illustration"
            target.mkdir(parents=True)
            (target / source.name).write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "alias collision"):
                load_catalog(root)


class PromptProjectionTests(unittest.TestCase):
    def test_animagine_compiles_verified_ordered_tags_and_keeps_unknowns_visible(self) -> None:
        result = compile_prompt(sample_projection(), "animagine-xl4-ordered-v1", ROOT)
        positive = result["channels"]["positive"]
        self.assertLess(positive.index("solo"), positive.index("sitting"))
        self.assertLess(positive.index("sitting"), positive.index("twisted_torso"))
        self.assertTrue(
            positive.endswith("masterpiece, high score, great score, absurdres")
        )
        self.assertNotIn("score_9", positive)
        self.assertIsNone(result["channels"]["instruction"])
        self.assertIn("text", result["channels"]["negative"])
        self.assertIn("watermark", result["channels"]["negative"])
        self.assertIn(
            "UNKNOWN_VOCABULARY",
            {item["code"] for item in result["diagnostics"]},
        )
        self.assertIn(
            "CONTROL_REQUIRES_ROUTE_BINDING",
            {item["code"] for item in result["diagnostics"]},
        )
        self.assertNotIn("Bind a reviewed full-body pose artifact", positive)

    def test_anima_hybrid_preserves_verified_tags_and_adds_reviewed_prose(self) -> None:
        result = compile_prompt(sample_projection(), "anima-aesthetic-hybrid-v1", ROOT)
        positive = result["channels"]["positive"]
        self.assertIn("solo", positive)
        self.assertIn("twisted torso", positive)
        self.assertNotIn("torso_twist", positive)
        self.assertIn("approved adult original character", positive)
        self.assertIn("private hot-spring veranda", positive)
        self.assertIsNone(result["channels"]["instruction"])
        self.assertTrue(all(value is False for value in result["authority"].values()))

    def test_qwen_compiles_ordered_reference_ownership_without_tag_dump(self) -> None:
        result = compile_prompt(sample_projection(), "qwen-edit-2511-instruction-v1", ROOT)
        instruction = result["channels"]["instruction"]
        self.assertIsNone(result["channels"]["positive"])
        self.assertIsNone(result["channels"]["negative"])
        self.assertIn("Image 1", instruction)
        self.assertIn("identity", instruction)
        self.assertIn("face design", instruction)
        self.assertIn(
            "Do not copy: source outfit, source pose, source background", instruction
        )
        self.assertLess(instruction.index("Image 1"), instruction.index("Image 2"))
        self.assertLess(instruction.index("Image 2"), instruction.index("Image 3"))
        self.assertNotIn("mystery_token", instruction)
        self.assertEqual(
            [item["id"] for item in result["reference_bindings"]],
            ["character-canon", "robe-study", "pose-study"],
        )

    def test_qwen_refuses_more_references_than_the_pinned_graph_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 3 references"):
            compile_prompt(
                sample_projection(reference_count=4),
                "qwen-edit-2511-instruction-v1",
                ROOT,
            )

    def test_compilation_is_deterministic_and_validation_detects_tampering(self) -> None:
        projection = sample_projection()
        first = compile_prompt(projection, "animagine-xl4-ordered-v1", ROOT)
        second = compile_prompt(
            copy.deepcopy(projection), "animagine-xl4-ordered-v1", ROOT
        )
        self.assertEqual(first, second)
        self.assertEqual(validate_prompt_projection(first, projection, ROOT), first)
        changed = copy.deepcopy(first)
        changed["channels"]["positive"] += ", score_9"
        with self.assertRaisesRegex(ValueError, "Changed or invalid prompt projection"):
            validate_prompt_projection(changed, projection, ROOT)

    def test_changed_source_projection_is_rejected(self) -> None:
        projection = sample_projection()
        projection["creative_intent"]["brief"] += " Changed without reprojection."
        with self.assertRaisesRegex(
            ValueError, "Changed or invalid adult illustration projection"
        ):
            compile_prompt(projection, "animagine-xl4-ordered-v1", ROOT)

    def test_invalid_or_authoritative_source_projection_is_rejected(self) -> None:
        projection = sample_projection()
        projection["execution_authorized"] = True
        with self.assertRaisesRegex(
            ValueError, "Changed or invalid adult illustration projection"
        ):
            compile_prompt(projection, "animagine-xl4-ordered-v1", ROOT)


if __name__ == "__main__":
    unittest.main()
