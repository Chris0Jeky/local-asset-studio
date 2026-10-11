"""Decoded EXIF pixels and native packages, without launching applications."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import native_exports as native
from PIL import Image, ImageCms, ImageOps, JpegImagePlugin

TRANSPOSE = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
             4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
             6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
             8: Image.Transpose.ROTATE_90}


class NativeOrientationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.exports = native.NativeExports(ROOT, self.root)

    def asset(self, name='photo.jpg', orientation=6, size=(12, 8), profile=None):
        path = self.root / name
        with Image.new('RGB', size) as image:
            image.putdata([(x * 19, y * 29, (x + y) * 11)
                           for y in range(size[1]) for x in range(size[0])])
            exif = Image.Exif(); exif[274] = orientation
            image.save(path, quality=95, subsampling=0, exif=exif,
                       **({'icc_profile': profile} if profile is not None else {}))
        return {'id': 'frame-' + path.stem, 'path': name, 'filename': name,
                'media_type': 'image/jpeg',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def expected(self, asset, orientation):
        with Image.open(self.root / asset['path']) as encoded:
            oriented = encoded.transpose(TRANSPOSE[orientation]) if orientation in TRANSPOSE else encoded.copy()
            with oriented:
                return oriented.convert('RGBA')

    def test_all_orientations_use_decoded_upright_pixels_and_preserve_sources(self):
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                asset = self.asset(orientation=orientation)
                original = (self.root / asset['path']).read_bytes()
                records, _ = self.exports._asset_records('atlas', [asset])
                dimensions, pixels, converted = self.exports._images(records)
                try:
                    with self.expected(asset, orientation) as expected:
                        self.assertEqual(dimensions, expected.size)
                        self.assertEqual(pixels, 96)
                        self.assertEqual(converted[0][1].tobytes(), expected.tobytes())
                    self.assertEqual((self.root / asset['path']).read_bytes(), original)
                    self.assertEqual(native.sha256(self.root / asset['path']), asset['sha256'])
                finally:
                    for _, image in converted: image.close()

    def test_shared_canvas_uses_display_dimensions_before_decode(self):
        first = self.asset('first.jpg', 6)
        matching = self.asset('matching.jpg', 1, (8, 12))
        records, _ = self.exports._asset_records('atlas', [first, matching])
        size, _, converted = self.exports._images(records)
        try: self.assertEqual(size, (8, 12))
        finally:
            for _, image in converted: image.close()
        mismatch = self.asset('mismatch.jpg', 1)
        records, _ = self.exports._asset_records('atlas', [first, mismatch])
        original_load = JpegImagePlugin.JpegImageFile.load
        loads = []
        def load(image, *args, **kwargs):
            loads.append(Path(image.filename).name)
            return original_load(image, *args, **kwargs)
        with patch.object(JpegImagePlugin.JpegImageFile, 'load', load):
            with self.assertRaisesRegex(native.NativeExportError, 'share one canvas'):
                self.exports._images(records)
        self.assertNotIn('mismatch.jpg', loads)

    def test_oriented_over_budget_image_is_refused_without_decode_or_transpose(self):
        asset = self.asset()
        records, _ = self.exports._asset_records('atlas', [asset])
        with patch.object(native, 'MAX_PIXELS', 95), \
                patch.object(JpegImagePlugin.JpegImageFile, 'load', side_effect=AssertionError('decoded')), \
                patch.object(ImageOps, 'exif_transpose', side_effect=AssertionError('transposed')):
            with self.assertRaisesRegex(native.NativeExportError, 'pixels'):
                self.exports._images(records)

    def test_png_header_orientation_and_late_metadata_do_not_bypass_canvas_contract(self):
        path = self.root / 'oriented.png'
        with Image.new('RGB', (12, 8)) as source:
            source.putdata([(x * 19, y * 29, (x + y) * 11) for y in range(8) for x in range(12)])
            exif = Image.Exif(); exif[274] = 6
            source.save(path, exif=exif)
        raw = path.read_bytes()
        # Move the intact eXIf chunk after IDAT, preserving all chunk CRCs.
        chunks = []; offset = 8
        while offset < len(raw):
            length = int.from_bytes(raw[offset:offset + 4], 'big') + 12
            chunks.append(raw[offset:offset + length]); offset += length
        exif_chunk = next(chunk for chunk in chunks if chunk[4:8] == b'eXIf')
        late = raw[:8] + b''.join(chunk for chunk in chunks[:-1] if chunk != exif_chunk) + exif_chunk + chunks[-1]
        for is_late, payload in ((False, raw), (True, late)):
            with self.subTest(late=is_late):
                path.write_bytes(payload)
                asset = {'id': 'png-frame', 'path': path.name, 'filename': path.name,
                         'media_type': 'image/png', 'sha256': native.sha256(path)}
                records, _ = self.exports._asset_records('atlas', [asset])
                dimensions, _, converted = self.exports._images(records)
                try:
                    with Image.open(path) as encoded:
                        expected = encoded.copy() if is_late else encoded.transpose(Image.Transpose.ROTATE_270)
                        with expected, expected.convert('RGBA') as rgba:
                            self.assertEqual(dimensions, rgba.size)
                            self.assertEqual(converted[0][1].tobytes(), rgba.tobytes())
                    output = io.BytesIO(); converted[0][1].save(output, format='PNG')
                    with Image.open(io.BytesIO(output.getvalue())) as image:
                        self.assertNotIn(274, image.getexif())
                    self.assertEqual(path.read_bytes(), payload)
                finally:
                    for _, image in converted: image.close()

    def test_all_packages_have_upright_interchange_and_original_snapshots(self):
        asset = self.asset()
        original = (self.root / asset['path']).read_bytes()
        with self.expected(asset, 6) as expected:
            for kind in ('atlas', 'ora', 'godot'):
                with self.subTest(kind=kind):
                    target = self.root / kind
                    result = self.exports.execute(target, kind, [asset], {})
                    self.assertEqual(result['measurements']['canvas'], [8, 12])
                    self.assertEqual(result['measurements']['anchor'], [4, 12])
                    self.assertEqual((target / 'sources/00-frame-photo.jpg').read_bytes(), original)
                    with Image.open(target / 'interchange/frame-00-frame-photo.png') as image:
                        self.assertEqual(image.tobytes(), expected.tobytes())
                        self.assertNotIn(274, image.getexif())
                        self.assertNotIn('exif', image.info)
                    with zipfile.ZipFile(target / 'native-sources.zip') as archive:
                        self.assertEqual(archive.read('sources/00-frame-photo.jpg'), original)
                    if kind == 'ora':
                        with zipfile.ZipFile(target / 'layers.ora') as archive:
                            stack = ET.fromstring(archive.read('stack.xml'))
                        self.assertEqual((stack.get('w'), stack.get('h')), ('8', '12'))
                    else:
                        manifest = json.loads((target / 'atlas/manifest.json').read_text())
                        x, y, width, height = manifest['frames'][0]['region']
                        with Image.open(target / 'atlas/atlas.png') as image:
                            with image.crop((x, y, x + width, y + height)) as frame:
                                self.assertEqual(frame.tobytes(), expected.tobytes())
                        self.assertEqual(manifest['anchor'], [4, 12])
                    if kind == 'godot':
                        self.assertTrue((target / 'godot/project.godot').is_file())

    def test_oriented_icc_conversion_and_intermediate_cleanup(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        asset = self.asset(profile=profile)
        original_transpose = ImageOps.exif_transpose
        transposed = []
        def transpose(image):
            result = original_transpose(image); transposed.append(result); return result
        records, _ = self.exports._asset_records('atlas', [asset])
        with patch.object(ImageOps, 'exif_transpose', side_effect=transpose):
            _, _, converted = self.exports._images(records)
        try:
            with self.expected(asset, 6) as expected, ImageCms.profileToProfile(
                    expected, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                    ImageCms.createProfile('sRGB'), outputMode='RGBA') as reference:
                self.assertEqual(converted[0][1].tobytes(), reference.tobytes())
            self.assertEqual(len(transposed), 1)
            with self.assertRaises(ValueError): transposed[0].getpixel((0, 0))
        finally:
            for _, image in converted: image.close()
        bad = self.asset('bad.jpg', profile=b'not an ICC profile')
        records, _ = self.exports._asset_records('atlas', [bad])
        transposed.clear()
        with patch.object(ImageOps, 'exif_transpose', side_effect=transpose):
            with self.assertRaisesRegex(native.NativeExportError, 'Invalid ICC'):
                self.exports._images(records)
        self.assertEqual(len(transposed), 1)
        with self.assertRaises(ValueError): transposed[0].getpixel((0, 0))


class ProductionOrientationTests(unittest.TestCase):
    def setUp(self):
        import test_production as fixtures
        fixtures.ProductionTests.setUp(self)

    def tearDown(self):
        import test_production as fixtures
        fixtures.ProductionTests.tearDown(self)

    def test_native_plan_and_package_use_display_canvas_without_generation(self):
        from test_server import FakeStudio
        (self.root / 'scripts').mkdir()
        for name in ('game_asset_media.py', 'godot_asset_adapter.py'):
            (self.root / 'scripts' / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        with Image.new('RGB', (12, 8), 'purple') as image:
            exif = Image.Exif(); exif[274] = 6
            payload = io.BytesIO(); image.save(payload, format='JPEG', exif=exif)
        studio = FakeStudio(self.root, [])
        asset = studio.import_image('oriented.jpg', 'image/jpeg', payload.getvalue())['asset']
        with patch.object(studio, '_request', side_effect=AssertionError('backend contacted')), \
                patch.object(native.godot, 'execute', side_effect=AssertionError('engine launched')):
            project = studio.production.native({'kind': 'godot', 'ids': [asset['id']],
                                                'verify_engine': False})
            self.assertEqual(studio.production.get(project['id'], full=True)['plan']['options']['anchor'], [4, 12])
            studio.production.start(project['id']); studio.production.run(project['id'])
        state = studio.production.get(project['id'])['state']
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['measurements']['canvas'], [8, 12])
        self.assertEqual(sum(1 for args, _ in studio.requests if args[0] == '/prompt'), 0)
        self.assertEqual(studio.assets.file(asset['id']).read_bytes(), payload.getvalue())
