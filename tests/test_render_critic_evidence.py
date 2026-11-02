"""Owned fixtures for reference-comparison evidence, without a Blender or model server."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_critic as rc


def png16(path, value, colour_type=2):
    """Real 16-bit RGB/RGBA PNG, including valid CRCs; Pillow exposes RGB as 8-bit."""
    channels = 3 if colour_type == 2 else 4
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    scan = b'\0' + struct.pack('>H', value) * (8 * channels)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 16, colour_type, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(scan * 8)) + chunk(b'IEND', b''))


def tiff16(path, value):
    """Uncompressed little-endian RGB16 TIFF; no optional TIFF-writing dependency."""
    count = 10
    bits_offset = 8 + 2 + count * 12 + 4
    pixels_offset = bits_offset + 6
    entries = [(256, 4, 1, 8), (257, 4, 1, 8), (258, 3, 3, bits_offset),
               (259, 3, 1, 1), (262, 3, 1, 2), (273, 4, 1, pixels_offset),
               (277, 3, 1, 3), (278, 4, 1, 8), (279, 4, 1, 8 * 8 * 3 * 2), (284, 3, 1, 1)]
    header = b'II' + struct.pack('<HIH', 42, 8, count)
    table = b''.join(struct.pack('<HHII', *e) for e in entries) + struct.pack('<I', 0)
    path.write_bytes(header + table + struct.pack('<HHH', 16, 16, 16) + struct.pack('<H', value) * (8 * 8 * 3))


class ReferenceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ref = self.root / 'reference'; self.ref.mkdir()
        self.cand = self.root / 'candidate'; self.cand.mkdir()
        # Any inference request in these tests is a failure, including fallback on missing evidence.
        network = patch.object(rc.urllib.request, 'urlopen', side_effect=AssertionError('unexpected model request'))
        self.net = network.start(); self.addCleanup(network.stop)

    def image(self, folder, name='view_front.png', mode='RGBA', value=(80, 90, 100, 255), size=(8, 8)):
        p = folder / name; Image.new(mode, size, value).save(p); return p

    def pair(self):
        return self.image(self.cand), self.image(self.ref)

    def check(self, images, reference):
        return rc.check(images, reference=reference, diff_only=True)

    def assert_incomplete(self, result):
        self.assertIn('error', result)
        self.assertIs(result.get('evidence_complete'), False)
        self.assertIs(result['changed'], True)  # conservative compatibility for existing bool consumers
        self.assertIsNone(result['model'])
        self.net.assert_not_called()

    def test_unchanged_control_remains_quiet(self):
        c, r = self.pair(); result = self.check([c], [r])
        self.assertFalse(result['changed']); self.net.assert_not_called()

    def test_alpha_only_loss_is_not_cleared(self):
        c = self.image(self.cand, value=(80, 90, 100, 0)); r = self.image(self.ref)
        result = self.check([c], [r])
        self.assertTrue(result['changed'])
        self.assertEqual(result['pixel_diff']['front']['changed_px'], 64)

    def test_palette_transparency_is_part_of_evidence(self):
        c, r = self.pair()
        im = Image.new('P', (8, 8), 1); im.putpalette([0, 0, 0, 80, 90, 100] + [0] * 762)
        im.save(r, transparency=0); im.save(c, transparency=1)
        self.assertTrue(self.check([c], [r])['changed'])

    def test_reference_only_view_cannot_disappear(self):
        c, r = self.pair(); back = self.image(self.ref, 'view_back.png')
        self.assert_incomplete(self.check([c], [r, back]))

    def test_candidate_only_view_is_incomplete_not_a_defect_label(self):
        c, r = self.pair(); back = self.image(self.cand, 'view_back.png')
        self.assert_incomplete(self.check([c, back], [r]))

    def test_duplicate_reference_labels_are_not_last_writer_wins(self):
        c, r = self.pair(); alias = self.image(self.ref, 'front.png', value=(255, 0, 0, 255))
        self.assert_incomplete(self.check([c], [alias, r]))

    def test_duplicate_candidate_labels_are_not_overwritten(self):
        c, r = self.pair(); alias = self.image(self.cand, 'front.png', value=(255, 0, 0, 255))
        self.assert_incomplete(self.check([alias, c], [r]))

    def test_repeated_same_path_is_not_multiple_views(self):
        c, r = self.pair(); self.assert_incomplete(self.check([c, c], [r, r]))

    def test_frame_suffixes_remain_distinct(self):
        self.assertNotEqual(rc._label('view_front_001.png'), rc._label('view_front_002.png'))

    def test_pairs_are_matched_by_label_not_list_order(self):
        c, r = self.pair()
        cb = self.image(self.cand, 'view_back.png', value=(12, 34, 56, 255))
        rb = self.image(self.ref, 'view_back.png', value=(12, 34, 56, 255))
        result = self.check([c, cb], [rb, r]); self.assertFalse(result['changed'])

    def test_observed_sizes_and_policy_are_retained(self):
        c, r = self.pair(); result = self.check([c], [r])
        self.assertEqual(result.get('view_sizes'), {'front': {'candidate': [8, 8], 'reference': [8, 8]}})
        self.assertEqual(result.get('pixel_policy'), {'level': 8, 'min_pixels': 20, 'channels': 'decoded-RGBA8',
                                                     'colour_management': 'none'})
        self.assertIs(result.get('evidence_complete'), True)

    def test_png_16bit_rgb_cannot_silently_lose_low_bits(self):
        c, r = self.cand / 'front.png', self.ref / 'front.png'
        png16(c, 0x4001); png16(r, 0x4000)
        with Image.open(c) as image: self.assertEqual(image.mode, 'RGB')
        self.assert_incomplete(self.check([c], [r]))

    def test_png_16bit_rgba_is_also_refused(self):
        c, r = self.cand / 'front.png', self.ref / 'front.png'
        png16(c, 0x4001, 6); png16(r, 0x4000, 6)
        self.assert_incomplete(self.check([c], [r]))

    def test_integer_precision_images_are_not_clamped(self):
        c = self.image(self.cand, 'front.tiff', 'I', 1000)
        r = self.image(self.ref, 'front.tiff', 'I', 1001)
        self.assert_incomplete(self.check([c], [r]))

    def test_float_precision_images_are_not_clamped(self):
        c = self.image(self.cand, 'front.tiff', 'F', 0.4)
        r = self.image(self.ref, 'front.tiff', 'F', 0.5)
        self.assert_incomplete(self.check([c], [r]))

    def test_animated_image_is_not_just_its_first_frame(self):
        c, r = self.pair()
        im = Image.new('RGBA', (8, 8), (80, 90, 100, 255))
        im.save(c, save_all=True, append_images=[Image.new('RGBA', (8, 8), (255, 0, 0, 255))], duration=10)
        self.assert_incomplete(self.check([c], [r]))

    def test_rgb16_tiff_cannot_hide_behind_rgb_mode(self):
        c, r = self.cand / 'front.tiff', self.ref / 'front.tiff'
        tiff16(c, 0x4001); tiff16(r, 0x4000)
        with Image.open(c) as image:
            self.assertEqual(image.mode, 'RGB')
            self.assertEqual(tuple(image.tag_v2[258]), (16, 16, 16))
        self.assert_incomplete(self.check([c], [r]))

    def test_unknown_container_precision_is_not_inferred_from_mode(self):
        c, r = self.cand / 'front.ppm', self.ref / 'front.ppm'
        for p, value in ((c, 0x4001), (r, 0x4000)):
            p.write_bytes(b'P6\n8 8\n65535\n' + struct.pack('>H', value) * (8 * 8 * 3))
        with Image.open(c) as image: self.assertEqual(image.mode, 'RGB')
        self.assert_incomplete(self.check([c], [r]))

    def test_eight_bit_tiff_remains_usable(self):
        c = self.image(self.cand, 'front.tiff'); r = self.image(self.ref, 'front.tiff')
        self.assertFalse(self.check([c], [r])['changed'])

    def test_diff_only_without_reference_never_calls_model(self):
        c, _ = self.pair()
        with self.assertRaisesRegex(ValueError, 'reference'): rc.check([c], diff_only=True)
        self.net.assert_not_called()

    def test_invalid_pixel_level_is_rejected_before_read(self):
        for level in (-1, 256, 0.5, True, float('nan')):
            with self.subTest(level=level), self.assertRaises(ValueError):
                rc.pixel_diff(['not-there.png'], ['not-there.png'], level=level)

    def test_incomplete_reference_cannot_reach_model_even_when_requested(self):
        c, r = self.pair(); rb = self.image(self.ref, 'view_back.png')
        self.assert_incomplete(rc.check([c], reference=[r, rb]))

    def test_error_rows_are_not_scored_as_clean_or_detected(self):
        c, r = self.pair(); rb = self.image(self.ref, 'view_back.png')
        result = dict(self.check([c], [r, rb]), truth={'category': 'clean'}, id='incomplete')
        summary = rc.score([result]); self.assertEqual(summary['errors'], 1)
        self.assertEqual(sum(summary['detection'][k] for k in ('tp', 'fp', 'tn', 'fn')), 0)

    def test_incomplete_direct_pixel_diff_is_rejected(self):
        c, r = self.pair(); rb = self.image(self.ref, 'view_back.png')
        with self.assertRaises(ValueError): rc.pixel_diff([c], [r, rb])


if __name__ == '__main__': unittest.main()
