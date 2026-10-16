"""Readability gate for the R2 motion preview: sustained motion and the declared sample count.

Synthetic decoded frame sequences drive the gate's own functions. A frozen-after-first-change clip and a
short clip must fail; a steadily moving clip with the declared 32 samples must pass.
"""
import importlib.util
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'docs/adaptive-studio/assets/production/20261013-v2-motion-readable-r2'
spec = importlib.util.spec_from_file_location('assert_readable_export', FOLDER / 'assert_readable_export.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
LAS = gate.REGIONS['las']


def frame(offset):
    im = Image.new('RGB', (320, 180), (0, 0, 0))
    ImageDraw.Draw(im).rectangle((220 + offset, 0, 227 + offset, 179), fill=(255, 255, 255))
    return im


def clip(offsets):
    return [frame(o) for o in offsets]


class ReadableMotionGate(unittest.TestCase):
    def test_declared_sample_count_comes_from_timeline(self):
        self.assertEqual(gate.expected_samples(), 32)  # TIMELINE.json: 8 s x 4 fps
        self.assertTrue(gate.sample_count_ok(32, 32))
        self.assertTrue(gate.sample_count_ok(31, 32))
        self.assertTrue(gate.sample_count_ok(33, 32))
        self.assertFalse(gate.sample_count_ok(30, 32))
        self.assertFalse(gate.sample_count_ok(24, 32))

    def test_steadily_moving_clip_passes(self):
        images = clip([(6 * i) % 54 for i in range(32)])
        self.assertTrue(gate.clip_passes(images, 32, LAS))

    def test_clip_frozen_after_first_change_fails(self):
        images = clip([min(6 * i, 18) for i in range(32)])  # moves for four samples, then holds still
        results = gate.region_results(images, LAS)
        self.assertFalse(gate.clip_passes(images, 32, LAS))
        for name in LAS:
            self.assertLess(results[name]['moving_pair_fraction'], gate.SUSTAINED_FRACTION, name)

    def test_all_still_clip_fails(self):
        self.assertFalse(gate.clip_passes(clip([0] * 32), 32, LAS))

    def test_short_clip_fails_even_when_moving(self):
        self.assertFalse(gate.clip_passes(clip([(6 * i) % 54 for i in range(24)]), 32, LAS))

    def test_long_clip_fails_the_exact_count(self):
        self.assertFalse(gate.clip_passes(clip([(6 * i) % 54 for i in range(40)]), 32, LAS))


if __name__ == '__main__':
    unittest.main()
