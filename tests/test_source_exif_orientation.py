"""#1234/#1861: display-oriented source coordinates without rewriting original evidence.

Synthetic JPEGs, PNGs and WebPs, SQLite workspace imports and graph preparation only. No engine
request, model download, background worker or generation is permitted here.
"""
import copy
import hashlib
import io
import itertools
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

import test_parallax as parallax_fixture
import test_tiles as tile_fixture
import continuation
import parallax
import tiles


# Explicit EXIF transforms keep the expected result independent of exif_transpose.
TRANSFORMS = {
    2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}
FORMATS = ('JPEG', 'PNG', 'WEBP')
MIMES = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}


def fixture_image(orientation, size=(640, 512), format='JPEG'):
    image = Image.new('RGB', size, (30, 40, 50))
    draw = ImageDraw.Draw(image)
    width, height = size
    for box, colour in (
        ((0, 0, width // 2, height // 2), (210, 30, 40)),
        ((width // 2, 0, width, height // 2), (30, 190, 60)),
        ((0, height // 2, width // 2, height), (40, 60, 220)),
        ((width // 2, height // 2, width, height), (220, 170, 30)),
        ((31, 67, 113, 151), (240, 230, 210)),
    ):
        draw.rectangle(box, fill=colour)
    exif = Image.Exif()
    if orientation is not None:
        exif[274] = orientation
    out = io.BytesIO()
    image.save(out, format, quality=95, lossless=True, exif=exif)
    raw = out.getvalue()
    with Image.open(io.BytesIO(raw)) as decoded:
        pixels = decoded.convert('RGB')
    expected = pixels.transpose(TRANSFORMS[orientation]) if orientation in TRANSFORMS else pixels
    return raw, expected


class SourceOrientationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in ('presets', 'workflows/api', 'config', 'fake-comfy/input', 'fake-comfy/output'):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        (self.root / 'config/local.json').write_text(json.dumps({'comfy_root': str(self.root / 'fake-comfy')}))
        presets = [parallax_fixture.ROUTE, tile_fixture.ROUTE]
        (self.root / 'presets/catalog.json').write_text(json.dumps({'presets': presets}))
        for preset in presets:
            shutil.copyfile(parallax_fixture.ROOT / preset['graph'], self.root / preset['graph'])
        no_worker = patch.object(threading.Thread, 'start', lambda *_: None)
        no_worker.start()
        self.addCleanup(no_worker.stop)
        self.studio = parallax_fixture.FakeStudio(self.root)

    def tearDown(self):
        self.assertEqual(self.studio.requests, [], 'Orientation must never submit generation or contact an engine')

    def source(self, orientation, size=(640, 512), format='JPEG'):
        raw, expected = fixture_image(orientation, size, format)
        asset = self.studio.import_image('orientation.' + format.lower(), MIMES[format], raw)['asset']
        return asset, raw, expected

    def test_context_reports_display_dimensions_for_all_eight_orientations(self):
        for format, orientation in itertools.product(FORMATS, range(1, 9)):
            with self.subTest(format=format, orientation=orientation):
                asset, raw, expected = self.source(orientation, format=format)
                context = continuation.source_context(self.studio, asset['id'])
                self.assertEqual((context['width'], context['height']), expected.size)
                self.assertEqual(context['sha256'], hashlib.sha256(raw).hexdigest())

    def test_header_exif_dimensions_need_no_pixel_decode(self):
        loaders = {'JPEG': 'JpegImagePlugin.JpegImageFile', 'PNG': 'PngImagePlugin.PngImageFile', 'WEBP': 'WebPImagePlugin.WebPImageFile'}
        for format in FORMATS:
            with self.subTest(format=format):
                asset, raw, expected = self.source(6, format=format)
                with patch('PIL.' + loaders[format] + '.load', side_effect=AssertionError('Header EXIF must not inflate a raster')):
                    context = continuation.source_context(self.studio, asset['id'])
                self.assertEqual((context['width'], context['height']), expected.size)
                self.assertEqual(context['sha256'], hashlib.sha256(raw).hexdigest())

    def test_png_pixel_limit_refuses_before_metadata_or_rgb_decode(self):
        stream = io.BytesIO(); Image.new('RGB', (96, 64)).save(stream, 'PNG'); raw = stream.getvalue()
        asset = self.studio.import_image('no-exif.png', 'image/png', raw)['asset']
        readers = (('context', lambda: continuation.source_context(self.studio, asset['id'])),
                   ('RGB', lambda: continuation.source_rgb(raw)))
        for name, read in readers:
            with self.subTest(reader=name), patch.object(Image, 'MAX_IMAGE_PIXELS', 4000), self.assertWarns(Image.DecompressionBombWarning):
                # 6144 pixels is in Pillow's warning-only range. Neither PNG getexif()
                # nor the editing conversion may inflate it past the strict limit.
                with patch('PIL.PngImagePlugin.PngImageFile.load', side_effect=AssertionError('Oversized PNG must not inflate a raster')) as decode:
                    with self.assertRaises(Image.DecompressionBombError):
                        read()
                    decode.assert_not_called()
        self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)

    def test_png_exif_after_image_data_uses_the_same_display_coordinates(self):
        raw, expected = fixture_image(6, format='PNG')
        chunks, position = [], 8
        while position < len(raw):
            length = int.from_bytes(raw[position:position + 4], 'big')
            chunks.append(raw[position:position + length + 12]); position += length + 12
        exif = next(chunk for chunk in chunks if chunk[4:8] == b'eXIf')
        # A legal eXIf chunk can follow IDAT; retain its original CRC and all pixels.
        raw = raw[:8] + b''.join(chunk for chunk in chunks if chunk[4:8] not in (b'eXIf', b'IEND')) + exif + chunks[-1]
        asset = self.studio.import_image('late-exif.png', 'image/png', raw)['asset']
        context = continuation.source_context(self.studio, asset['id'])
        self.assertEqual((context['width'], context['height']), expected.size)
        for reader in (parallax._source, tiles._source):
            with self.subTest(reader=reader.__module__):
                _, actual = reader(self.studio, asset['id'])
                with actual:
                    self.assertEqual(actual.size, expected.size)
                    self.assertEqual(actual.tobytes(), expected.tobytes())
                    self.assertIn(actual.getexif().get(274), (None, 1))
        self.assertEqual(context['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)

    def test_both_loaders_decode_all_eight_pixel_transforms(self):
        for format, orientation in itertools.product(FORMATS, range(1, 9)):
            asset, raw, expected = self.source(orientation, format=format)
            for route in (parallax, tiles):
                with self.subTest(format=format, orientation=orientation, route=route.__name__):
                    context, actual = route._source(self.studio, asset['id'])
                    self.assertEqual(actual.size, expected.size)
                    self.assertEqual(actual.tobytes(), expected.tobytes())
                    self.assertIn(actual.getexif().get(274), (None, 1), 'Decoded pixels must not retain a second rotation')
                    self.assertEqual(context['sha256'], hashlib.sha256(raw).hexdigest())
                    self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)

    def test_untagged_sources_keep_their_pixels_and_dimensions(self):
        for format, route in itertools.product(FORMATS, (parallax, tiles)):
            with self.subTest(format=format, route=route.__name__):
                asset, raw, expected = self.source(None, format=format)
                context, actual = route._source(self.studio, asset['id'])
                self.assertEqual(actual.tobytes(), expected.tobytes())
                self.assertEqual((context['width'], context['height']), expected.size)
                self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)

    def test_tampered_source_bytes_are_still_refused(self):
        asset, _, _ = self.source(6)
        self.studio.assets.file(asset['id']).write_bytes(fixture_image(8)[0])
        for route in (parallax, tiles):
            with self.subTest(route=route.__name__), self.assertRaisesRegex(ValueError, 'Source bytes changed'):
                route._source(self.studio, asset['id'])

    def test_16_bit_sources_need_explicit_conversion_in_both_loaders(self):
        stream = io.BytesIO(); Image.new('I;16', (640, 512), 32768).save(stream, 'PNG'); raw = stream.getvalue()
        asset = self.studio.import_image('16-bit.png', 'image/png', raw)['asset']
        for route in (parallax, tiles):
            with self.subTest(route=route.__name__), self.assertRaisesRegex(ValueError, '16-bit.*8-bit RGB'):
                route._source(self.studio, asset['id'])
        self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)

    def test_parallax_status_and_prepare_agree_on_display_coordinates(self):
        for format, orientation in itertools.product(FORMATS, range(1, 9)):
            with self.subTest(format=format, orientation=orientation):
                asset, raw, expected = self.source(orientation, format=format)
                width, height = expected.size
                status = parallax.source_status(self.studio, asset['id'])
                self.assertTrue(status['eligible'])
                self.assertEqual((status['width'], status['height']), expected.size)
                view = [width - 48, height - 48, width - 16, height - 16]
                prepared = parallax.prepare(self.studio, {'asset_id': asset['id'], 'objects': 'the lamp', 'view': [view]})
                self.assertEqual((prepared['width'], prepared['height']), expected.size)
                self.assertEqual(prepared['plan']['view_polygons'], parallax._polygons([view], width, height))
                self.assertEqual(prepared['plan']['source_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual((self.studio.experiments / 'uploads' / prepared['file']).read_bytes(), raw)
                self.assertEqual((self.root / 'fake-comfy/input' / prepared['file']).read_bytes(), raw)
                _, graph, _, _, _ = self.studio.prepare(self.parallax_payload(prepared))
                for key, expected_size in zip(('width', 'height'), expected.size):
                    node, field = parallax_fixture.ROUTE[key]
                    self.assertEqual(graph[str(node)]['inputs'][field], expected_size)
                self.assertFalse(prepared['generation_submitted'])

    @staticmethod
    def parallax_payload(prepared):
        return {'preset_id': parallax_fixture.ROUTE['id'], 'parallax': prepared['claim'], 'batch_count': 1,
                'parent_assets': [prepared['plan']['source_asset_id']],
                'controls': {'reference': prepared['file'], 'positive': prepared['words'],
                             'width': prepared['width'], 'height': prepared['height']}}

    def test_legacy_unrotated_parallax_dimensions_are_refused_before_dispatch(self):
        asset, _, _ = self.source(6)
        prepared = parallax.prepare(self.studio, {'asset_id': asset['id'], 'objects': 'the lamp'})
        payload = self.parallax_payload(prepared)
        claim = copy.deepcopy(payload['parallax'])
        claim.update(width=640, height=512)
        claim['plan_id'] = parallax.plan_id(claim)
        payload['parallax'] = claim
        payload['controls'].update(width=640, height=512)
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.studio.prepare(payload)

    def test_tile_cross_uses_visible_pixels_and_removes_orientation_metadata(self):
        for format, orientation in itertools.product(FORMATS, range(1, 9)):
            with self.subTest(format=format, orientation=orientation):
                asset, raw, expected = self.source(orientation, size=(512, 512), format=format)
                prepared = tiles.prepare(self.studio, {'asset_id': asset['id'], 'band_px': 112})
                upload = self.studio.experiments / 'uploads' / prepared['file']
                with Image.open(upload) as actual:
                    self.assertEqual(actual.tobytes(), tiles.repaint_input(expected, 112).tobytes())
                    self.assertIn(actual.getexif().get(274), (None, 1))
                self.assertEqual(prepared['plan']['source_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(self.studio.assets.file(asset['id']).read_bytes(), raw)
                self.assertFalse(prepared['generation_submitted'])


if __name__ == '__main__':
    unittest.main()
