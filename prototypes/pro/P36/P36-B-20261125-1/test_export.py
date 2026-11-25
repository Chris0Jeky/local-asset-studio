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

    def production_concept_probe(self):
        """Manufactured test assertions; never evidence of actual owner acceptance."""
        production = self.p.create_family('adversarial', 'c' * 32, 'probe-character', self.family['policy'])
        r = copy.deepcopy(self.family['receipts'][self.family['heads']['concept']])
        for key in ('family_id', 'workspace_id', 'character_id', 'mode'):
            r['payload'][key] = production[key]
        r['payload']['recipe'] = {'route_id': 'test-read-only', 'controls': {}}
        for a in r['payload']['artifacts']:
            a['asset_id'] = 'test-asset'; a['source'] = 'test:manufactured-assertion'
            a['licence']['source'] = 'test:terms'
        for view in r['payload']['identity']['sheet']['views']:
            for feature in view['features'].values():
                if feature['provenance'] == 'fixture_truth': feature['provenance'] = 'human_annotated'
        for feature in r['payload']['identity']['anchor_features'].values():
            if feature['provenance'] == 'fixture_truth': feature['provenance'] = 'human_annotated'
        for dimension, state, actor in [('generation', 'completed', 'test-operator'),
                                        ('inspection', 'inspected', 'test-reviewer'),
                                        ('acceptance', 'accepted', 'owner')]:
            r = self.p.attest(r, dimension, state, actor, 'test:manufactured-assertion')
        return production, r

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
                     'owner-models/private.png', 'a/<bad>.png', 'COM¹.png', 'LPT².png',
                     'CONIN$.png', 'CONOUT$.png', 'CON .png'):
            with self.subTest(path=path), self.assertRaises(self.p.PipelineError):
                self.p.safe_relative(path)

    def test_foreign_character_metadata_cannot_be_exported(self):
        self.metadata['id'] = 'somebody-else'
        with self.assertRaises(self.p.PipelineError):
            self.exporter.build_manifest(self.family, self.assets, self.metadata)

    def test_forged_pixel_measurement_is_recomputed_from_media(self):
        bad = copy.deepcopy(self.family)
        r = copy.deepcopy(bad['receipts'][bad['heads']['unreal']])
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

    def test_operational_next_step_requires_fresh_media_even_for_synthetic_probe(self):
        artifact = next(iter(self.family['receipts'].values()))['payload']['artifacts'][0]
        (self.assets / artifact['path']).write_bytes(b'changed')
        gate = self.p.next_gate(self.family, 'unreal', asset_root=self.assets)
        self.assertFalse(gate['passed'])
        self.assertIn('media_verification_failed', [b['code'] for b in gate['blockers']])

    def test_production_stage_cannot_advance_on_metadata_alone(self):
        production, r = self.production_concept_probe()
        self.assertFalse(self.p.next_gate(production, 'turnaround')['passed'])
        # Even concept admission into a production family needs actual media.
        with self.assertRaisesRegex(self.p.PipelineError, 'media|asset root'):
            self.p.record_receipt(production, r)

    def test_schema_invalid_metadata_cannot_publish_handoff(self):
        for field, value in [('profile', {}), ('style', {'tags': []}),
                             ('voice', {}), ('animations', {}), ('versus', 'claimed')]:
            bad = copy.deepcopy(self.metadata); bad[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(self.p.PipelineError, 'schema'):
                self.exporter.build_manifest(self.family, self.assets, bad)

    def test_encoded_colour_contract_rejects_linear_or_premultiplied_images(self):
        for field, value in [('colour_space', 'linear-srgb'), ('alpha', 'premultiplied')]:
            bad = copy.deepcopy(self.family)
            r = copy.deepcopy(bad['receipts'][bad['heads']['unreal']])
            r['payload']['artifacts'][0][field] = value
            for dimension, state, actor in [('generation', 'completed', 'fixture'),
                                            ('inspection', 'inspected', 'fixture'),
                                            ('acceptance', 'accepted', 'owner')]:
                r = self.p.attest(r, dimension, state, actor, 'fixture:colour-contract')
            bad['heads']['unreal'] = r['id']; bad['receipts'][r['id']] = r
            with self.subTest(field=field), self.assertRaisesRegex(self.p.PipelineError, 'encoding'):
                self.exporter.build_manifest(bad, self.assets, self.metadata)

    def test_production_cannot_relabel_explicit_fixture_recipe(self):
        production, r = self.production_concept_probe()
        r['payload']['recipe']['fixture'] = True; r = self.p.seal(r)
        with self.assertRaisesRegex(self.p.PipelineError, 'synthetic|Synthetic|fixture'):
            self.p.record_receipt(production, r, asset_root=self.assets)

    def test_production_colour_anchor_must_be_pixel_measured(self):
        production, r = self.production_concept_probe()
        r['payload']['identity']['anchor_features']['eyes']['provenance'] = 'human_annotated'
        r = self.p.seal(r)
        with self.assertRaisesRegex(self.p.PipelineError, 'anchor|Anchor'):
            self.p.record_receipt(production, r, asset_root=self.assets)

    def test_production_quality_cannot_carry_fixture_marker(self):
        production, r = self.production_concept_probe()
        r['payload']['quality'] = [{'name': 'extra', 'outcome': 'pass', 'evidence_ref': 'fixture:claim'}]
        r = self.p.seal(r)
        with self.assertRaisesRegex(self.p.PipelineError, 'synthetic|Synthetic|fixture'):
            self.p.record_receipt(production, r, asset_root=self.assets)

    def test_production_admission_remeasures_valid_concept(self):
        production, r = self.production_concept_probe()
        admitted = self.p.record_receipt(production, r, asset_root=self.assets)
        self.assertTrue(self.p.next_gate(admitted, 'turnaround', asset_root=self.assets)['passed'])
        artifact = r['payload']['artifacts'][0]
        (self.assets / artifact['path']).write_bytes(b'changed after review')
        self.assertFalse(self.p.next_gate(admitted, 'turnaround', asset_root=self.assets)['passed'])

    def test_idempotent_production_record_still_verifies_media(self):
        production, r = self.production_concept_probe()
        admitted = self.p.record_receipt(production, r, asset_root=self.assets)
        (self.assets / r['payload']['artifacts'][0]['path']).unlink()
        with self.assertRaises(self.p.PipelineError):
            self.p.record_receipt(admitted, r, asset_root=self.assets)
        with self.assertRaises(self.p.PipelineError):
            self.p.record_receipt(admitted, r)

    def test_private_named_root_is_rejected_before_opening(self):
        for name in ('owner-models', '_owner', 'OWNER-MODELS'):
            root = self.root / name; root.mkdir(); (root / 'a.bin').write_bytes(b'public test fixture')
            with self.subTest(name=name), self.assertRaisesRegex(self.p.PipelineError, 'Private'):
                self.p.contained_file(root, 'a.bin')

    def test_glb_renamed_vrm_does_not_establish_vrm_format(self):
        source = self.assets / 'toon' / 'model.glb'; path = self.root / 'fake.vrm'
        path.write_bytes(source.read_bytes())
        with self.assertRaisesRegex(self.p.PipelineError, 'VRM extension'):
            self.exporter._model_format({'bytes': path.stat().st_size}, path)


if __name__ == '__main__': unittest.main()
