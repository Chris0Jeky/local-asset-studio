"""#1704: blank, uniform or fully transparent still outputs carry an advisory; indexing never fails on it."""
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from test_server import server


def png(image):
    stream = io.BytesIO(); image.save(stream, format='PNG'); return stream.getvalue()


def varied():
    image = Image.new('RGB', (32, 32), '#202020'); ImageDraw.Draw(image).rectangle((8, 8, 20, 20), fill='#ff8000'); return image


class BlankOutputAdvisoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup); self.root = Path(temporary.name)
        (self.root / 'config').mkdir(); (self.root / 'presets').mkdir()
        (self.root / 'presets/catalog.json').write_text('{"presets": []}')
        (self.root / 'config/local.json').write_text(json.dumps({'comfy_root': str(self.root / 'fake-comfy')}))
        with patch.object(threading.Thread, 'start', lambda *_: None):
            self.studio = server.Studio(self.root)
        (self.root / 'fake-comfy/output').mkdir(parents=True)

    def job(self, name, data, **extra):
        (self.root / 'fake-comfy/output' / name).write_bytes(data)
        return {'id': 'job-' + name.replace('.', '-'), 'status': 'completed', 'preset_id': 'p', 'controls': {}, 'created_at': 1, 'submissions': [],
                'outputs': [{'filename': name, 'subfolder': '', 'type': 'output', 'media_type': 'image', **extra}]}

    def index(self, name, data, **extra):
        job = self.job(name, data, **extra); self.studio.index_outputs(job); return job['outputs'][0]

    def test_uniform_picture_is_flagged_but_recorded_normally(self):
        output = self.index('flat.png', png(Image.new('RGB', (32, 32), '#000000')))
        self.assertEqual(output.get('blank'), 'uniform'); self.assertIn('asset_id', output)

    def test_uniform_grey_and_opaque_rgba_are_flagged(self):
        self.assertEqual(self.index('grey.png', png(Image.new('L', (8, 8), 7))).get('blank'), 'uniform')
        self.assertEqual(self.index('opaque.png', png(Image.new('RGBA', (8, 8), (9, 9, 9, 255)))).get('blank'), 'uniform')

    def test_fully_transparent_picture_is_flagged_even_with_varied_colour(self):
        image = varied().convert('RGBA'); image.putalpha(0)
        self.assertEqual(self.index('clear.png', png(image)).get('blank'), 'transparent')

    def test_real_pictures_carry_no_advisory(self):
        self.assertNotIn('blank', self.index('real.png', png(varied())))
        image = Image.new('RGBA', (16, 16), (10, 10, 10, 0)); image.putpixel((3, 3), (200, 10, 10, 255))
        self.assertNotIn('blank', self.index('dot.png', png(image)))

    def test_unreadable_file_gets_no_advisory_and_indexing_succeeds(self):
        output = self.index('broken.png', b'\x89PNG not really a picture')
        self.assertNotIn('blank', output); self.assertNotIn('snapshot_error', output)

    def test_non_image_media_is_not_inspected(self):
        with patch('review_media.blank_kind') as check:
            self.index('clip.png', png(Image.new('RGB', (4, 4))), media_type='video')
        check.assert_not_called()

    def test_advisory_reaches_the_public_job_without_changing_status(self):
        job = self.job('p.png', png(Image.new('RGB', (8, 8))))
        self.studio.index_outputs(job)
        public = self.studio.public(job)
        self.assertEqual(public['outputs'][0]['blank'], 'uniform'); self.assertEqual(public['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
