"""Exercise the actual protected-edit entry point, not only the new helper."""
from contextlib import closing
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.character_edit_pixels import changed_mask


class CharacterEditCopyIntegrationTests(unittest.TestCase):
    def test_public_entry_point_uses_bounded_all_channel_comparison(self):
        with closing(Image.new('RGBA', (1025, 7), (17, 31, 47, 0))) as a, closing(a.copy()) as b:
            b.putpixel((512, 3), (18, 31, 47, 0))
            with patch.object(ImageChops, 'difference', wraps=ImageChops.difference) as difference:
                with closing(changed_mask(a, b)) as result:
                    self.assertEqual(result.getbbox(), (512, 3, 513, 4))
                    self.assertEqual(result.histogram()[255], 1)
            self.assertGreater(len(difference.call_args_list), 1)
            self.assertTrue(all(call.args[0].width <= 512 and call.args[0].height <= 512
                                for call in difference.call_args_list))
            self.assertEqual(a.getpixel((512, 3)), (17, 31, 47, 0))

    def test_public_dimension_error_is_unchanged(self):
        with closing(Image.new('RGB', (7, 5))) as a, closing(Image.new('RGB', (5, 7))) as b:
            with self.assertRaisesRegex(ValueError, 'Cannot compare differing dimensions'): changed_mask(a, b)


if __name__ == '__main__': unittest.main()
