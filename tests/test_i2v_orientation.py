"""EXIF-aware Wan preparation and portable previews; no inference is executed."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import test_i2v_diagnostics as fixtures
import i2v_diagnostics as diagnostics

TRANSPOSE = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
             4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
             6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
             8: Image.Transpose.ROTATE_90}


def source(path, orientation=None):
    with Image.new('RGB', (12, 8)) as image:
        image.putdata([(x*19, y*29, (x+y)*11) for y in range(8) for x in range(12)])
        exif = Image.Exif()
        if orientation is not None: exif[274] = orientation
        image.save(path, format='PNG', exif=exif)


class OrientationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'source.png'

    def test_metadata_uses_oriented_canvas_and_discloses_encoded_geometry(self):
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                source(self.path, orientation)
                result = diagnostics.image_metadata(self.path)
                expected = [8, 12] if orientation >= 5 else [12, 8]
                self.assertEqual(result['dimensions'], expected)
                self.assertEqual(result['orientation'], 'portrait' if orientation >= 5 else 'landscape')
                self.assertEqual(result.get('encoded_dimensions'), [12, 8])
                self.assertEqual(result.get('exif_orientation'), orientation)
                self.assertEqual(result['format'], 'PNG')

    def test_preview_applies_each_rotation_and_mirror_before_center_crop(self):
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                source(self.path, orientation); original = self.path.read_bytes()
                output = self.root / ('preview-%d.png' % orientation)
                plan = diagnostics.render_preprocessed(self.path, output, 6, 6)
                with Image.open(self.path) as image:
                    oriented = image.transpose(TRANSPOSE[orientation]) if orientation in TRANSPOSE else image.copy()
                    with oriented:
                        box = (0, 2, 8, 10) if orientation >= 5 else (2, 0, 10, 8)
                        with oriented.crop(box) as crop, crop.resize((6, 6), Image.Resampling.BILINEAR) as expected, Image.open(output) as actual:
                            self.assertEqual(actual.tobytes(), expected.tobytes())
                            self.assertNotIn(274, actual.getexif())
                        self.assertEqual(plan['source_dimensions'], list(oriented.size))
                        self.assertEqual(plan['crop_box'], list(box))
                self.assertEqual(self.path.read_bytes(), original)

    def test_jpeg_metadata_does_not_decode_pixels_to_swap_axes(self):
        from unittest.mock import patch
        from PIL import JpegImagePlugin
        path = self.root / 'photo.jpg'
        with Image.new('RGB', (12, 8)) as image:
            exif = Image.Exif(); exif[274] = 6
            image.save(path, exif=exif)
        with patch.object(JpegImagePlugin.JpegImageFile, 'load', side_effect=AssertionError('unexpected JPEG pixel decode')):
            result = diagnostics.image_metadata(path)
        self.assertEqual(result['dimensions'], [8, 12])
        self.assertEqual(result['encoded_dimensions'], [12, 8])

    def test_unoriented_inputs_keep_existing_dimensions_and_pixels(self):
        source(self.path)
        result = diagnostics.image_metadata(self.path)
        self.assertEqual(result['dimensions'], [12, 8])
        self.assertEqual(result.get('exif_orientation'), 1)
        output = self.root / 'unchanged.png'
        diagnostics.render_preprocessed(self.path, output, 12, 8)
        with Image.open(self.path) as original, Image.open(output) as actual:
            self.assertEqual(actual.tobytes(), original.tobytes())


class WanPreparationOrientationTests(unittest.TestCase):
    setUp = fixtures.I2VDiagnosticTests.setUp
    tearDown = fixtures.I2VDiagnosticTests.tearDown

    def test_rotated_source_does_not_switch_an_already_matching_portrait_pair(self):
        source(self.root / 'experiments/uploads' / self.reference, 6)
        studio = fixtures.I2VDiagnosticTests.studio(self)
        prepared, graph, _, controls, _ = studio.prepare({'preset_id': 'wan22-i2v', 'controls': {'reference': self.reference}})
        self.assertEqual([graph['7']['inputs']['width'], graph['7']['inputs']['height']], [512, 768])
        self.assertEqual(prepared['_prepared_source']['source']['dimensions'], [8, 12])
        self.assertEqual(prepared['_prepared_source']['orientation_action'], 'preserved requested orientation')
        self.assertEqual(studio.jobs, {})
        self.assertTrue(studio.queue.empty())


if __name__ == '__main__':
    unittest.main()
