"""Addressable figure children are local Workspace assets; no generation is submitted."""
from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
import uuid
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from http_refusal_transport import atomic_json_post
from test_server import server


def register_sheet(store, root):
    source = Path(root) / "sheet.png"
    image = Image.new("RGB", (100, 80), "red")
    ImageDraw.Draw(image).rectangle((50, 0, 99, 79), fill="blue")
    image.save(source, "PNG")
    job = {
        "id": "sheet-job",
        "created_at": 123.0,
        "preset_id": "sheet-fixture",
        "preset_name": "Character sheet",
        "parent_assets": [],
        "outputs": [{"filename": "sheet.png", "media_type": "image", "prompt_id": "sheet-prompt"}],
    }
    return store.register(job, 0, source), source


class AddressableFigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = server.AssetWorkspace(self.root)
        self.parent, self.original = register_sheet(self.store, self.root)
        self.parent_record = self.store.get(self.parent)
        self.workspace_id = self.store.snapshot()["workspace_id"]

    def payload(self, **changes):
        value = {
            "workspace_id": self.workspace_id,
            "request_id": uuid.uuid4().hex,
            "asset_id": self.parent,
            "parent_sha256": self.parent_record["sha256"],
            "rectangles": [
                {"x": 0, "y": 0, "width": 5000, "height": 10000},
                {"x": 5000, "y": 0, "width": 5000, "height": 10000},
            ],
            "require_non_overlapping": True,
        }
        value.update(changes)
        return value

    def test_split_creates_ordered_ordinary_children_with_direct_lineage(self):
        before_bytes = self.store.file(self.parent).read_bytes()
        before_revision = self.store.get(self.parent)["metadata_revision"]
        result = self.store.split_figures(self.payload(request_id="addressable-figures-0001"))

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["action"], "split_figures")
        self.assertEqual(result["parent_asset_id"], self.parent)
        self.assertEqual(result["workspace_id"], self.workspace_id)
        self.assertFalse(result["generation_submitted"])
        self.assertEqual(result["created"], [row["asset_id"] for row in result["figures"]])
        self.assertEqual([row["index"] for row in result["figures"]], [1, 2])
        self.assertEqual(
            [row["crop_pixels"] for row in result["figures"]],
            [
                {"left": 0, "top": 0, "right": 50, "bottom": 80},
                {"left": 50, "top": 0, "right": 100, "bottom": 80},
            ],
        )

        children = [self.store.get(asset_id) for asset_id in result["created"]]
        self.assertEqual([child["lineage"] for child in children], [[self.parent], [self.parent]])
        self.assertEqual([child["source"]["operation"] for child in children], ["figure-crop", "figure-crop"])
        self.assertEqual([child["source"]["parent_asset_id"] for child in children], [self.parent, self.parent])
        self.assertEqual([child["source"]["crop_basis_points"] for child in children], self.payload()["rectangles"])
        self.assertEqual([child["preset_id"] for child in children], ["sheet-fixture", "sheet-fixture"])
        self.assertTrue(all(child["media_type"] == "image" and child["filename"].endswith(".png") for child in children))

        with Image.open(self.store.file(children[0]["id"])) as left:
            self.assertEqual(left.size, (50, 80))
            self.assertEqual(left.getpixel((25, 40)), (255, 0, 0))
        with Image.open(self.store.file(children[1]["id"])) as right:
            self.assertEqual(right.size, (50, 80))
            self.assertEqual(right.getpixel((25, 40)), (0, 0, 255))

        self.assertEqual(self.store.file(self.parent).read_bytes(), before_bytes)
        self.assertEqual(self.store.get(self.parent)["metadata_revision"], before_revision)
        self.assertEqual(len(self.store.snapshot()["assets"]), 3)

    def test_exact_retry_is_idempotent_and_changed_request_identity_is_rejected(self):
        payload = self.payload(request_id="addressable-figures-0002")
        first = self.store.split_figures(payload)
        replay = self.store.split_figures(copy.deepcopy(payload))
        self.assertEqual(replay, first)
        self.assertEqual(len(self.store.snapshot()["assets"]), 3)
        changed = copy.deepcopy(payload)
        changed["rectangles"][0]["width"] = 4000
        with self.assertRaises(server.WorkspaceError) as raised:
            self.store.split_figures(changed)
        self.assertEqual(raised.exception.code, "asset_request_reused")
        self.assertEqual(len(self.store.snapshot()["assets"]), 3)

    def test_receipt_is_read_only_and_retains_every_child_identity(self):
        payload = self.payload(request_id="addressable-figures-0003")
        first = self.store.split_figures(payload)
        observed = self.store.command_status(payload["request_id"], self.workspace_id)
        self.assertEqual(observed["created"], first["created"])
        self.assertEqual(observed["figures"], first["figures"])
        self.assertEqual(observed["workspace_id"], self.workspace_id)
        self.assertFalse(observed["generation_submitted"])
        self.assertEqual(len(self.store.snapshot()["assets"]), 3)

    def test_bounds_overlap_scope_hash_and_trashed_parent_fail_before_children(self):
        bad_rectangles = [
            [{"x": -1, "y": 0, "width": 1, "height": 1}],
            [{"x": 0, "y": 0, "width": 0, "height": 1}],
            [{"x": 9000, "y": 0, "width": 1001, "height": 10000}],
            [{"x": True, "y": 0, "width": 10, "height": 10}],
            [],
        ]
        for index, rectangles in enumerate(bad_rectangles):
            with self.subTest(rectangles=rectangles), self.assertRaises(server.WorkspaceError):
                self.store.split_figures(self.payload(request_id=f"addressable-invalid-{index:04d}", rectangles=rectangles))
        overlap = [
            {"x": 0, "y": 0, "width": 6000, "height": 10000},
            {"x": 5000, "y": 0, "width": 5000, "height": 10000},
        ]
        with self.assertRaisesRegex(server.WorkspaceError, "overlap"):
            self.store.split_figures(self.payload(request_id="addressable-overlap-001", rectangles=overlap))
        with self.assertRaises(server.WorkspaceError) as scope:
            self.store.split_figures(self.payload(request_id="addressable-scope-00001", workspace_id="b" * 32))
        self.assertEqual(scope.exception.code, "asset_workspace_conflict")
        with self.assertRaisesRegex(server.WorkspaceError, "changed|hash|source"):
            self.store.split_figures(self.payload(request_id="addressable-hash-000001", parent_sha256="a" * 64))

        self.store.update({
            "workspace_id": self.workspace_id,
            "ids": [self.parent],
            "action": "trash",
            "request_id": "addressable-trash-command",
            "expected_revisions": {self.parent: 0},
        })
        with self.assertRaisesRegex(server.WorkspaceError, "Restore|trashed"):
            self.store.split_figures(self.payload(request_id="addressable-trash-00001"))
        self.assertEqual(len(self.store.snapshot()["assets"]), 1)


class AddressableFigureHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = server.AssetWorkspace(self.root)
        self.parent, _ = register_sheet(self.store, self.root)
        self.record = self.store.get(self.parent)
        self.workspace_id = self.store.snapshot()["workspace_id"]

        class Handler(server.Handler):
            studio = SimpleNamespace(assets=self.store)

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def request(self, method, path, data=None, host="127.0.0.1:8191", origin="http://127.0.0.1:8191"):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        try:
            connection.request(
                method,
                path,
                json.dumps(data) if data is not None else None,
                {"Host": host, "Origin": origin, "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read()), dict(response.getheaders())
        finally:
            connection.close()

    def payload(self):
        return {
            "workspace_id": self.workspace_id,
            "request_id": "addressable-http-00001",
            "asset_id": self.parent,
            "parent_sha256": self.record["sha256"],
            "rectangles": [{"x": 0, "y": 0, "width": 5000, "height": 10000}],
            "require_non_overlapping": True,
        }

    def test_http_split_and_receipt_are_local_non_generating_operations(self):
        status, result, headers = self.request("POST", "/api/assets/split-figures", self.payload())
        self.assertEqual(status, 201, result)
        self.assertEqual(len(result["created"]), 1)
        self.assertFalse(result["generation_submitted"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, observed, _ = self.request(
            "GET",
            "/api/assets/commands/" + self.payload()["request_id"] + "?workspace_id=" + self.workspace_id,
        )
        self.assertEqual(status, 200)
        self.assertEqual(observed["created"], result["created"])
        self.assertEqual(len(self.store.snapshot()["assets"]), 2)

    def test_remote_origin_is_rejected_before_body_or_asset_creation(self):
        body = json.dumps(self.payload()).encode("utf-8")
        status, _ = atomic_json_post(
            self.http.server_port,
            "/api/assets/split-figures",
            body,
            host="evil.test",
            origin="http://127.0.0.1:8191",
        )
        self.assertEqual(status, 403)
        self.assertEqual(len(self.store.snapshot()["assets"]), 1)

    def test_receipt_failure_is_unconfirmed_and_rolls_back_children(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE TRIGGER reject_figure_receipt BEFORE INSERT ON asset_commands "
                "BEGIN SELECT RAISE(ABORT, 'receipt fault'); END"
            )
        status, data, _ = self.request("POST", "/api/assets/split-figures", self.payload())
        self.assertEqual(status, 503)
        self.assertEqual(data["code"], "asset_storage_unconfirmed")
        self.assertEqual(len(self.store.snapshot()["assets"]), 1)


if __name__ == "__main__":
    unittest.main()
