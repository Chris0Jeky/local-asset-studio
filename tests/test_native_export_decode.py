"""Real image preflight and owned-buffer lifetime; no native application launch."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import native_exports as native
try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, 'Optional Pillow not installed')
class NativeDecodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.exports = native.NativeExports(ROOT, self.root)

    def asset(self, name='frame.png', size=(4, 6), mode='RGBA'):
        with Image.new(mode, size) as im: im.save(self.root / name)
        path = self.root / name
        return {'id': 'frame-' + path.stem, 'path': name, 'filename': name,
                'media_type': 'image/png', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def records(self, assets):
        return self.exports._asset_records('atlas', assets)[0]

    def track_loads(self, loads):
        original = Image.open
        def opened(*args, **kwargs):
            image = original(*args, **kwargs)
            load = image.load
            def tracked(*a, **kw):
                loads.append(Path(image.filename).name)
                return load(*a, **kw)
            image.load = tracked
            return image
        return patch.object(Image, 'open', side_effect=opened)

    def test_pixel_limit_refuses_before_decode(self):
        assets = [self.asset()]; loads = []
        with self.track_loads(loads), patch.object(native, 'MAX_PIXELS', 23):
            with self.assertRaisesRegex(native.NativeExportError, 'pixels'):
                self.exports.execute(self.root / 'out', 'atlas', assets, {})
        self.assertEqual(loads, [], 'over-budget source must not be decoded')
        self.assertFalse((self.root / 'out').exists())

    def test_aggregate_limit_does_not_decode_the_crossing_image(self):
        records = self.records([self.asset('first.png'), self.asset('second.png')]); loads = []
        with self.track_loads(loads), patch.object(native, 'MAX_PIXELS', 47):
            with self.assertRaisesRegex(native.NativeExportError, 'pixels'):
                self.exports._images(records)
        self.assertIn('first.png', loads)
        self.assertNotIn('second.png', loads)

    def test_dimension_and_shared_canvas_checks_precede_decode(self):
        cases = ([self.asset('wide.png', (8193, 1))],
                 [self.asset('first.png'), self.asset('wrong.png', (6, 4))])
        for assets in cases:
            with self.subTest(files=[a['path'] for a in assets]):
                records = self.records(assets); loads = []
                with self.track_loads(loads), self.assertRaises(native.NativeExportError):
                    self.exports._images(records)
                self.assertNotIn(assets[-1]['path'], loads)

    def test_apng_and_animated_webp_are_not_silently_flattened(self):
        for extension, fmt, media_type in [('png', 'PNG', 'image/png'), ('webp', 'WEBP', 'image/webp')]:
            with self.subTest(format=fmt), Image.new('RGBA', (4, 6), 'red') as first, Image.new('RGBA', (4, 6), 'blue') as second:
                path = self.root / ('animation.' + extension)
                first.save(path, format=fmt, save_all=True, append_images=[second], duration=100, loop=0)
                with Image.open(path) as source: self.assertEqual(source.n_frames, 2)
                asset = {'id': 'animated-frame', 'path': path.name, 'filename': path.name,
                         'media_type': media_type, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                with self.assertRaisesRegex(native.NativeExportError, 'still|frame|animat'):
                    self.exports.execute(self.root / ('out-' + extension), 'ora', [asset], {})
                self.assertFalse((self.root / ('out-' + extension)).exists())

    def conversions(self, images):
        original = Image.Image.convert
        def convert(source, *args, **kwargs):
            result = original(source, *args, **kwargs); images.append(result); return result
        return patch.object(Image.Image, 'convert', convert)

    def assert_closed(self, images):
        self.assertTrue(images)
        for image in images:
            with self.assertRaises(ValueError): image.getpixel((0, 0))

    def test_rejected_later_image_closes_earlier_conversions(self):
        records = self.records([self.asset('first.png'), self.asset('wrong.png', (6, 4))]); images = []
        with self.conversions(images), self.assertRaises(native.NativeExportError):
            self.exports._images(records)
        self.assert_closed(images)

    def test_invalid_options_close_conversions_before_creating_output(self):
        assets = [self.asset()]; images = []
        with self.conversions(images), self.assertRaises(native.NativeExportError):
            self.exports.execute(self.root / 'out', 'atlas', assets, {'duration_ms': 0})
        self.assert_closed(images)
        self.assertFalse((self.root / 'out').exists())

    def test_success_and_packaging_failure_close_owned_conversions(self):
        assets = [self.asset()]
        # Use visible pixels; normal exports must remain possible.
        with Image.new('RGBA', (4, 6), 'purple') as im: im.save(self.root / 'frame.png')
        assets[0]['sha256'] = hashlib.sha256((self.root / 'frame.png').read_bytes()).hexdigest()
        for fails in (False, True):
            target = self.root / str(fails); images = []
            with self.conversions(images):
                if fails:
                    with patch.object(self.exports, '_pack', side_effect=OSError('disk unavailable')):
                        with self.assertRaisesRegex(OSError, 'disk unavailable'):
                            self.exports.execute(target, 'ora', assets, {})
                    self.assertTrue((target / 'failure.json').exists())
                else:
                    result = self.exports.execute(target, 'ora', assets, {})
                    self.assertEqual(result['measurements']['canvas'], [4, 6])
                    self.assertTrue((target / 'native-sources.zip').is_file())
            # Packaging libraries own their conversions; this adapter's first
            # conversion is the one whose lifetime is asserted here.
            self.assert_closed(images[:1])

    def test_exact_pixel_limit_is_admitted_without_a_redundant_copy(self):
        records = self.records([self.asset()]); images = []
        with self.conversions(images), patch.object(native, 'MAX_PIXELS', 24):
            size, pixels, converted = self.exports._images(records)
        try:
            self.assertEqual((size, pixels), ((4, 6), 24))
            self.assertIs(converted[0][1], images[0])
            self.assertEqual(converted[0][1].mode, 'RGBA')
        finally:
            for _, image in converted: image.close()
            for image in images: image.close()


if __name__ == '__main__': unittest.main()
