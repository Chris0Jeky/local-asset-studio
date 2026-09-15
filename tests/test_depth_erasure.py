"""Real-pixel tests for fixed-canvas depth-guide erasure, never neural inference."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def picture(mode='L', fmt='PNG', size=(16, 12)):
    with Image.new(mode, size) as image:
        if mode in ('L', 'RGB'):
            for y in range(size[1]):
                for x in range(size[0]):
                    v = (x * 7 + y * 13) % 254 + 1
                    image.putpixel((x, y), v if mode == 'L' else (v, 255 - v, 10))
        with io.BytesIO() as out:
            image.save(out, format=fmt)
            return out.getvalue()


class DepthErasureTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'studio_workflow/depth_erasure.py').exists(), 'depth erasure implementation missing')
        from studio_workflow import depth_erasure
        self.m = depth_erasure

    def erase(self, raw=None, boxes=None):
        raw = picture() if raw is None else raw
        return self.m.erase_png(raw, hashlib.sha256(raw).hexdigest(), [[2, 3, 7, 8]] if boxes is None else boxes)

    def test_grayscale_preserves_every_outside_pixel(self):
        raw = picture(); output, receipt = self.erase(raw)
        with Image.open(io.BytesIO(raw)) as before, Image.open(io.BytesIO(output)) as after:
            self.assertEqual(before.size, after.size); self.assertEqual(after.mode, 'L')
            for y in range(12):
                for x in range(16):
                    expected = 0 if 2 <= x < 7 and 3 <= y < 8 else before.getpixel((x, y))
                    self.assertEqual(after.getpixel((x, y)), expected)
        self.assertEqual(receipt['erased_pixels'], 25)
        self.assertEqual(receipt['changed_pixels'], 25)
        self.assertEqual(receipt['outside_pixels_equal'], True)
        self.assertEqual(receipt['source_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['output_sha256'], hashlib.sha256(output).hexdigest())
        self.assertEqual(receipt['authority'], 'none')
        self.assertFalse(receipt['generation_submitted'])
        self.assertFalse(receipt['native_control_qualified'])

    def test_rgb_overlap_union_and_right_bottom_exclusive(self):
        raw = picture('RGB'); boxes = [[0, 0, 4, 4], [2, 2, 6, 6], [15, 11, 16, 12]]
        output, receipt = self.erase(raw, boxes)
        self.assertEqual(receipt['erased_pixels'], 29)
        self.assertEqual(receipt['changed_pixels'], 29)
        with Image.open(io.BytesIO(raw)) as before, Image.open(io.BytesIO(output)) as after:
            self.assertEqual(after.mode, 'RGB')
            for y in range(12):
                for x in range(16):
                    erased = any(l <= x < r and t <= y < b for l, t, r, b in boxes)
                    self.assertEqual(after.getpixel((x, y)), (0, 0, 0) if erased else before.getpixel((x, y)))

    def test_empty_operation_retains_exact_bytes_and_zero_counts(self):
        raw = picture(); output, receipt = self.erase(raw, [])
        self.assertEqual(output, raw)
        self.assertEqual(receipt['erased_pixels'], 0)
        self.assertEqual(receipt['changed_pixels'], 0)

    def test_already_black_pixels_are_not_counted_as_changed(self):
        raw = picture(); output, _ = self.erase(raw)
        twice, receipt = self.erase(output)
        self.assertEqual(receipt['erased_pixels'], 25)
        self.assertEqual(receipt['changed_pixels'], 0)
        with Image.open(io.BytesIO(output)) as a, Image.open(io.BytesIO(twice)) as b:
            self.assertEqual(a.tobytes(), b.tobytes())

    def test_refuses_wrong_hash_and_malformed_png(self):
        with self.assertRaises(ValueError): self.m.erase_png(picture(), '0' * 64, [])
        for expected in ('bad', None, True):
            with self.subTest(expected=expected), self.assertRaises(ValueError): self.m.erase_png(picture(), expected, [])
        with self.assertRaises(ValueError): self.erase(b'not an image')
        with self.assertRaises(ValueError): self.erase(picture()[:50])
        with self.assertRaises(ValueError): self.erase(b' ' * (self.m.MAX_IMAGE_BYTES + 1))

    def test_refuses_rectangles_without_mutating_input(self):
        raw = picture(); original = bytes(raw)
        bad = (None, {}, [[-1, 0, 3, 3]], [[0, 0, 17, 1]], [[0, 0, 1, 13]],
               [[2, 0, 2, 1]], [[0, 2, 1, 1]], [[False, 0, 1, 1]], [[0., 0, 1, 1]],
               [[0, 0, 1]], [[0, 0, 1, 1]] * 65, [[0, 0, 1, 1], [0, 0, 1, 1]])
        for boxes in bad:
            with self.subTest(boxes=boxes), self.assertRaises(ValueError):
                self.m.erase_png(raw, hashlib.sha256(raw).hexdigest(), boxes)
            self.assertEqual(raw, original)

    def test_refuses_modes_formats_and_animation(self):
        for mode, fmt in (('RGBA', 'PNG'), ('P', 'PNG'), ('I;16', 'PNG'), ('RGB', 'JPEG')):
            with self.subTest(mode=mode, fmt=fmt), self.assertRaises(ValueError): self.erase(picture(mode, fmt))
        with Image.new('L', (16, 12), 100) as first, Image.new('L', (16, 12), 200) as second:
            with io.BytesIO() as out:
                first.save(out, format='PNG', save_all=True, append_images=[second], duration=100)
                animated = out.getvalue()
        with self.assertRaises(ValueError): self.erase(animated)

    def test_refuses_excessive_canvas_before_decode(self):
        with self.assertRaises(ValueError): self.erase(picture('P', size=(8193, 1)))

    def test_refuses_transparency_even_on_rgb(self):
        with Image.new('RGB', (16, 12), 'white') as image, io.BytesIO() as out:
            image.save(out, format='PNG', transparency=(255, 255, 255))
            raw = out.getvalue()
        with self.assertRaises(ValueError): self.erase(raw)

    def test_deterministic_operation_and_canonical_rectangles(self):
        raw = picture(); a, ra = self.erase(raw, [[2, 2, 4, 4], [0, 0, 1, 1]])
        b, rb = self.erase(raw, [[0, 0, 1, 1], [2, 2, 4, 4]])
        self.assertEqual(a, b); self.assertEqual(ra, rb)
        self.assertEqual(ra['rectangles'], [[0, 0, 1, 1], [2, 2, 4, 4]])

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/depth_erasure.py'), *map(str, args)],
                              cwd=tempfile.gettempdir(), text=True, capture_output=True, timeout=15)

    def test_cli_real_files_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'depth.png'; boxes = root / 'boxes.json'; out = root / 'erased.png'
            source.write_bytes(picture()); boxes.write_text('[[2,3,7,8]]')
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            args = (source, '--expected-sha256', sha, '--rectangles', boxes, '--out', out)
            result = self.cli(*args); self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['changed_pixels'], 25)
            before = out.read_bytes(); result = self.cli(*args)
            self.assertEqual(result.returncode, 2); self.assertEqual(out.read_bytes(), before)
            result = self.cli(source, '--expected-sha256', sha, '--rectangles', boxes, '--out', source)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha)

    def test_cli_invalid_input_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'depth.png'; boxes = root / 'boxes.json'; out = root / 'erased.png'
            source.write_bytes(picture()); boxes.write_text('[[true,0,1,1]]')
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            result = self.cli(source, '--expected-sha256', sha, '--rectangles', boxes, '--out', out)
            self.assertEqual(result.returncode, 2); self.assertFalse(out.exists())
            self.assertFalse(json.loads(result.stderr)['generation_submitted'])


if __name__ == '__main__':
    unittest.main()
