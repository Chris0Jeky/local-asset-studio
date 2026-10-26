"""Check the research examples, without implementing a receipt schema/importer."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CloudArtifactReceiptContractTests(unittest.TestCase):
    def evidence(self, heading):
        text = (ROOT / "docs/FRONTIER-ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertTrue(heading in text, "missing receipt design examples")
        section = text.split(heading, 1)[1]
        return json.loads(section.split("```json\n", 1)[1].split("```", 1)[0])

    def test_landing_contract_requires_recipe_ids_and_independent_states(self):
        text = (ROOT / "docs/research/FRONTIER-MCP-ASSETS-2026-10-01-PIPELINES.md").read_text(encoding="utf-8")
        landing = text.split("## Landing contract (all pipelines)", 1)[1]
        required = ("full resolved recipe", "every known provider prompt/job/prediction ID",
                    "execution success", "reviewed", "accepted", "licensing", "commercial review", "null")
        self.assertEqual([term for term in required if term not in landing], [])

    def test_cloud_examples_keep_complete_recipe_and_multiple_known_ids(self):
        examples = self.evidence("### Illustrative cloud receipts")
        for receipt in examples:
            with self.subTest(example=receipt["example"]):
                recipe = receipt["resolved_recipe"]
                self.assertTrue(recipe["tool_revision"])
                self.assertTrue(recipe["model_revision"])
                self.assertEqual(recipe["references"], [])
                self.assertEqual(set(recipe["parameters"]), {
                    "prompt", "negative_prompt", "seed", "width", "height", "steps",
                    "guidance", "sampler", "schedule", "output_format",
                })
                self.assertEqual(set(receipt["provider_ids"]), {"prompt", "job", "prediction"})
        known = examples[0]["provider_ids"]
        self.assertTrue(known["prompt"])
        self.assertEqual(len(known["job"]), 2)
        self.assertTrue(known["prediction"])

    def test_reviewed_rejection_is_not_acceptance(self):
        rejected, unknown_license = self.evidence("### Illustrative cloud receipts")
        self.assertIs(rejected["execution_success"], True)
        self.assertIs(rejected["reviewed"], True)
        self.assertIs(rejected["accepted"], False)
        self.assertIs(unknown_license["accepted"], True)
        self.assertIsNone(unknown_license["licensing"])
        self.assertIsNone(unknown_license["commercial_review"])

    def test_unknown_states_stay_independently_nullable(self):
        record = self.evidence("### Proposed evidence record")
        self.assertTrue({"execution_success", "reviewed", "licensing"} <= record.keys())
        self.assertIsNone(record["execution_success"])
        self.assertIsNone(record["reviewed"])
        self.assertIsNone(record["acceptance"]["accepted"])
        self.assertIsNone(record["licensing"])
        self.assertIsNone(record["commercial_review"]["state"])


if __name__ == "__main__":
    unittest.main()
