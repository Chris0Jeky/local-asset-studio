from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from unittest import mock

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


def _guide_mask_projection() -> dict:
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
    return project(intent)


class AdultIllustrationPromptConstraintBindingTests(unittest.TestCase):
    def test_qwen_keeps_guide_and_mask_constraints_out_of_instruction_prose(self) -> None:
        projection = _guide_mask_projection()

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

    def test_public_catalog_loader_patch_reaches_compile_path(self) -> None:
        from studio_prompt import (
            adult_illustration_prompt_projection as facade,
        )

        projection = _guide_mask_projection()
        with mock.patch(
            "studio_prompt.adult_illustration_prompt_projection.load_catalog",
            side_effect=ValueError("patched-loader-probe"),
        ):
            with self.assertRaisesRegex(ValueError, "patched-loader-probe"):
                facade.compile_prompt(
                    projection,
                    "qwen-edit-2511-instruction-v1",
                    ROOT,
                )

    def test_direct_impl_import_is_fail_closed_without_facade(self) -> None:
        snippet = textwrap.dedent(
            """\
            import json
            import pathlib
            import sys

            root = pathlib.Path(sys.argv[1])
            from studio_prompt import (
                _adult_illustration_prompt_projection_impl as impl,
            )
            assert (
                "studio_prompt.adult_illustration_prompt_projection"
                not in sys.modules
            ), "public facade already loaded"
            from studio_prompt.adult_illustration_projection import project
            assert (
                "studio_prompt.adult_illustration_prompt_projection"
                not in sys.modules
            ), "public facade loaded transitively"

            intent = json.loads(
                (
                    root / "examples/adult-illustration/hot-spring-study.json"
                ).read_text(encoding="utf-8")
            )
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
            result = impl.compile_prompt(
                projection, "qwen-edit-2511-instruction-v1", root
            )
            assert result["state"] == "requires_binding", result["state"]
            bindings = [
                item
                for item in result["diagnostics"]
                if item["code"] == "CONSTRAINT_REQUIRES_ROUTE_BINDING"
            ]
            assert bindings, "missing CONSTRAINT_REQUIRES_ROUTE_BINDING"
            keyed = {
                (item.get("constraint_id"), item.get("mechanism"))
                for item in bindings
            }
            assert keyed == {
                ("bench-contact", "guide"),
                ("wardrobe-write-scope", "mask"),
            }, keyed
            instruction = result["channels"]["instruction"]
            assert (
                "Maintain visible and anatomically coherent contact"
                not in instruction
            ), instruction
            assert (
                "Only the reviewed wardrobe region may change" not in instruction
            ), instruction
            """
        )
        proc = subprocess.run(
            [sys.executable, "-c", snippet, str(ROOT)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
