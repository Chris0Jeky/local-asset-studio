"""Exact raster and source-completeness acceptance, no model inference."""
import copy
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from studio_workflow import addressable_figures as figures
from test_server import server


class FigurePrecisionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.workspace = server.AssetWorkspace(self.root)

    def parent(self, size=(3, 1), raw=None, fmt='PNG'):
        path = self.root / ('source.' + fmt.lower())
        if raw is None:
            image = Image.new('RGBA', size)
            image.putdata([(x % 256, 120, 200, 0 if x == 0 else 255) for x in range(size[0] * size[1])])
            image.save(path, fmt)
        else: path.write_bytes(raw)
        job = {'id': 'source-fixture-' + hashlib.sha256(path.read_bytes()).hexdigest(), 'created_at': 123, 'preset_id': 'fixture', 'preset_name': 'fixture',
               'parent_assets': [], 'outputs': [{'filename': path.name, 'media_type': 'image'}]}
        identifier = self.workspace.register(job, 0, path)
        return self.workspace.get(identifier)

    def command(self, parent, rectangles):
        return {'workspace_id': self.workspace.snapshot()['workspace_id'], 'request_id': 'precise-figure-request',
                'asset_id': parent['id'], 'parent_sha256': parent['sha256'], 'rectangles': rectangles,
                'require_non_overlapping': True}

    def test_zero_pixel_crop_is_a_domain_refusal_not_an_expanded_crop(self):
        parent = self.parent((1, 1)); before = self.workspace.snapshot()
        request = self.command(parent, [{'x': 0, 'y': 0, 'width': 1, 'height': 10000}])
        with self.assertRaisesRegex(server.WorkspaceError, 'smaller than one source pixel'):
            figures.split_figures(self.workspace, request)
        self.assertEqual(self.workspace.snapshot(), before)
        with self.workspace.connection() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM asset_commands WHERE request_id=?', (request['request_id'],)).fetchone())

    def test_late_zero_width_box_is_rejected_before_any_png_is_published(self):
        parent = self.parent((1, 1)); before = set(self.workspace.media.iterdir())
        request = self.command(parent, [{'x': 0, 'y': 0, 'width': 5000, 'height': 10000},
                                        {'x': 5000, 'y': 0, 'width': 5000, 'height': 10000}])
        with patch.object(figures, '_snapshot_png', side_effect=AssertionError('must validate every box first')):
            with self.assertRaisesRegex(server.WorkspaceError, 'smaller than one source pixel'):
                figures.split_figures(self.workspace, request)
        self.assertEqual(set(self.workspace.media.iterdir()), before)

    def test_children_reassemble_exact_rgba_pixels_and_bind_parent_revision(self):
        parent = self.parent(); request = self.command(parent, [
            {'x': 0, 'y': 0, 'width': 5000, 'height': 10000},
            {'x': 5000, 'y': 0, 'width': 5000, 'height': 10000}])
        before = self.workspace.file(parent['id']).read_bytes()
        result = figures.split_figures(self.workspace, request)
        pixels = []
        for identifier in result['created']:
            child = self.workspace.get(identifier)
            self.assertEqual(child['source']['parent_metadata_revision'], parent['metadata_revision'])
            self.assertEqual(child['source']['crop_coordinate_policy'], 'basis-points-nearest-half-up/v1')
            self.assertEqual(child['lineage'], [parent['id']])
            with Image.open(self.workspace.file(identifier)) as image: pixels.extend(image.get_flattened_data())
        with Image.open(io.BytesIO(before)) as original: self.assertEqual(pixels, list(original.get_flattened_data()))
        self.assertEqual(figures.split_figures(self.workspace, copy.deepcopy(request)), result)
        self.assertEqual(self.workspace.file(parent['id']).read_bytes(), before)

    def test_truncated_png_with_complete_pixels_is_not_a_complete_source(self):
        stream = io.BytesIO(); Image.new('RGB', (10, 10), 'red').save(stream, 'PNG')
        # Pillow.load can decode all pixels without IEND; verify must also attest
        # the container is complete rather than accepting those pixels alone.
        for missing in (1, 4, 5, 8, 12):
            with self.subTest(missing=missing):
                parent = self.parent(raw=stream.getvalue()[:-missing])
                request = self.command(parent, [{'x': 0, 'y': 0, 'width': 10000, 'height': 10000}])
                with self.assertRaisesRegex(server.WorkspaceError, 'complete supported still image'):
                    figures.split_figures(self.workspace, request)
        self.assertTrue(all(asset['source'].get('operation') != 'figure-crop' for asset in self.workspace.snapshot()['assets']))

    def test_damaged_png_chunk_crc_is_refused_before_children(self):
        stream = io.BytesIO(); Image.new('RGB', (10, 10), 'red').save(stream, 'PNG')
        raw = bytearray(stream.getvalue()); at = raw.index(b'IDAT')
        size = int.from_bytes(raw[at-4:at], 'big'); raw[at+4+size] ^= 1
        parent = self.parent(raw=bytes(raw))
        request = self.command(parent, [{'x': 0, 'y': 0, 'width': 10000, 'height': 10000}])
        with self.assertRaisesRegex(server.WorkspaceError, 'complete supported still image'):
            figures.split_figures(self.workspace, request)
        self.assertEqual(len(self.workspace.snapshot()['assets']), 1)

    def test_bytes_after_first_iend_are_refused_even_if_a_second_iend_is_terminal(self):
        stream = io.BytesIO(); Image.new('RGB', (10, 10), 'red').save(stream, 'PNG')
        raw = stream.getvalue()
        # Pillow.verify stops at the first IEND. A suffix-only check can therefore
        # be bypassed by appending arbitrary bytes followed by another canonical IEND.
        forged = raw + b'ignored-after-real-iend' + raw[-12:]
        parent = self.parent(raw=forged)
        request = self.command(parent, [{'x': 0, 'y': 0, 'width': 10000, 'height': 10000}])
        with self.assertRaisesRegex(server.WorkspaceError, 'complete supported still image'):
            figures.split_figures(self.workspace, request)
        self.assertEqual(len(self.workspace.snapshot()['assets']), 1)

    def test_shared_raster_boundaries_are_canonical_for_small_sources(self):
        for width in range(1, 35):
            for edge in (1, 2499, 2500, 4999, 5000, 5001, 7500, 9999):
                expected = (edge * width + 5000) // 10000
                if expected in (0, width): continue  # empty halves are explicitly refused
                left = figures._pixel_box(self.workspace, {'x': 0, 'y': 0, 'width': edge, 'height': 10000}, width, 1)
                right = figures._pixel_box(self.workspace, {'x': edge, 'y': 0, 'width': 10000-edge, 'height': 10000}, width, 1)
                self.assertEqual(left['right'], expected); self.assertEqual(right['left'], expected)


if __name__ == '__main__': unittest.main()
