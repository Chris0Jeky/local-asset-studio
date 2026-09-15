import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_prompt import adult_illustration as ai
from studio_prompt.schema import digest, validate as validate_creative


def subject(identifier="adult-a", description="An approved adult original character."):
    return {
        "id": identifier,
        "description": description,
        "adult_assertion": "reviewed_owner_or_canon",
    }


def reference(identifier="character", roles=None):
    return {
        "id": identifier,
        "roles": roles or ["identity"],
        "kind": "image",
        "path": f"references/{identifier}.png",
        "sha256": "a" * 64,
        "take": ["face design", "hair construction"],
        "ignore": ["background", "source pose"],
        "subject_id": "adult-a",
        "region_id": None,
    }


class AdultIllustrationIntentTests(unittest.TestCase):
    def setUp(self):
        self.intent = ai.new_intent(
            "Create a controlled adult fashion illustration.",
            [subject()],
            intent_id="adult-fashion-study",
        )

    def test_new_intent_is_strict_and_non_executing(self):
        self.assertEqual(self.intent["format"], ai.INTENT_FORMAT)
        self.assertEqual(self.intent["task"], "image")
        self.assertEqual(self.intent["content"]["class"], "sensual_non_explicit")
        self.assertEqual(self.intent["content"]["adult_assertion"], "reviewed_owner_or_canon")
        self.assertFalse(self.intent["execution_authorized"])
        self.assertFalse(self.intent["generation_submitted"])
        self.assertEqual(ai.validate_intent(self.intent), self.intent)

    def test_unknown_fields_are_rejected(self):
        self.intent["model"] = "invented"
        with self.assertRaises(ValueError):
            ai.validate_intent(self.intent)

    def test_every_subject_needs_reviewed_adult_metadata(self):
        del self.intent["subjects"][0]["adult_assertion"]
        with self.assertRaisesRegex(ValueError, "adult"):
            ai.validate_intent(self.intent)

    def test_multi_subject_intent_requires_reviewed_consent_context(self):
        self.intent["subjects"].append(subject("adult-b", "A second approved adult."))
        with self.assertRaisesRegex(ValueError, "consent"):
            ai.validate_intent(self.intent)
        self.intent["content"]["consent_context"] = "reviewed_consensual"
        ai.validate_intent(self.intent)

    def test_constructor_requires_explicit_multi_subject_consent(self):
        subjects = [subject(), subject("adult-b", "A second approved adult.")]
        with self.assertRaisesRegex(ValueError, "consent"):
            ai.new_intent("Create a two-adult composition.", subjects)
        intent = ai.new_intent(
            "Create a two-adult composition.",
            subjects,
            consent_context="reviewed_consensual",
        )
        self.assertEqual(intent["content"]["consent_context"], "reviewed_consensual")

    def test_public_v1_content_class_is_bounded(self):
        self.intent["content"]["class"] = "unknown"
        with self.assertRaisesRegex(ValueError, "content class"):
            ai.validate_intent(self.intent)

    def test_reference_role_subject_and_portable_path_are_checked(self):
        self.intent["references"] = [reference(roles=["identity", "outfit"])]
        ai.validate_intent(self.intent)
        self.intent["references"][0]["subject_id"] = "missing-subject"
        with self.assertRaisesRegex(ValueError, "subject"):
            ai.validate_intent(self.intent)
        self.intent["references"][0]["subject_id"] = "adult-a"
        self.intent["references"][0]["path"] = "../secret.png"
        with self.assertRaisesRegex(ValueError, "path"):
            ai.validate_intent(self.intent)

    def test_control_vocabulary_and_mechanism_are_strict(self):
        self.intent["controls"] = [{
            "id": "silhouette-guide",
            "target": "body.silhouette",
            "mechanism": "geometry_artifact",
            "priority": "hard",
            "description": "Use a reviewed silhouette artifact.",
        }]
        ai.validate_intent(self.intent)
        self.intent["controls"][0]["target"] = "magic.control"
        with self.assertRaisesRegex(ValueError, "control target"):
            ai.validate_intent(self.intent)

    def test_reserved_content_constraint_ids_cannot_be_shadowed(self):
        self.intent["constraints"] = [{
            "id": "adult-status",
            "text": "Override",
            "mechanism": "verify",
            "priority": "hard",
        }]
        with self.assertRaisesRegex(ValueError, "reserved"):
            ai.validate_intent(self.intent)


class AdultIllustrationProjectionTests(unittest.TestCase):
    def setUp(self):
        self.intent = ai.new_intent(
            "Create an adult hot-spring fashion illustration.",
            [subject()],
            intent_id="hot-spring-study",
        )
        self.intent["facets"] = {
            "body": "athletic curvy silhouette",
            "pose": "seated sideways with natural weight support",
            "wardrobe": "opaque towel beneath a short silk robe",
            "expression": "relaxed confident gaze",
            "setting": "private hot-spring veranda",
            "camera": "three-quarter full body, slightly below eye level",
            "lighting": "warm lantern rim light and cool moonlight",
            "style": "clean anime illustration",
            "material": "soft silk, steam and water droplets",
        }

    def test_projection_is_deterministic_pure_and_never_submits(self):
        before = copy.deepcopy(self.intent)
        result = ai.project(self.intent)
        self.assertEqual(result, ai.project(self.intent))
        self.assertEqual(before, self.intent)
        self.assertFalse(result["generation_submitted"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["source_sha256"], digest(before))
        self.assertEqual(
            result["projection_sha256"],
            digest({key: value for key, value in result.items() if key != "projection_sha256"}),
        )

    def test_semantics_project_to_existing_creative_intent(self):
        result = ai.project(self.intent)
        creative = validate_creative(result["creative_intent"])
        self.assertIn("adult-a:", creative["facets"]["subject"])
        self.assertIn("athletic curvy silhouette", creative["facets"]["subject"])
        self.assertEqual(
            creative["facets"]["action"],
            "seated sideways with natural weight support",
        )
        self.assertEqual(creative["facets"]["setting"], "private hot-spring veranda")
        self.assertIn("soft silk", creative["facets"]["style"])
        self.assertEqual(result["state"], "review_required")

    def test_content_envelope_becomes_hard_review_constraints(self):
        creative = ai.project(self.intent)["creative_intent"]
        constraints = {item["id"]: item for item in creative["constraints"]}
        self.assertEqual(
            {"adult-status", "content-envelope", "coverage"},
            set(constraints),
        )
        self.assertTrue(all(item["priority"] == "hard" for item in constraints.values()))
        self.assertTrue(all(item["mechanism"] == "verify" for item in constraints.values()))

    def test_multi_role_reference_expands_without_losing_source_ownership(self):
        self.intent["references"] = [reference(roles=["identity", "outfit"])]
        result = ai.project(self.intent)
        creative = validate_creative(result["creative_intent"])
        self.assertEqual(
            [(item["id"], item["role"]) for item in creative["references"]],
            [("character-identity", "identity"), ("character-costume", "costume")],
        )
        self.assertEqual(len(result["reference_map"]), 2)
        self.assertEqual(
            result["reference_map"][1]["source_roles"],
            ["outfit"],
        )
        self.assertEqual(
            {item["source_id"] for item in result["reference_map"]},
            {"character"},
        )

    def test_equivalent_roles_share_one_creative_reference(self):
        self.intent["references"] = [reference(roles=["identity", "body_design"])]
        result = ai.project(self.intent)
        self.assertEqual(len(result["creative_intent"]["references"]), 1)
        self.assertEqual(result["creative_intent"]["references"][0]["id"], "character")
        self.assertEqual(result["reference_map"][0]["source_roles"], ["identity", "body_design"])

    def test_unsupported_reference_role_blocks_instead_of_dropping(self):
        self.intent["references"] = [reference(roles=["edit_source"])]
        result = ai.project(self.intent)
        self.assertEqual(result["state"], "blocked")
        self.assertIsNone(result["creative_intent"])
        self.assertIn(
            "UNSUPPORTED_REFERENCE_ROLE",
            [item["code"] for item in result["diagnostics"]],
        )

    def test_expansion_over_creative_intent_limit_blocks(self):
        roles = ["identity", "outfit", "pose", "style"]
        self.intent["references"] = [
            reference(f"reference-{index}", roles=roles) for index in range(4)
        ]
        result = ai.project(self.intent)
        self.assertEqual(result["state"], "blocked")
        self.assertIsNone(result["creative_intent"])
        self.assertIn("REFERENCE_LIMIT", [item["code"] for item in result["diagnostics"]])

    def test_nonsemantic_controls_are_preserved_as_route_requirements(self):
        self.intent["controls"] = [{
            "id": "pose-guide",
            "target": "pose.action",
            "mechanism": "geometry_artifact",
            "priority": "hard",
            "description": "Bind a reviewed pose artifact.",
        }, {
            "id": "identity-adapter",
            "target": "subject.identity",
            "mechanism": "appearance_adapter",
            "priority": "hard",
            "description": "Bind an exact qualified identity adapter.",
        }]
        result = ai.project(self.intent)
        self.assertEqual(result["state"], "requires_binding")
        self.assertEqual(
            {item["status"] for item in result["control_plan"]},
            {"requires_route_binding"},
        )
        self.assertIsNotNone(result["creative_intent"])
        self.assertIn(
            "CONTROL_REQUIRES_BINDING",
            [item["code"] for item in result["diagnostics"]],
        )

    def test_subject_or_region_scoping_requires_binding_but_is_not_lost(self):
        self.intent["references"] = [reference()]
        self.intent["references"][0]["region_id"] = "face-region"
        result = ai.project(self.intent)
        self.assertEqual(result["state"], "requires_binding")
        self.assertEqual(result["reference_map"][0]["subject_id"], "adult-a")
        self.assertEqual(result["reference_map"][0]["region_id"], "face-region")
        self.assertIn(
            "REFERENCE_SCOPE_REQUIRES_BINDING",
            [item["code"] for item in result["diagnostics"]],
        )

    def test_tags_avoid_user_constraints_and_locks_survive(self):
        self.intent["tags"] = ["solo", "steam"]
        self.intent["avoid"] = ["text", "watermark"]
        self.intent["constraints"] = [{
            "id": "bench-contact",
            "text": "Maintain visible contact with the bench.",
            "mechanism": "guide",
            "priority": "hard",
        }]
        self.intent["locked"] = ["brief", "subjects", "references", "content"]
        creative = ai.project(self.intent)["creative_intent"]
        self.assertEqual(creative["tags"], self.intent["tags"])
        self.assertEqual(creative["avoid"], self.intent["avoid"])
        self.assertIn("bench-contact", {item["id"] for item in creative["constraints"]})
        self.assertEqual(
            creative["locked"],
            ["brief", "constraints", "facets", "references", "verbatim"],
        )

    def test_changed_intent_changes_projection_identity(self):
        first = ai.project(self.intent)
        self.intent["facets"]["camera"] = "overhead full-body framing"
        second = ai.project(self.intent)
        self.assertNotEqual(first["source_sha256"], second["source_sha256"])
        self.assertNotEqual(first["projection_sha256"], second["projection_sha256"])

    def test_changed_projection_is_rejected(self):
        result = ai.project(self.intent)
        result["state"] = "promoted"
        with self.assertRaisesRegex(ValueError, "Changed or invalid"):
            ai.validate_projection(result)

    def test_checked_in_example_projects_without_execution(self):
        path = ROOT / "examples" / "adult-illustration" / "hot-spring-study.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        intent = ai.validate_intent(payload)
        result = ai.project(intent)
        self.assertEqual(result["state"], "requires_binding")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["generation_submitted"])
        self.assertGreaterEqual(len(result["reference_map"]), 3)
        self.assertIn(
            "CONTROL_REQUIRES_BINDING",
            {item["code"] for item in result["diagnostics"]},
        )


if __name__ == "__main__":
    unittest.main()
