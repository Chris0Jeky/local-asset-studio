"""Use the production static handler: a fixture MIME server is not delivery proof."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_ui_island_static as fixture


class LookPreviewStaticTests(unittest.TestCase):
    def test_exact_derivative_is_delivered_by_production_handler(self):
        status, headers, data = fixture.get('/static/look-previews/night-shift-ma-responsive-1024.webp')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Content-Type'), 'image/webp')
        self.assertEqual(len(data), 26460)
        self.assertEqual(hashlib.sha256(data).hexdigest(), '156df8bb9178be20691f5a6d0686a32d9be67daad61f84252119a15ccd489192')

    def test_unlisted_images_and_parent_escape_remain_unavailable(self):
        for path in ['/static/look-previews/other.webp', '/static/look-previews/../../presets/looks.json',
                     '/static/workshop-assets/night-shift.svg']:
            with self.subTest(path=path):
                self.assertNotEqual(fixture.get(path)[0], 200)

    def test_existing_peer_webp_is_not_admitted_as_general_static_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'app'
            folder = root / 'static/look-previews'
            folder.mkdir(parents=True)
            (folder / 'other.webp').write_bytes(b'existing unlisted peer')
            with patch.object(fixture.server, '__file__', str(root / 'server.py')):
                self.assertEqual(fixture.get('/static/look-previews/other.webp')[0], 404)

    def test_wrong_host_remains_rejected(self):
        self.assertEqual(fixture.get('/static/look-previews/night-shift-ma-responsive-1024.webp', host='127.0.0.1:5173')[0], 403)


if __name__ == '__main__': unittest.main()
