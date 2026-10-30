"""Empty-picture advisory (#1704): flat or fully transparent stills are said so; nothing else changes."""
import io
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
import test_looks as fixture
import review_media


def png(mode='RGB', colour='#000000', size=(64, 48), draw=None):
    image = Image.new(mode, size, colour)
    if draw: draw(ImageDraw.Draw(image))
    stream = io.BytesIO(); image.save(stream, format='PNG'); image.close()
    return stream.getvalue()


class EmptyPictureTests(unittest.TestCase):
    def test_flat_transparent_and_ordinary_pictures(self):
        self.assertEqual(review_media.empty_picture(png()), 'uniform')
        self.assertEqual(review_media.empty_picture(png(colour='#7f7f80')), 'uniform', 'near-flat noise still reads as one colour')
        self.assertEqual(review_media.empty_picture(png('RGBA', (0, 0, 0, 0))), 'transparent')
        self.assertEqual(review_media.empty_picture(png(draw=lambda d: d.rectangle((10, 10, 20, 20), fill='white'))), '')
        silhouette = png('RGBA', (0, 0, 0, 0), draw=lambda d: d.ellipse((8, 8, 40, 40), fill=(0, 0, 0, 255)))
        self.assertEqual(review_media.empty_picture(silhouette), '', 'a one-colour sprite on transparency is a result')

    def test_unsupported_input_raises(self):
        with self.assertRaises(ValueError): review_media.empty_picture(b'not an image')


class EmptyPictureIndexTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp

    def stored(self, data):
        payload = {'preset_id': self.studio.catalog()['presets'][0]['id'], 'controls': {}}
        job = self.studio.create_job(payload, enqueue=False); stored = self.studio.jobs[job['id']]
        path = self.root / 'fake-comfy/output/result.png'; path.parent.mkdir(exist_ok=True); path.write_bytes(data)
        stored['outputs'] = [{'filename': path.name, 'subfolder': '', 'type': 'output', 'media_type': 'image'}]
        return stored

    def test_indexing_flags_a_flat_still_once_and_keeps_the_outcome(self):
        stored = self.stored(png()); stored['status'] = 'completed'
        with patch.object(review_media, 'empty_picture', wraps=review_media.empty_picture) as metric:
            self.studio.index_outputs(stored); self.studio.index_outputs(stored)
        self.assertEqual(metric.call_count, 1)
        self.assertIn('asset_id', stored['outputs'][0])
        self.assertEqual(stored['outputs'][0]['empty_picture'], 'uniform')
        self.assertEqual(stored['status'], 'completed')

    def test_ordinary_still_records_empty_string_and_unreadable_one_records_nothing(self):
        stored = self.stored(png(draw=lambda d: d.line((0, 0, 63, 47), fill='white')))
        self.studio.index_outputs(stored); self.assertEqual(stored['outputs'][0]['empty_picture'], '')
        stored = self.stored(png())
        with patch.object(review_media, 'empty_picture', side_effect=ValueError('bad')): self.studio.index_outputs(stored)
        self.assertNotIn('empty_picture', stored['outputs'][0])
        self.assertIn('asset_id', stored['outputs'][0])


if __name__ == '__main__': unittest.main()
