"""Offline contract and actual-file tests; these do not run a neural model."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(points=None, people=1):
    points = points or [[64 + i * 3, 32 + i * 8, .8] for i in range(18)]
    return json.dumps({'version': 1.3, 'canvas_width': 256, 'canvas_height': 256,
                       'people': [{'pose_keypoints_2d': sum(points, [])} for _ in range(people)]}).encode()


class PoseArtifactTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'studio_workflow/pose_artifact.py').exists(), 'pose artifact implementation missing')
        from studio_workflow import pose_artifact
        self.p = pose_artifact

    def make(self, raw=None, **kw):
        return self.p.import_openpose(raw or source(), width=256, height=256,
                                      coordinate_space='pixels', **kw)

    def test_exact_source_and_stable_identity(self):
        raw = source()
        a = self.make(raw)
        self.assertEqual(a['source']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(a, self.p.validate(json.loads(json.dumps(a))))
        self.assertEqual(a, self.make(raw))
        self.assertEqual(a['authority'], 'none')
        self.assertEqual(a['review'], 'unreviewed')

    def test_zero_is_not_missing(self):
        points = [[0, 0, .8]] + [[0, 0, 0]] * 17
        a = self.make(source(points))
        self.assertEqual(a['joints']['nose']['x'], 0)
        self.assertIsNone(a['joints']['neck'])
        self.assertEqual(self.p.export_openpose(a)['people'][0]['pose_keypoints_2d'][:3], [0., 0., .8])

    def test_normalized_coordinates_require_explicit_scale(self):
        raw = source([[.5, 1., .8]] * 18)
        a = self.p.import_openpose(raw, width=256, height=256, coordinate_space='normalized')
        self.assertEqual(a['joints']['nose']['x'], 128)
        self.assertEqual(a['joints']['nose']['y'], 256)
        self.assertEqual(self.make(raw)['joints']['nose']['x'], .5)
        with self.assertRaises(ValueError):
            self.p.import_openpose(raw, width=256, height=256, coordinate_space='auto')

    def test_ambiguous_person_requires_selection(self):
        with self.assertRaises(ValueError):
            self.make(source(people=2))
        self.assertEqual(self.make(source(people=2), person_index=1)['source']['person_index'], 1)
        for index in (-1, 2, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.make(source(people=2), person_index=index)

    def test_reject_empty_layout_and_unrepresented_channels(self):
        data = json.loads(source())
        for key, value in [('people', []), ('canvas_width', 512), ('animals', [])]:
            d = copy.deepcopy(data); d[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.make(json.dumps(d).encode())
        for key, value in [('pose_keypoints_2d', [0] * 75), ('hand_left_keypoints_2d', [0] * 63),
                           ('face_keypoints_2d', [0] * 210), ('pose_keypoints_3d', [0] * 72)]:
            d = copy.deepcopy(data); d['people'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.make(json.dumps(d).encode())

    def test_reject_bad_points_and_canvas(self):
        for triple in ([True, 2, .8], [-1, 2, .8], [257, 2, .8], [1, 2, 1.1], [1, 2, -1], [1, 2, False]):
            with self.subTest(triple=triple), self.assertRaises(ValueError): self.make(source([triple] * 18))
        for width in (True, 0, 8193, 10.5):
            with self.subTest(width=width), self.assertRaises(ValueError):
                self.p.import_openpose(source(), width=width, height=256, coordinate_space='pixels')

    def test_bounded_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xff', b'[' * 100 + b']' * 100,
                    b' ' * (self.p.MAX_BYTES + 1), b'{"x":' + b'9' * 10000 + b'}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError): self.p.loads(raw)

    def test_changed_and_fabricated_artifacts_refuse(self):
        for field, value in [('id', '0' * 64), ('authority', 'execute'), ('review', 'approved'), ('extra', True)]:
            a = self.make(); a[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.p.validate(a)
        a = self.make(); a['joints']['nose']['x'] += 1
        with self.assertRaises(ValueError): self.p.validate(a)

    def test_atomic_stale_edit_and_unknown_joint_refusal(self):
        a = self.make(); before = copy.deepcopy(a)
        for expected, edits in [('0' * 64, {'nose': [12, 20]}),
                                (a['id'], {'nose': [12, 20], 'bad_joint': [1, 2]}),
                                (a['id'], {'nose': [12, 20], 'neck': [-1, 2]}),
                                (a['id'], {'nose': [True, 2]})]:
            with self.subTest(edits=edits), self.assertRaises(ValueError): self.p.revise(a, expected, edits)
            self.assertEqual(a, before)

    def test_revision_preserves_parent_and_noop(self):
        a = self.make(); before = copy.deepcopy(a)
        b = self.p.revise(a, a['id'], {'nose': [12, 20], 'neck': None})
        self.assertEqual(a, before)
        self.assertEqual(b['parent_id'], a['id'])
        self.assertNotEqual(b['id'], a['id'])
        self.assertEqual(b['joints']['nose'], {'x': 12., 'y': 20., 'confidence': None, 'origin': 'manual'})
        self.assertIsNone(b['joints']['neck'])
        self.assertEqual(b['source'], a['source'])
        self.assertEqual(self.p.revise(b, b['id'], {'nose': [12, 20]}), b)
        self.assertEqual(self.p.revise(a, a['id'], {}), a)

    def test_export_threshold_and_manual_presence_sentinel(self):
        a = self.make(source([[0, 0, .2]] + [[20, 20, .8]] * 17))
        b = self.p.revise(a, a['id'], {'neck': [10, 10]})
        out = self.p.export_openpose(b, .3)
        self.assertEqual(out['people'][0]['pose_keypoints_2d'][:6], [0, 0, 0, 10., 10., 1.])
        for bad in (-1, 1.1, True, float('nan')):
            with self.subTest(bad=bad), self.assertRaises(ValueError): self.p.export_openpose(b, bad)

    def test_raster_pixels_and_filtered_limbs(self):
        from PIL import Image
        from studio_workflow.pose_raster import render_png
        a = self.make(source([[0, 0, .2]] + [[20, 20, 0]] * 17))
        with Image.open(io.BytesIO(render_png(a, .3))) as image:
            self.assertEqual(image.size, (256, 256)); self.assertIsNone(image.getbbox())
        with Image.open(io.BytesIO(render_png(a, .1))) as image:
            self.assertNotEqual(image.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(render_png(self.make()), render_png(self.make()))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/pose_artifact.py'), *map(str, args)],
                              cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=15)

    def test_cli_roundtrip_exclusive_outputs_and_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); raw = root / 'source.json'; out = root / 'pose.json'
            raw.write_bytes(source())
            args = ('import', raw, '--width', '256', '--height', '256', '--coordinate-space', 'pixels', '--out', out)
            result = self.cli(*args); self.assertEqual(result.returncode, 0, result.stderr)
            a = json.loads(out.read_text()); original = out.read_bytes()
            result = self.cli(*args); self.assertEqual(result.returncode, 2)
            self.assertEqual(out.read_bytes(), original)
            result = self.cli('inspect', out); self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['id'], a['id'])
            edits = root / 'edits.json'; edits.write_text('{"nose":[12,20]}')
            changed = root / 'changed.json'
            result = self.cli('revise', out, '--expected-id', a['id'], '--edits', edits, '--out', changed)
            self.assertEqual(result.returncode, 0, result.stderr)
            for command, dest in [('render', root / 'pose.png'), ('export-json', root / 'openpose.json')]:
                result = self.cli(command, changed, '--out', dest)
                self.assertEqual(result.returncode, 0, result.stderr); self.assertTrue(dest.exists())
                receipt = json.loads(result.stdout)
                self.assertEqual(receipt['output_sha256'], hashlib.sha256(dest.read_bytes()).hexdigest())
                self.assertFalse(receipt['generation_submitted'])

    def test_cli_invalid_input_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); raw = root / 'bad.json'; out = root / 'output.png'
            raw.write_text('{"id":"not a pose"}')
            result = self.cli('render', raw, '--out', out)
            self.assertEqual(result.returncode, 2); self.assertFalse(out.exists())
            self.assertFalse(json.loads(result.stderr)['generation_submitted'])


if __name__ == '__main__':
    unittest.main()
