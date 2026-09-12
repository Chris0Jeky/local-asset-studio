"""Regression coverage for RGB+tRNS contexts and decoded bundle transparency."""
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from scripts import character_edit_pixels as px


class ContextTransparency(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = {'intent': {'context_box': [1, 1, 4, 4], 'patch_alignment': 8}}
        self.mask = Image.new('L', (5, 5), 255)

    def source(self, transparency=(30, 60, 90), profile=None):
        image = Image.new('RGB', (5, 5), (30, 60, 90))
        image.putpixel((2, 2), (31, 61, 91))
        options = {'transparency': transparency}
        if profile is not None: options['icc_profile'] = profile
        image.save(self.root/'source.png', **options)
        result = px.png(self.root/'source.png')
        self.assertEqual('RGB', result.mode)
        self.assertEqual(transparency, result.info['transparency'])
        return result

    def context(self, source):
        patches, meta = px._patches(source, self.mask, self.plan)
        return patches['context.png'], patches['edit-mask.png'], meta

    def test_rgb_trns_is_materialized_as_rgba(self):
        source = self.source(); context, _, _ = self.context(source)
        self.assertEqual('RGBA', context.mode)
        self.assertEqual(source.convert('RGBA').crop((1, 1, 4, 4)).tobytes(),
                         context.crop((0, 0, 3, 3)).tobytes())

    def test_saved_context_preserves_transparent_and_opaque_pixels(self):
        source = self.source(); context, _, _ = self.context(source)
        px._save(context, self.root/'context.png'); loaded = px.png(self.root/'context.png').convert('RGBA')
        self.assertEqual((30, 60, 90, 0), loaded.getpixel((0, 0)))
        self.assertEqual((31, 61, 91, 255), loaded.getpixel((1, 1)))

    def test_trns_padding_is_transparent_and_not_editable(self):
        context, mask, meta = self.context(self.source())
        self.assertEqual([0, 0, 5, 5], meta['padding_ltrb'])
        self.assertEqual((0, 0, 0, 0), context.convert('RGBA').getpixel((7, 7)))
        self.assertEqual(0, mask.getpixel((7, 7)))
        self.assertEqual(255, mask.getpixel((0, 0)))

    def test_black_transparency_key_does_not_make_padding_opaque(self):
        source = self.source(transparency=(0, 0, 0))
        # The colour key need not actually occur in the source.
        context, _, _ = self.context(source)
        self.assertEqual((30, 60, 90, 255), context.convert('RGBA').getpixel((0, 0)))
        self.assertEqual((0, 0, 0, 0), context.convert('RGBA').getpixel((7, 7)))

    def test_source_bytes_mode_and_metadata_are_not_changed(self):
        source = self.source(); raw = (self.root/'source.png').read_bytes()
        pixels, info = source.tobytes(), dict(source.info)
        self.context(source)
        self.assertEqual(raw, (self.root/'source.png').read_bytes())
        self.assertEqual('RGB', source.mode); self.assertEqual(pixels, source.tobytes())
        self.assertEqual(info, source.info)

    def test_opaque_rgb_keeps_existing_mode_and_padding(self):
        source = Image.new('RGB', (5, 5), (30, 60, 90))
        context, _, _ = self.context(source)
        self.assertEqual('RGB', context.mode)
        self.assertEqual(source.crop((1, 1, 4, 4)).tobytes(), context.crop((0, 0, 3, 3)).tobytes())
        self.assertEqual((0, 0, 0), context.getpixel((7, 7)))

    def test_rgba_partial_alpha_and_hidden_rgb_are_preserved(self):
        source = Image.new('RGBA', (5, 5), (30, 60, 90, 127))
        source.putpixel((2, 2), (31, 61, 91, 0))
        context, _, _ = self.context(source)
        self.assertEqual(source.crop((1, 1, 4, 4)).tobytes(), context.crop((0, 0, 3, 3)).tobytes())
        self.assertEqual((0, 0, 0, 0), context.getpixel((7, 7)))

    def test_profile_retained_during_transparency_normalization(self):
        context, _, _ = self.context(self.source(profile=b'fixture-profile'))
        px._save(context, self.root/'context.png')
        self.assertEqual(b'fixture-profile', px.png(self.root/'context.png').info['icc_profile'])

    def test_aligned_crop_does_not_grow_or_resample(self):
        self.plan['intent']['patch_alignment'] = 1
        source = self.source(); context, _, meta = self.context(source)
        self.assertEqual((3, 3), context.size); self.assertEqual([0, 0, 0, 0], meta['padding_ltrb'])
        self.assertEqual(source.convert('RGBA').crop((1, 1, 4, 4)).tobytes(), context.convert('RGBA').tobytes())


class TransparencyRoundtrip(unittest.TestCase):
    """Use the actual edit planner, source verifier and apply path in repository CI."""
    def setUp(self):
        from scripts.character_edit_demo import create
        from scripts.character_study import read_json
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'job'; create(self.root)
        self.plan = read_json(self.root/'plan.json')

    def ref(self, name):
        from scripts.character_study import file_sha
        return {'path': name, 'sha256': file_sha(self.root/name)}

    def rgb_plan(self, transparent):
        from scripts.character_edit import make_plan
        from scripts.character_study import sha
        with Image.open(self.root/'source.png') as source: rgb = source.convert('RGB')
        options = {'transparency': (43, 107, 161)} if transparent else {}
        rgb.save(self.root/'rgb-source.png', **options)
        self.plan['document']['source'] = self.ref('rgb-source.png')
        self.plan['intent']['document_sha256'] = sha(self.plan['document'])
        self.plan = make_plan(self.plan['document'], self.plan['intent'], self.plan['catalog'])
        px.prepare(self.root, self.plan, 'rgb-bundle')

    def test_transparent_context_noop_remains_exact(self):
        self.rgb_plan(True)
        receipt = px.apply(self.root, self.plan, 'rgb-bundle', self.ref('rgb-bundle/context.png'), 'noop')
        self.assertEqual(0, receipt['changed_pixels']); self.assertFalse(receipt['semantic_approval'])
        with Image.open(self.root/'rgb-source.png') as source, Image.open(self.root/'noop/result.png') as result:
            self.assertEqual(source.convert('RGBA').tobytes(), result.convert('RGBA').tobytes())

    def test_repair_preserves_transparent_pixels_outside_write_mask(self):
        self.rgb_plan(True)
        receipt = px.apply(self.root, self.plan, 'rgb-bundle', self.ref('candidate.png'), 'repaired')
        self.assertEqual(4032, receipt['changed_pixels'])
        self.assertEqual(0, receipt['outside_mask_changed_pixels'])
        with Image.open(self.root/'rgb-source.png') as source, Image.open(self.root/'repaired/result.png') as result:
            self.assertEqual(source.convert('RGBA').getpixel((60, 120)), result.getpixel((60, 120)))
            self.assertEqual(0, result.getpixel((60, 120))[3])
            self.assertEqual(255, result.getpixel((80, 120))[3])

    def test_rehashed_transparency_only_bundle_forgery_is_rejected(self):
        from scripts.character_study import read_json, sha, write_json
        self.rgb_plan(False)
        context_path = self.root/'rgb-bundle/context.png'
        with Image.open(context_path) as source:
            self.assertEqual('RGB', source.mode); altered = source.copy()
        # RGB bytes and mode stay equal; only the tRNS meaning changes.
        altered.save(context_path, transparency=(43, 107, 161))
        bundle_path = self.root/'rgb-bundle/bundle.json'; bundle = read_json(bundle_path)
        bundle['files']['context.png']['sha256'] = self.ref('rgb-bundle/context.png')['sha256']
        bundle['bundle_sha256'] = sha({k: v for k, v in bundle.items() if k != 'bundle_sha256'})
        bundle_path.unlink(); write_json(bundle_path, bundle)
        with self.assertRaisesRegex(ValueError, 'pixels/profile'):
            px.apply(self.root, self.plan, 'rgb-bundle', self.ref('candidate.png'), 'forged-result')
        self.assertFalse((self.root/'forged-result').exists())


if __name__ == '__main__': unittest.main()
