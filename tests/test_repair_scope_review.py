"""CPU image/mask contract tests; no ComfyUI, model or native application."""
import copy
from io import BytesIO
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageChops
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import repair_scope_review as review


def fixture():
    original = Image.new('RGBA', (23, 19), (91, 131, 170, 255))
    original.putpixel((0, 0), (12, 34, 56, 0))
    authored = Image.new('L', original.size, 0)
    authored.paste(255, (7, 7, 11, 10))
    effective = authored.copy(); effective.putpixel((6, 7), 64); effective.putpixel((7, 7), 128)
    effective.putpixel((10, 9), 0)
    protect = Image.new('L', original.size, 0); protect.paste(255, (15, 0, 23, 19))
    work = Image.new('L', (15, 14), 0); work.paste(128, (4, 5, 7, 8))
    work_protect = Image.new('L', work.size, 255); work_protect.paste(0, (1, 2, 12, 11))
    images = {'context': Image.new('RGBA', work.size, (10, 20, 30, 0)), 'work_write': work,
              'work_protect': work_protect, 'authored_write': authored,
              'effective_write': effective, 'source_protect': protect}
    geometry = {'context_box': [2, 3, 13, 12], 'source_size': [23, 19], 'work_size': [15, 14],
                'resized_size': [11, 9], 'padding_ltrb': [1, 2, 3, 3]}
    return original, images, geometry


class ScopeReviewTests(unittest.TestCase):
    def test_inverse_alpha_all_256_values_are_exact_after_png_roundtrip(self):
        mask = Image.frombytes('L', (256, 1), bytes(range(256)))
        exported = review.inverse_alpha(mask, Image.new('L', mask.size, 0))
        self.assertEqual(exported.mode, 'RGBA')
        with BytesIO() as stream:
            exported.save(stream, format='PNG'); stream.seek(0)
            with Image.open(stream) as decoded:
                # Comfy LoadImage MASK output: 1 - alpha/255.
                self.assertEqual(ImageChops.invert(decoded.getchannel('A')).tobytes(), mask.tobytes())
        self.assertEqual(exported.getpixel((0, 0)), (0, 0, 0, 255))
        self.assertEqual(exported.getpixel((255, 0)), (0, 0, 0, 0))

    def test_cutout_alpha_cannot_be_passed_as_write_mask(self):
        with self.assertRaises(ValueError): review.inverse_alpha(Image.new('RGBA', (5, 5)), Image.new('L', (5, 5)))

    def test_mask_profile_transparency_and_exif_are_not_reinterpreted(self):
        for key, value in [('icc_profile', b'profile'), ('transparency', 0), ('exif', b'bad')]:
            mask = Image.new('L', (5, 5)); mask.info[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): review.inverse_alpha(mask, Image.new('L', mask.size))

    def test_mask_dimensions_and_binary_protection_are_checked(self):
        with self.assertRaises(ValueError): review.inverse_alpha(Image.new('L', (5, 5)), Image.new('L', (6, 5)))
        with self.assertRaises(ValueError): review.inverse_alpha(Image.new('L', (5, 5)), Image.new('L', (5, 5), 127))

    def test_write_and_protection_overlap_rejected_not_subtracted(self):
        with self.assertRaises(ValueError): review.inverse_alpha(Image.new('L', (5, 5), 1), Image.new('L', (5, 5), 255))

    def test_transparency_of_context_does_not_change_exported_scope(self):
        original, images, geometry = fixture()
        _, summary = review.scope_views(original, images, geometry)
        exported = review.inverse_alpha(images['work_write'], images['work_protect'])
        self.assertEqual(exported.getchannel('A').getpixel((0, 0)), 255)
        self.assertEqual(exported.getchannel('A').getpixel((5, 6)), 127)
        self.assertEqual(summary['work']['support_pixels'], 9)

    def test_scope_comparison_counts_expansion_contraction_and_coverage(self):
        original, images, geometry = fixture()
        views, summary = review.scope_views(original, images, geometry)
        self.assertEqual(summary['authored']['support_pixels'], 12)
        self.assertEqual(summary['effective']['support_pixels'], 12)
        self.assertEqual(summary['effective']['fractional_pixels'], 2)
        self.assertEqual(summary['added_support_pixels'], 1)
        self.assertEqual(summary['removed_support_pixels'], 1)
        self.assertEqual(summary['coverage_changed_pixels'], 3)
        self.assertEqual(summary['protected_pixels'], 8 * 19)
        self.assertEqual(set(views), {'source-effective.png', 'scope-change.png', 'work-scope.png'})
        self.assertFalse(summary['semantic_approval']); self.assertFalse(summary['neural_inference'])

    def test_every_input_buffer_and_metadata_remain_unchanged(self):
        original, images, geometry = fixture()
        before = [(im.mode, im.size, im.tobytes(), copy.deepcopy(im.info)) for im in [original, *images.values()]]
        spec = copy.deepcopy(geometry)
        review.scope_views(original, images, geometry)
        self.assertEqual(before, [(im.mode, im.size, im.tobytes(), im.info) for im in [original, *images.values()]])
        self.assertEqual(spec, geometry)

    def test_full_resolution_masks_not_thumbnail_counts_are_reported(self):
        original, images, geometry = fixture()
        images['effective_write'].putpixel((2, 3), 1)
        _, summary = review.scope_views(original, images, geometry)
        self.assertEqual(summary['effective']['support_pixels'], 13)
        self.assertEqual(summary['effective']['bounds'], [2, 3, 11, 10])

    def test_padding_must_not_be_writable(self):
        original, images, geometry = fixture(); images['work_write'].putpixel((0, 0), 1)
        with self.assertRaises(ValueError): review.scope_views(original, images, geometry)

    def test_padding_must_be_protected_even_when_not_writable(self):
        original, images, geometry = fixture(); images['work_protect'].putpixel((0, 0), 0)
        with self.assertRaises(ValueError): review.scope_views(original, images, geometry)

    def test_source_mask_may_not_escape_context(self):
        original, images, geometry = fixture(); images['effective_write'].putpixel((0, 0), 1)
        with self.assertRaises(ValueError): review.scope_views(original, images, geometry)

    def test_empty_effective_mask_or_protection_conflict_refused(self):
        for mode in ('empty', 'overlap'):
            original, images, geometry = fixture()
            if mode == 'empty': images['effective_write'].paste(0, (0, 0, 23, 19))
            else: images['source_protect'].putpixel((6, 7), 255)
            with self.subTest(mode=mode), self.assertRaises(ValueError): review.scope_views(original, images, geometry)

    def test_context_and_transform_dimensions_cannot_disagree(self):
        for change in ('size', 'padding', 'bool', 'negative', 'empty'):
            original, images, geometry = fixture()
            if change == 'size': geometry['work_size'] = [15, 15]
            elif change == 'padding': geometry['padding_ltrb'][2] = 4
            elif change == 'bool': geometry['padding_ltrb'][0] = True
            elif change == 'negative': geometry['context_box'][0] = -1
            else: geometry['resized_size'][0] = 0
            with self.subTest(change=change), self.assertRaises(ValueError): review.scope_views(original, images, geometry)

    def test_context_is_rgba_not_implicitly_flattened(self):
        original, images, geometry = fixture(); images['context'] = images['context'].convert('RGB')
        with self.assertRaises(ValueError): review.scope_views(original, images, geometry)

    def test_generated_html_is_offline_and_escapes_caller_text(self):
        original, images, geometry = fixture(); views, summary = review.scope_views(original, images, geometry)
        html = review.render_html(views, summary, {'request_sha256': '</pre><script>alert(1)</script>'}).decode('utf-8')
        self.assertNotIn('<script', html.lower())
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Content-Security-Policy', html)
        self.assertIn('data:image/png;base64,', html)
        self.assertIn('not colour managed', html)
        self.assertIn('not accepted artwork', html)
        self.assertIn('comfy-mask.png', html)
        self.assertNotIn('https://', html)

    def test_html_puts_scope_counts_before_views_and_collapses_raw_evidence(self):
        original, images, geometry = fixture(); views, summary = review.scope_views(original, images, geometry)
        html = review.render_html(views, summary, {'expected_effective_write_sha256': 'a' * 64}).decode('utf-8')
        self.assertIn('data-stat="effective_support"', html)
        self.assertIn('data-stat="added_support"', html)
        self.assertIn('data-stat="removed_support"', html)
        self.assertIn('data-stat="coverage_changed"', html)
        self.assertLess(html.index('data-stat="effective_support"'), html.index('<img'))
        self.assertIn('<details id="raw-evidence">', html)
        self.assertIn('<summary>Technical evidence and file identities</summary>', html)
        self.assertIn('for="effective-mask-digest"', html)
        self.assertIn('readonly', html)

    def test_readonly_digest_cannot_inject_markup(self):
        original, images, geometry = fixture(); views, summary = review.scope_views(original, images, geometry)
        digest = '</textarea><script>bad()</script>'
        html = review.render_html(views, summary, {'expected_effective_write_sha256': digest}).decode('utf-8')
        self.assertNotIn('<script', html.lower())
        self.assertIn('id="effective-mask-digest"', html)
        self.assertIn('&lt;/textarea&gt;', html)

    def test_views_are_bounded_diagnostic_derivatives(self):
        original, images, geometry = fixture(); views, _ = review.scope_views(original, images, geometry)
        for raw in views.values():
            with Image.open(BytesIO(raw)) as decoded:
                self.assertLessEqual(max(decoded.size), 1280)
                self.assertEqual(decoded.mode, 'RGB')

    def test_work_protection_cannot_have_fractional_pixels(self):
        original, images, geometry = fixture(); images['work_protect'].putpixel((2, 3), 128)
        with self.assertRaises(ValueError): review.scope_views(original, images, geometry)


if __name__ == '__main__': unittest.main()
