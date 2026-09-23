"""Pose guide rasters: the Klein thin-line guide stays byte-for-byte, the OpenPose mode matches controlnet_aux (#445)."""
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'app'))

from studio_workflow import pose_raster  # noqa: E402
import pose_guide  # noqa: E402

FIXTURES = ROOT / 'tests/fixtures/pose-openpose'
STANDING = [(.50, .12), (.50, .19), (.42, .20), (.39, .31), (.37, .42), (.58, .20), (.61, .31), (.63, .42), (.45, .47),
            (.44, .66), (.44, .86), (.55, .47), (.56, .66), (.56, .86), (.475, .108), (.525, .108), (.45, .12), (.55, .12)]
# Pixel hashes of studio.coco18-lines/v1 recorded before the OpenPose mode existed (22 September 2026, Pillow 12.1.1):
# the route proved on combine-klein-9b-skeleton must keep drawing exactly these pixels.
KLEIN_PIXELS = {(832, 1216): '4764d960ee515fe9b35ff489fc6e8c44785ac8aa24c197f9bf39266dae38351a',
                (1024, 1536): '7529669227d5122bd614438c58e381c3d54ec7742f3c33d1690dd27c34490389'}
# cv2.ellipse2Poly(center, axes, angle, 0, 360, 1) from OpenCV 5.0.0 (ComfyUI's embedded Python), as JSON lists.
ELLIPSES = {((416, 608), (120, 12), 63): (315, 'cc70902744e320a41cad9cd0bac6f99788352e9b1794fbf71a14cdbd43bf5bdb'),
            ((10, 20), (0, 4), 0): (17, 'cbda441069982898f81bf284c64398087d6021caf25d8cfb78a733f3002c5a1e'),
            ((300, 200), (57, 8), -135): (249, '71c9d5cbb65d5d0cfed90d80d6612d373b6ec461eee61555baa8e671537c6d7f'),
            ((0, 0), (700, 24), 179): (355, 'bf6fb5de21b28e7026aee46b3cdef42656235a3a25fc302abd376e4c48054fa4')}


def standing(width, height):
    return pose_guide.artifact({'width': width, 'height': height,
                                'keypoints': [[round(x * width, 2), round(y * height, 2)] for x, y in STANDING]})


def pixels(data):
    with Image.open(io.BytesIO(data)) as image:
        return image.convert('RGB')


class KleinGuideUnchanged(unittest.TestCase):
    def test_default_renderer_draws_the_recorded_pixels(self):
        for canvas, digest in KLEIN_PIXELS.items():
            with self.subTest(canvas=canvas):
                art = standing(*canvas); data = pose_raster.render_png(art)
                self.assertEqual(data, pose_raster.render_png(art, .3, pose_raster.RENDERER))
                self.assertEqual(hashlib.sha256(pixels(data).tobytes()).hexdigest(), digest)

    def test_default_identity_is_unchanged(self):
        identity = pose_raster.renderer_identity()
        self.assertEqual(identity['renderer_id'], 'studio.coco18-lines/v1')
        self.assertNotIn('reference', identity)
        self.assertEqual(pose_raster.renderer_sha256(), pose_raster.renderer_sha256(pose_raster.RENDERER))


class OpenPoseConvention(unittest.TestCase):
    def test_matches_the_installed_controlnet_aux_drawing(self):
        cases = json.loads((FIXTURES / 'cases.json').read_text(encoding='utf-8'))
        report = json.loads((FIXTURES / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['reference'], pose_raster.OPENPOSE_REFERENCE)
        self.assertEqual(report['ellipse2poly_replica']['mismatches'], 0)
        self.assertEqual(report['cv2_circle_r4_rows'], list(pose_raster._OPENPOSE_DOT))
        self.assertEqual(len(cases), 4)
        for name, case in cases.items():
            with self.subTest(case=name):
                ours = pixels(pose_raster.render_png(case['artifact'], renderer=pose_raster.OPENPOSE_RENDERER))
                with Image.open(FIXTURES / (name + '.aux.png')) as image: aux = image.convert('RGB')
                self.assertEqual(ours.size, aux.size)
                self.assertEqual(sorted(c for _, c in ours.getcolors(4096)), sorted(c for _, c in aux.getcolors(4096)))
                differs = ImageChops.difference(ours, aux).convert('L').point(lambda v: 255 if v else 0)
                differing = differs.histogram()[255]
                self.assertGreaterEqual(1 - differing / (aux.width * aux.height), .999)
                # Every differing pixel sits on an outline of the aux drawing (fill-rule rasterisation), never inside a limb.
                flat = [ImageChops.difference(band.filter(ImageFilter.MaxFilter(3)), band.filter(ImageFilter.MinFilter(3)))
                        for band in aux.split()]
                edge = ImageChops.lighter(ImageChops.lighter(flat[0], flat[1]), flat[2]).point(lambda v: 255 if v else 0)
                interior = ImageChops.logical_and(differs.convert('1'), ImageChops.invert(edge).convert('1'))
                self.assertIsNone(interior.getbbox(), name)

    def test_ellipse_polygon_reproduces_cv2(self):
        for (center, axes, angle), (count, digest) in ELLIPSES.items():
            with self.subTest(center=center, axes=axes, angle=angle):
                points = [list(p) for p in pose_raster._ellipse_polygon(*center, *axes, angle)]
                self.assertEqual(len(points), count)
                self.assertEqual(hashlib.sha256(json.dumps(points).encode()).hexdigest(), digest)

    def test_stick_width_scales_like_xinsir(self):
        for size, scale in (((448, 448), 1), ((499, 320), 1), ((500, 320), 2), ((832, 1216), 3), ((1024, 1536), 3),
                            ((2048, 1024), 4), ((8192, 64), 7)):
            with self.subTest(size=size): self.assertEqual(pose_raster.openpose_stick_scale(*size), scale)

    def test_limb_colours_follow_the_limb_not_the_end_joint(self):
        art = standing(832, 1216)
        image = pixels(pose_raster.render_png(art, renderer=pose_raster.OPENPOSE_RENDERER))
        # Right upper arm (shoulder 2 -> elbow 3) is limb 2 in aux order: (255, 170, 0) at 60 %, sampled mid-limb.
        x = int((STANDING[2][0] + STANDING[3][0]) / 2 * 832); y = int((STANDING[2][1] + STANDING[3][1]) / 2 * 1216)
        self.assertEqual(image.getpixel((x, y)), (153, 102, 0))
        # Joints are drawn last at full colour: the right elbow dot is COLORS[3].
        self.assertEqual(image.getpixel((int(STANDING[3][0] * 832), int(STANDING[3][1] * 1216))), (255, 255, 0))

    def test_unknown_renderer_is_refused_and_identities_differ(self):
        art = standing(256, 384)
        for bad in ('studio.coco18-lines/v2', '', None):
            with self.subTest(renderer=bad), self.assertRaises(ValueError): pose_raster.render_png(art, renderer=bad)
        self.assertNotEqual(pose_raster.renderer_sha256(pose_raster.OPENPOSE_RENDERER), pose_raster.renderer_sha256())
        self.assertEqual(pose_raster.renderer_identity(pose_raster.OPENPOSE_RENDERER)['reference']['file_sha256'],
                         '763d2680ca67e13bd373153e65cfb098a168be4da5d3118c6f9ffe16c94ac89a')
        self.assertNotEqual(pose_raster.render_png(art), pose_raster.render_png(art, renderer=pose_raster.OPENPOSE_RENDERER))


if __name__ == '__main__':
    unittest.main()
