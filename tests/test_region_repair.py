"""Repair a marked region (#1857): the RGBA input composed from the owner's boxes, its refusals, its Generate binding, and the
HTTP route through a real Studio whose only ComfyUI seam is scripted (FakeStudio). Nothing here reaches a GPU or submits work."""
import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
SPEC = importlib.util.spec_from_file_location("region_repair_server", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
import region_repair  # noqa: E402  (bare name, never `from app import`)

CATALOG = json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]
REPAIR = next(p for p in CATALOG if p["id"] == "anime-masked-repair")
DEMO_GRAPH = {"1": {"class_type": "KSampler", "inputs": {"text": "demo", "seed": 1}}}
DEMO = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"], "seed": ["1", "seed"]}
WORDS = "1girl, raised hand, five fingers"


def picture(size=(96, 64)):
    """Every pixel distinct enough that a shifted or resampled copy would differ."""
    image = Image.new("RGB", size); width, height = size
    image.putdata([(x * 2 % 256, y * 3 % 256, (x + y) % 256) for y in range(height) for x in range(width)])
    return image


def png(image):
    stream = io.BytesIO(); image.save(stream, "PNG"); return stream.getvalue()


class FakeStudio(server.Studio):
    def __init__(self, root): self.requests = []; super().__init__(root)
    def _request(self, *args, **kwargs): self.requests.append((args, kwargs)); raise AssertionError("ComfyUI must not be contacted")


def make_root(test):
    test.tmp = tempfile.TemporaryDirectory(); test.addCleanup(test.tmp.cleanup); test.root = root = Path(test.tmp.name)
    (root / "presets").mkdir(); (root / "workflows/api").mkdir(parents=True); (root / "config").mkdir()
    (root / "fake-comfy/input").mkdir(parents=True); (root / "fake-comfy/output/Studio").mkdir(parents=True)
    (root / "config/local.json").write_text(json.dumps({"comfy_root": str(root / "fake-comfy")}))
    (root / "presets/catalog.json").write_text(json.dumps({"presets": [DEMO, REPAIR]}))
    (root / "workflows/api/demo-api.json").write_text(json.dumps(DEMO_GRAPH))
    shutil.copyfile(ROOT / REPAIR["graph"], root / REPAIR["graph"])


class PrepareTests(unittest.TestCase):
    def setUp(self):
        make_root(self)
        patcher = patch.object(threading.Thread, "start", lambda *_: None); patcher.start(); self.addCleanup(patcher.stop)
        self.studio = FakeStudio(self.root)

    def source(self, image=None, privacy="regular"):
        return self.studio.import_image("hand.png", "image/png", png(image or picture()), privacy=privacy)["asset"]

    def uploads(self): return sorted(p.name for p in (self.root / "fake-comfy/input").iterdir())

    def test_alpha_is_zero_inside_the_boxes_and_opaque_outside_with_the_source_rgb_and_size(self):
        asset = self.source(); boxes = [[8, 8, 24, 20], [20, 16, 40, 40]]
        prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": boxes})
        self.assertFalse(prepared["generation_submitted"]); self.assertEqual(self.studio.requests, [])
        stored = self.root / "experiments/uploads" / prepared["file"]
        self.assertEqual((self.root / "fake-comfy/input" / prepared["file"]).read_bytes(), stored.read_bytes())
        self.assertEqual(hashlib.sha256(stored.read_bytes()).hexdigest(), prepared["plan"]["mask_sha256"])
        with Image.open(stored) as image:
            self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGBA", (96, 64)))
            self.assertEqual(image.convert("RGB").tobytes(), picture().tobytes())
            alpha = image.getchannel("A")
            inside = lambda x, y: any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in boxes)
            expected = bytes(0 if inside(x, y) else 255 for y in range(64) for x in range(96))
            self.assertEqual(alpha.tobytes(), expected)
        plan = prepared["plan"]
        self.assertEqual(plan, {"version": 1, "preset_id": REPAIR["id"], "source_asset_id": asset["id"], "source_sha256": asset["sha256"],
                                "mask_file": prepared["file"], "mask_sha256": prepared["sha256"], "boxes": boxes, "size": [96, 64]})
        self.assertEqual((prepared["width"], prepared["height"], prepared["context"]["asset_id"]), (96, 64, asset["id"]))

    def test_a_palette_or_grey_source_keeps_its_picture_as_rgb(self):
        grey = picture().convert("L"); asset = self.source(grey)
        prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 8, 8]]})
        with Image.open(self.root / "experiments/uploads" / prepared["file"]) as image: self.assertEqual(image.convert("RGB").tobytes(), grey.convert("RGB").tobytes())

    def test_refusals_upload_nothing(self):
        asset = self.source(); private = self.source(privacy="private"); odd = self.source(Image.new("RGB", (90, 64)))
        demo = {"asset_id": asset["id"], "preset_id": REPAIR["id"]}
        before = self.uploads()
        for body, message in (
                (dict(demo, boxes=[]), "drag at least one box"),
                (dict(demo, boxes="8,8,24,24"), "drag at least one box"),
                (dict(demo, boxes=[[0, 0, 97, 20]]), "not inside the 96 × 64 picture"),
                (dict(demo, boxes=[[-1, 0, 20, 20]]), "not inside"),
                (dict(demo, boxes=[[20, 0, 10, 20]]), "not inside"),
                (dict(demo, boxes=[[0, 0, 7, 20]]), "too small"),
                (dict(demo, boxes=[[0, 0, 20.0, 20]]), "four whole pixel numbers"),
                (dict(demo, boxes=[[0, 0, True, 20]]), "four whole pixel numbers"),
                (dict(demo, boxes=[[0, 0, 8, 8]] * 17), "at most 16"),
                (dict(demo, boxes=[[0, 0, 96, 64]]), "image-to-image"),
                (dict(demo, boxes=[[0, 0, 60, 64]]), "covers 62%"),
                (dict(demo, boxes=[[0, 0, 8, 8]], preset_id="demo"), "masked-repair recipe"),
                (dict(demo, boxes=[[0, 0, 8, 8]], extra=1), "takes asset_id"),
                ({"asset_id": odd["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 8, 8]]}, "divisible by 8"),
                ({"asset_id": private["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 8, 8]]}, "not found")):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, message): region_repair.prepare(self.studio, body)
        with self.assertRaisesRegex(ValueError, "Keep this private picture private"):
            region_repair.prepare(self.studio, {"asset_id": private["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 8, 8]]}, privacy="all")
        audio = self.studio.assets.get(asset["id"])
        with patch.object(type(self.studio.assets), "get", lambda *_a, **_k: dict(audio, media_type="audio")), self.assertRaisesRegex(ValueError, "image asset"):
            region_repair.prepare(self.studio, dict(demo, boxes=[[0, 0, 8, 8]]))
        self.assertEqual(self.uploads(), before, "a refused prepare stores nothing")
        self.assertEqual(self.studio.requests, [])

    def test_a_private_source_prepares_a_private_upload(self):
        private = self.source(privacy="private")
        prepared = region_repair.prepare(self.studio, {"asset_id": private["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 16, 16]]}, privacy="all", creation_privacy="private")
        self.assertTrue((self.root / "experiments/private/uploads" / prepared["file"]).is_file())
        self.assertFalse((self.root / "experiments/uploads" / prepared["file"]).exists())

    def test_the_prepared_file_passes_the_mask_check_and_generate_binds_it(self):
        asset = self.source()
        prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[16, 8, 48, 40]]})
        self.studio._validate_rgba_mask_reference(REPAIR, self.root / "experiments/uploads" / prepared["file"])
        body = {"preset_id": REPAIR["id"], "controls": {"reference": prepared["file"], "positive": WORDS}, "batch_count": 1, "parent_assets": [asset["id"]]}
        job = self.studio.jobs[self.studio.create_job(body, enqueue=False)["id"]]
        node, field = REPAIR["reference"]
        self.assertEqual(job["graph"][node]["inputs"][field], prepared["file"])
        self.assertEqual(job["parent_assets"], [asset["id"]]); self.assertEqual(job["prompt_ids"], []); self.assertEqual(self.studio.requests, [])


class HttpRouteTests(unittest.TestCase):
    def setUp(self):
        make_root(self)
        with patch.object(threading.Thread, "start", lambda *_: None): self.studio = FakeStudio(self.root)
        self.http = server.create_server(self.root, port=0, studio_factory=lambda _: self.studio)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 5); self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def call(self, body, origin="http://127.0.0.1:8191"):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=10)
        try:
            connection.request("POST", "/api/repair/prepare", json.dumps(body), headers={"Host": "127.0.0.1:8191", "Origin": origin, "Content-Type": "application/json"})
            reply = connection.getresponse(); return reply.status, json.loads(reply.read())
        finally: connection.close()

    def test_prepare_route_returns_201_and_submits_nothing(self):
        asset = self.studio.import_image("hand.png", "image/png", png(picture()))["asset"]
        jobs = set(self.studio.jobs)
        status, body = self.call({"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 32, 32]]})
        self.assertEqual(status, 201); self.assertFalse(body["generation_submitted"]); self.assertRegex(body["file"], r"^[0-9a-f]{32}_repair-mask\.png$")
        self.assertEqual(body["plan"]["source_asset_id"], asset["id"])
        status, body = self.call({"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": []})
        self.assertEqual(status, 400); self.assertIn("drag at least one box", body["error"])
        self.assertEqual(self.call({"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 32, 32]]}, origin="https://evil.invalid")[0], 403)
        self.assertEqual(set(self.studio.jobs), jobs, "no job was created"); self.assertEqual(self.studio.requests, [], "no route reaches ComfyUI")


if __name__ == "__main__": unittest.main()
