"""Workspace thumbnails: sizes, aspect, alpha, orientation, cache, refusals and bounded decodes (synthetic images only)."""
import io
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
import asset_thumbs
from workspace import AssetWorkspace, WorkspaceError


def encoded(image, fmt='PNG', **options):
    stream = io.BytesIO(); image.save(stream, fmt, **options); return stream.getvalue()


class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = AssetWorkspace(self.root); self.count = 0

    def register(self, raw, suffix='.png', media_type='image'):
        self.count += 1; source = self.root / f'source-{self.count}{suffix}'; source.write_bytes(raw)
        job = {'id': f'job-{self.count}', 'preset_name': 'Fixture', 'outputs': [{'filename': source.name, 'media_type': media_type}]}
        return self.store.register(job, 0, source)

    def thumb(self, asset_id, size=asset_thumbs.DEFAULT_SIZE):
        path, tag = asset_thumbs.thumbnail(self.store, asset_id, size)
        with Image.open(path) as image: image.load(); return path, tag, image

    def test_long_edge_matches_each_allowed_size_and_keeps_aspect(self):
        landscape = self.register(encoded(Image.new('RGB', (1000, 500), 'teal')))
        portrait = self.register(encoded(Image.new('RGB', (600, 1800), 'navy')))
        for size in asset_thumbs.SIZES:
            with self.subTest(size=size):
                _, _, image = self.thumb(landscape, size)
                self.assertEqual((image.format, image.mode, image.size), ('WEBP', 'RGB', (size, size // 2)))
                _, _, image = self.thumb(portrait, size)
                self.assertEqual(image.size[1], size); self.assertAlmostEqual(image.size[0], size / 3, delta=1)

    def test_small_images_are_never_upscaled(self):
        _, _, image = self.thumb(self.register(encoded(Image.new('RGB', (100, 60), 'olive'))), 512)
        self.assertEqual(image.size, (100, 60))

    def test_alpha_is_kept_for_rgba_and_transparent_palette_images(self):
        rgba = Image.new('RGBA', (800, 800), (40, 80, 120, 255))
        rgba.paste((0, 0, 0, 0), (0, 0, 800, 300))  # a transparent band survives any resampling
        palette = Image.new('P', (64, 64), 1); palette.paste(0, (0, 0, 64, 20))
        for source in (encoded(rgba), encoded(palette, transparency=0)):
            with self.subTest(mode=Image.open(io.BytesIO(source)).mode):
                _, _, image = self.thumb(self.register(source))
                self.assertEqual(image.mode, 'RGBA'); self.assertEqual(image.getchannel('A').getextrema()[0], 0)

    def test_trns_transparency_in_rgb_and_grey_pngs_is_kept(self):
        rgb = Image.new('RGB', (64, 64), (200, 10, 10)); rgb.paste((0, 0, 0), (0, 0, 64, 20))
        grey = Image.new('L', (64, 64), 200); grey.paste(0, (0, 0, 64, 20))
        for source in (encoded(rgb, transparency=(0, 0, 0)), encoded(grey, transparency=0)):
            with self.subTest(mode=Image.open(io.BytesIO(source)).mode):
                _, _, image = self.thumb(self.register(source))
                self.assertEqual(image.mode, 'RGBA'); self.assertEqual(image.getchannel('A').getextrema(), (0, 255))

    def test_exif_orientation_is_applied_before_sizing(self):
        exif = Image.Exif(); exif[0x0112] = 6  # stored landscape, displayed rotated to portrait
        _, _, image = self.thumb(self.register(encoded(Image.new('RGB', (800, 400), 'maroon'), 'JPEG', exif=exif), '.jpg'), 256)
        self.assertEqual(image.size, (128, 256))

    def test_cache_is_keyed_by_content_and_size_and_a_hit_skips_decoding(self):
        raw = encoded(Image.new('RGB', (900, 300), 'purple'))
        first = self.register(raw); digest = self.store.get(first)['sha256']
        path, tag, _ = self.thumb(first)
        self.assertEqual(path, self.store.root / 'thumbs' / f'{digest}-384-v{asset_thumbs.THUMB_VERSION}.webp')
        self.assertEqual(tag, f'"{digest}-384-v{asset_thumbs.THUMB_VERSION}"')
        modified = path.stat().st_mtime_ns
        with patch.object(asset_thumbs, 'render', side_effect=AssertionError('a cache hit must not decode')):
            self.assertEqual(asset_thumbs.thumbnail(self.store, first), (path, tag))
            self.assertEqual(asset_thumbs.thumbnail(self.store, self.register(raw)), (path, tag), 'identical bytes share one thumbnail')
        self.assertEqual(path.stat().st_mtime_ns, modified)
        self.assertNotEqual(asset_thumbs.thumbnail(self.store, first, 256)[0], path)
        self.assertEqual(sorted(p.suffix for p in path.parent.iterdir()), ['.webp', '.webp'], 'no temporary files remain')

    def test_size_parameter_accepts_only_the_allow_list(self):
        self.assertEqual(asset_thumbs.requested_size(None), 384)
        self.assertEqual(asset_thumbs.requested_size(['512']), 512)
        for values in (['100'], ['abc'], [''], ['384', '512'], ['0384'], ['384.0']):
            with self.subTest(values=values), self.assertRaises(WorkspaceError) as caught: asset_thumbs.requested_size(values)
            self.assertEqual((caught.exception.status, caught.exception.code), (400, 'invalid_thumbnail_size'))
        with self.assertRaises(WorkspaceError): asset_thumbs.thumbnail(self.store, self.register(encoded(Image.new('RGB', (9, 9)))), 1000)

    def test_non_image_assets_are_refused_without_touching_the_cache(self):
        video = self.register(b'\x00\x00\x00\x18ftypmp42 fixture', '.mp4', 'video')
        with self.assertRaises(WorkspaceError) as caught: asset_thumbs.thumbnail(self.store, video)
        self.assertEqual((caught.exception.status, caught.exception.code), (404, 'thumbnail_unavailable'))
        self.assertFalse((self.store.root / 'thumbs').exists())
        with self.assertRaises(WorkspaceError): asset_thumbs.thumbnail(self.store, 'missing')

    def test_unreadable_images_are_a_clear_422_and_leave_nothing_behind(self):
        truncated = encoded(Image.effect_noise((300, 300), 40).convert('RGB'))[:400]
        for raw in (b'not an image at all', truncated):
            with self.subTest(raw=raw[:12]), self.assertRaises(WorkspaceError) as caught: asset_thumbs.thumbnail(self.store, self.register(raw))
            self.assertEqual((caught.exception.status, caught.exception.code), (422, 'thumbnail_unreadable'))
        self.assertEqual(list((self.store.root / 'thumbs').glob('*')) if (self.store.root / 'thumbs').exists() else [], [])

    def test_decompression_bombs_are_refused_as_unreadable(self):
        asset = self.register(encoded(Image.new('RGB', (100, 100))))
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 1000), self.assertRaises(WorkspaceError) as caught: asset_thumbs.thumbnail(self.store, asset)
        self.assertEqual(caught.exception.status, 422)

    def test_decompression_bomb_warnings_are_refused_too(self):
        asset = self.register(encoded(Image.new('RGB', (100, 100))))  # 10,000 px: above 6,000, below the 12,000 error line
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 6000), self.assertRaises(WorkspaceError) as caught: asset_thumbs.thumbnail(self.store, asset)
        self.assertEqual((caught.exception.status, caught.exception.code), (422, 'thumbnail_unreadable'))

    def test_browser_url_version_is_pinned_to_the_rendering_version(self):
        script = (Path(__file__).parents[1] / 'app/static/workspace.js').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'const ASSET_THUMB_VERSION *= *(\d+);', script), [str(asset_thumbs.THUMB_VERSION)])
        self.assertIn("'/thumb?v='+ASSET_THUMB_VERSION+'-'+encodeURIComponent(String(asset.sha256||'').slice(0,16))", script)
        self.assertEqual(asset_thumbs.url_version('ab' * 32), f'{asset_thumbs.THUMB_VERSION}-' + 'ab' * 8)
        tag = asset_thumbs.etag('ab' * 32, 384)
        self.assertTrue(asset_thumbs.names_content([asset_thumbs.url_version('ab' * 32)], tag))
        for values in (None, [], ['ab' * 32], [f'{asset_thumbs.THUMB_VERSION + 1}-' + 'ab' * 8], [asset_thumbs.url_version('cd' * 32)]):
            self.assertFalse(asset_thumbs.names_content(values, tag), values)

    def test_trashed_images_keep_serving_like_their_original_file(self):
        asset = self.register(encoded(Image.new('RGB', (40, 40))))
        self.store.update({'ids': [asset], 'action': 'trash', 'request_id': 'thumbnail-trash-fixture', 'expected_revisions': {asset: self.store.get(asset)['metadata_revision']}})
        self.assertTrue(asset_thumbs.thumbnail(self.store, asset)[0].is_file())

    def test_parallel_decodes_are_bounded(self):
        assets = [self.register(encoded(Image.new('RGB', (40 + i, 40)))) for i in range(6)]
        lock, active, peak, real = threading.Lock(), [0], [0], asset_thumbs.render
        def slow(source, size):
            with lock: active[0] += 1; peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock: active[0] -= 1
            return real(source, size)
        with patch.object(asset_thumbs, 'render', side_effect=slow):
            threads = [threading.Thread(target=asset_thumbs.thumbnail, args=(self.store, a)) for a in assets]
            for thread in threads: thread.start()
            for thread in threads: thread.join(10)
        self.assertLessEqual(peak[0], asset_thumbs.MAX_PARALLEL_DECODES)
        self.assertEqual(len(list((self.store.root / 'thumbs').glob('*.webp'))), 6)


if __name__ == '__main__':
    unittest.main()
