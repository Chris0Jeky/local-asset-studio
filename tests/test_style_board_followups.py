"""Style-board follow-ups remain review/setup operations; no generation is submitted."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_recipe_shortlist import make_studio
from test_recipe_shortlist_ordered import route, sources
from studio_workflow.setup_proposal import request as propose


class StyleBoardGuideContract(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_guide_uses_the_board_minimum(self):
        result = subprocess.run(
            [shutil.which("node"), str(Path(__file__).with_name("style_board_guide_contract.cjs"))],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class StyleBoardSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.s = make_studio(self.root)
        self.items = sources(self.s, self.root)
        self.p = route(self.s)
        self.p.pop("reference", None)
        self.p["reference_board"] = {"min": 1, "policy": "fixture board preprocessing"}
        for slot in self.p["reference_slots"]:
            slot["role"] = "style"
        self.s.experiments = self.root / "experiments"
        self.s.experiments.mkdir(exist_ok=True)
        self.s.comfy_root = self.root / "comfy"
        (self.s.comfy_root / "input").mkdir(parents=True)
        self.s.upload_count = 0
        from server import Studio
        self.s.upload = lambda *args: Studio.upload(self.s, *args)
        self.s._write_json_atomic = lambda path, value: path.write_text(json.dumps(value), encoding="utf-8")

        def stage(key):
            self.s.upload_count += 1
            asset = self.s.assets.get(key)
            value = self.s.upload(asset["filename"], "image/png", self.s.assets.file(key).read_bytes())
            return dict(value, parent_asset=key)

        self.s.asset_reference = stage
        self.before = {
            "version": 1,
            "updatedAt": 0,
            "templateHash": self.p["continuation_capability"]["template_sha256"],
            "pendingInputs": [],
            "recipe": {
                "preset": self.p["id"],
                "controls": {"positive": "Before"},
                "batch": 1,
                "references": [],
                "parent_assets": [],
                "parent_by_input": {},
            },
        }
        source = {**self.items[0], "role": "style"}
        self.q = {
            "goal": "reference-image",
            "preset_id": self.p["id"],
            "expected_template_sha256": self.p["continuation_capability"]["template_sha256"],
            "sources": [source],
            "draft": copy.deepcopy(self.before),
            "positive": "Keep the requested composition",
            "negative": "",
            "guidance": [{"contribution": "", "avoid": ""}],
        }
        self.scope = self.s.assets.snapshot()["workspace_id"]

    def store(self):
        from studio_workflow.setup_drafts import SetupDrafts
        return SetupDrafts(self.s)

    def create(self):
        return self.store().command({
            "action": "create",
            "workspace_id": self.scope,
            "request_id": "board-create",
            "draft": self.before,
        })

    def apply(self, current, report):
        return self.store().command({
            "action": "apply",
            "workspace_id": self.scope,
            "request_id": "board-apply",
            "draft_id": current["draft_id"],
            "expected_revision": current["revision"],
            "proposal_json": report["proposal_json"],
            "approved_proposal_sha256": report["proposal_sha256"],
        })

    def test_proposal_keeps_board_visual_and_prompt_channels_separate(self):
        report = propose(self.q, self.s)
        intent = report["intent"]
        self.assertEqual(intent["compiled_positive"], self.q["positive"])
        self.assertNotIn("Picture 1", intent["compiled_positive"])
        self.assertEqual(intent["sources"][0]["role_mode"], "style-board")
        self.assertEqual(intent["sources"][0]["transform"], {"policy": "fixture board preprocessing"})
        self.assertEqual(
            intent["reference_board"],
            {"minimum": 1, "slot_count": 3, "roles": ["style", "style", "style"]},
        )
        self.assertEqual(intent["lineage"]["by_input"], {})
        self.assertNotIn("reference", intent["controls"])
        self.assertFalse(report["generation_submitted"])

    def test_board_guidance_is_rejected_instead_of_silently_dropped(self):
        q = copy.deepcopy(self.q)
        q["guidance"][0]["contribution"] = "face"
        with self.assertRaisesRegex(ValueError, "board|guidance|Picture 1"):
            propose(q, self.s)
        self.assertEqual(self.s.upload_count, 0)

    def test_apply_persists_slot_placeholders_without_a_singular_reference_control(self):
        current = self.create()
        report = propose(self.q, self.s)
        result = self.apply(current, report)
        self.assertEqual(result["status"], "committed", result)
        recipe = result["draft"]["recipe"]
        self.assertEqual(self.s.upload_count, 1)
        self.assertNotIn("reference", recipe["controls"])
        self.assertNotIn("last_reference", recipe["controls"])
        self.assertEqual(recipe["parent_assets"], [self.q["sources"][0]["asset_id"]])
        self.assertEqual(recipe["parent_by_input"], {})
        self.assertEqual(len(recipe["references"]), 3)
        self.assertEqual(recipe["references"][0]["parent_asset"], self.q["sources"][0]["asset_id"])
        self.assertEqual(
            recipe["references"][1:],
            [
                {"slot": 2, "role": "style", "file": None, "pruned": True, "contribution": "", "avoid": ""},
                {"slot": 3, "role": "style", "file": None, "pruned": True, "contribution": "", "avoid": ""},
            ],
        )
        from app.references import compile_references
        graph, _ = self.s.graph_for(self.p)
        prompt_node, prompt_field = self.p["positive"]
        graph[prompt_node]["inputs"][prompt_field] = recipe["controls"]["positive"]
        compiled = compile_references(self.p, graph, recipe["references"], self.s.experiments / "uploads")
        self.assertEqual(len(compiled), 3)
        self.assertEqual(graph[prompt_node]["inputs"][prompt_field], self.q["positive"])
        self.assertFalse(result["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
