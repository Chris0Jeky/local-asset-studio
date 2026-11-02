import copy
import json
from pathlib import Path
import tempfile
import unittest

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
