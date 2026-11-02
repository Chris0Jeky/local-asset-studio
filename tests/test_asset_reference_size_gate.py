"""Source gates for POST /api/assets/reference (finding f-5cfce0cc4a, #1861).

asset_reference() must reject an oversize registered snapshot through a
stat-size check before read_bytes() loads it into thread memory, and must keep
attaching valid images unchanged without depending on host MIME registration.
"""
import hashlib
import io
import json
import mimetypes
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PIL import Image

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
        no_request = patch.object(self.studio, "_request", side_effect=AssertionError("Unexpected engine request"))
        no_request.start()
        self.addCleanup(no_request.stop)

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

    def test_webp_attachments_keep_bytes_and_privacy_without_host_mime_registration(self):
        # Python's strict default table can lack WebP. Linux MIME files often add it;
        # Windows need not. Exercise the real stdlib lookup with that entry absent.
        mime_db = mimetypes.MimeTypes(filenames=())
        mime_db.types_map[True].pop(".webp", None)
        self.assertIsNone(mime_db.guess_type("source.webp")[0])
        stream = io.BytesIO(); exif = Image.Exif(); exif[274] = 6
        Image.new("RGB", (12, 8), "green").save(stream, "WEBP", lossless=True, exif=exif)
        raw = stream.getvalue(); digest = hashlib.sha256(raw).hexdigest()
        for privacy in ("regular", "private"):
            with self.subTest(privacy=privacy):
                asset_id = self.studio.import_image("source.webp", "image/webp", raw, privacy=privacy)["asset"]["id"]
                with patch.object(mimetypes, "guess_type", mime_db.guess_type):
                    if privacy == "private":
                        with self.assertRaisesRegex(ValueError, "Keep this private source private"):
                            self.studio.asset_reference(asset_id, privacy="private")
                        with self.assertRaisesRegex(ValueError, "Asset not found"):
                            self.studio.asset_reference(asset_id)
                    attached = self.studio.asset_reference(asset_id, privacy=privacy, creation_privacy=privacy)
                self.assertEqual(attached["parent_asset"], asset_id)
                self.assertEqual((attached["sha256"], attached["context"]["sha256"]), (digest, digest))
                self.assertEqual((attached["context"]["width"], attached["context"]["height"]), (8, 12))
                self.assertEqual(attached.get("privacy", "regular"), privacy)
                uploads = self.studio.experiments / ("private/uploads" if privacy == "private" else "uploads")
                self.assertEqual((uploads / attached["file"]).read_bytes(), raw)
                self.assertEqual((self.studio.comfy_root / "input" / attached["file"]).read_bytes(), raw)
                self.assertEqual(self.studio.assets.file(asset_id, privacy=privacy).read_bytes(), raw)
                if privacy == "private":
                    self.assertFalse((self.studio.experiments / "uploads" / attached["file"]).exists())
        self.assertTrue(self.studio.queue.empty())

    def test_registered_jpeg_alias_still_attaches(self):
        stream = io.BytesIO(); Image.new("RGB", (12, 8), "green").save(stream, "JPEG")
        raw = stream.getvalue()
        asset_id = self._register(raw, "source.JPEG")
        attached = self.studio.asset_reference(asset_id)
        self.assertEqual(attached["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual((self.studio.experiments / "uploads" / attached["file"]).read_bytes(), raw)

    def test_source_suffix_does_not_bypass_format_validation(self):
        for name, raw, refusal in (
            ("mismatch.webp", png(), "Upload must be a PNG, JPG, or WebP"),
            ("unsupported.bmp", png(), "Upload must be a PNG, JPG, or WebP"),
            ("damaged.png", b"\x89PNG\r\n\x1a\ninvalid", "Source image is damaged"),
        ):
            with self.subTest(name=name):
                asset_id = self._register(raw, name)
                before = set(self.studio.experiments.rglob("*"))
                with self.assertRaisesRegex(ValueError, refusal):
                    self.studio.asset_reference(asset_id)
                self.assertEqual(set(self.studio.experiments.rglob("*")), before)
                self.assertEqual(list((self.studio.comfy_root / "input").iterdir()), [])
                self.assertEqual(self.studio.assets.file(asset_id).read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
