"""Export barriers exercise actual fixture bytes, not invented file digests."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


class ExportBootstrapTests(unittest.TestCase):
    def test_export_entrypoint_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('pack_export'),
                             'A checked Lumenfold manifest exporter is required')


class ExportTests(unittest.TestCase):
    def setUp(self):
        import pipeline
        import pack_export
        from fixtures import build_fixture, metadata
        self.p = pipeline; self.exporter = pack_export
        runtime = pipeline.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261125-1' / 'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'assets'
        self.family = build_fixture(self.assets)
        self.metadata = metadata()

    def tearDown(self): self.temp.cleanup()

    def test_draft_export_preserves_unknown_licence_and_never_claims_playable(self):
        manifest = self.exporter.build_manifest(self.family, self.assets, self.metadata)
        self.assertEqual(manifest['schema'], 'lumenfold.pack/1')
        self.assertEqual(manifest['status'], 'draft')
        self.assertEqual(manifest['models']['ue']['from'], 'glb')
        self.assertTrue(all(x['commercial'] == 'unknown' for x in manifest['files'].values()))
        ext = manifest['x-studio-character-pipeline']
        self.assertEqual(ext['mode'], 'synthetic')
        self.assertEqual(ext['evidence_state'], 'implemented')
        self.assertFalse(ext['perceptual_identity_verified'])

    def test_changed_bytes_block_export(self):
        artifact = next(iter(self.family['receipts'].values()))['payload']['artifacts'][0]
        path = self.assets / artifact['path']; path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(self.p.PipelineError, 'byte count|digest'):
            self.exporter.build_manifest(self.family, self.assets, self.metadata)

    def test_missing_bytes_block_export(self):
        artifact = next(iter(self.family['receipts'].values()))['payload']['artifacts'][0]
        (self.assets / artifact['path']).unlink()
        with self.assertRaisesRegex(self.p.PipelineError, 'Missing'):
            self.exporter.build_manifest(self.family, self.assets, self.metadata)

    def test_failed_stage_blocks_manifest_without_writing(self):
        bad = copy.deepcopy(self.family)
        r = bad['receipts'][bad['heads']['toon']]
        r['acceptance']['state'] = 'rejected'
        replacement = self.p.seal(r)
        bad['heads']['toon'] = replacement['id']; bad['receipts'][replacement['id']] = replacement
        out = self.root / 'export'
        with self.assertRaises(self.p.PipelineError):
            self.exporter.export_bundle(bad, self.assets, self.metadata, out)
        self.assertFalse(out.exists())

    def test_release_refuses_synthetic_receipts(self):
        with self.assertRaisesRegex(self.p.PipelineError, 'synthetic'):
            self.exporter.build_manifest(self.family, self.assets, self.metadata,
                                         release=True, intended_use='commercial-game')

    def test_bundle_has_replayable_sidecar_and_completion_receipt(self):
        out = self.root / 'export'
        result = self.exporter.export_bundle(self.family, self.assets, self.metadata, out)
        self.assertTrue((out / 'pack.json').is_file())
        self.assertEqual(self.p.load_json(out / 'family.json'), self.family)
        handoff = self.p.load_json(out / 'handoff.json')
        self.assertEqual(handoff['family_sha256'], self.p.digest(self.family))
        self.assertEqual(result['pack_sha256'], self.p.digest(self.p.load_json(out / 'pack.json')))
        self.assertFalse(handoff['generation_submitted'])

    def test_second_export_never_overwrites_or_retries_existing_destination(self):
        out = self.root / 'export'
        self.exporter.export_bundle(self.family, self.assets, self.metadata, out)
        before = (out / 'pack.json').read_bytes()
        with self.assertRaisesRegex(self.p.PipelineError, 'exists'):
            self.exporter.export_bundle(self.family, self.assets, self.metadata, out)
        self.assertEqual((out / 'pack.json').read_bytes(), before)

    def test_linked_asset_is_refused(self):
        artifact = next(iter(self.family['receipts'].values()))['payload']['artifacts'][0]
        path = self.assets / artifact['path']; other = self.root / 'outside.png'
        other.write_bytes(path.read_bytes()); path.unlink()
        try: path.symlink_to(other)
        except OSError: self.skipTest('Host does not permit creating symlinks')
        with self.assertRaisesRegex(self.p.PipelineError, 'Linked'):
            self.exporter.build_manifest(self.family, self.assets, self.metadata)

    def test_portable_paths_reject_traversal_windows_drives_and_reserved_names(self):
        for path in ('../escape.png', '/tmp/a', 'C:/asset.png', 'a\\b.png',
                     'a/../../b', 'CON.png', 'a/./b', 'a//b', 'a/file.png.',
                     'owner-models/private.png', 'a/<bad>.png'):
            with self.subTest(path=path), self.assertRaises(self.p.PipelineError):
                self.p.safe_relative(path)

    def test_foreign_character_metadata_cannot_be_exported(self):
        self.metadata['id'] = 'somebody-else'
        with self.assertRaises(self.p.PipelineError):
            self.exporter.build_manifest(self.family, self.assets, self.metadata)

    def test_forged_pixel_measurement_is_recomputed_from_media(self):
        bad = copy.deepcopy(self.family)
        r = bad['receipts'][bad['heads']['unreal']]
        view = r['payload']['identity']['sheet']['views'][0]
        view['features']['hair']['value'] = [82, 20, 90]
        # Small enough for the proxy threshold, but differs from actual measured bytes.
        for dimension, state, actor in [('generation', 'completed', 'fixture'),
                                        ('inspection', 'inspected', 'fixture'),
                                        ('acceptance', 'accepted', 'owner')]:
            r = self.p.attest(r, dimension, state, actor, 'fixture:changed-annotation')
        bad['heads']['unreal'] = r['id']; bad['receipts'][r['id']] = r
        with self.assertRaisesRegex(self.p.PipelineError, 'measurement'):
            self.exporter.build_manifest(bad, self.assets, self.metadata)

    def test_output_outside_runtime_is_refused_before_creation(self):
        outside = self.p.RUN_DIR / 'should-never-exist'
        with self.assertRaisesRegex(self.p.PipelineError, '.runtime'):
            self.exporter.export_bundle(self.family, self.assets, self.metadata, outside)
        self.assertFalse(outside.exists())


if __name__ == '__main__': unittest.main()
