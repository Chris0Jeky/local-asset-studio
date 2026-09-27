"""Make seamless (#1220): the deterministic Pillow steps on synthetic pictures, and the route through a real Studio whose only
ComfyUI seam is scripted (FakeStudio). Nothing here reaches a GPU."""
import hashlib
import importlib.util
import io
import json
import math
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
SPEC = importlib.util.spec_from_file_location("tiles_asset_server", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
import tiles  # noqa: E402  (bare name, never `from app import`)

try: import numpy
except ImportError: numpy = None

CATALOG = json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]
ROUTE = next(p for p in CATALOG if p.get("tile_route"))
DEMO_GRAPH = {"1": {"class_type": "KSampler", "inputs": {"text": "demo", "seed": 1}}}
DEMO = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"], "seed": ["1", "seed"]}
WORDS = "Seamless texture, flat front view of a grey stone wall, even soft lighting, no objects, no text, fills the whole frame."


def ramp(size=64, step=4):
    """Red rises by `step` per column; green and blue stay 0."""
    image = Image.new("RGB", (size, size))
    image.putdata([(x * step, 0, 0) for y in range(size) for x in range(size)])
    return image


def lit_texture(size=256):
    """A fine checker under one period of cosine light: periodic, so it tiles, but visibly lit from one side."""
    image = Image.new("RGB", (size, size))
    image.putdata([tuple(int(120 + 50 * math.cos(2 * math.pi * x / size) + (8 if (x // 2 + y // 2) % 2 else -8)) for _ in range(3))
                   for y in range(size) for x in range(size)])
    return image


def column_means(image):
    grey = image.convert("L"); width, height = grey.size; data = list(grey.tobytes())
    return [sum(data[y * width + x] for y in range(height)) / height for x in range(width)]


def png(image):
    stream = io.BytesIO(); image.save(stream, "PNG"); return stream.getvalue()


class ImageOperationTests(unittest.TestCase):
    def test_roll_half_moves_every_pixel_by_half_with_wrap(self):
        source = Image.new("RGB", (16, 16)); source.putdata([(x * 16, y * 16, 7) for y in range(16) for x in range(16)])
        rolled = tiles.roll_half(source)
        for x, y in ((0, 0), (3, 12), (15, 15), (8, 8)):
            self.assertEqual(rolled.getpixel((x, y)), source.getpixel(((x - 8) % 16, (y - 8) % 16)))
        self.assertEqual(tiles.roll_half(rolled).tobytes(), source.tobytes(), "rolling twice by half is the identity")

    def test_seam_score_matches_the_lab_formula_and_moves_to_the_centre_when_rolled(self):
        source = ramp()   # red 0..252: the wrap edge jumps 252 in red, 0 in green and blue; rows wrap without a jump
        self.assertEqual(tiles.seam(source), round((252 / 3 + 0) / 2, 2))
        self.assertEqual(tiles.inner_gradient(source), round((4 / 3 + 0) / 2, 2))
        rolled = tiles.roll_half(source)
        self.assertEqual(tiles.centre_seam(rolled), tiles.seam(source), "the old wrap seam sits on the centre lines after the roll")
        self.assertLess(tiles.seam(rolled), 2, "the rolled picture's wrap edges are the source's continuous middle")

    def test_repaint_input_is_the_rolled_texture_with_a_transparent_centre_cross(self):
        source = ramp(64); rgba = tiles.repaint_input(source, 16)
        self.assertEqual(rgba.mode, "RGBA"); self.assertEqual(rgba.convert("RGB").tobytes(), tiles.roll_half(source).tobytes())
        alpha = rgba.getchannel("A")
        self.assertEqual(alpha.getpixel((24, 5)), 0); self.assertEqual(alpha.getpixel((39, 60)), 0)     # vertical bar, x 24..39
        self.assertEqual(alpha.getpixel((5, 24)), 0); self.assertEqual(alpha.getpixel((60, 39)), 0)     # horizontal bar
        self.assertEqual(alpha.getpixel((23, 5)), 255); self.assertEqual(alpha.getpixel((40, 60)), 255); self.assertEqual(alpha.getpixel((5, 5)), 255)
        transparent = sum(1 for value in alpha.tobytes() if value == 0)
        self.assertEqual(transparent, 2 * 16 * 64 - 16 * 16)

    def test_composite_keeps_the_source_outside_the_feathered_cross(self):
        rolled, repaint = Image.new("RGB", (256, 256), (0, 0, 255)), Image.new("RGB", (256, 256), (255, 0, 0))
        joined = tiles.composite(rolled, repaint, 112, 12)
        self.assertEqual(joined.getpixel((10, 10)), (0, 0, 255), "far from the cross nothing changes")
        self.assertEqual(joined.getpixel((128, 10)), (255, 0, 0), "the middle of a bar is the repaint")
        edge = joined.getpixel((128 - 56, 10))
        self.assertTrue(100 < edge[0] < 160 and edge[0] + edge[2] in (254, 255, 256), edge)

    def test_circular_blur_commutes_with_the_roll_so_it_tiles(self):
        source = Image.effect_noise((96, 96), 60).convert("RGB")
        first = tiles.circular_blur(tiles.roll_half(source), 8)
        second = tiles.roll_half(tiles.circular_blur(source, 8))
        self.assertEqual(first.tobytes(), second.tobytes())
        with self.assertRaisesRegex(ValueError, "third of the tile side"): tiles.circular_blur(source, 40)

    def test_flatten_removes_low_frequency_light_and_keeps_the_texture_seamless(self):
        lit = lit_texture()
        before, after = column_means(lit), column_means(tiles.flatten(lit, tiles.default_sigma(256)))
        spread = lambda values: max(values) - min(values)
        # A Gaussian keeps exp(-2 pi^2 sigma^2 / P^2) = 84 % of a one-period cosine at sigma 24, P 256: the flatten removes the rest.
        self.assertGreater(spread(before), 90); self.assertLess(spread(after), spread(before) * 0.25)
        flat = tiles.flatten(lit, 24)
        self.assertEqual(tiles.flatten(tiles.roll_half(lit), 24).tobytes(), tiles.roll_half(flat).tobytes(), "the correction itself tiles")
        self.assertLessEqual(tiles.seam(flat), tiles.seam(lit) + 1, "flattening never opens the wrap seam")
        grey = Image.new("RGB", (64, 64), (90, 90, 90))
        self.assertEqual(tiles.flatten(grey, 8).tobytes(), grey.tobytes(), "an evenly lit picture is unchanged")

    @unittest.skipUnless(numpy, "numpy is not a Studio dependency; this cross-check runs where it is installed")
    def test_flatten_agrees_with_the_lab_fft_formula(self):
        np = numpy; sigma = 24; lit = lit_texture()
        a = np.asarray(lit, np.float64)
        fy = np.fft.fftfreq(256)[:, None]; fx = np.fft.fftfreq(256)[None, :]
        blur = lambda ch: np.real(np.fft.ifft2(np.fft.fft2(ch) * np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))))
        lab = np.stack([a[..., c] * a[..., c].mean() / np.maximum(blur(a[..., c]), 1) for c in range(3)], -1).clip(0, 255)
        ours = np.asarray(tiles.flatten(lit, sigma), np.float64)
        self.assertLess(float(np.abs(ours - lab).mean()), 1.5)

    def test_repeat_preview_is_nine_identical_cells(self):
        preview = tiles.repeat_preview(ramp(64), cell=32)
        self.assertEqual(preview.size, (96, 96))
        first = preview.crop((0, 0, 32, 32)).tobytes()
        self.assertTrue(all(preview.crop((c * 32, r * 32, c * 32 + 32, r * 32 + 32)).tobytes() == first for c in range(3) for r in range(3)))
        self.assertEqual(tiles.repeat_preview(ramp(64)).size, (192, 192), "a small tile is shown at full size")

    def test_only_square_flat_sizes_are_eligible_with_a_reason(self):
        self.assertIsNone(tiles.eligibility(1024, 1024))
        wide = tiles.eligibility(1344, 768)
        self.assertIn("square", wide); self.assertIn("1344 × 768", wide)
        self.assertIn("multiple of 16", tiles.eligibility(1000, 1000))
        self.assertIn("between 256 and 1536", tiles.eligibility(128, 128))
        self.assertEqual(tiles.default_sigma(1024), 96, "the lab's flatten radius at 1024 px")

    def test_the_seam_band_choice_is_the_labs_two_widths_with_a_reason_when_one_does_not_fit(self):
        """Owner, 27 Sep 2026: a wider band hides the floor's repeating plank ends. The lab measured 112 px (wall) and 160 px (floor v2)."""
        self.assertEqual([(c["name"], c["band_px"], c["available"]) for c in tiles.band_choices(1024)], [("narrow", 112, True), ("wide", 160, True)])
        small = tiles.band_choices(256)
        self.assertTrue(small[0]["available"]); self.assertIsNone(small[0]["reason"])
        self.assertFalse(small[1]["available"]); self.assertIn("at least 320 px", small[1]["reason"]); self.assertIn("256 px", small[1]["reason"])
        self.assertTrue(tiles.band_choices(320)[1]["available"])
        for value, band in ((160, 160), ("160", 160), (" 112 ", 112), (160.0, 160), ("1.6e2", 160)):
            with self.subTest(value=value): self.assertEqual(tiles.band_value(value), band)
        for value in (113, "113", 160.5, "nan", "inf", True, None, [160], {"px": 160}, "wide", 14, 514, "", "1e30", "1e999999", "-1e30", 10 ** 40):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "even whole number from 16 to 512"): tiles.band_value(value)

    def test_the_catalog_registers_one_masked_tile_route(self):
        self.assertEqual(tiles.route_problems(CATALOG), [])
        self.assertTrue(ROUTE["requires_rgba_mask"]); self.assertFalse(ROUTE["verified"])
        self.assertIn("more than one", tiles.route_problems([ROUTE, dict(ROUTE, id="copy")])[0])
        self.assertTrue(tiles.route_problems([dict(ROUTE, requires_rgba_mask=False)]))
        graph = json.loads((ROOT / ROUTE["graph"]).read_text(encoding="utf-8"))
        node, field = ROUTE["reference"]
        self.assertEqual(graph[node]["class_type"], "LoadImage")
        noise = next(n for n in graph.values() if n["class_type"] == "SetLatentNoiseMask")
        self.assertEqual(noise["inputs"]["mask"], [node, 1], "the repaint region is the LoadImage mask, 1 - alpha")
        self.assertEqual(graph[ROUTE["denoise"][0]]["inputs"]["denoise"], 0.8)


class FakeStudio(server.Studio):
    def __init__(self, root, replies=()): self.replies = iter(replies); self.requests = []; super().__init__(root)
    def _request(self, *args, **kwargs):
        self.requests.append((args, kwargs)); reply = next(self.replies)
        if isinstance(reply, Exception): raise reply
        return reply


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True); (self.root / "config").mkdir()
        (self.root / "fake-comfy/input").mkdir(parents=True); (self.root / "fake-comfy/output/Studio").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [DEMO, ROUTE]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(DEMO_GRAPH))
        shutil.copyfile(ROOT / ROUTE["graph"], self.root / ROUTE["graph"])
        patcher = patch.object(threading.Thread, "start", lambda *_: None); patcher.start(); self.addCleanup(patcher.stop)

    def studio(self, replies=()): return FakeStudio(self.root, replies)

    def source(self, studio, image=None):
        return studio.import_image("wall.png", "image/png", png(image or lit_texture()))["asset"]

    def payload(self, prepared, **overrides):
        body = {"preset_id": ROUTE["id"], "tile": prepared["plan"], "controls": {"reference": prepared["file"], "positive": WORDS},
                "batch_count": 1, "parent_assets": [prepared["plan"]["source_asset_id"]]}
        body.update(overrides); return body

    def test_source_status_flags_flat_textures_and_gives_the_reason_for_non_square(self):
        studio = self.studio()
        square = tiles.source_status(studio, self.source(studio)["id"])
        self.assertTrue(square["eligible"]); self.assertIsNone(square["reason"]); self.assertIn("Flat textures only", square["flag"])
        self.assertEqual(square["preset_id"], ROUTE["id"])
        self.assertEqual((square["band_px"], [c["band_px"] for c in square["band_choices"]]), (112, [112, 160]))
        self.assertFalse(square["band_choices"][1]["available"], "a 256 px texture cannot take a 160 px band")
        wide = tiles.source_status(studio, self.source(studio, Image.new("RGB", (320, 256), "grey"))["id"])
        self.assertFalse(wide["eligible"]); self.assertIn("320 × 256", wide["reason"])
        self.assertEqual(studio.requests, [])

    def test_prepare_stores_the_rolled_cross_as_an_upload_and_submits_nothing(self):
        studio = self.studio(); asset = self.source(studio)
        prepared = tiles.prepare(studio, {"asset_id": asset["id"]})
        plan = prepared["plan"]
        self.assertFalse(prepared["generation_submitted"]); self.assertEqual(studio.requests, [])
        self.assertEqual((plan["size"], plan["band_px"], plan["feather_px"], plan["flatten_sigma_px"]), (256, 112, 12, 24))
        self.assertEqual(plan["source_sha256"], asset["sha256"]); self.assertEqual(plan["preset_id"], ROUTE["id"])
        stored = self.root / "experiments/uploads" / prepared["file"]
        self.assertEqual(hashlib.sha256(stored.read_bytes()).hexdigest(), plan["rolled_sha256"])
        self.assertEqual((self.root / "fake-comfy/input" / prepared["file"]).read_bytes(), stored.read_bytes())
        with Image.open(stored) as image: self.assertEqual(image.tobytes(), tiles.repaint_input(lit_texture(), 112).tobytes())
        self.assertEqual(prepared["seam_source"], tiles.seam(lit_texture()))
        self.assertEqual(tiles.prepare(studio, {"asset_id": asset["id"], "band_px": 64, "flatten": False})["plan"]["flatten_sigma_px"], 0)
        self.assertEqual(tiles.prepare(studio, {"asset_id": asset["id"], "band_px": "96"})["plan"]["band_px"], 96, "a form value arrives as text")
        jobs_before = len(studio.jobs)
        for body, message in (({"asset_id": self.source(studio, Image.new("RGB", (320, 256)))["id"]}, "square texture"),
                              ({"asset_id": asset["id"], "band_px": 113}, "even whole number"), ({"asset_id": asset["id"], "band_px": 200}, "half the tile side"),
                              ({"asset_id": asset["id"], "band_px": 160}, "half the tile side"), ({"asset_id": asset["id"], "band_px": "wide"}, "even whole number"),
                              ({"asset_id": asset["id"], "band_px": True}, "even whole number"),
                              ({"asset_id": asset["id"], "flatten": "yes"}, "true or false"), ({"asset_id": asset["id"], "denoise": 1}, "takes asset_id")):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, message): tiles.prepare(studio, body)
        self.assertEqual(len(studio.jobs), jobs_before + 1, "only the second source's import; a refused prepare creates no job")

    def test_generate_binds_only_the_prepared_cross_of_the_unchanged_source(self):
        studio = self.studio(); prepared = tiles.prepare(studio, {"asset_id": self.source(studio)["id"]})
        _, graph, _, _, _ = studio.prepare(self.payload(prepared))
        self.assertEqual(graph[ROUTE["reference"][0]]["inputs"]["image"], prepared["file"])
        job = studio.jobs[studio.create_job(self.payload(prepared), enqueue=False)["id"]]
        self.assertEqual(job["tile"], prepared["plan"]); self.assertEqual(job["prompt_ids"], []); self.assertEqual(studio.requests, [])
        recipe = json.loads((studio.runs / job["id"] / "recipe.json").read_text(encoding="utf-8"))
        self.assertEqual(recipe["tile"], prepared["plan"]); self.assertEqual(studio.public(job)["tile"], prepared["plan"])
        other = studio.upload("other.png", "image/png", png(tiles.repaint_input(ramp(256, 1), 112)))["file"]
        plan = prepared["plan"]
        refusals = [
            ({"tile": None}, "starts from Make seamless"),
            ({"batch_count": 2}, "batch count to 1"),
            ({"parent_assets": []}, "missing from lineage"),
            ({"controls": {"reference": other, "positive": WORDS}}, "prepared seam cross"),
            ({"tile": dict(plan, band_px=64)}, "no longer matches its source"),
            ({"tile": dict(plan, rolled_sha256="0" * 64)}, "changed or is missing"),
            ({"tile": dict(plan, extra=1)}, "Invalid seamless-tile plan"),
            ({"controls": {"reference": prepared["file"]}}, "Fill in the wording"),
        ]
        for overrides, message in refusals:
            with self.subTest(overrides=overrides), self.assertRaisesRegex((ValueError, server.StudioError), message):
                studio.create_job(self.payload(prepared, **overrides), enqueue=False)
        with self.assertRaisesRegex(ValueError, "runs only on the seamless-tile recipe"):
            studio.prepare({"preset_id": "demo", "tile": plan, "controls": {}, "parent_assets": [plan["source_asset_id"]]})
        (self.root / "experiments/uploads" / prepared["file"]).write_bytes(png(Image.new("RGBA", (256, 256))))
        with self.assertRaisesRegex(ValueError, "changed or is missing"): studio.prepare(self.payload(prepared))

    def test_a_trashed_or_changed_source_refuses_the_plan(self):
        studio = self.studio(); asset = self.source(studio); prepared = tiles.prepare(studio, {"asset_id": asset["id"]})
        studio.assets.file(asset["id"]).write_bytes(png(ramp(256, 1)))
        with self.assertRaisesRegex(ValueError, "changed"): studio.prepare(self.payload(prepared))

    def run_repaint(self, studio, prepared, repaint):
        (self.root / "fake-comfy/output/Studio/Z-Image-Seam-Repair_00001_.png").write_bytes(png(repaint))
        studio.replies = iter([{"queue_running": [], "queue_pending": []}, {"prompt_id": "seam-prompt"},
                               {"seam-prompt": {"status": {"status_str": "success"}, "outputs": {"10": {"images": [
                                   {"filename": "Z-Image-Seam-Repair_00001_.png", "subfolder": "Studio", "type": "output"}]}}}}])
        job = studio.jobs[studio.create_job(self.payload(prepared), enqueue=False)["id"]]
        studio._run(job); return job

    def test_a_completed_repaint_is_finished_once_with_metrics_preview_lineage_and_receipts(self):
        studio = self.studio(); asset = self.source(studio); prepared = tiles.prepare(studio, {"asset_id": asset["id"]})
        rolled = tiles.roll_half(lit_texture())
        job = self.run_repaint(studio, prepared, rolled)   # a repaint that returns the rolled texture unchanged
        self.assertEqual(job["status"], "completed"); self.assertEqual([a[0] for a, _ in studio.requests if a], ["/queue", "/prompt", "/history/seam-prompt"])
        self.assertEqual(job["submissions"][0]["graph"][ROUTE["reference"][0]]["inputs"]["image"], prepared["file"])
        finished = studio.jobs[job["tile_finish"]["job_id"]]
        self.assertEqual(finished["operation"], tiles.OPERATION); self.assertEqual(finished["status"], "completed")
        tile_asset, preview_asset = (studio.assets.get(o["asset_id"]) for o in finished["outputs"])
        repaint_asset = job["outputs"][0]["asset_id"]
        self.assertEqual(tile_asset["lineage"], [asset["id"], repaint_asset]); self.assertEqual(preview_asset["lineage"], [asset["id"], repaint_asset])
        metrics = tile_asset["source"]["tile"]
        self.assertEqual(metrics["seam_source"], tiles.seam(lit_texture()))
        self.assertEqual(metrics["preview_asset_id"], preview_asset["id"]); self.assertEqual(tile_asset["source"]["prompt_id"], "seam-prompt")
        self.assertIn("Seam ", metrics["summary"]); self.assertIn("not art acceptance", metrics["summary"]); self.assertIn("112 px seam band", metrics["summary"])
        self.assertEqual(metrics["band_px"], 112)
        with Image.open(studio.assets.file(preview_asset["id"])) as preview: self.assertEqual(preview.size, (768, 768))
        with Image.open(studio.assets.file(tile_asset["id"])) as tile:
            self.assertEqual(tile.tobytes(), tiles.flatten(tiles.composite(rolled, rolled, 112, 12), 24).tobytes())
        receipt = finished["tile_receipt"]
        self.assertEqual((receipt["repaint_prompt_id"], receipt["repaint_job_id"], receipt["plan"]), ("seam-prompt", job["id"], prepared["plan"]))
        self.assertEqual(receipt["submitted_graph"], job["submissions"][0]["graph"]); self.assertEqual(receipt["repaint_controls"]["reference"], prepared["file"])
        self.assertEqual(set(receipt["files"]), {"tile.png", "tile-3x3.png", "tile-unflattened.png"})
        requests = len(studio.requests)
        self.assertIs(tiles.finish(studio, job["id"]), finished, "finishing again returns the first result")
        self.assertEqual(len(studio.requests), requests, "finishing never reaches ComfyUI")
        reloaded = self.studio(); self.assertEqual(reloaded.jobs[finished["id"]]["outputs"][0]["asset_id"], tile_asset["id"])

    def test_a_wide_band_is_prepared_repainted_and_recorded_in_the_receipt(self):
        """The panel's "wide" choice: 160 px on a texture large enough to take it, carried from the plan to the tile's receipt."""
        studio = self.studio(); source = lit_texture(384); asset = self.source(studio, source)
        prepared = tiles.prepare(studio, {"asset_id": asset["id"], "band_px": 160})
        self.assertEqual(prepared["plan"]["band_px"], 160)
        with Image.open(self.root / "experiments/uploads" / prepared["file"]) as image: self.assertEqual(image.tobytes(), tiles.repaint_input(source, 160).tobytes())
        rolled = tiles.roll_half(source); job = self.run_repaint(studio, prepared, rolled)
        self.assertEqual(job["tile"]["band_px"], 160)
        finished = studio.jobs[job["tile_finish"]["job_id"]]; receipt = finished["tile_receipt"]
        self.assertEqual((receipt["plan"]["band_px"], receipt["metrics"]["band_px"]), (160, 160))
        self.assertIn("160 px", receipt["steps"][0]); self.assertIn("160 px seam band", finished["message"])
        with Image.open(studio.assets.file(finished["outputs"][0]["asset_id"])) as tile:
            self.assertEqual(tile.tobytes(), tiles.flatten(tiles.composite(rolled, rolled, 160, 12), tiles.default_sigma(384)).tobytes())

    def test_a_finish_failure_is_recorded_and_never_changes_the_repaint_outcome(self):
        studio = self.studio(); prepared = tiles.prepare(studio, {"asset_id": self.source(studio)["id"]})
        job = self.run_repaint(studio, prepared, Image.new("RGB", (128, 128)))
        self.assertEqual(job["status"], "completed"); self.assertIn("128 × 128", job["tile_finish"]["error"])
        self.assertEqual([j for j in studio.jobs.values() if j.get("operation") == tiles.OPERATION], [])
        with self.assertRaisesRegex(ValueError, "not a seamless-tile repaint"): tiles.finish(studio, next(j for j in studio.jobs if j != job["id"]))

    def test_a_lost_link_to_the_finished_tile_is_rebuilt(self):
        """Review on #1224: the repaint's save can fail after the finished job was stored (a Windows write lock), or the
        Studio can stop between the two saves. The link must hold in memory, and Finish tile must restore it after a restart."""
        studio = self.studio(); prepared = tiles.prepare(studio, {"asset_id": self.source(studio)["id"]})
        original = server.Studio._save
        def flaky(this, job):
            if job.get("tile_finish", {}).get("job_id") and not getattr(flaky, "failed", False):
                flaky.failed = True; raise OSError("record_write_locked")
            return original(this, job)
        with patch.object(server.Studio, "_save", flaky):
            job = self.run_repaint(studio, prepared, tiles.roll_half(lit_texture()))
        identifier = tiles.finish_id(job["id"])
        self.assertTrue(flaky.failed); self.assertEqual(job["tile_finish"]["job_id"], identifier, "no false 'not finished' after a failed save")
        # A restart that lost the link entirely: the finished job is on disk, the repaint record has no link.
        state = studio.runs / job["id"] / "state.json"; record = json.loads(state.read_text(encoding="utf-8")); record.pop("tile_finish", None)
        state.write_text(json.dumps(record), encoding="utf-8")
        restarted = self.studio(); repaint = restarted.jobs[job["id"]]
        self.assertNotIn("tile_finish", repaint)
        self.assertEqual(tiles.finish(restarted, job["id"])["id"], identifier)
        self.assertEqual(repaint["tile_finish"]["job_id"], identifier)
        self.assertIn("Seam ", repaint["tile_finish"]["summary"])
        self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["tile_finish"]["job_id"], identifier, "the rebuilt link is saved")

    def test_finish_waits_for_a_completed_repaint(self):
        studio = self.studio(); prepared = tiles.prepare(studio, {"asset_id": self.source(studio)["id"]})
        job = studio.jobs[studio.create_job(self.payload(prepared), enqueue=False)["id"]]
        with self.assertRaisesRegex(ValueError, "after its repaint completes"): tiles.finish(studio, job["id"])


class HttpRouteTests(unittest.TestCase):
    def setUp(self):
        RouteTests.setUp(self)
        self.studio = FakeStudio(self.root)
        patch.stopall()   # the Studio is built with its worker parked; the HTTP server thread must really start
        self.http = server.create_server(self.root, port=0, studio_factory=lambda _: self.studio)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 5); self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def call(self, method, path, body=None, origin="http://127.0.0.1:8191"):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=10)
        try:
            headers = {"Host": "127.0.0.1:8191", "Origin": origin, "Content-Type": "application/json"}
            connection.request(method, path, None if body is None else json.dumps(body), headers=headers)
            reply = connection.getresponse(); return reply.status, json.loads(reply.read())
        finally: connection.close()

    def test_status_prepare_and_finish_routes(self):
        wide = RouteTests.source(self, self.studio, Image.new("RGB", (320, 256), "grey"))
        status, body = self.call("GET", "/api/tiles/source/" + wide["id"])
        self.assertEqual(status, 200); self.assertFalse(body["eligible"]); self.assertIn("square", body["reason"]); self.assertIn("Flat textures only", body["flag"])
        status, body = self.call("POST", "/api/tiles/prepare", {"asset_id": wide["id"]})
        self.assertEqual(status, 400); self.assertIn("320 × 256", body["error"])
        square = RouteTests.source(self, self.studio)
        status, body = self.call("POST", "/api/tiles/prepare", {"asset_id": square["id"]})
        self.assertEqual(status, 201); self.assertEqual(body["plan"]["source_asset_id"], square["id"]); self.assertFalse(body["generation_submitted"])
        status, body = self.call("POST", "/api/tiles/prepare", {"asset_id": square["id"], "band_px": "160"})
        self.assertEqual(status, 400); self.assertIn("half the tile side (128 px)", body["error"])
        self.assertRegex(self.call("POST", "/api/tiles/prepare", {"asset_id": square["id"]})[1]["file"], r"^[0-9a-f]{32}_seam-cross\.png$")
        status, body = self.call("POST", "/api/tiles/finish", {"job_id": ["not", "a", "string"]})
        self.assertEqual(status, 400); self.assertIn("Unknown job", body["error"])
        status, body = self.call("POST", "/api/tiles/finish", {"job_id": square["job_id"]})
        self.assertEqual(status, 400); self.assertIn("not a seamless-tile repaint", body["error"])
        status, _ = self.call("POST", "/api/tiles/prepare", {"asset_id": square["id"]}, origin="https://evil.invalid")
        self.assertEqual(status, 403)
        self.assertEqual(self.studio.requests, [], "no route reaches ComfyUI")
