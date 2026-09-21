"""Decode-order, format and raster-boundary contracts for figure source intake."""
from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from studio_workflow import addressable_figures
from test_addressable_figures import register_sheet
from test_server import server


def payload(store, parent, sha256, request_id):
    return {
        "workspace_id": store.snapshot()["workspace_id"],
        "request_id": request_id,
        "asset_id": parent,
        "parent_sha256": sha256,
        "rectangles": [{"x": 0, "y": 0, "width": 10000, "height": 10000}],
        "require_non_overlapping": True,
    }


def register_image(store, root, filename, image_format):
    source = Path(root) / filename
    Image.new("RGB", (3, 1), "red").save(source, image_format)
    job = {
        "id": "format-" + image_format.lower(),
        "created_at": 123.0,
        "preset_id": "format-fixture",
        "preset_name": "Format fixture",
        "parent_assets": [],
        "outputs": [
            {
                "filename": source.name,
                "media_type": "image",
                "prompt_id": "format-prompt-" + image_format.lower(),
            }
        ],
    }
    return store.register(job, 0, source)


class AddressableFigureDecodeTests(unittest.TestCase):
    def test_pixel_limit_precedes_exif_transform_and_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = server.AssetWorkspace(root)
            parent, _ = register_sheet(store, root)
            record = store.get(parent)
            command = payload(
                store,
                parent,
                record["sha256"],
                "addressable-decode-" + uuid.uuid4().hex,
            )
            with (
                patch.object(addressable_figures, "MAX_PARENT_PIXELS", 1),
                patch.object(
                    addressable_figures.ImageOps,
                    "exif_transpose",
                    side_effect=AssertionError("oversized source reached pixel decode"),
                ) as transpose,
                self.assertRaisesRegex(server.WorkspaceError, "40 megapixels"),
            ):
                addressable_figures.split_figures(store, command)
            transpose.assert_not_called()
            self.assertEqual(len(store.snapshot()["assets"]), 1)

    def test_palette_transparency_survives_content_addressed_crop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = server.AssetWorkspace(root)
            source = root / "transparent-sheet.png"
            image = Image.new("P", (2, 1))
            image.putpalette([0, 0, 0, 255, 0, 0] + [0, 0, 0] * 254)
            image.putdata([0, 1])
            image.save(source, "PNG", transparency=0)
            job = {
                "id": "transparent-sheet-job",
                "created_at": 123.0,
                "preset_id": "transparent-sheet",
                "preset_name": "Transparent sheet",
                "parent_assets": [],
                "outputs": [
                    {
                        "filename": source.name,
                        "media_type": "image",
                        "prompt_id": "transparent-sheet-prompt",
                    }
                ],
            }
            parent = store.register(job, 0, source)
            record = store.get(parent)
            result = addressable_figures.split_figures(
                store,
                payload(
                    store,
                    parent,
                    record["sha256"],
                    "addressable-alpha-" + uuid.uuid4().hex,
                ),
            )
            with Image.open(store.file(result["created"][0])) as child:
                self.assertEqual(child.mode, "RGBA")
                self.assertEqual(child.getpixel((0, 0))[3], 0)
                self.assertEqual(child.getpixel((1, 0))[3], 255)

    def test_non_web_image_format_is_refused_before_transform_or_child_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = server.AssetWorkspace(root)
            parent = register_image(store, root, "unsupported-sheet.bmp", "BMP")
            record = store.get(parent)
            command = payload(
                store,
                parent,
                record["sha256"],
                "addressable-format-" + uuid.uuid4().hex,
            )
            with (
                patch.object(
                    addressable_figures.ImageOps,
                    "exif_transpose",
                    side_effect=AssertionError("unsupported format reached transform"),
                ) as transpose,
                self.assertRaisesRegex(server.WorkspaceError, "supported still image"),
            ):
                addressable_figures.split_figures(store, command)
            transpose.assert_not_called()
            self.assertEqual(len(store.snapshot()["assets"]), 1)

    def test_adjacent_basis_point_rectangles_share_one_raster_boundary(self):
        left = addressable_figures._pixel_box(
            object(), {"x": 0, "y": 0, "width": 5000, "height": 10000}, 3, 1
        )
        right = addressable_figures._pixel_box(
            object(), {"x": 5000, "y": 0, "width": 5000, "height": 10000}, 3, 1
        )
        self.assertEqual(left["right"], right["left"])
        self.assertEqual(left["right"] - left["left"], 2)
        self.assertEqual(right["right"] - right["left"], 1)
        self.assertEqual(
            (left["right"] - left["left"]) + (right["right"] - right["left"]),
            3,
        )


if __name__ == "__main__":
    unittest.main()
