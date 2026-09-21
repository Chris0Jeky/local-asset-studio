import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_adult_illustration_intelligence.py"
TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from adult_illustration_intelligence_fixtures import valid_documents, write_documents


def load_validator():
    spec = importlib.util.spec_from_file_location("adult_intelligence_validator", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load validator from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdultIllustrationIntelligenceValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def validate(self, mutate=None):
        documents = valid_documents()
        if mutate:
            mutate(documents)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_documents(root, documents)
            return self.validator.validate_paths(root)

    def test_valid_contracts_pass_without_runtime_authority(self):
        self.assertEqual(self.validate(), [])

    def test_missing_required_manifest_is_reported(self):
        errors = self.validate(lambda docs: docs.pop("prompt-dialects.json"))
        self.assertTrue(any("missing required manifest" in error for error in errors))

    def test_duplicate_json_keys_are_rejected(self):
        documents = valid_documents()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_documents(root, documents)
            path = root / "research" / "adult-illustration" / "prompt-dialects.json"
            path.write_text(
                '{"schema":"a","schema":"b","kind":"x"}', encoding="utf-8"
            )
            errors = self.validator.validate_paths(root)
        self.assertTrue(any("Duplicate JSON key" in error for error in errors))

    def test_prompt_dialect_cannot_be_executable_or_authoritative(self):
        def mutate(docs):
            docs["prompt-dialects.json"]["executable"] = True
            docs["prompt-dialects.json"]["authority"] = "generation"

        errors = self.validate(mutate)
        joined = "\n".join(errors)
        self.assertIn("executable false", joined)
        self.assertIn("authority none", joined)

    def test_prompt_profile_rejects_unknown_route_and_mixed_mode(self):
        def mutate(docs):
            profile = docs["prompt-dialects.json"]["profiles"][0]
            profile["route_candidate_ids"] = ["missing-route"]
            profile["mode"] = "mixed-family-magic"

        errors = self.validate(mutate)
        joined = "\n".join(errors)
        self.assertIn("unknown route", joined)
        self.assertIn("unsupported prompt mode", joined)

    def test_instruction_profile_refuses_tag_separator(self):
        def mutate(docs):
            docs["prompt-dialects.json"]["profiles"][1]["tag_separator"] = ", "

        errors = self.validate(mutate)
        self.assertTrue(any("instruction profile" in error for error in errors))

    def test_prompt_profile_rejects_unknown_vocabulary_contract(self):
        def mutate(docs):
            docs["prompt-dialects.json"]["profiles"][0]["vocabulary_ids"] = [
                "missing-vocabulary"
            ]

        errors = self.validate(mutate)
        self.assertTrue(any("unknown vocabulary" in error for error in errors))

    def test_vocabulary_aliases_cannot_collide(self):
        def mutate(docs):
            first = docs["tag-vocabulary-example.json"]["entries"][0]
            second = copy.deepcopy(first)
            second["id"] = "second"
            second["canonical"] = "other"
            second["aliases"] = ["three-quarter view"]
            docs["tag-vocabulary-example.json"]["entries"].append(second)

        errors = self.validate(mutate)
        self.assertTrue(any("alias" in error.lower() and "collision" in error.lower() for error in errors))

    def test_verified_vocabulary_requires_immutable_source_revision(self):
        def mutate(docs):
            entry = docs["tag-vocabulary-example.json"]["entries"][0]
            entry["status"] = "verified"
            entry["accepted"] = True
            entry["source"] = {
                "kind": "danbooru_export",
                "url": "https://example.com/tags.csv",
                "revision": "main",
            }

        errors = self.validate(mutate)
        joined = "\n".join(errors)
        self.assertIn("immutable source revision", joined)
        self.assertIn("top-level compilation approval", joined)

    def test_unreleased_technique_cannot_be_ready_for_qualification(self):
        def mutate(docs):
            docs["technique-candidates.json"]["candidates"][1][
                "ready_for_qualification"
            ] = True

        errors = self.validate(mutate)
        self.assertTrue(any("unreleased" in error for error in errors))

    def test_technique_requires_blockers_and_https_source(self):
        def mutate(docs):
            item = docs["technique-candidates.json"]["candidates"][0]
            item["promotion_blockers"] = []
            item["source_urls"] = ["http://example.com/adapter"]

        errors = self.validate(mutate)
        joined = "\n".join(errors)
        self.assertIn("promotion blockers", joined)
        self.assertIn("HTTPS", joined)

    def test_source_intake_refuses_authority(self):
        def mutate(docs):
            record = docs["source-intake-example.json"]["records"][0]
            record["download_authorized"] = True
            record["install_authorized"] = True
            record["execution_authorized"] = True

        errors = self.validate(mutate)
        joined = "\n".join(errors)
        self.assertIn("download_authorized false", joined)
        self.assertIn("install_authorized false", joined)
        self.assertIn("execution_authorized false", joined)

    def test_selected_source_file_requires_size_and_sha256(self):
        def mutate(docs):
            docs["source-intake-example.json"]["records"][0]["files"][0][
                "selected"
            ] = True

        errors = self.validate(mutate)
        self.assertTrue(any("selected file" in error for error in errors))

    def test_provider_specific_identity_is_required(self):
        def mutate(docs):
            record = docs["source-intake-example.json"]["records"][1]
            record["provider_version_id"] = None
            record["immutable_revision"] = None

        errors = self.validate(mutate)
        self.assertTrue(any("Civitai" in error and "version" in error for error in errors))

    def test_pinned_snapshot_requires_immutable_revision(self):
        def mutate(docs):
            record = docs["source-intake-example.json"]["records"][0]
            record["snapshot_state"] = "pinned"
            record["immutable_revision"] = "main"

        errors = self.validate(mutate)
        self.assertTrue(any("immutable revision" in error for error in errors))


    def test_checked_in_intelligence_manifests_are_valid(self):
        self.assertEqual(self.validator.validate_paths(ROOT), [])

    def test_non_string_array_members_fail_closed(self):
        def mutate(docs):
            docs["prompt-dialects.json"]["profiles"][0]["source_urls"] = [{}]

        errors = self.validate(mutate)
        self.assertTrue(any("source URLs" in error for error in errors))

    def test_accepted_vocabulary_requires_verified_immutable_provenance(self):
        def mutate(docs):
            vocabulary = docs["tag-vocabulary-example.json"]
            vocabulary["accepted_for_compilation"] = True
            vocabulary["entries"][0]["accepted"] = True

        errors = self.validate(mutate)
        joined = " | ".join(errors)
        self.assertIn("verified status", joined)
        self.assertIn("immutable source provenance", joined)

    def test_canonical_provider_url_must_match_recorded_identity(self):
        def mutate_hf(docs):
            docs["source-intake-example.json"]["records"][0][
                "provider_model_id"
            ] = "other-org/other-model"

        hf_errors = self.validate(mutate_hf)
        self.assertTrue(
            any("canonical URL identity" in error for error in hf_errors)
        )

        def mutate_civitai(docs):
            docs["source-intake-example.json"]["records"][1][
                "canonical_url"
            ] = "https://civitai.com/models/999999?modelVersionId=111111"

        civitai_errors = self.validate(mutate_civitai)
        self.assertTrue(
            any("canonical URL identity" in error for error in civitai_errors)
        )

    def test_source_intake_rejects_duplicate_normalized_file_paths(self):
        def mutate(docs):
            files = docs["source-intake-example.json"]["records"][0]["files"]
            duplicate = copy.deepcopy(files[0])
            duplicate["id"] = "weights-copy"
            duplicate["path"] = "folder/../model.safetensors"
            files[0]["path"] = "model.safetensors"
            files.append(duplicate)

        errors = self.validate(mutate)
        joined = " | ".join(errors)
        self.assertIn("file path is unsafe", joined)

        def mutate_exact(docs):
            files = docs["source-intake-example.json"]["records"][0]["files"]
            duplicate = copy.deepcopy(files[0])
            duplicate["id"] = "weights-copy"
            files.append(duplicate)

        exact_errors = self.validate(mutate_exact)
        self.assertTrue(
            any("duplicate file path" in error for error in exact_errors)
        )



if __name__ == "__main__":
    unittest.main()
