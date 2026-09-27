"""Parallax layers (#1219): the deterministic Pillow steps on synthetic pictures, and the route through a real Studio whose only
ComfyUI seam is scripted (FakeStudio). Nothing here reaches a GPU."""
import hashlib
import importlib.util
import io
import json
import random
import shutil
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
SPEC = importlib.util.spec_from_file_location("parallax_asset_server", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
import continuation  # noqa: E402  (bare names, never `from app import`)
import parallax  # noqa: E402

CATALOG = json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]
ROUTE = next(p for p in CATALOG if p.get("parallax_route"))
DEMO_GRAPH = {"1": {"class_type": "KSampler", "inputs": {"text": "demo", "seed": 1}}}
DEMO = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"], "seed": ["1", "seed"]}
OBJECTS = "the desk and the lamp"
DESK = (150, 300, 400, 470)          # the foreground block in the synthetic room
WINDOW = [300, 40, 480, 250]         # the far view, as a box


def png(image):
    stream = io.BytesIO(); image.save(stream, "PNG"); return stream.getvalue()


def speckle(size, seed, cell=8, low=40, high=200):
    """A textured picture: squares of random grey-ish colours, so every patch has corners to register on."""
    rng = random.Random(seed); image = Image.new("RGB", size); draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            base = rng.randint(low, high); draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(base, max(0, base - rng.randint(0, 30)), min(255, base + rng.randint(0, 30))))
    return image


def room(size=(512, 512)):
    """(source, plate, isolate): a textured wall with a bright-textured window view, and a textured desk in front of both."""
    wall = speckle(size, 1, low=30, high=110)
    wall.paste(speckle((WINDOW[2] - WINDOW[0], WINDOW[3] - WINDOW[1]), 2, cell=6, low=120, high=240), tuple(WINDOW[:2]))
    desk = speckle((DESK[2] - DESK[0], DESK[3] - DESK[1]), 3, cell=10, low=20, high=90)
    source = wall.copy(); source.paste(desk, DESK[:2])
    isolate = Image.new("RGB", size, "white"); isolate.paste(desk, DESK[:2])
    return source, wall, isolate


def klein(image, scale=1.01, dx=-3.0, dy=2.0, fill=(0, 0, 0)):
    """What Klein does to an edit: the content comes back about 1 % larger and a few pixels off (edit_x = scale x + dx)."""
    return image.transform(image.size, Image.AFFINE, (1 / scale, 0, -dx / scale, 0, 1 / scale, -dy / scale), resample=Image.BICUBIC, fillcolor=fill)


def naive_grow(mask, px):
    width, height = mask.size; data = mask.load(); out = Image.new("L", mask.size); put = out.load()
    for y in range(height):
        for x in range(width):
            put[x, y] = 255 if any(data[i, j] for i in range(max(0, x - px), min(width, x + px + 1)) for j in range(max(0, y - px), min(height, y + px + 1))) else 0
    return out


def mask_from(rows):
    image = Image.new("L", (len(rows[0]), len(rows))); image.putdata([255 if c == "#" else 0 for row in rows for c in row]); return image


class MaskTests(unittest.TestCase):
    def test_grow_is_an_exact_square_dilation_and_shrink_its_dual(self):
        rng = random.Random(7); mask = Image.new("L", (40, 30)); mask.putdata([255 if rng.random() < 0.03 else 0 for _ in range(1200)])
        for px in (1, 2, 5):
            with self.subTest(px=px):
                self.assertEqual(parallax.grow(mask, px).tobytes(), naive_grow(mask, px).tobytes())
                self.assertEqual(parallax.shrink(mask, px).tobytes(), ImageChops.invert(naive_grow(ImageChops.invert(mask), px)).tobytes())
        self.assertEqual(parallax.grow(mask, 0).tobytes(), mask.tobytes())

    def test_parts_fill_holes_and_drop_small(self):
        mask = mask_from(["..........",
                          ".#####....",
                          ".#...#..#.",
                          ".#####....",
                          "..........",
                          "##......##",
                          "#.......#.",
                          "##.......#"])
        self.assertEqual(sorted(sum(x1 - x0 for _, x0, x1 in part) for part in parallax.parts(mask)), [1, 4, 5, 12])
        filled = parallax.fill_holes(mask)
        self.assertEqual(filled.getpixel((2, 2)), 255, "the enclosed hole is filled")
        self.assertEqual(filled.getpixel((1, 6)), 0, "a gap open to the border is not a hole")
        dropped = parallax.drop_small(filled, 6)
        self.assertEqual(parallax.count(dropped), 15, "only the filled box survives: the 1-, 4- and 5-pixel parts are specks")

    def test_near_matte_takes_the_non_white_foreground_with_its_white_details(self):
        isolate = Image.new("RGB", (200, 160), "white"); draw = ImageDraw.Draw(isolate)
        draw.rectangle((40, 40, 159, 119), fill=(60, 50, 40)); draw.rectangle((70, 60, 100, 80), fill=(250, 250, 250))   # a white paper on the desk
        draw.rectangle((5, 5, 7, 7), fill=(0, 0, 0))                                                                      # a speck
        matte = parallax.near_matte(isolate, dict(parallax.PARAMETERS, min_part_px=100))
        self.assertEqual(matte.getbbox(), (40, 40, 160, 120)); self.assertEqual(parallax.count(matte), 120 * 80)


class RegistrationTests(unittest.TestCase):
    def test_a_klein_sized_edit_is_registered_back_to_the_source(self):
        source, plate, _ = room()
        edit = klein(source)
        registered, record = parallax.register(source, edit, source)
        self.assertIsNone(record["fallback"]); self.assertGreaterEqual(record["patches_used"], 6)
        (a, b, c), (d, e, f) = record["affine_x"], record["affine_y"]
        self.assertAlmostEqual(a, 1.01, delta=0.002); self.assertAlmostEqual(e, 1.01, delta=0.002)
        self.assertAlmostEqual(c, -3.0, delta=0.6); self.assertAlmostEqual(f, 2.0, delta=0.6)
        self.assertLess(abs(b) + abs(d), 0.004)
        inner = (40, 40, 472, 472)
        before, _ = parallax.error(edit.crop(inner), source.crop(inner)); after, _ = parallax.error(registered.crop(inner), source.crop(inner))
        self.assertLess(after, before / 3, (before, after))
        self.assertLess(max(record["median_abs_shift_after"]), 0.35)

    def test_an_isolate_on_white_registers_from_its_foreground_alone(self):
        source, _, isolate = room()
        registered, record = parallax.register(source, klein(isolate, 1.012, -4.0, -1.0, fill=(255, 255, 255)), (255, 255, 255))
        self.assertIsNone(record["fallback"])
        self.assertAlmostEqual(record["affine_x"][0], 1.012, delta=0.003); self.assertAlmostEqual(record["affine_x"][2], -4.0, delta=1.0)
        box = parallax.near_matte(registered).getbbox()   # bicubic resampling softens each edge by about a pixel
        self.assertTrue(all(abs(got - want) <= 1 for got, want in zip(box, DESK)), box)

    def test_an_unrelated_edit_falls_back_to_a_resize_and_says_so(self):
        source, _, _ = room()
        registered, record = parallax.register(source, speckle((640, 640), 99), source)
        self.assertIn("No registration", record["fallback"]); self.assertEqual(registered.size, source.size)
        self.assertEqual(record["resized_to"], [512, 512]); self.assertEqual((record["affine_x"], record["affine_y"]), ([1, 0, 0], [0, 1, 0]))

    def test_the_robust_fit_ignores_a_moved_object(self):
        points = [(x, y, 0.01 * x - 3, 0.01 * y + 2) for x in range(64, 480, 64) for y in range(64, 480, 96)]
        points += [(x, 300, 25.0, -20.0) for x in (100, 150, 200, 250)]     # a removed desk drags these four patches away
        fit, inliers = parallax.robust_affine(points)
        self.assertEqual(len(inliers), len(points) - 4)
        self.assertAlmostEqual(fit[0][0], 1.01, places=4); self.assertAlmostEqual(fit[1][2], 2.0, places=3)


class LayerTests(unittest.TestCase):
    def test_ring_fill_copies_the_nearest_known_pixel(self):
        image = Image.new("RGB", (60, 20)); image.putdata([(x * 4, y * 10, 9) for y in range(20) for x in range(60)])
        known = Image.new("L", (60, 20)); known.paste(255, (0, 0, 30, 20))
        target = Image.new("L", (60, 20)); target.paste(255, (0, 0, 45, 20))
        filled, unfilled = parallax.ring_fill(image, known, target)
        self.assertEqual(unfilled, 0)
        for x, y in ((30, 5), (37, 12), (44, 19)): self.assertEqual(filled.getpixel((x, y)), image.getpixel((29, y)), (x, y))
        self.assertEqual(filled.getpixel((50, 5)), (0, 0, 0), "outside the target nothing is invented")
        self.assertEqual(filled.getpixel((10, 3)), image.getpixel((10, 3)))

    def test_colour_match_maps_the_plate_statistics_onto_the_source_in_the_ring(self):
        source = speckle((64, 64), 5)
        plate = Image.merge("RGB", [band.point(lambda v: int(v * 0.5 + 30)) for band in source.split()])
        ring = Image.new("L", (64, 64), 255)
        matched, record = parallax.colour_match(plate, source, ring)
        self.assertLess(parallax.error(matched, source)[0], 1.0)
        self.assertAlmostEqual(record["gain"][0], 2.0, delta=0.05)
        self.assertIn("skipped", parallax.colour_match(plate, source, Image.new("L", (64, 64)))[1])

    def test_route_c2_layers_recomposite_to_the_source(self):
        source, plate, isolate = room()
        view = parallax._polygons([WINDOW], 512, 512)
        images, record = parallax.layers(source, plate, isolate, view)
        self.assertEqual(record["layers"], ["far", "mid", "near"]); self.assertEqual(record["shifts_px"], [3, 10, 24])
        self.assertLess(record["recomposite_mean_abs_error"], 1.0, record)
        self.assertEqual(parallax.recomposite([images["far"], images["mid"], images["near"]], source.size).size, source.size)
        far, mid, near = (images[name].getchannel("A") for name in ("far", "mid", "near"))
        self.assertEqual(far.getbbox(), (WINDOW[0] - 32, WINDOW[1] - 32, WINDOW[2] + 32, WINDOW[3] + 32), "the view plus its 32 px ring")
        self.assertEqual(mid.getpixel((400, 100)), 0, "the view is cut out of the mid layer"); self.assertEqual(mid.getpixel((50, 50)), 255)
        self.assertEqual(near.getpixel((250, 400)), 255); self.assertEqual(near.getpixel((50, 50)), 0)
        self.assertEqual(images["mid"].getpixel((250, 400))[:3], plate.getpixel((250, 400)), "behind the desk the mid layer is the (already matching) plate")
        self.assertEqual(images["far"].getpixel((WINDOW[0] - 10, 100))[:3], source.getpixel((WINDOW[0], 100)), "the ring repeats the nearest view pixel")
        self.assertEqual(images["far"].getpixel((350, 245))[:3], source.getpixel((350, 245)), "inside the view the far layer is the source")
        self.assertEqual(images["strip"].size, ((512 - 48) * 3 + 20, 512))
        self.assertEqual(record["near_px"], (DESK[2] - DESK[0]) * (DESK[3] - DESK[1]))
        self.assertIn("within", parallax.summary(record)); self.assertIn("not art acceptance", parallax.summary(record))

    def test_without_a_marked_view_there_are_two_layers(self):
        source, plate, isolate = room()
        images, record = parallax.layers(source, plate, isolate, [])
        self.assertIsNone(images["far"]); self.assertEqual(record["layers"], ["mid", "near"]); self.assertEqual(record["shifts_px"], [10, 24])
        self.assertLess(record["recomposite_mean_abs_error"], 1.0)
        self.assertIn("no far view marked", parallax.summary(record))


class ContractTests(unittest.TestCase):
    def test_eligibility_names_the_size(self):
        self.assertIsNone(parallax.eligibility(1344, 768))
        self.assertIn("1000 × 768", parallax.eligibility(1000, 768)); self.assertIn("16 px grid", parallax.eligibility(1000, 768))
        self.assertIn("between 512 and 2048", parallax.eligibility(256, 768))
        self.assertIn("megapixels", parallax.eligibility(1920, 1088))

    def test_views_objects_and_plan_identity(self):
        self.assertEqual(parallax._polygons([[10, 20, 50, 60]], 100, 100), [[[10, 20], [49, 20], [49, 59], [10, 59]]])
        self.assertEqual(parallax._polygons([[[0, 0], [50, 10], [40, 90]]], 100, 100), [[[0, 0], [50, 10], [40, 90]]])
        for bad, message in (([[10, 20, 5, 60]], "inside"), ([[10, 20, 15, 60]], "at least 8"), ([[0, 0, 9, 9]] * 5, "at most 4"), ([[[0, 0], [1, 1]]], "3 to 16"),
                             ([[[0, 0], [500, 0], [0, 50]]], "inside"), ("box", "at most 4")):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, message): parallax._polygons(bad, 100, 100)
        self.assertEqual(parallax._objects("  the desk,\n the chair "), "the desk, the chair")
        for bad in ("", "   ", "[describe]", "x" * 300, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError): parallax._objects(bad)
        self.assertIn("Remove the desk and the lamp, leaving", parallax.words("plate", OBJECTS))
        self.assertIn("except the desk and the lamp with a plain pure white", parallax.words("isolate", OBJECTS))
        plan = {"version": 1, "preset_id": "p", "source_asset_id": "a", "source_sha256": "0" * 64, "source_file": "f", "width": 512, "height": 512, "objects": OBJECTS, "view_polygons": []}
        self.assertEqual(parallax.plan_id(plan), parallax.plan_id(dict(plan, stage="isolate", plan_id="x")), "the stage is not part of the plan")
        self.assertNotEqual(parallax.plan_id(plan), parallax.plan_id(dict(plan, objects="the chair")))

    def test_the_catalog_registers_one_parallax_edit_on_the_verified_klein_graph(self):
        self.assertEqual(parallax.route_problems(CATALOG), [])
        self.assertFalse(ROUTE["verified"])
        flux = next(p for p in CATALOG if p["id"] == "flux-edit")
        self.assertEqual(ROUTE["graph"], flux["graph"]); self.assertTrue(flux["verified"])
        self.assertEqual({k: ROUTE[k] for k in ("positive", "seed", "width", "height", "reference", "bindings_extra")}, {k: flux[k] for k in ("positive", "seed", "width", "height", "reference", "bindings_extra")})
        self.assertIn("more than one", parallax.route_problems([ROUTE, dict(ROUTE, id="copy")])[0])
        self.assertTrue(parallax.route_problems([dict(ROUTE, requires_rgba_mask=True)])); self.assertTrue(parallax.route_problems([dict(ROUTE, width=None)]))
        graph = json.loads((ROOT / ROUTE["graph"]).read_text(encoding="utf-8"))
        capability = continuation.capability(ROUTE, graph)
        self.assertEqual(capability["operation"], "parallax-stage")
        self.assertFalse(any(capability["operation"] in routes for routes in continuation.ROUTES.values()), "never offered as a Continue route")


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
        (self.root / "fake-comfy/input").mkdir(parents=True); (self.root / "fake-comfy/output/Verified").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [DEMO, ROUTE]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(DEMO_GRAPH))
        shutil.copyfile(ROOT / ROUTE["graph"], self.root / ROUTE["graph"])
        patcher = patch.object(threading.Thread, "start", lambda *_: None); patcher.start(); self.addCleanup(patcher.stop)
        self.pictures = room()

    def studio(self, replies=()): return FakeStudio(self.root, replies)

    def source(self, studio, image=None):
        return studio.import_image("room.png", "image/png", png(image or self.pictures[0]))["asset"]

    def prepared(self, studio, **body):
        return parallax.prepare(studio, dict({"asset_id": self.source(studio)["id"], "objects": OBJECTS, "view": [WINDOW]}, **body))

    def payload(self, stage, **overrides):
        body = {"preset_id": ROUTE["id"], "parallax": stage["claim"], "batch_count": 1, "parent_assets": [stage["plan"]["source_asset_id"]],
                "controls": {"reference": stage["file"], "positive": stage["words"], "width": stage["width"], "height": stage["height"]}}
        body.update(overrides); return body

    def test_source_status_gives_the_reason_for_an_unfit_picture(self):
        studio = self.studio()
        status = parallax.source_status(studio, self.source(studio)["id"])
        self.assertTrue(status["eligible"]); self.assertIsNone(status["reason"]); self.assertIn("view mask is yours", status["flag"]); self.assertEqual(status["preset_id"], ROUTE["id"])
        small = parallax.source_status(studio, self.source(studio, Image.new("RGB", (320, 256), "grey"))["id"])
        self.assertFalse(small["eligible"]); self.assertIn("320 × 256", small["reason"])
        self.assertEqual(studio.requests, [])

    def test_prepare_attaches_the_unchanged_source_and_returns_the_plate_stage(self):
        studio = self.studio(); stage = self.prepared(studio)
        plan, claim = stage["plan"], stage["claim"]
        self.assertFalse(stage["generation_submitted"]); self.assertEqual(studio.requests, [])
        self.assertEqual((stage["stage"], stage["other_stage"], claim["stage"]), ("plate", "isolate", "plate"))
        self.assertEqual(plan["view_polygons"], parallax._polygons([WINDOW], 512, 512)); self.assertEqual(plan["plan_id"], parallax.plan_id(plan))
        self.assertEqual(stage["words"], parallax.words("plate", OBJECTS))
        stored = self.root / "experiments/uploads" / stage["file"]
        self.assertEqual(hashlib.sha256(stored.read_bytes()).hexdigest(), plan["source_sha256"])
        self.assertEqual((self.root / "fake-comfy/input" / stage["file"]).read_bytes(), stored.read_bytes())
        self.assertEqual(self.prepared(studio, view=None)["plan"]["view_polygons"], [])
        asset = self.source(studio)
        for body, message in (({"asset_id": asset["id"]}, "Name the foreground"), ({"asset_id": asset["id"], "objects": OBJECTS, "view": [[0, 0, 600, 10]]}, "inside"),
                              ({"asset_id": asset["id"], "objects": OBJECTS, "seed": 1}, "takes asset_id"),
                              ({"asset_id": self.source(studio, Image.new("RGB", (520, 512)))["id"], "objects": OBJECTS}, "16 px grid")):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, message): parallax.prepare(studio, body)

    def test_generate_binds_the_source_at_its_size_and_refuses_anything_else(self):
        studio = self.studio(); stage = self.prepared(studio)
        _, graph, _, _, _ = studio.prepare(self.payload(stage))
        self.assertEqual(graph[ROUTE["reference"][0]]["inputs"]["image"], stage["file"])
        self.assertEqual((graph["10"]["inputs"]["width"], graph["9"]["inputs"]["height"]), (512, 512))
        self.assertEqual(graph[ROUTE["positive"][0]]["inputs"]["text"], stage["words"])
        job = studio.jobs[studio.create_job(self.payload(stage), enqueue=False)["id"]]
        self.assertEqual(job["parallax"], stage["claim"]); self.assertEqual(job["prompt_ids"], []); self.assertEqual(studio.requests, [])
        self.assertEqual(json.loads((studio.runs / job["id"] / "recipe.json").read_text(encoding="utf-8"))["parallax"], stage["claim"])
        self.assertEqual(studio.public(job)["parallax"], stage["claim"])
        other = studio.upload("other.png", "image/png", png(speckle((512, 512), 8)))["file"]
        claim = stage["claim"]
        refusals = [
            ({"parallax": None}, "starts from Make parallax layers"),
            ({"batch_count": 2}, "batch count to 1"),
            ({"parent_assets": []}, "missing from lineage"),
            ({"controls": {"reference": other, "positive": "x", "width": 512, "height": 512}}, "prepared source picture"),
            ({"controls": {"reference": stage["file"], "positive": "x", "width": 256, "height": 512}}, "source size, 512 × 512"),
            ({"controls": {"reference": stage["file"], "positive": " ", "width": 512, "height": 512}}, "Say what the clean plate edit does"),
            ({"parallax": dict(claim, objects="the chair")}, "altered"),
            ({"parallax": dict(claim, stage="depth")}, "Invalid parallax plan"),
            ({"parallax": dict(claim, extra=1)}, "Invalid parallax plan"),
        ]
        for overrides, message in refusals:
            with self.subTest(overrides=overrides), self.assertRaisesRegex((ValueError, server.StudioError), message):
                studio.create_job(self.payload(stage, **overrides), enqueue=False)
        with self.assertRaisesRegex(ValueError, "runs only on the parallax-layers recipe"):
            studio.prepare({"preset_id": "demo", "parallax": claim, "controls": {}, "parent_assets": [claim["source_asset_id"]]})
        (self.root / "experiments/uploads" / stage["file"]).write_bytes(png(Image.new("RGB", (512, 512))))
        with self.assertRaisesRegex(ValueError, "changed or is missing"): studio.prepare(self.payload(stage))

    def test_next_stage_loads_the_isolate_wording_for_the_same_plan(self):
        studio = self.studio(); stage = self.prepared(studio)
        job = studio.jobs[studio.create_job(self.payload(stage), enqueue=False)["id"]]
        isolate = parallax.next_stage(studio, {"job_id": job["id"]})
        self.assertEqual((isolate["stage"], isolate["claim"]["stage"], isolate["plan"]), ("isolate", "isolate", stage["plan"]))
        self.assertEqual(isolate["words"], parallax.words("isolate", OBJECTS)); self.assertFalse(isolate["generation_submitted"])
        self.assertEqual(parallax.next_stage(studio, {"job_id": job["id"], "stage": "plate"})["stage"], "plate")
        with self.assertRaisesRegex(ValueError, "not a parallax edit"): parallax.next_stage(studio, {"job_id": self.source(studio)["job_id"]})
        self.assertEqual(studio.requests, [])

    def run_stage(self, studio, stage, picture, number):
        name = "FLUX-Edit_%05d_.png" % number; prompt = "%s-prompt-%d" % (stage["stage"], number)
        (self.root / "fake-comfy/output/Verified" / name).write_bytes(png(picture))
        studio.replies = iter([{"queue_running": [], "queue_pending": []}, {"prompt_id": prompt},
                               {prompt: {"status": {"status_str": "success"}, "outputs": {"13": {"images": [{"filename": name, "subfolder": "Verified", "type": "output"}]}}}}])
        job = studio.jobs[studio.create_job(self.payload(stage), enqueue=False)["id"]]
        studio._run(job); return job

    def test_both_edits_are_split_once_with_layers_strip_lineage_and_receipts(self):
        studio = self.studio(); source, plate, isolate = self.pictures; plate_stage = self.prepared(studio)
        plate_job = self.run_stage(studio, plate_stage, klein(plate, fill=None), 1)
        self.assertEqual(plate_job["status"], "completed"); self.assertNotIn("parallax_finish", plate_job, "one stage alone finishes nothing and records no failure")
        with self.assertRaisesRegex(ValueError, "Run the isolate edit"): parallax.finish(studio, plate_job["id"])
        isolate_job = self.run_stage(studio, parallax.next_stage(studio, {"job_id": plate_job["id"]}), klein(isolate, 1.012, -4, -1, fill=(255, 255, 255)), 2)
        self.assertEqual(isolate_job["status"], "completed")
        finished = studio.jobs[isolate_job["parallax_finish"]["job_id"]]
        self.assertEqual(plate_job["parallax_finish"]["job_id"], finished["id"]); self.assertEqual(finished["operation"], parallax.OPERATION)
        self.assertEqual(finished["id"], parallax.finish_id(plate_job["id"], isolate_job["id"]))
        assets = [studio.assets.get(output["asset_id"]) for output in finished["outputs"]]
        self.assertEqual([a["source"]["parallax"]["layer"] for a in assets], ["far", "mid", "near", "strip"])
        edits = [plate_job["outputs"][0]["asset_id"], isolate_job["outputs"][0]["asset_id"]]
        for asset in assets: self.assertEqual(asset["lineage"], [plate_stage["plan"]["source_asset_id"]] + edits)
        with Image.open(studio.assets.file(assets[0]["id"])) as far: self.assertEqual((far.mode, far.size), ("RGBA", (512, 512)))
        receipt = finished["parallax_receipt"]; metrics = receipt["metrics"]
        self.assertLess(metrics["recomposite_mean_abs_error"], 1.0, metrics); self.assertIn("recomposite_max_abs_error", metrics)
        self.assertEqual((receipt["stages"]["plate"]["prompt_id"], receipt["stages"]["isolate"]["prompt_id"]), ("plate-prompt-1", "isolate-prompt-2"))
        self.assertEqual(receipt["stages"]["isolate"]["submitted_graph"], isolate_job["submissions"][0]["graph"])
        for name in ("plate", "isolate"):
            self.assertIsNone(metrics["registration"][name]["fallback"]); self.assertAlmostEqual(metrics["registration"][name]["affine_x"][0], 1.01, delta=0.004)
        self.assertEqual(receipt["plan"], plate_stage["plan"]); self.assertEqual(receipt["parameters"], parallax.PARAMETERS)
        self.assertEqual(set(receipt["files"]), {"far.png", "mid.png", "near.png", "parallax-strip.png", "plate-registered.png", "isolate-registered.png", "plate-matched.png", "near-matte.png", "view-mask.png"})
        for filename, digest in receipt["files"].items(): self.assertEqual(hashlib.sha256((studio.runs / finished["id"] / filename).read_bytes()).hexdigest(), digest)
        self.assertIn("within", assets[0]["source"]["parallax"]["summary"])
        requests = len(studio.requests)
        self.assertIs(parallax.finish(studio, plate_job["id"]), finished, "finishing again returns the first result")
        self.assertEqual(len(studio.requests), requests, "splitting never reaches ComfyUI")
        self.assertEqual(self.studio().jobs[finished["id"]]["outputs"][1]["asset_id"], assets[1]["id"], "the split survives a restart")
        # A rerun of the plate is split again with the newest isolate: a new pair, a new result.
        rerun = self.run_stage(studio, plate_stage, klein(plate, fill=None), 3)
        self.assertEqual(rerun["parallax_finish"]["job_id"], parallax.finish_id(rerun["id"], isolate_job["id"]))
        self.assertEqual(isolate_job["parallax_finish"]["job_id"], rerun["parallax_finish"]["job_id"])

    def test_a_split_failure_is_recorded_and_never_changes_the_edit_outcome(self):
        studio = self.studio(); _, plate, isolate = self.pictures; stage = self.prepared(studio)
        plate_job = self.run_stage(studio, stage, plate, 1)
        with patch.object(parallax, "layers", side_effect=ValueError("synthetic split fault")):
            isolate_job = self.run_stage(studio, parallax.next_stage(studio, {"job_id": plate_job["id"]}), isolate, 2)
        self.assertEqual(isolate_job["status"], "completed"); self.assertIn("synthetic split fault", isolate_job["parallax_finish"]["error"])
        self.assertEqual([j for j in studio.jobs.values() if j.get("operation") == parallax.OPERATION], [])
        self.assertEqual(parallax.finish(studio, isolate_job["id"])["operation"], parallax.OPERATION, "Split layers by hand after the fault is fixed")


class HttpRouteTests(unittest.TestCase):
    def setUp(self):
        RouteTests.setUp(self)
        self.studio = FakeStudio(self.root)
        patch.stopall()   # the Studio is built with its worker parked; the HTTP server thread must really start
        self.http = server.create_server(self.root, port=0, studio_factory=lambda _: self.studio)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 5); self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def call(self, method, path, body=None, origin="http://127.0.0.1:8191"):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=30)
        try:
            headers = {"Host": "127.0.0.1:8191", "Origin": origin, "Content-Type": "application/json"}
            connection.request(method, path, None if body is None else json.dumps(body), headers=headers)
            reply = connection.getresponse(); return reply.status, json.loads(reply.read())
        finally: connection.close()

    def test_status_prepare_stage_and_finish_routes(self):
        small = RouteTests.source(self, self.studio, Image.new("RGB", (320, 256), "grey"))
        status, body = self.call("GET", "/api/parallax/source/" + small["id"])
        self.assertEqual(status, 200); self.assertFalse(body["eligible"]); self.assertIn("320 × 256", body["reason"])
        status, body = self.call("POST", "/api/parallax/prepare", {"asset_id": small["id"], "objects": OBJECTS})
        self.assertEqual(status, 400); self.assertIn("320 × 256", body["error"])
        picture = RouteTests.source(self, self.studio)
        status, body = self.call("POST", "/api/parallax/prepare", {"asset_id": picture["id"], "objects": OBJECTS, "view": [WINDOW]})
        self.assertEqual(status, 201); self.assertEqual((body["stage"], body["plan"]["source_asset_id"]), ("plate", picture["id"])); self.assertFalse(body["generation_submitted"])
        status, body = self.call("POST", "/api/parallax/stage", {"job_id": picture["job_id"]})
        self.assertEqual(status, 400); self.assertIn("not a parallax edit", body["error"])
        status, body = self.call("POST", "/api/parallax/finish", {"job_id": ["not", "a", "string"]})
        self.assertEqual(status, 400); self.assertIn("Unknown job", body["error"])
        status, _ = self.call("POST", "/api/parallax/prepare", {"asset_id": picture["id"], "objects": OBJECTS}, origin="https://evil.invalid")
        self.assertEqual(status, 403)
        self.assertEqual(self.studio.requests, [], "no route reaches ComfyUI")


if __name__ == "__main__":
    unittest.main()
