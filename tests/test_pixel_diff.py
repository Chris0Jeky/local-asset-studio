"""Tiled comparison must preserve every RGBA channel and bound native scratch."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.pixel_diff import changed_mask


def legacy_mask(a, b):
    # The old full-image algorithm, with explicit cleanup only for the test oracle.
    with a.convert('RGBA') as left, b.convert('RGBA') as right:
        with ImageChops.difference(left, right) as diff:
            channels = diff.split(); maximum = Image.new('L', a.size, 0)
            try:
                for channel in channels:
                    newer = ImageChops.lighter(maximum, channel)
                    maximum.close(); maximum = newer
                return maximum.point(lambda value: 255 if value else 0)
            finally:
                maximum.close()
                for channel in channels: channel.close()


class PixelDiffTests(unittest.TestCase):
    def assert_parity(self, a, b):
        before = (a.tobytes(), b.tobytes(), dict(a.info), dict(b.info))
        with legacy_mask(a, b) as expected, changed_mask(a, b) as actual:
            self.assertEqual(actual.mode, 'L')
            self.assertEqual(actual.size, a.size)
            self.assertEqual(actual.tobytes(), expected.tobytes())
            self.assertEqual(sum(actual.histogram()[1:255]), 0)
        self.assertEqual((a.tobytes(), b.tobytes(), dict(a.info), dict(b.info)), before)

    def test_native_difference_is_bounded_in_both_dimensions(self):
        with Image.new('RGBA', (1025, 1027)) as a, a.copy() as b:
            with patch.object(ImageChops, 'difference', wraps=ImageChops.difference) as difference:
                with changed_mask(a, b) as result:
                    self.assertEqual(result.getbbox(), None)
            self.assertGreater(len(difference.call_args_list), 0)
            self.assertTrue(all(call.args[0].width <= 512 and call.args[0].height <= 512
                                for call in difference.call_args_list))

    def test_every_channel_including_invisible_rgb_is_detected(self):
        for alpha in (0, 1, 127, 255):
            for channel in range(4):
                with self.subTest(alpha=alpha, channel=channel):
                    with Image.new('RGBA', (7, 5), (17, 31, 47, alpha)) as a, a.copy() as b:
                        pixel = list(b.getpixel((3, 2))); pixel[channel] ^= 1
                        b.putpixel((3, 2), tuple(pixel))
                        self.assert_parity(a, b)
                        with changed_mask(a, b) as result:
                            self.assertEqual(result.histogram()[255], 1)
                            self.assertEqual(result.getpixel((3, 2)), 255)

    def test_odd_wide_tall_and_tile_boundary_changes(self):
        for size in ((1, 1537), (1537, 1), (513, 511), (511, 513), (1025, 1027), (1, 1)):
            with self.subTest(size=size):
                with Image.new('RGBA', size, (9, 8, 7, 0)) as a, a.copy() as b:
                    for x in {0, min(511, size[0]-1), min(512, size[0]-1), size[0]-1}:
                        for y in {0, min(511, size[1]-1), min(512, size[1]-1), size[1]-1}:
                            b.putpixel((x, y), (10, 8, 7, 0))
                    self.assert_parity(a, b)

    def test_modes_match_original_conversion(self):
        for mode in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA', 'CMYK', 'I', 'F'):
            with self.subTest(mode=mode):
                with Image.new('RGB', (19, 13), (20, 80, 160)) as source:
                    source.putpixel((2, 3), (190, 90, 10))
                    with source.convert(mode) as a, a.copy() as b:
                        b.putpixel((3, 4), a.getpixel((2, 3)))
                        self.assert_parity(a, b)

    def test_mixed_modes_match_original(self):
        with Image.new('RGB', (513, 3), (17, 31, 47)) as a, a.convert('RGBA') as b:
            self.assert_parity(a, b)
            b.putpixel((512, 2), (17, 31, 47, 0)); self.assert_parity(a, b)

    def test_rgb_transparency_survives_tile_crop(self):
        with Image.new('RGB', (513, 7), (17, 31, 47)) as a, a.copy() as b:
            a.info['transparency'] = (17, 31, 47)
            self.assert_parity(a, b)
            with changed_mask(a, b) as result: self.assertEqual(result.histogram()[255], 513 * 7)

    def test_palette_colour_and_alpha_are_both_compared(self):
        with Image.new('P', (513, 5), 0) as a, a.copy() as b:
            a.putpalette([17, 31, 47] + [0, 0, 0] * 255)
            b.putpalette([18, 31, 47] + [0, 0, 0] * 255)
            a.info['transparency'] = bytes([0] + [255] * 255)
            b.info['transparency'] = bytes([0] + [255] * 255)
            self.assert_parity(a, b)
            with changed_mask(a, b) as result: self.assertEqual(result.histogram()[255], 513 * 5)

    def test_no_change_and_same_object(self):
        with Image.new('RGBA', (517, 515), (99, 12, 77, 0)) as source:
            self.assert_parity(source, source)
            with changed_mask(source, source) as result: self.assertIsNone(result.getbbox())

    def test_success_closes_scratch_but_keeps_output_and_callers_live(self):
        with Image.new('RGBA', (513, 7), (1, 2, 3, 0)) as a, a.copy() as b:
            created = []; closed = []
            original_new = Image.Image._new; original_close = Image.Image.close
            def track_new(image, core):
                result = original_new(image, core); created.append(result); return result
            def track_close(image):
                closed.append(id(image)); return original_close(image)
            with patch.object(Image.Image, '_new', track_new), patch.object(Image.Image, 'close', track_close):
                result = changed_mask(a, b)
                try:
                    self.assertEqual({id(image) for image in created} - set(closed), {id(result)})
                    self.assertIsNone(result.getbbox())
                    self.assertNotIn(id(a), closed); self.assertNotIn(id(b), closed)
                finally: result.close()

    def test_empty_dimensions_match_original(self):
        for size in ((0, 0), (0, 7), (7, 0)):
            with self.subTest(size=size):
                with Image.new('RGBA', size) as a, a.copy() as b: self.assert_parity(a, b)

    def test_dimensions_rejected_before_allocation(self):
        with Image.new('RGB', (7, 5)) as a, Image.new('RGB', (5, 7)) as b:
            with patch.object(Image, 'new', wraps=Image.new) as allocate:
                with self.assertRaisesRegex(ValueError, 'Cannot compare differing dimensions'): changed_mask(a, b)
                self.assertEqual(allocate.call_count, 0)

    def test_failures_close_all_owned_images_and_preserve_callers(self):
        operations = ((ImageChops, 'difference'), (ImageChops, 'lighter'),
                      (Image.Image, 'getchannel'), (Image.Image, 'point'), (Image.Image, 'paste'))
        for owner, name in operations:
            with self.subTest(operation=name):
                with Image.new('RGBA', (513, 7), (1, 2, 3, 0)) as a, a.copy() as b:
                    created = []; closed = []
                    original_new = Image.Image._new; original_close = Image.Image.close
                    def track_new(image, core):
                        result = original_new(image, core); created.append(result); return result
                    def track_close(image):
                        closed.append(id(image)); return original_close(image)
                    with patch.object(Image.Image, '_new', track_new), patch.object(Image.Image, 'close', track_close):
                        with patch.object(owner, name, side_effect=MemoryError('injected allocation failure')):
                            with self.assertRaisesRegex(MemoryError, 'injected'): changed_mask(a, b)
                    self.assertTrue(created)
                    self.assertTrue({id(image) for image in created}.issubset(set(closed)))
                    self.assertEqual(a.getpixel((0, 0)), (1, 2, 3, 0))
                    self.assertEqual(b.getpixel((0, 0)), (1, 2, 3, 0))


if __name__ == '__main__': unittest.main()
