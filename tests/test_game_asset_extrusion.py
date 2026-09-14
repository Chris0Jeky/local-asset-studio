"""Atlas borders duplicate source RGBA bytes, including RGB under low alpha."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
import game_asset_media as media
try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, 'Optional Pillow not installed')
class ExtrusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def frame(self, name, size=(4, 6), offset=0):
        image = Image.new('RGBA', size)
        alpha = (0, 1, 2, 64, 127, 128, 254, 255)
        for y in range(size[1]):
            for x in range(size[0]):
                image.putpixel((x, y), ((100 + x * 17 + offset) % 256, (50 + y * 29) % 256,
                                       (200 + x + y) % 256, alpha[(x + y + offset) % len(alpha)]))
        path = self.root / (name + '.png'); image.save(path); self.addCleanup(image.close)
        raw = path.read_bytes()
        return image, {'id': name, 'path': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'duration_ms': 80}, raw

    def assert_cell(self, sheet, source, region, padding, extrude):
        x, y, w, h = region
        for dy in range(-padding, h + padding):
            for dx in range(-padding, w + padding):
                if -extrude <= dx < w + extrude and -extrude <= dy < h + extrude:
                    expected = source.getpixel((min(w - 1, max(0, dx)), min(h - 1, max(0, dy))))
                else: expected = (0, 0, 0, 0)
                self.assertEqual(sheet.getpixel((x + dx, y + dy)), expected, (dx, dy, extrude))

    def test_borders_are_exact_for_all_supported_alpha_and_extrusion_widths(self):
        source, frame, raw = self.frame('frame-a')
        manifest = {'schema_version': 1, 'canvas': list(source.size), 'anchor': [2, 6], 'clip': 'idle', 'loop': True, 'frames': [frame]}
        original = copy.deepcopy(manifest)
        for extrude in (0, 1, 2, 3, 8, 16):
            padding = min(16, extrude + 1)
            with self.subTest(extrude=extrude):
                output = self.root / f'atlas-{extrude}'
                result = media.atlas(manifest, self.root, output, padding=padding, extrude=extrude)
                with Image.open(output / 'atlas.png') as sheet:
                    self.assert_cell(sheet, source, result['frames'][0]['region'], padding, extrude)
                self.assertEqual(result['frames'][0]['pixel_sha256'], hashlib.sha256(source.tobytes()).hexdigest())
        self.assertEqual((self.root / frame['path']).read_bytes(), raw)
        self.assertEqual(manifest, original)

    def test_adjacent_cells_and_partial_last_row_do_not_bleed(self):
        entries = [self.frame(f'frame-{i}', offset=i) for i in range(3)]
        manifest = {'schema_version': 1, 'canvas': [4, 6], 'anchor': [2, 6], 'clip': 'idle', 'loop': False,
                    'frames': [entry for _, entry, _ in entries]}
        result = media.atlas(manifest, self.root, self.root / 'grid', columns=2, padding=4, extrude=3)
        with Image.open(self.root / 'grid/atlas.png') as sheet:
            for (source, _, _), record in zip(entries, result['frames']):
                self.assert_cell(sheet, source, record['region'], 4, 3)
            self.assertIsNone(sheet.crop((12, 14, 24, 28)).getbbox())
        self.assertEqual([frame['duration_ms'] for frame in result['frames']], [80] * 3)
        self.assertEqual(result['anchor'], [2, 6])

    def test_single_pixel_frame_and_repeated_exports_are_exact(self):
        source, frame, _ = self.frame('point', (1, 1), offset=1)
        manifest = {'schema_version': 1, 'canvas': [1, 1], 'anchor': [0, 0], 'clip': 'point', 'loop': True, 'frames': [frame]}
        for name in ('first', 'second'):
            result = media.atlas(manifest, self.root, self.root / name, padding=3, extrude=2)
            with Image.open(self.root / name / 'atlas.png') as sheet:
                self.assert_cell(sheet, source, result['frames'][0]['region'], 3, 2)
        self.assertEqual((self.root / 'first/atlas.png').read_bytes(), (self.root / 'second/atlas.png').read_bytes())


if __name__ == '__main__': unittest.main()
