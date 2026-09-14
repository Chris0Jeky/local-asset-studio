"""Direct contracts for Restyle continuation branches hidden by preparation."""
import copy
import hashlib
import io
import json
import shutil
import unittest

from PIL import Image

import continuation
import test_continuation as base


class RestyleValidationBranchTests(unittest.TestCase):
    def setUp(self):
        self.case = base.ContinuationTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

        catalog = json.loads((base.ROOT / "presets/catalog.json").read_text(encoding="utf-8"))
        nova = next(preset for preset in catalog["presets"] if preset["id"] == "style-pose-nova")
        graph_path = self.case.root / nova["graph"]
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base.ROOT / nova["graph"], graph_path)
        local_catalog = json.loads((self.case.root / "presets/catalog.json").read_text(encoding="utf-8"))
        local_catalog["presets"].append(nova)
        (self.case.root / "presets/catalog.json").write_text(json.dumps(local_catalog), encoding="utf-8")

        self.preset = self.case.studio.preset("style-pose-nova")
        self.graph, _ = self.case.studio.graph_for(self.preset)
        stream = io.BytesIO()
        Image.new("RGB", (8, 12), "green").save(stream, "PNG")
        self.style = self.case.studio.upload("style.png", "image/png", stream.getvalue())
        self.claim = dict(
            self.case.claim,
            intent="restyle",
            preset_id="style-pose-nova",
            template_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        )
        self.payload = {
            "preset_id": "style-pose-nova",
            "controls": {
                "positive": self.case.attachment["context"]["positive"],
                "last_reference": self.case.attachment["file"],
            },
            "parent_assets": [self.case.asset_id],
            "references": [
                {"role": "style", "file": self.style["file"], "sha256": self.style["sha256"]},
                {"role": "style", "file": None},
                {"role": "style", "file": None},
            ],
            "continuation": self.claim,
        }
        source_node, source_field = self.preset["last_reference"]
        self.graph[str(source_node)]["inputs"][str(source_field)] = self.case.attachment["file"]
        style_node, style_field = self.preset["reference_slots"][0]["binding"]
        self.graph[str(style_node)]["inputs"][str(style_field)] = self.style["file"]

    def test_board_minimum_message_is_owned_by_continuation_validation(self):
        payload = copy.deepcopy(self.payload)
        payload["references"] = [
            {"role": "style", "file": None},
            {"role": "style", "file": None},
            {"role": "style", "file": None},
        ]
        with self.assertRaisesRegex(
            ValueError,
            r"Add at least 1 picture whose look you want to the style board\.",
        ):
            continuation.validate(self.case.studio, payload, self.preset, copy.deepcopy(self.graph))

    def test_unpruned_empty_slot_names_the_authored_example_failure(self):
        # Picture 1 is valid, while the untouched Picture 2 loader still points at
        # its authored example. Call validation directly: Studio.prepare() prunes or
        # rejects the board before this invariant can otherwise be distinguished.
        graph = copy.deepcopy(self.graph)
        second_node, _ = self.preset["reference_slots"][1]["binding"]
        self.assertIn(str(second_node), graph)
        with self.assertRaisesRegex(
            ValueError,
            r"An empty style-board slot still carries the recipe example; reattach the board\.",
        ):
            continuation.validate(self.case.studio, self.payload, self.preset, graph)


if __name__ == "__main__":
    unittest.main()
