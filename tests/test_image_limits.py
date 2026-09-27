"""Thread-safe decompression-bomb refusal without process-wide warnings state (#1061)."""
import io
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow.image_limits import open_bounded


def encoded_png(size):
    with Image.new('RGB', size, 'red') as image:
        with io.BytesIO() as out:
            image.save(out, format='PNG')
            return out.getvalue()


class ImageLimitsTests(unittest.TestCase):
    def test_refuses_between_one_and_two_times_the_limit_without_touching_warning_filters(self):
        raw = encoded_png((100, 100))
        with warnings.catch_warnings(record=True):
            snapshot = list(warnings.filters)
            with patch.object(Image, 'MAX_IMAGE_PIXELS', 6000):
                with self.assertRaises(Image.DecompressionBombError):
                    with open_bounded(io.BytesIO(raw)):
                        pass
            self.assertEqual(list(warnings.filters), snapshot)

    def test_accepts_an_image_within_the_limit(self):
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 6000):
            with open_bounded(io.BytesIO(encoded_png((10, 10)))) as image:
                self.assertEqual(image.size, (10, 10))
                image.load()

    def test_no_limit_when_max_image_pixels_is_none(self):
        with patch.object(Image, 'MAX_IMAGE_PIXELS', None):
            with open_bounded(io.BytesIO(encoded_png((100, 100)))) as image:
                self.assertEqual(image.size, (100, 100))
                image.load()

    def test_request_path_modules_hold_no_catch_warnings(self):
        for relative in ('app/asset_thumbs.py', 'app/native_exports.py',
                         'studio_workflow/depth_erasure.py', 'studio_workflow/pose_route_binding.py'):
            with self.subTest(module=relative):
                text = (ROOT / relative).read_text(encoding='utf-8')
                self.assertNotIn('catch_warnings', text)
                self.assertIn('open_bounded', text)

    def test_game_asset_media_decoders_refuse_by_pixel_budget_without_warning_filters(self):
        # The Studio's native exports call these through media.atlas/media.ora on request threads.
        sys.path.insert(0, str(ROOT / 'scripts'))
        import game_asset_media as media
        self.assertNotIn('catch_warnings', (ROOT / 'scripts/game_asset_media.py').read_text(encoding='utf-8'))
        with Image.new('RGBA', (100, 100)) as picture, io.BytesIO() as out:
            picture.save(out, format='PNG'); raw = out.getvalue()
        with warnings.catch_warnings(record=True):
            snapshot = list(warnings.filters)
            # 10,000 px sits between Pillow's warning (6,000) and error (12,000) lines, under the 16 MP budget.
            with patch.object(Image, 'MAX_IMAGE_PIXELS', 6000):
                with self.assertRaisesRegex(ValueError, 'exceeds pixel budget'): media.decode_png(raw)
            self.assertEqual(list(warnings.filters), snapshot)
        self.assertEqual(media.decode_png(raw).size, (100, 100))


if __name__ == '__main__': unittest.main()
