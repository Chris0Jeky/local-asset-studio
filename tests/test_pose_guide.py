"""The drawn-pose endpoint: real Studio storage, real PNG pixels, and never one ComfyUI request."""
import importlib.util
import io
import json
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
SPEC = importlib.util.spec_from_file_location("pose_asset_server", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
import pose_guide  # noqa: E402  (server.py puts app/ on sys.path; a bare name, never `from app import`)
from http_refusal_transport import atomic_json_post  # noqa: E402

GRAPH = {"1": {"inputs": {"text": "native positive", "width": 512, "height": 512, "seed": 1, "reference": "default.png"}}}
PRESET = {"id": "demo", "name": "Demo", "category": "Test", "graph": "workflows/api/demo-api.json",
          "positive": ["1", "text"], "width": ["1", "width"], "height": ["1", "height"], "seed": ["1", "seed"]}
CANVAS = {"width": 256, "height": 384}
# Fractions of the canvas: the module's own neutral standing figure, in COCO-18 order.
STANDING = [(.50, .12), (.50, .19), (.42, .20), (.39, .31), (.37, .42), (.58, .20), (.61, .31), (.63, .42), (.45, .47),
            (.44, .66), (.44, .86), (.55, .47), (.56, .66), (.56, .86), (.475, .108), (.525, .108), (.45, .12), (.55, .12)]
YELLOW = (255, 255, 0)      # pose_raster COLORS[3]: the right-elbow dot and the right-elbow limb


def keypoints(unknown=()):
    return [None if index in unknown else [round(x * CANVAS["width"], 2), round(y * CANVAS["height"], 2)]
            for index, (x, y) in enumerate(STANDING)]


def payload(unknown=(), **overrides):
    return dict({**CANVAS, "keypoints": keypoints(unknown)}, **overrides)


class NoComfyStudio(server.Studio):
    """A real Studio whose only ComfyUI seam records the attempt instead of making it."""
    def __init__(self, root): self.requests = []; super().__init__(root)
    def _request(self, *args, **kwargs): self.requests.append((args, kwargs)); raise AssertionError("The pose editor must never reach ComfyUI")


class PoseGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True)
        (self.root / "config").mkdir(); (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [PRESET]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        with patch.object(threading.Thread, "start", lambda *_: None): self.studio = NoComfyStudio(self.root)

    def uploads(self): return sorted(p.name for p in (self.root / "experiments/uploads").glob("*.png"))

    def colours(self, raw):
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.mode, "RGB")
            return image.size, dict((colour, count) for count, colour in image.getcolors(1 << 20))

    def test_a_drawn_pose_is_stored_exactly_like_an_uploaded_picture(self):
        result = pose_guide.render(self.studio, payload())
        self.assertEqual(result["renderer"], "studio.coco18-lines/v1")
        self.assertFalse(result["generation_submitted"])
        self.assertRegex(result["file"], r"^[0-9a-f]{32}_drawn-pose\.png$")
        self.assertRegex(result["artifact_id"], r"^[0-9a-f]{64}$")
        self.assertEqual((result["width"], result["height"]), (CANVAS["width"], CANVAS["height"]))
        stored = self.root / "experiments/uploads" / result["file"]
        raw = stored.read_bytes()
        self.assertEqual(len(raw), result["bytes"])
        self.assertEqual(server.hashlib.sha256(raw).hexdigest(), result["sha256"])
        # Same folder, same sidecar and the same copy into ComfyUI's input that /api/upload writes.
        self.assertEqual(json.loads((stored.parent / (result["file"] + ".json")).read_text())["sha256"], result["sha256"])
        self.assertEqual((self.root / "fake-comfy/input" / result["file"]).read_bytes(), raw)
        size, colours = self.colours(raw)
        self.assertEqual(size, (CANVAS["width"], CANVAS["height"]))
        self.assertGreater(colours[(0, 0, 0)], CANVAS["width"] * CANVAS["height"] * .5, "the guide is a figure on black")
        self.assertEqual(len([c for c in colours if c != (0, 0, 0)]), 18, "one colour per COCO-18 joint, as pose_raster draws them")
        self.assertEqual(self.studio.requests, [])

    def test_an_unknown_joint_and_the_limbs_touching_it_are_left_out(self):
        _, drawn = self.colours((self.root / "experiments/uploads" / pose_guide.render(self.studio, payload())["file"]).read_bytes())
        self.assertIn(YELLOW, drawn)
        _, without = self.colours((self.root / "experiments/uploads" / pose_guide.render(self.studio, payload(unknown={3}))["file"]).read_bytes())
        self.assertNotIn(YELLOW, without, "a missing joint is omitted, not drawn at coordinate zero")
        self.assertEqual(self.studio.requests, [])

    def test_every_hand_placed_joint_is_manual_with_no_detector_confidence(self):
        drawn = pose_guide.artifact(payload(unknown={16}))
        self.assertEqual(drawn["authority"], "none"); self.assertEqual(drawn["review"], "unreviewed")
        self.assertIsNone(drawn["joints"]["right_ear"])
        placed = [joint for joint in drawn["joints"].values() if joint]
        self.assertEqual(len(placed), 17)
        self.assertEqual({joint["origin"] for joint in placed}, {"manual"})
        self.assertEqual({joint["confidence"] for joint in placed}, {None})

    def test_malformed_poses_are_refused_and_write_nothing(self):
        cases = {
            "seventeen joints": payload(keypoints=keypoints()[:-1]),
            "a nineteenth joint": payload(keypoints=keypoints() + [[1, 1]]),
            "a bare number": payload(keypoints=[0] + keypoints()[1:]),
            "a three-value joint": payload(keypoints=[[1, 2, 3]] + keypoints()[1:]),
            "a non-finite coordinate": payload(keypoints=[[float("inf"), 2]] + keypoints()[1:]),
            "a joint past the canvas": payload(keypoints=[[CANVAS["width"] + 1, 2]] + keypoints()[1:]),
            "a negative coordinate": payload(keypoints=[[-1, 2]] + keypoints()[1:]),
            "a fractional canvas": payload(width=256.5),
            "a boolean canvas": payload(width=True),
            "a canvas below the grid limit": payload(width=32),
            "a canvas above the grid limit": payload(height=2048),
            "a canvas off the grid": payload(width=250),
            "a single joint": payload(unknown=set(range(1, 18))),
            "an extra field": dict(payload(), preset_id="combine-klein-9b-skeleton"),
            "a missing field": {"width": 256, "keypoints": keypoints()},
            "a list, not an object": [CANVAS, keypoints()],
        }
        for name, bad in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError): pose_guide.render(self.studio, bad)
        self.assertEqual(self.uploads(), [])
        self.assertEqual(self.studio.requests, [])


class PoseGuideRouteTests(unittest.TestCase):
    def setUp(self):
        PoseGuideTests.setUp(self)
        self.http = server.create_server(self.root, port=0, studio_factory=lambda _: self.studio)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.thread.join, 5); self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)

    def call(self, method, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        try:
            headers = {"Host": "127.0.0.1:8191", "Origin": "http://127.0.0.1:8191", "Content-Type": "application/json"}
            connection.request(method, path, body if body is None else json.dumps(body), headers=headers)
            reply = connection.getresponse(); return reply.status, reply.read()
        finally: connection.close()

    def test_the_route_stores_a_guide_the_uploads_route_serves_back(self):
        status, raw = self.call("POST", "/api/pose/render", payload())
        self.assertEqual(status, 201, raw)
        result = json.loads(raw)
        served, image = self.call("GET", "/api/uploads/" + result["file"])
        self.assertEqual(served, 200)
        self.assertEqual(image, (self.root / "experiments/uploads" / result["file"]).read_bytes())
        self.assertEqual(server.hashlib.sha256(image).hexdigest(), result["sha256"])
        self.assertEqual(self.studio.requests, [], "drawing a guide reaches no model")
        self.assertFalse(self.studio.jobs, "drawing a guide creates no job")

    def test_the_route_refuses_malformed_and_oversized_bodies_in_the_usual_error_shape(self):
        status, raw = self.call("POST", "/api/pose/render", payload(width=250))
        self.assertEqual(status, 400); self.assertIn("multiple of 8", json.loads(raw)["error"])
        oversized = b" " * (pose_guide.MAX_BODY_BYTES + 1) + json.dumps(payload()).encode()
        status, result = atomic_json_post(self.http.server_port, "/api/pose/render", oversized)
        self.assertEqual(status, 400); self.assertIn("too large", result["error"])
        self.assertEqual(self.uploads(), []); self.assertEqual(self.studio.requests, [])

    def test_the_route_keeps_the_loopback_host_and_origin_guard(self):
        body = json.dumps(payload()).encode()
        self.assertEqual(atomic_json_post(self.http.server_port, "/api/pose/render", body, host="evil.invalid")[0], 403)
        self.assertEqual(atomic_json_post(self.http.server_port, "/api/pose/render", body, origin="https://evil.invalid")[0], 403)
        self.assertEqual(self.uploads(), [])

    uploads = PoseGuideTests.uploads


if __name__ == "__main__": unittest.main()
