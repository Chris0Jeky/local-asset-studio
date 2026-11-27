"""Export regressions use synthetic fixtures; no generation or native import."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import export_guard
import fixtures
import pack_export
import pipeline


class ExportGuardTests(unittest.TestCase):
    def setUp(self):
        runtime = pipeline.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'store' / 'packs' / 'p36-fixture'
        self.metadata = fixtures.metadata()

    def reused_family(self, *, earlier='yes', later='yes', change=None, omit_source=False,
                      different_asset=False):
        family = pipeline.create_family('p36-fixture', 'a' * 32, 'p36-fixture',
                                        fixtures.policy(), mode='synthetic')
        for stage in pipeline.STAGES:
            receipt = fixtures.stage_receipt(family, stage, self.assets)
            if stage == 'concept':
                artifact = receipt['payload']['artifacts'][0]
                artifact['licence']['commercial'] = earlier
                if omit_source:
                    artifact.pop('source')
            if stage == 'unreal':
                artifact = copy.deepcopy(family['receipts'][family['heads']['concept']]['payload']['artifacts'][0])
                artifact['key'] = 'reused-concept'
                artifact['licence']['commercial'] = later
                if different_asset:
                    artifact['asset_id'] = 'fixture-another-workspace-asset'
                if change:
                    change(artifact)
                receipt['payload']['artifacts'].append(artifact)
            for dimension, state, actor in [('generation', 'completed', 'fixture'),
                                            ('inspection', 'inspected', 'fixture'),
                                            ('acceptance', 'accepted', 'owner')]:
                receipt = pipeline.attest(receipt, dimension, state, actor, 'fixture:export-guard-test')
            family = pipeline.record_receipt(family, receipt)
        return family

    def assert_conflict(self, family, code='artifact_provenance_conflict'):
        before = pipeline.canonical_bytes(family)
        with patch.object(export_guard, '_build_manifest') as downstream:
            with self.assertRaises(pipeline.PipelineError) as caught:
                export_guard.build_guarded_manifest(family, self.assets, self.metadata)
        self.assertEqual(caught.exception.code, code)
        downstream.assert_not_called()
        self.assertEqual(pipeline.canonical_bytes(family), before)

    def test_reproduces_upstream_commercial_fact_loss_and_refuses_it(self):
        family = self.reused_family(earlier='yes', later='no')
        original = pack_export.build_manifest(family, self.assets, self.metadata)
        self.assertEqual(original['files']['concept-front']['commercial'], 'yes')
        later = family['receipts'][family['heads']['unreal']]['payload']['artifacts'][-1]
        self.assertEqual(later['licence']['commercial'], 'no')
        self.assert_conflict(family)

    def test_all_unequal_commercial_declarations_refuse_in_both_orders(self):
        for earlier, later in [('yes', 'unknown'), ('unknown', 'yes'), ('no', 'yes'),
                               ('no', 'unknown'), ('unknown', 'no')]:
            with self.subTest(earlier=earlier, later=later):
                self.assert_conflict(self.reused_family(earlier=earlier, later=later))

    def test_source_terms_name_restrictions_and_extra_licence_facts_cannot_disappear(self):
        changes = {
            'artifact_source': lambda a: a.update(source='fixture:another-source'),
            'terms_source': lambda a: a['licence'].update(source='fixture:other-terms'),
            'licence_name': lambda a: a['licence'].update(name='Different terms'),
            'restrictions': lambda a: a['licence'].update(restrictions='No redistribution'),
            'extra_fact': lambda a: a['licence'].update(territory='Recorded clause; not a user assumption'),
        }
        for field, change in changes.items():
            with self.subTest(field=field):
                self.assert_conflict(self.reused_family(change=change))

    def test_missing_source_compares_the_effective_workspace_asset_locator(self):
        family = self.reused_family(omit_source=True)
        pack = export_guard.build_guarded_manifest(family, self.assets, self.metadata)
        self.assertEqual(pack['files']['concept-front']['source'],
                         'studio-workspace:' + family['workspace_id'] + '/asset/fixture-concept-front')
        self.assert_conflict(self.reused_family(omit_source=True, different_asset=True))

    def test_same_path_with_changed_digest_size_or_case_refuses_before_byte_reads(self):
        changes = [lambda a: a.update(sha256='b' * 64),
                   lambda a: a.update(bytes=a['bytes'] + 1),
                   lambda a: a.update(path='Concept/front.png')]
        for change in changes:
            with self.subTest(change=change):
                self.assert_conflict(self.reused_family(change=change), 'artifact_content_conflict')

    def test_consistent_reuse_keeps_exact_family_and_file_facts(self):
        family = self.reused_family(earlier='unknown', later='unknown')
        before_family = pipeline.canonical_bytes(family)
        before_metadata = pipeline.canonical_bytes(self.metadata)
        original = pack_export.build_manifest(family, self.assets, self.metadata)
        guarded = export_guard.build_guarded_manifest(family, self.assets, self.metadata)
        self.assertEqual(guarded['files'], original['files'])
        self.assertEqual(guarded['models'], original['models'])
        ext = guarded['x-studio-character-pipeline']
        self.assertEqual(ext['family_sha256'], pipeline.digest(family))
        self.assertEqual(ext['concept_receipt'], family['heads']['concept'])
        self.assertEqual(ext['stage_receipts'], family['heads'])
        self.assertEqual(ext['consumer_admission']['source_metadata_sha256'], pipeline.digest(self.metadata))
        self.assertEqual(pipeline.canonical_bytes(family), before_family)
        self.assertEqual(pipeline.canonical_bytes(self.metadata), before_metadata)
        self.assertEqual(guarded['files']['concept-front']['commercial'], 'unknown')

    def test_draft_declares_required_staging_without_inventing_joined_or_rig_proof(self):
        family = fixtures.build_fixture(self.assets)
        pack = export_guard.build_guarded_manifest(family, self.assets, self.metadata)
        self.assertEqual(pack['status'], 'draft')
        self.assertNotIn('joined', pack['models']['glb'])
        ext = pack['x-studio-character-pipeline']
        self.assertEqual(ext['unreal_import'], 'planned')
        self.assertFalse(ext['perceptual_identity_verified'])
        admission = ext['consumer_admission']
        self.assertFalse(admission['current_direct_import_allowed'])
        self.assertTrue(admission['staged_validator_required'])
        self.assertEqual(admission['state'], 'staged_validation_required')
        self.assertEqual(admission['rig_compatibility'], 'unverified')
        self.assertEqual(admission['joined_topology'], 'unverified')
        self.assertEqual(admission['native_import_state'], 'not_executed_by_exporter')

    def test_guarded_manifest_passes_exact_pack_v1_schema(self):
        import jsonschema
        family = fixtures.build_fixture(self.assets)
        pack = export_guard.build_guarded_manifest(family, self.assets, self.metadata)
        schema = json.loads(Path(pack_export.__file__).with_name('lumenfold.pack.schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(pack)

    def test_rejected_identity_and_uncertain_generation_still_block(self):
        for dimension, state, actor in [('acceptance', 'rejected', 'owner'),
                                        ('generation', 'uncertain', 'fixture')]:
            with self.subTest(dimension=dimension):
                family = fixtures.build_fixture(self.assets)
                receipt = family['receipts'][family['heads']['unreal']]
                receipt = pipeline.attest(receipt, dimension, state, actor, 'fixture:blocked')
                family['receipts'][receipt['id']] = receipt
                family['heads']['unreal'] = receipt['id']
                with self.assertRaisesRegex(pipeline.PipelineError, 'Export blocked'):
                    export_guard.build_guarded_manifest(family, self.assets, self.metadata)

    def test_changed_bytes_cannot_use_cached_green_receipts(self):
        family = fixtures.build_fixture(self.assets)
        artifact = family['receipts'][family['heads']['concept']]['payload']['artifacts'][0]
        path = self.assets / artifact['path']
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(pipeline.PipelineError, 'byte count|digest'):
            export_guard.build_guarded_manifest(family, self.assets, self.metadata)

    def test_release_still_refuses_synthetic_family(self):
        family = fixtures.build_fixture(self.assets)
        with self.assertRaisesRegex(pipeline.PipelineError, 'synthetic'):
            export_guard.build_guarded_manifest(family, self.assets, self.metadata,
                                                release=True, intended_use='commercial-game')

    def test_supplied_lumenfold_validator_checks_real_fixture_bytes(self):
        root = os.environ.get('P36_LUMENFOLD_ROOT')
        if not root:
            self.skipTest('Set P36_LUMENFOLD_ROOT to a trusted source snapshot for consumer comparison')
        validator = Path(root) / 'pipelines' / 'characters' / 'validate_pack.py'
        self.assertTrue(validator.is_file(), 'Supplied consumer validator is missing')
        spec = importlib.util.spec_from_file_location('p36_consumer_validate_pack', validator)
        consumer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(consumer)
        consumer.ROOT = self.root / 'store'
        family = fixtures.build_fixture(self.assets)
        pack = export_guard.build_guarded_manifest(family, self.assets, self.metadata)
        self.assertEqual(consumer.validate_doc(pack, pack['id'], False, check_files=True), [])
        artifact = family['receipts'][family['heads']['concept']]['payload']['artifacts'][0]
        (self.assets / artifact['path']).write_bytes(b'stale')
        self.assertTrue(consumer.validate_doc(pack, pack['id'], False, check_files=True))


if __name__ == '__main__':
    unittest.main()
