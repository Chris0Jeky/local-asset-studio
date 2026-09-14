"""Actual raster and preservation contracts; no model or native adapter involved."""
import copy
from fractions import Fraction
import unittest

from PIL import Image
from scripts import repair_pixel_transforms as rp


def spec(size=(16, 16), **changes):
    value = {'version': 'straight-rgba-bilinear-v1', 'box': [0, 0, *size],
             'scale': [1, 1], 'padding': [0, 0, 0, 0], 'alignment': 1}
    value.update(changes)
    return value


def source(size=(16, 16)):
    image = Image.new('RGBA', size)
    image.putdata([((x * 37 + y * 3) % 256, (y * 53 + x) % 256,
                    (x * 17 + y * 29) % 256, (0, 1, 127, 255)[(x + y) % 4])
                   for y in range(size[1]) for x in range(size[0])])
    return image


def masks(size=(16, 16)):
    write = Image.new('L', size, 0)
    for y in range(6, 10):
        for x in range(6, 10): write.putpixel((x, y), 255)
    return write, Image.new('L', size, 0)


class Geometry(unittest.TestCase):
    def test_odd_rounding_and_independent_pixel_centre_mapping(self):
        request = spec(box=[3, 5, 10, 14], scale=[3, 2], padding=[2, 1, 3, 1])
        before = copy.deepcopy(request)
        geometry = rp.compile_transform([20, 20], request)
        self.assertEqual([11, 14], geometry['resized_size'])
        self.assertEqual([16, 16], geometry['work_size'])
        self.assertEqual([11, 7], geometry['mapping']['x']['scale'])
        self.assertEqual([14, 9], geometry['mapping']['y']['scale'])
        for axis, start, end, scale, pad in (('x', 3, 10, Fraction(11, 7), 2),
                                            ('y', 5, 14, Fraction(14, 9), 1)):
            actual = geometry['mapping'][axis]
            for centre in (start, end - 1, Fraction(2 * start - 1, 2), Fraction(2 * end - 1, 2)):
                expected = (centre - start + Fraction(1, 2)) * scale - Fraction(1, 2) + pad
                mapped = centre * Fraction(*actual['scale']) + Fraction(*actual['offset'])
                self.assertEqual(expected, mapped)
                self.assertEqual(centre, (mapped - Fraction(*actual['offset'])) / Fraction(*actual['scale']))
        self.assertFalse(geometry['resampling_performed'])
        self.assertEqual(before, request)

    def test_invalid_or_unbounded_transforms_fail_before_raster_allocation(self):
        invalid = [dict(scale=[True, 1]), dict(scale=[1.0, 1]), dict(scale=[0, 1]),
                   dict(scale=[1, 4096]), dict(scale=[5, 1]), dict(box=[0, 0, 17, 16]),
                   dict(padding=[0, -1, 0, 0]), dict(padding=[65536] * 4),
                   dict(alignment=True), dict(version='unknown'), dict(feather=1)]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                rp.compile_transform([16, 16], spec(**change))


class Raster(unittest.TestCase):
    def test_straight_channels_have_an_independent_bilinear_oracle(self):
        inner = Image.new('RGBA', (2, 2))
        inner.putdata([(0, 0, 0, 0), (120, 0, 240, 0),
                       (0, 120, 120, 120), (120, 120, 0, 240)])
        original = Image.new('RGBA', (8, 8)); original.paste(inner, (3, 3))
        write = Image.new('L', (8, 8)); write.putpixel((3, 3), 255)
        prepared = rp.prepare_pixels(original, write, Image.new('L', (8, 8)),
                                     spec((8, 8), box=[3, 3, 5, 5], scale=[3, 2]))
        expected = [(0, 0, 0, 0), (60, 0, 120, 0), (120, 0, 240, 0),
                    (0, 60, 60, 60), (60, 60, 90, 90), (120, 60, 120, 120),
                    (0, 120, 120, 120), (60, 120, 60, 180), (120, 120, 0, 240)]
        self.assertEqual(bytes(channel for pixel in expected for channel in pixel),
                         prepared['images']['context'].tobytes())
        self.assertTrue(prepared['geometry']['resampling_performed'])

    def test_asymmetric_padding_is_explicit_and_never_writable(self):
        original = source((20, 20)); write, protect = masks((20, 20))
        request = spec(box=[3, 5, 10, 14], scale=[3, 2], padding=[2, 1, 3, 1])
        prepared = rp.prepare_pixels(original, write, protect, request)
        for name in ('context', 'work_write', 'work_protect'):
            self.assertEqual((16, 16), prepared['images'][name].size)
        for y in range(16):
            for x in range(16):
                if not (2 <= x < 13 and 1 <= y < 15):
                    self.assertEqual(0, prepared['images']['work_write'].getpixel((x, y)))
                    self.assertEqual((0, 0, 0, 0), prepared['images']['context'].getpixel((x, y)))

    def test_effective_coverage_includes_resampling_support(self):
        original = source(); write, protect = masks()
        prepared = rp.prepare_pixels(original, write, protect, spec(scale=[1, 2]))
        effective = prepared['images']['effective_write']
        self.assertTrue(any(a == 0 and b > 0 for a, b in zip(write.tobytes(), effective.tobytes())))
        protect.putpixel((4, 6), 255)
        with self.assertRaisesRegex(ValueError, '[Pp]rotect'):
            rp.prepare_pixels(original, write, protect, spec(scale=[1, 2]))

    def test_thin_protection_survives_downsampling(self):
        original = source((32, 32)); write, protect = masks((32, 32))
        for y in range(32): protect.putpixel((25, y), 255)
        prepared = rp.prepare_pixels(original, write, protect, spec((32, 32), scale=[1, 4]))
        projected = prepared['images']['work_protect']
        self.assertIsNotNone(projected.getbbox())
        for y in range(8): self.assertEqual(255, projected.getpixel((6, y)))

    def test_partial_coverage_and_invisible_source_rgb_remain_authoritative(self):
        original = source(); write, protect = masks()
        for index, value in enumerate((1, 127, 128, 254)): write.putpixel((6 + index, 6), value)
        protect.putpixel((1, 1), 255)
        before = [im.tobytes() for im in (original, write, protect)]
        request = spec(scale=[3, 2], padding=[1, 2, 3, 2])
        prepared = rp.prepare_pixels(original, write, protect, request)
        candidate = Image.new('RGBA', prepared['images']['context'].size, (250, 240, 230, 255))
        rendered = rp.render_pixels(original, write, protect, request, candidate)
        result, coverage = rendered['result'], rendered['effective_write']
        for y in range(16):
            for x in range(16):
                if coverage.getpixel((x, y)) == 0 or protect.getpixel((x, y)):
                    self.assertEqual(original.getpixel((x, y)), result.getpixel((x, y)))
        self.assertEqual(0, rendered['outside_changes'])
        self.assertEqual(0, rendered['protected_changes'])
        self.assertFalse(rendered['no_op'])
        self.assertEqual(before, [im.tobytes() for im in (original, write, protect)])

    def test_resampled_context_and_padding_only_changes_are_exact_no_ops(self):
        original = source(); write, protect = masks()
        request = spec(scale=[1, 2], padding=[1, 2, 3, 2])
        context = rp.prepare_pixels(original, write, protect, request)['images']['context']
        for padding_changed in (False, True):
            candidate = context.copy()
            if padding_changed: candidate.putpixel((0, 0), (255, 127, 63, 31))
            rendered = rp.render_pixels(original, write, protect, request, candidate)
            self.assertEqual(original.tobytes(), rendered['result'].tobytes())
            self.assertTrue(rendered['no_op'])
            self.assertIsNone(rendered['delta'].getbbox())

    def test_wrong_mask_candidate_and_colour_are_refused(self):
        original = source(); write, protect = masks(); request = spec()
        for candidate in (Image.new('RGBA', (15, 16)), Image.new('L', (16, 16))):
            with self.assertRaises(ValueError): rp.render_pixels(original, write, protect, request, candidate)
        candidate = source(); candidate.info['icc_profile'] = b'another-profile'
        with self.assertRaises(ValueError): rp.render_pixels(original, write, protect, request, candidate)
        for invalid in (Image.new('RGBA', (16, 16)), Image.new('L', (15, 16))):
            with self.assertRaises(ValueError): rp.prepare_pixels(original, invalid, protect, request)
        protect.putpixel((1, 1), 1)
        with self.assertRaises(ValueError): rp.prepare_pixels(original, write, protect, request)


if __name__ == '__main__':
    unittest.main()
