"""Decode-order contracts for bounded addressable-figure source intake."""
from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from studio_workflow import addressable_figures
from test_addressable_figures import register_sheet
from test_server import server


class AddressableFigureDecodeTests(unittest.TestCase):
    def test_pixel_limit_precedes_exif_transform_and_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = server.AssetWorkspace(root)
            parent, _ = register_sheet(store, root)
            record = store.get(parent)
            payload = {
                "workspace_id": store.snapshot()["workspace_id"],
                "request_id": "addressable-decode-" + uuid.uuid4().hex,
                "asset_id": parent,
                "parent_sha256": record["sha256"],
                "rectangles": [
                    {"x": 0, "y": 0, "width": 10000, "height": 10000}
                ],
                "require_non_overlapping": True,
            }
            with (
                patch.object(addressable_figures, "MAX_PARENT_PIXELS", 1),
                patch.object(
                    addressable_figures.ImageOps,
                    "exif_transpose",
                    side_effect=AssertionError("oversized source reached pixel decode"),
                ) as transpose,
                self.assertRaisesRegex(server.WorkspaceError, "40 megapixels"),
            ):
                addressable_figures.split_figures(store, payload)
            transpose.assert_not_called()
            self.assertEqual(len(store.snapshot()["assets"]), 1)


if __name__ == "__main__":
    unittest.main()
