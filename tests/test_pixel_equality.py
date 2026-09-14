"""Exact two-stage bundle equality with bounded byte conversions and lifetime."""
from contextlib import closing
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tests' / 'fixtures'))
from scripts import pixel_diff
from bundle_equality_baseline import same_pixels as legacy_same


def same_pixels(a, b):
    # The initial red run exercises the frozen original predicate until the new
    # implementation exists, rather than failing solely because an import lacks it.
    return getattr(pixel_diff, 'same_pixels', legacy_same)(a, b)


class PixelEqualityTests(unittest.TestCase):
    def assert_parity(self, a, b):
        before = (a.tobytes(), b.tobytes(), dict(a.info), dict(b.info))
        self.assertIs(same_pixels(a, b), legacy_same(a, b))
        self.assertEqual(before, (a.tobytes(), b.tobytes(), dict(a.info), dict(b.info)))

    def test_no_full_image_byte_conversion(self):
        calls=[]; original=Image.Image.tobytes
        def observed(image, *args, **kwargs):
            calls.append(image.size); return original(image, *args, **kwargs)
        with closing(Image.new('RGBA',(1025,1027),(17,31,47,0))) as a, closing(a.copy()) as b:
            with patch.object(Image.Image, 'tobytes', observed): self.assertTrue(same_pixels(a,b))
        self.assertTrue(calls)
        self.assertTrue(all(w<=512 and h<=512 for w,h in calls), calls)

    def test_different_mode_and_size_are_false_before_allocating(self):
        with closing(Image.new('RGB',(3,5))) as a, closing(Image.new('RGBA',(3,5))) as b:
            with patch.object(Image.Image, 'crop', side_effect=AssertionError('no crop')):
                self.assertFalse(same_pixels(a,b))
        with closing(Image.new('RGB',(3,5))) as a, closing(Image.new('RGB',(5,3))) as b:
            self.assertFalse(same_pixels(a,b))

    def test_all_supported_modes_equal_and_different(self):
        for mode in ('1','L','LA','P','RGB','RGBA','I','F','CMYK'):
            with self.subTest(mode=mode):
                with closing(Image.new('RGB',(513,7),(20,80,160))) as rgb:
                    rgb.putpixel((512,6),(190,90,10))
                    with closing(rgb.convert(mode)) as a, closing(a.copy()) as b:
                        self.assert_parity(a,b)
                        b.putpixel((0,0),a.getpixel((512,6))); self.assert_parity(a,b)

    def test_palette_bytes_equal_but_colours_differ(self):
        with closing(Image.new('P',(513,7))) as a, closing(a.copy()) as b:
            a.putpalette([1,2,3]+[0]*765); b.putpalette([2,2,3]+[0]*765)
            self.assertEqual(a.tobytes(),b.tobytes())
            self.assertFalse(same_pixels(a,b)); self.assert_parity(a,b)

    def test_raw_indices_differ_even_when_palette_colours_match(self):
        with closing(Image.new('P',(513,7))) as a, closing(a.copy()) as b:
            palette=[1,2,3]*256; a.putpalette(palette); b.putpalette(palette)
            b.putpixel((512,6),1)
            with closing(a.convert('RGBA')) as ar, closing(b.convert('RGBA')) as br:
                self.assertEqual(ar.tobytes(),br.tobytes())
            self.assertFalse(same_pixels(a,b)); self.assert_parity(a,b)

    def test_rgb_trns_difference_is_not_lost(self):
        with closing(Image.new('RGB',(513,7),(17,31,47))) as a, closing(a.copy()) as b:
            a.info['transparency']=(17,31,47)
            self.assertEqual(a.tobytes(),b.tobytes())
            self.assertFalse(same_pixels(a,b)); self.assert_parity(a,b)
            b.info['transparency']=(17,31,47); self.assertTrue(same_pixels(a,b))

    def test_palette_alpha_difference_is_not_lost(self):
        with closing(Image.new('P',(513,7))) as a, closing(a.copy()) as b:
            a.info['transparency']=bytes([0]+[255]*255)
            b.info['transparency']=bytes([127]+[255]*255)
            self.assertFalse(same_pixels(a,b)); self.assert_parity(a,b)

    def test_invisible_rgb_and_alpha_each_cause_inequality(self):
        for channel in range(4):
            with closing(Image.new('RGBA',(1025,3),(1,2,3,0))) as a, closing(a.copy()) as b:
                value=list(b.getpixel((1024,2))); value[channel]^=1; b.putpixel((1024,2),tuple(value))
                self.assertFalse(same_pixels(a,b)); self.assert_parity(a,b)

    def test_odd_one_bit_widths_and_empty_images_match(self):
        for size in ((1,1),(513,1),(1,1025),(1025,7),(0,0),(0,7),(7,0)):
            with self.subTest(size=size):
                with closing(Image.new('1',size,1)) as a, closing(a.copy()) as b:
                    self.assert_parity(a,b)
                    if size[0] and size[1]:
                        b.putpixel((size[0]-1,size[1]-1),0); self.assert_parity(a,b)

    def test_fixed_random_modes_match_original(self):
        rng=random.Random(370)
        for mode,bpp in (('L',1),('LA',2),('RGB',3),('RGBA',4)):
            for width in (17,511,513):
                with closing(Image.frombytes(mode,(width,3),rng.randbytes(width*3*bpp))) as a, closing(a.copy()) as b:
                    self.assert_parity(a,b)
                    b.putpixel((width-1,2),a.getpixel((0,0))); self.assert_parity(a,b)

    def test_icc_is_still_caller_owned_not_a_pixel_change(self):
        with closing(Image.new('RGBA',(3,3))) as a, closing(a.copy()) as b:
            a.info['icc_profile']=b'profile-a'; b.info['icc_profile']=b'profile-b'
            self.assertTrue(same_pixels(a,b)); self.assert_parity(a,b)

    def test_early_exit_does_not_visit_later_tiles(self):
        calls=[]; original=Image.Image.crop
        def observed(image,box):
            calls.append(box); return original(image,box)
        with closing(Image.new('RGBA',(1025,7))) as a, closing(a.copy()) as b:
            b.putpixel((0,0),(1,0,0,0))
            with patch.object(Image.Image,'crop',observed): self.assertFalse(same_pixels(a,b))
        self.assertEqual(calls,[(0,0,512,7)]*2)

    def test_success_and_early_exit_close_all_scratch(self):
        for changed in (False,True):
            with closing(Image.new('RGBA',(513,7))) as a, closing(a.copy()) as b:
                if changed:b.putpixel((0,0),(1,0,0,0))
                created=[];closed=[];new=Image.Image._new;close=Image.Image.close
                def track_new(image,core):
                    result=new(image,core);created.append(result);return result
                def track_close(image):closed.append(id(image));return close(image)
                with patch.object(Image.Image,'_new',track_new),patch.object(Image.Image,'close',track_close):
                    self.assertIs(same_pixels(a,b),not changed)
                self.assertTrue({id(im) for im in created}.issubset(set(closed)))
                self.assertNotIn(id(a),closed);self.assertNotIn(id(b),closed)

    def test_failure_closes_scratch_without_closing_callers(self):
        with closing(Image.new('RGBA',(513,7))) as a, closing(a.copy()) as b:
            created=[];closed=[];new=Image.Image._new;close=Image.Image.close
            def track_new(image,core):
                result=new(image,core);created.append(result);return result
            def track_close(image):closed.append(id(image));return close(image)
            with patch.object(Image.Image,'_new',track_new),patch.object(Image.Image,'close',track_close):
                with patch.object(Image.Image,'tobytes',side_effect=MemoryError('injected')):
                    with self.assertRaises(MemoryError):same_pixels(a,b)
            self.assertTrue(created)
            self.assertTrue({id(im) for im in created}.issubset(set(closed)))
            self.assertNotIn(id(a),closed);self.assertNotIn(id(b),closed)
            self.assertEqual(a.getpixel((0,0)),(0,0,0,0))


if __name__=='__main__':unittest.main()
