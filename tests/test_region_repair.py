"""Repair a marked region (#1857): the RGBA input composed from the owner's boxes, its refusals, its Generate binding, and the
HTTP route through a real Studio whose only ComfyUI seam is scripted (FakeStudio). Nothing here reaches a GPU or submits work."""
import hashlib
import importlib.util
import io
import json
import random
import shutil
import struct
import sys
import tempfile
import threading
import unittest
import zlib
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


def png16(colour_type):
    """A valid 96 x 64 PNG with midpoint 16-bit samples, including truecolour Pillow decodes as RGB8."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    channels = {0: 1, 2: 3, 6: 4}[colour_type]
    rows = (b'\0' + b'\x80\x00' * (96 * channels)) * 64
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 96, 64, 16, colour_type, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


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
        for source in (picture().convert("L"), picture().quantize(colors=16)):
            with self.subTest(mode=source.mode):
                asset = self.source(source)
                prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 8, 8]]})
                with Image.open(self.root / "experiments/uploads" / prepared["file"]) as image:
                    self.assertEqual(image.convert("RGB").tobytes(), source.convert("RGB").tobytes())

    def test_jpeg_png_and_webp_boxes_use_display_oriented_pixels(self):
        for format, mime in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")):
            with self.subTest(format=format):
                stream = io.BytesIO(); exif = Image.Exif(); exif[274] = 6
                picture().save(stream, format, exif=exif, lossless=True); raw = stream.getvalue()
                asset = self.studio.import_image("rotated." + format.lower(), mime, raw)["asset"]
                with Image.open(io.BytesIO(raw)) as encoded:
                    expected = encoded.convert("RGB").transpose(Image.Transpose.ROTATE_270)
                # This box is inside the displayed 64 x 96 picture, outside the encoded 96 x 64 axes.
                boxes = [[48, 80, 56, 88]]
                prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": boxes})
                self.assertEqual(prepared["plan"]["size"], [64, 96])
                self.assertEqual((prepared["context"]["width"], prepared["context"]["height"]), (64, 96))
                with Image.open(self.root / "experiments/uploads" / prepared["file"]) as result:
                    self.assertEqual(result.size, (64, 96))
                    self.assertEqual(result.convert("RGB").tobytes(), expected.tobytes())
                    self.assertEqual(result.getchannel("A").tobytes(), bytes(0 if 48 <= x < 56 and 80 <= y < 88 else 255 for y in range(96) for x in range(64)))
                    self.assertIn(result.getexif().get(274), (None, 1), "the prepared mask must not rotate a second time")
                self.assertEqual(prepared["plan"]["source_sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(self.studio.assets.file(asset["id"]).read_bytes(), raw)
                self.assertFalse(prepared["generation_submitted"])
        self.assertEqual(self.studio.requests, [])

    def test_overlapping_boxes_are_counted_once_for_the_large_region_refusal(self):
        asset = self.source()
        # The boxes sum to 100%, but their union is 56/96 of the source and is permitted.
        boxes = [[0, 0, 48, 64], [8, 0, 56, 64]]
        prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": boxes})
        with Image.open(self.root / "experiments/uploads" / prepared["file"]) as result:
            self.assertEqual(result.getchannel("A").tobytes(), (bytes(56) + bytes([255]) * 40) * 64)
        before = self.uploads()
        with self.assertRaisesRegex(ValueError, "covers 67%"):
            region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 48, 64], [16, 0, 64, 64]]})
        self.assertEqual(self.uploads(), before)
        self.assertEqual(self.studio.requests, [])

    def test_existing_transparency_does_not_expand_the_owners_mask(self):
        source = picture().convert("RGBA"); source.putalpha(Image.frombytes("L", source.size, bytes([0, 1, 128, 255]) * (96 * 64 // 4)))
        asset = self.source(source)
        prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 24, 24]]})
        with Image.open(self.root / "experiments/uploads" / prepared["file"]) as result:
            self.assertEqual(result.convert("RGB").tobytes(), picture().tobytes(), "hidden RGB is retained")
            self.assertEqual(result.getchannel("A").tobytes(), bytes(0 if 8 <= x < 24 and 8 <= y < 24 else 255 for y in range(64) for x in range(96)))

    def test_16_bit_png_requires_explicit_conversion_before_repair(self):
        for colour_type in (0, 2, 6):
            with self.subTest(colour_type=colour_type):
                raw = png16(colour_type)
                asset = self.studio.import_image("16-bit.png", "image/png", raw)["asset"]
                before = self.uploads()
                with self.assertRaisesRegex(ValueError, "16-bit.*8-bit RGB"):
                    region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 24, 24]]})
                self.assertEqual(self.uploads(), before)
                self.assertEqual(self.studio.assets.file(asset["id"]).read_bytes(), raw)
        self.assertEqual(self.studio.requests, [])

    def test_noncanonical_png_headers_refuse_before_repair_conversion(self):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
        for colour_type in (0, 2, 6):
            original = png16(colour_type)
            eight_bit = bytearray(original[16:29]); eight_bit[8] = 8
            for layout, prefix in (('metadata before IHDR', chunk(b'tEXt', b'note\0leading metadata')),
                                   ('duplicate IHDR', chunk(b'IHDR', eight_bit))):
                with self.subTest(colour_type=colour_type, layout=layout):
                    # Pillow accepts both layouts and decodes the later 16-bit IHDR,
                    # while byte 24 belongs to metadata or the earlier 8-bit header.
                    raw = original[:8] + prefix + original[8:]
                    asset = self.studio.import_image('ambiguous-16-bit.png', 'image/png', raw)['asset']
                    before = self.uploads()
                    with self.assertRaisesRegex(ValueError, 'PNG.*header.*8-bit RGB'):
                        region_repair.prepare(self.studio, {'asset_id': asset['id'], 'preset_id': REPAIR['id'], 'boxes': [[8, 8, 24, 24]]})
                    self.assertEqual(self.uploads(), before)
                    self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)
        self.assertEqual(self.studio.requests, [])

    def test_cmyk_jpeg_converts_to_rgb_in_display_coordinates(self):
        source = Image.new("CMYK", (96, 64))
        for box, colour in (((0, 0, 48, 32), (0, 255, 255, 0)), ((48, 0, 96, 32), (255, 0, 255, 0)),
                            ((0, 32, 48, 64), (255, 255, 0, 0)), ((48, 32, 96, 64), (0, 0, 0, 255))):
            source.paste(colour, box)
        stream = io.BytesIO(); exif = Image.Exif(); exif[274] = 6
        source.save(stream, "JPEG", quality=100, exif=exif); raw = stream.getvalue()
        asset = self.studio.import_image("cmyk.jpg", "image/jpeg", raw)["asset"]
        prepared = region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 16, 16]]})
        with Image.open(self.root / "experiments/uploads" / prepared["file"]) as result:
            self.assertEqual((result.mode, result.size), ("RGBA", (64, 96)))
            self.assertEqual([result.getpixel(point) for point in ((16, 24), (48, 24), (16, 72), (48, 72))],
                             [(0, 0, 255, 255), (255, 0, 0, 255), (0, 0, 0, 255), (0, 255, 0, 255)])
        self.assertEqual(prepared["plan"]["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.studio.assets.file(asset["id"]).read_bytes(), raw)

    def test_large_composed_png_has_a_repair_specific_refusal(self):
        # A small-enough JPEG can expand beyond the 20 MiB upload limit when its RGB gains mask alpha.
        source = Image.frombytes("RGB", (3072, 2304), random.Random(1861).randbytes(3072 * 2304 * 3))
        stream = io.BytesIO(); source.save(stream, "JPEG", quality=90); raw = stream.getvalue()
        self.assertLess(len(raw), 20 * 1024 * 1024)
        asset = self.studio.import_image("large.jpg", "image/jpeg", raw)["asset"]
        before = self.uploads(); jobs = set(self.studio.jobs)
        with self.assertRaisesRegex(ValueError, "prepared repair PNG.*20 MiB.*[Rr]esize a copy"):
            region_repair.prepare(self.studio, {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 24, 24]]})
        self.assertEqual(self.uploads(), before)
        self.assertEqual(set(self.studio.jobs), jobs)
        self.assertEqual(self.studio.assets.file(asset["id"]).read_bytes(), raw)
        self.assertEqual(self.studio.requests, [])

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
        stream = io.BytesIO(); exif = Image.Exif(); exif[274] = 6
        picture().save(stream, 'PNG', exif=exif); raw = stream.getvalue()
        private = self.studio.import_image('private.png', 'image/png', raw, privacy='private')['asset']
        prepared = region_repair.prepare(self.studio, {"asset_id": private["id"], "preset_id": REPAIR["id"], "boxes": [[0, 0, 16, 16]]}, privacy="all", creation_privacy="private")
        self.assertTrue((self.root / "experiments/private/uploads" / prepared["file"]).is_file())
        self.assertFalse((self.root / "experiments/uploads" / prepared["file"]).exists())
        self.assertEqual(prepared['plan']['size'], [64, 96])
        self.assertEqual(self.studio.assets.file(private['id'], privacy='all').read_bytes(), raw)

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

    def call(self, body, origin="http://127.0.0.1:8191", **headers):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=10)
        try:
            connection.request("POST", "/api/repair/prepare", json.dumps(body), headers={"Host": "127.0.0.1:8191", "Origin": origin, "Content-Type": "application/json", **headers})
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

    def test_a_private_picture_is_prepared_under_private_creation(self):
        asset = self.studio.import_image("hand.png", "image/png", png(picture()), privacy="private")["asset"]
        body = {"asset_id": asset["id"], "preset_id": REPAIR["id"], "boxes": [[8, 8, 32, 32]]}
        private = {"X-Studio-Privacy": "all", "X-Studio-Creation-Privacy": "private"}
        status, reply = self.call(body, **private)
        self.assertEqual(status, 201, reply); self.assertFalse(reply["generation_submitted"])
        self.assertTrue((self.root / "experiments/private/uploads" / reply["file"]).is_file())
        self.assertFalse((self.root / "experiments/uploads" / reply["file"]).exists())
        status, reply = self.call(body, **{"X-Studio-Privacy": "all"})
        self.assertEqual(status, 400); self.assertIn("Keep this private picture private", reply["error"])
        self.assertEqual(self.studio.requests, [])


if __name__ == "__main__": unittest.main()
