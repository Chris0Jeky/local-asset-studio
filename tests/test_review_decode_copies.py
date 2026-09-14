"""Exact decode parity and a causal guard against the no-op orientation copy."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps, PngImagePlugin, features
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import review_media


def encoded(mode='RGBA', orientation=None, fmt='PNG', transparency=None):
    with Image.new('RGBA', (7, 5)) as rgba:
        rgba.putdata([(i * 19 % 256, i * 37 % 256, i * 61 % 256, (0, 127, 255)[i % 3])
                      for i in range(35)])
        with rgba.convert(mode) as image:
            options = {}
            if orientation is not None:
                exif = Image.Exif(); exif[274] = orientation
                options['exif'] = exif
            if transparency is not None: options['transparency'] = transparency
            if fmt == 'PNG':
                metadata = PngImagePlugin.PngInfo()
                metadata.add_text('prompt', 'must not appear in blind preview')
                options['pnginfo'] = metadata
                options['icc_profile'] = b'profile-not-colour-managed'
            buffer = io.BytesIO(); image.save(buffer, format=fmt, **options)
            return buffer.getvalue()


def legacy_decode(data):
    """Pre-optimisation successful decode path, including transformation metadata."""
    with Image.open(io.BytesIO(data), formats=('PNG', 'JPEG', 'WEBP')) as source:
        orientation = source.getexif().get(274, 1); size = list(source.size)
        with ImageOps.exif_transpose(source) as oriented:
            image = oriented.convert('RGBA')
        image.info.clear()
        return image, {'encoded_size': size, 'oriented_size': list(image.size),
                       'exif_orientation': orientation,
                       'colour': '8-bit review preview; embedded ICC profiles are not colour-managed'}


class ReviewDecodeCopiesTests(unittest.TestCase):
    def assert_parity(self, data):
        expected, old_transform = legacy_decode(data)
        actual, new_transform = review_media.decode(data)
        try:
            self.assertEqual(actual.mode, 'RGBA')
            self.assertEqual(actual.size, expected.size)
            self.assertEqual(actual.tobytes(), expected.tobytes())
            self.assertEqual(new_transform, old_transform)
            self.assertEqual(actual.info, {})
        finally: expected.close(); actual.close()

    def test_no_op_orientation_avoids_transpose_copy(self):
        for orientation in (None, 0, 1, 9, 65535):
            with self.subTest(orientation=orientation):
                data = encoded(orientation=orientation)
                with patch.object(ImageOps, 'exif_transpose', wraps=ImageOps.exif_transpose) as transpose:
                    image, _ = review_media.decode(data)
                    try: self.assertEqual(transpose.call_count, 0)
                    finally: image.close()

    def test_transposing_orientations_still_use_real_transpose(self):
        for orientation in range(2, 9):
            with self.subTest(orientation=orientation):
                data = encoded(orientation=orientation)
                with patch.object(ImageOps, 'exif_transpose', wraps=ImageOps.exif_transpose) as transpose:
                    image, _ = review_media.decode(data)
                    try: self.assertEqual(transpose.call_count, 1)
                    finally: image.close()
                self.assert_parity(data)

    def test_supported_modes_and_orientations_match_original(self):
        for mode in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA'):
            for orientation in (None, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                with self.subTest(mode=mode, orientation=orientation):
                    self.assert_parity(encoded(mode, orientation))

    def test_rgb_and_palette_transparency_match_original(self):
        for mode, transparency in (('RGB', (0, 0, 0)), ('P', bytes([0, 127] + [255] * 254))):
            for orientation in (None, 1, 6):
                with self.subTest(mode=mode, orientation=orientation):
                    self.assert_parity(encoded(mode, orientation, transparency=transparency))

    def test_hidden_rgb_is_not_discarded(self):
        image, _ = review_media.decode(encoded())
        try: self.assertEqual(image.getpixel((3, 0)), (57, 111, 183, 0))
        finally: image.close()

    def test_jpeg_parity(self):
        for orientation in (None, 1, 6, 8): self.assert_parity(encoded('RGB', orientation, 'JPEG'))

    @unittest.skipUnless(features.check('webp'), 'Pillow has no WebP codec')
    def test_webp_parity(self):
        for orientation in (None, 1, 6, 8): self.assert_parity(encoded('RGBA', orientation, 'WEBP'))

    def test_results_survive_source_close_and_are_independent(self):
        data = encoded(); before = bytes(data)
        a, _ = review_media.decode(data); b, _ = review_media.decode(data)
        try:
            original = b.tobytes(); a.putpixel((0, 0), (1, 2, 3, 4))
            self.assertEqual(b.tobytes(), original)
            self.assertEqual(data, before)
        finally: a.close(); b.close()

    def test_pixel_budget_refusal_remains(self):
        with patch.object(review_media, 'MAX_PIXELS', 34):
            with self.assertRaisesRegex(ValueError, 'decode budget'): review_media.decode(encoded())

    def test_unsupported_mode_remains_refused(self):
        with Image.new('I;16', (7, 5)) as image:
            buffer = io.BytesIO(); image.save(buffer, format='PNG')
        with self.assertRaisesRegex(ValueError, '8-bit'): review_media.decode(buffer.getvalue())

    def test_animated_png_remains_refused(self):
        with Image.new('RGBA', (7, 5), 'red') as a, Image.new('RGBA', (7, 5), 'blue') as b:
            buffer = io.BytesIO(); a.save(buffer, format='PNG', save_all=True, append_images=[b], duration=100)
        with self.assertRaisesRegex(ValueError, 'still images'): review_media.decode(buffer.getvalue())

    def test_corrupt_and_truncated_data_remain_refused(self):
        for data in (b'', b'not an image', encoded()[:40]):
            with self.subTest(data=data):
                with self.assertRaises(ValueError): review_media.decode(data)


if __name__ == '__main__': unittest.main()
