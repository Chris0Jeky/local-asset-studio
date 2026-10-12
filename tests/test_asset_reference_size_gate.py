"""Stat-size gate for POST /api/assets/reference (finding f-5cfce0cc4a).

asset_reference() must reject an oversize registered snapshot through a
stat-size check before read_bytes() loads it into thread memory, and must keep
attaching small valid images unchanged.
"""
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from test_server import GRAPH, PRESET, png, server

LIMIT = 20 * 1024 * 1024


class AssetReferenceSizeGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir()
        (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir()
        (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "fake-comfy/output").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        no_thread = patch.object(threading.Thread, "start", lambda *_: None)
        no_thread.start()
        self.addCleanup(no_thread.stop)
        self.studio = server.Studio(self.root)

    def _register(self, data, name):
        src = self.root / "fake-comfy" / "output" / name
        src.write_bytes(data)
        job = {"id": uuid.uuid4().hex, "preset_id": "demo", "preset_name": "Demo",
               "created_at": 0, "parent_assets": [],
               "outputs": [{"filename": name, "media_type": "image", "type": "output",
                            "subfolder": "", "seed": 1}]}
        asset_id = self.studio.assets.register(job, 0, src)
        self.assertIsNotNone(asset_id)
        return asset_id

    def _grow_oversize(self, asset_id, extra=1):
        path = self.studio.assets.file(asset_id)
        with open(path, "r+b") as handle:
            handle.truncate(LIMIT + extra)
        self.assertGreater(path.stat().st_size, LIMIT)
        return path

    def test_oversize_snapshot_rejected_without_full_read(self):
        asset_id = self._register(png(), "big.png")
        self._grow_oversize(asset_id)
        with patch.object(Path, "read_bytes",
                          side_effect=AssertionError("oversize snapshot must not be fully read")):
            with self.assertRaisesRegex(server.StudioError, "20 MiB"):
                self.studio.asset_reference(asset_id)

    def test_oversize_gate_holds_when_source_context_is_bypassed(self):
        asset_id = self._register(png(), "big.png")
        self._grow_oversize(asset_id)
        asset = self.studio.assets.get(asset_id)
        with patch.object(server.continuation, "source_context",
                          return_value={"sha256": asset["sha256"]}), \
             patch.object(Path, "read_bytes",
                          side_effect=AssertionError("oversize snapshot must not be fully read")):
            with self.assertRaisesRegex(server.StudioError, "20 MiB"):
                self.studio.asset_reference(asset_id)

    def test_small_valid_image_still_attaches(self):
        asset_id = self._register(png(), "small.png")
        attached = self.studio.asset_reference(asset_id)
        self.assertEqual(attached["parent_asset"], asset_id)
        self.assertEqual(attached["context"]["asset_id"], asset_id)
        self.assertEqual((self.studio.experiments / "uploads" / attached["file"]).read_bytes(),
                         self.studio.assets.file(asset_id).read_bytes())


if __name__ == "__main__":
    unittest.main()
