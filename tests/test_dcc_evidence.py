import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from PIL import Image
from studio_workflow.core import canonical, digest
from studio_workflow.research_intake import sha
from studio_workflow import dcc_evidence as de


def scene():
    return {'format': 'studio.dcc-scene/v1', 'complete': True,
            'runtime': {'version': 'synthetic-not-blender'}, 'limitations': ['synthetic fixture'],
            'content': {'objects': {'Cube': {'vertices': 8, 'topology_sha256': 'a' * 64}},
                        'images': {}, 'actions': {}}, 'findings': []}


def bundle(root, color=(50, 100, 150, 255)):
    root.mkdir()
    (root / 'scene.json').write_bytes(canonical(scene()))
    views = {}
    for name in ('front', 'profile'):
        path = root / (name + '.png'); Image.new('RGBA', (8, 8), color).save(path)
        views[name] = {'path': path.name, 'sha256': sha(path.read_bytes())}
    document = {'format': 'studio.dcc-evidence/v1',
                'capture_contract': {'view_ids': ['front', 'profile'], 'resolution': [8, 8],
                                     'camera_rig_sha256': 'c' * 64,
                                     'render_settings': {'engine': 'synthetic', 'frame': 1}},
                'scene': {'path': 'scene.json', 'sha256': sha((root / 'scene.json').read_bytes())},
                'views': views, 'scope': 'synthetic_fixture'}
    (root / 'evidence.json').write_bytes(canonical(document))
    return document


def save(root, doc):
    (root / 'evidence.json').write_bytes(canonical(doc))


def png_chunk(kind, content):
    return (struct.pack('>I', len(content)) + kind + content
            + struct.pack('>I', zlib.crc32(kind + content) & 0xffffffff))


def truecolor_png(depth, alpha, sample):
    # Real PNG framing/sample bytes, independent of Pillow's RGB8 writer.
    pixel = (sample, 0, 0) + ((2**depth - 1,) if alpha else ())
    row = b'\0' + struct.pack('>' + ('H' if depth == 16 else 'B') * len(pixel), *pixel) * 8
    return (b'\x89PNG\r\n\x1a\n'
            + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, depth, 6 if alpha else 2, 0, 0, 0))
            + png_chunk(b'IDAT', zlib.compress(row * 8)) + png_chunk(b'IEND', b''))


class EvidenceTests(unittest.TestCase):
    def compare(self, a, b, **kw):
        return de.compare_bundles(a, b, ['front', 'profile'], ['profile'], **kw)

    def test_same_count_connectivity_change_detected(self):
        other = scene(); other['content']['objects']['Cube']['topology_sha256'] = 'b' * 64
        result = de.compare_scenes(scene(), other)
        self.assertFalse(result['equal'])
        self.assertIn('/objects/Cube/topology_sha256', [r['path'] for r in result['changes']])

    def test_order_and_runtime_identity_not_geometry_change(self):
        before = scene(); before['content']['objects']['Other'] = {'vertices': 4}
        after = copy.deepcopy(before)
        after['content']['objects'] = dict(reversed(list(after['content']['objects'].items())))
        after['runtime']['version'] = 'different-runtime'
        self.assertTrue(de.compare_scenes(before, after)['equal'])

    def test_unchanged_synthetic_evidence_not_art_or_native_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); bundle(b)
            result = self.compare(a, b)
            self.assertEqual(result['status'], 'within_declared_tolerance')
            self.assertEqual(result['acceptance']['artistic'], 'not_evaluated')
            self.assertEqual(result['acceptance']['native_execution'], 'not_attested')
            self.assertFalse(result['baseline_promoted'])
            self.assertEqual(result['views']['profile']['role'], 'holdout')

    def test_one_changed_pixel_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
            path = b / 'front.png'
            with Image.open(path) as image:
                image.putpixel((0, 0), (51, 100, 150, 255)); image.save(path)
            doc['views']['front']['sha256'] = sha(path.read_bytes()); save(b, doc)
            result = self.compare(a, b)
            self.assertEqual(result['status'], 'different')
            self.assertEqual(result['views']['front']['max_channel_delta'], 1)
            self.assertEqual(result['views']['front']['changed_pixel_fraction'], 1 / 64)
            self.assertEqual(self.compare(a, b, max_channel_delta=1)['status'], 'within_declared_tolerance')

    def test_16_bit_truecolor_pngs_cannot_match_after_silent_reduction(self):
        for alpha in (False, True):
            with self.subTest(alpha=alpha), tempfile.TemporaryDirectory() as tmp:
                # The supported 8-bit contract still observes a one-unit change.
                control = de._image_delta(truecolor_png(8, alpha, 128), truecolor_png(8, alpha, 129), [8, 8])
                self.assertEqual(control['max_channel_delta'], 1)
                a, b = Path(tmp) / 'a', Path(tmp) / 'b'
                ad, bd = bundle(a), bundle(b)
                raw_a, raw_b = truecolor_png(16, alpha, 32768), truecolor_png(16, alpha, 33023)
                for root, doc, raw in ((a, ad, raw_a), (b, bd, raw_b)):
                    (root / 'front.png').write_bytes(raw)
                    doc['views']['front']['sha256'] = sha(raw); save(root, doc)
                with self.assertRaisesRegex(ValueError, '8-bit'):
                    self.compare(a, b)
                self.assertEqual((a / 'front.png').read_bytes(), raw_a)
                self.assertEqual((b / 'front.png').read_bytes(), raw_b)

    def test_ambiguous_ihdr_layout_cannot_bypass_the_png_contract(self):
        for depth in (8, 16):
            for alpha in (False, True):
                raw = truecolor_png(depth, alpha, 128 if depth == 8 else 32768)
                # Pillow accepts both layouts. The extra 8-bit IHDR can hide a
                # later 16-bit IHDR from a guard that trusts only byte offset 24.
                extra_header = png_chunk(b'IHDR', raw[16:24] + b'\x08' + raw[25:29])
                for name, prefix in (('leading metadata', png_chunk(b'tEXt', b'note\0fixture')),
                                     ('repeated IHDR', extra_header)):
                    with self.subTest(depth=depth, alpha=alpha, layout=name), tempfile.TemporaryDirectory() as tmp:
                        a, b = Path(tmp) / 'a', Path(tmp) / 'b'
                        bundle(a, (128, 0, 0, 255)); doc = bundle(b, (128, 0, 0, 255))
                        ambiguous = raw[:8] + prefix + raw[8:]
                        (b / 'front.png').write_bytes(ambiguous)
                        doc['views']['front']['sha256'] = sha(ambiguous); save(b, doc)
                        with self.assertRaisesRegex(ValueError, 'IHDR'):
                            self.compare(a, b)
                        self.assertEqual((b / 'front.png').read_bytes(), ambiguous)

    def test_unsupported_png_depth_and_layout_refuse_before_pixel_decode(self):
        high_depth = truecolor_png(16, True, 32768)
        rgb8 = truecolor_png(8, False, 128)
        repeated = rgb8[:33] + rgb8[8:]
        for raw in (high_depth, repeated):
            with self.subTest(header=raw[8:33]), patch('PIL.PngImagePlugin.PngImageFile.load',
                    side_effect=AssertionError('Unsupported source must not inflate pixels')) as load:
                with self.assertRaises(ValueError):
                    de._pixels(raw, [8, 8])
                load.assert_not_called()

    def test_missing_holdout_is_incomplete_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
            del doc['views']['profile']; save(b, doc)
            self.assertEqual(self.compare(a, b)['status'], 'incomplete')

    def test_camera_contract_mismatch_is_incomparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
            doc['capture_contract']['camera_rig_sha256'] = 'e' * 64; save(b, doc)
            self.assertEqual(self.compare(a, b)['status'], 'incomparable')

    def test_tampering_rejected_before_image_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); bundle(b)
            (b / 'profile.png').write_bytes(b'invalid')
            with self.assertRaisesRegex(ValueError, 'hash'): self.compare(a, b)

    def test_escape_absolute_and_windows_paths_rejected(self):
        for name in ('../secret.png', '/tmp/a.png', 'C:/a.png', 'sub\\a.png', 'a//b.png'):
            with self.subTest(path=name), tempfile.TemporaryDirectory() as tmp:
                a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
                doc['views']['front']['path'] = name; save(b, doc)
                with self.assertRaises(ValueError): self.compare(a, b)

    def test_symlink_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); bundle(b)
            (b / 'front.png').unlink()
            try: (b / 'front.png').symlink_to(a / 'front.png')
            except OSError: self.skipTest('Symlinks unavailable')
            with self.assertRaises(ValueError): self.compare(a, b)

    def test_empty_required_or_holdout_and_invalid_tolerance_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); bundle(b)
            for required, holdout in (([], []), (['front'], []), (['front'], ['profile']),
                                      (['front', 'front'], ['front'])):
                with self.assertRaises(ValueError): de.compare_bundles(a, b, required, holdout)
            for number in (True, -1, 256, float('nan'), 0.5):
                with self.assertRaises(ValueError): self.compare(a, b, max_channel_delta=number)

    def test_declared_resolution_cannot_mask_resized_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
            Image.new('RGBA', (4, 4)).save(b / 'front.png')
            doc['views']['front']['sha256'] = sha((b / 'front.png').read_bytes()); save(b, doc)
            with self.assertRaisesRegex(ValueError, 'resolution'): self.compare(a, b)

    def test_incomplete_scene_cannot_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
            s = scene(); s['complete'] = False
            (b / 'scene.json').write_bytes(canonical(s))
            doc['scene']['sha256'] = sha((b / 'scene.json').read_bytes()); save(b, doc)
            self.assertEqual(self.compare(a, b)['status'], 'incomplete')

    def test_known_findings_prevent_technical_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'; bundle(a); doc = bundle(b)
            s = scene(); s['findings'] = [{'code': 'missing_external_image', 'id': 'Texture'}]
            (b / 'scene.json').write_bytes(canonical(s))
            doc['scene']['sha256'] = sha((b / 'scene.json').read_bytes()); save(b, doc)
            self.assertEqual(self.compare(a, b)['status'], 'different')


class ProbeIntentTests(unittest.TestCase):
    def setup_files(self, root):
        exe = root / 'Blender portable.exe'; exe.write_bytes(b'fake-test-executable')
        asset = root / 'fixture.blend'; asset.write_bytes(b'fake-test-asset')
        cfg = root / 'local.json'; cfg.write_text(json.dumps({'blender': str(exe)}))
        return cfg, exe, asset

    def test_content_pinned_plan_does_not_execute_or_write_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cfg, exe, asset = self.setup_files(root)
            result = de.probe_intent(cfg, asset, root / 'run')
            self.assertFalse(result['executable'])
            self.assertFalse(result['process_started'])
            self.assertEqual(result['argv'][0], str(exe))
            self.assertIn('--disable-autoexec', result['argv'])
            self.assertEqual(result['source']['sha256'], sha(asset.read_bytes()))
            other = dict(result); checksum = other.pop('plan_sha256')
            self.assertEqual(checksum, digest(other))
            self.assertFalse((root / 'run').exists())

    def test_byte_change_changes_intent_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cfg, exe, asset = self.setup_files(root)
            before = de.probe_intent(cfg, asset, root / 'run')
            exe.write_bytes(b'another-test-executable')
            after = de.probe_intent(cfg, asset, root / 'run')
            self.assertNotEqual(before['plan_sha256'], after['plan_sha256'])

    def test_missing_configuration_and_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cfg, exe, asset = self.setup_files(root)
            with self.assertRaises(ValueError): de.probe_intent(cfg, asset, root)
            cfg.write_text('{}')
            with self.assertRaises(ValueError): de.probe_intent(cfg, asset, root / 'run')

    def test_relative_executable_is_not_resolved_via_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); cfg, exe, asset = self.setup_files(root)
            cfg.write_text('{"blender":"blender"}')
            with self.assertRaises(ValueError): de.probe_intent(cfg, asset, root / 'run')
