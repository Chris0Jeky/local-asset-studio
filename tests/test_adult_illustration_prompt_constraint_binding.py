from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from studio_prompt.adult_illustration_projection import project
from studio_prompt.adult_illustration_prompt_projection import compile_prompt


ROOT = Path(__file__).resolve().parents[1]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class AdultIllustrationPromptConstraintBindingTests(unittest.TestCase):
    def test_qwen_keeps_guide_and_mask_constraints_out_of_instruction_prose(self) -> None:
        intent = json.loads(
            (ROOT / "examples/adult-illustration/hot-spring-study.json").read_text(
                encoding="utf-8"
            )
        )
        # One source with two reviewed roles expands to two CreativeIntent
        # references. This isolates constraint routing from the separately tested
        # three-reference limit of the pinned Qwen graph profile.
        intent["references"] = intent["references"][:1]
        intent["constraints"].append(
            {
                "id": "wardrobe-write-scope",
                "text": "Only the reviewed wardrobe region may change.",
                "mechanism": "mask",
                "priority": "hard",
            }
        )
        projection = project(intent)

        result = compile_prompt(
            projection,
            "qwen-edit-2511-instruction-v1",
            ROOT,
        )

        instruction = result["channels"]["instruction"]
        self.assertNotIn(
            "Maintain visible and anatomically coherent contact",
            instruction,
        )
        self.assertNotIn("Only the reviewed wardrobe region may change", instruction)
        self.assertIn("Keep the result within the reviewed sensual", instruction)
        bindings = {
            (item.get("constraint_id"), item.get("mechanism"))
            for item in result["diagnostics"]
            if item["code"] == "CONSTRAINT_REQUIRES_ROUTE_BINDING"
        }
        self.assertEqual(
            bindings,
            {
                ("bench-contact", "guide"),
                ("wardrobe-write-scope", "mask"),
            },
        )
        self.assertEqual(result["state"], "requires_binding")
        self.assertEqual(result["source_document_sha256"], _digest(projection))


if __name__ == "__main__":
    unittest.main()
