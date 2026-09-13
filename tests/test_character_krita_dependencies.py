"""Pinned dependency contracts; fake document mechanics, never native acceptance."""
import copy
import json
import unittest

import test_character_krita_session as mechanics
import test_character_krita_session_entrypoints as preparation
from integrations.krita import document_session as ds, native_edit
from scripts import character_krita_session as entrypoints
from scripts.character_study import read_json


class LiveDependencyTests(unittest.TestCase):
    def setUp(self):
        mechanics.SessionTests.setUp(self)
        self.upstream = self.root / 'upstream.json'
        self.upstream.write_text('{"source":"original"}', encoding='utf-8')
        self.dependencies = [ds.record(self.upstream)]
        self.plan['live_dependencies'] = copy.deepcopy(self.dependencies)
        self.native.write_text(json.dumps(self.plan), encoding='utf-8')
        self.request.unlink()
        ds.prepare_request(self.capture / 'snapshot.json', self.native, self.request, self.dependencies)

    def rewrite_request(self, dependencies):
        value = ds.read_json(self.request)
        value['dependencies'] = dependencies
        self.request.write_text(json.dumps(value), encoding='utf-8')

    def assert_refused(self, message='dependenc'):
        before = self.session.inspect()
        with self.assertRaisesRegex(ValueError, message):
            self.session.import_request(self.request)
        self.assertEqual(self.session.inspect(), before)
        self.assertFalse((self.package / 'live-intent.json').exists())
        self.assertFalse((self.package / 'live-result.json').exists())
        self.assertEqual(len(self.doc.nodes), 2)

    def test_removal_cannot_hide_changed_upstream(self):
        self.upstream.write_text('{"source":"changed"}', encoding='utf-8')
        self.rewrite_request([])
        self.assert_refused()

    def test_substitution_with_valid_other_file_is_refused(self):
        other = self.root / 'other.json'; other.write_text('{}', encoding='utf-8')
        self.rewrite_request([ds.record(other)])
        self.assert_refused()

    def test_changed_hash_cannot_rebind_upstream(self):
        self.upstream.write_text('{"source":"changed"}', encoding='utf-8')
        self.rewrite_request([ds.record(self.upstream)])
        self.assert_refused()

    def test_extra_records_are_refused(self):
        other = self.root / 'other.json'; other.write_text('{}', encoding='utf-8')
        self.rewrite_request(self.dependencies + [ds.record(other)])
        self.assert_refused()

    def test_duplicate_records_are_refused(self):
        self.rewrite_request(self.dependencies * 2)
        self.assert_refused()

    def test_request_builder_cannot_replace_prepared_manifest(self):
        for index, records in enumerate(([], self.dependencies * 2)):
            with self.subTest(records=records):
                output = self.root / ('forbidden-%d.json' % index)
                with self.assertRaisesRegex(ValueError, 'dependenc'):
                    ds.prepare_request(self.capture / 'snapshot.json', self.native, output, records)
                self.assertFalse(output.exists())

    def test_valid_bound_request_preserves_pixels_and_record(self):
        before = self.request.read_bytes()
        result = self.session.import_request(self.request)
        self.assertEqual(self.doc.pixelData(), self.result)
        self.assertEqual(self.request.read_bytes(), before)
        self.assertFalse(result['neural_inference'])
        self.assertFalse(result['semantic_approval'])

    def test_unchanged_manifest_still_checks_current_bytes(self):
        self.upstream.write_bytes(b'changed')
        self.assert_refused('hash changed')

    def test_legacy_package_still_reads_but_live_import_requires_reprepare(self):
        self.plan.pop('live_dependencies')
        self.native.write_text(json.dumps(self.plan), encoding='utf-8')
        native_edit.read_plan(self.native)  # File-based native reader remains compatible.
        value = ds.read_json(self.request); value['native_plan'] = ds.record(self.native)
        self.request.write_text(json.dumps(value), encoding='utf-8')
        self.assert_refused('prepar|dependenc')

    def test_omitted_argument_uses_the_manifest_instead_of_an_empty_list(self):
        output = self.root / 'default-request.json'
        value = ds.prepare_request(self.capture / 'snapshot.json', self.native, output)
        self.assertEqual(value['dependencies'], self.dependencies)

    def test_reordered_manifest_preserves_the_same_complete_set(self):
        other = self.root / 'aaa.json'; other.write_text('{}', encoding='utf-8')
        pins = self.dependencies + [ds.record(other)]
        self.plan['live_dependencies'] = pins
        self.native.write_text(json.dumps(self.plan), encoding='utf-8')
        value = ds.read_json(self.request)
        value['native_plan'] = ds.record(self.native)
        value['dependencies'] = list(reversed(pins))
        self.request.write_text(json.dumps(value), encoding='utf-8')
        self.session.import_request(self.request)
        self.assertEqual(self.doc.pixelData(), self.result)

    def test_malformed_and_oversize_manifests_fail_without_document_changes(self):
        for manifest in (None, {}, self.dependencies * 257,
                         [{'path': 'relative.json', 'sha256': 'a'*64}],
                         [{'path': str(self.upstream), 'sha256': 'not-a-hash'}],
                         [dict(self.dependencies[0], extra='untrusted')]):
            with self.subTest(manifest=repr(manifest)[:80]):
                self.rewrite_request(manifest)
                self.assert_refused()


class PreparedManifestTests(unittest.TestCase):
    setUp = preparation.RequestTests.setUp

    def test_real_protected_preparation_binds_the_entire_transitive_manifest(self):
        plan = read_json(self.package / 'native-plan.json')
        value = entrypoints.request(self.workspace, self.capture / 'snapshot.json', 'native-package', self.capture / 'request.json')
        self.assertEqual(plan.get('live_dependencies'), value['dependencies'])
        paths = {item['path'] for item in value['dependencies']}
        for path in ('plan.json', 'document.json', 'native-source.kra', 'prepared/bundle.json', 'source.png', 'revision-2/result.json'):
            self.assertIn(str((self.workspace / path).resolve()), paths)
        self.assertEqual(value['dependencies'], sorted(value['dependencies'], key=lambda item: item['path']))


class LegacyFilePackageTests(unittest.TestCase):
    def test_legacy_expected_plan_revalidates_without_adding_live_authority(self):
        import test_character_krita as fixture
        fixture.CharacterKrita.setUp(self)
        plan = read_json(self.native_plan)
        plan.pop('live_dependencies')
        self.native_plan.write_text(json.dumps(plan), encoding='utf-8')
        self.assertEqual(entrypoints.krita._expected(self.root, plan['dependencies'], bind_live_dependencies=False)[0], plan)
        # Real execute must pass the legacy comparison before its explicitly mocked install boundary.
        from unittest.mock import patch
        with patch.object(entrypoints.krita, 'install', side_effect=RuntimeError('reached verified legacy boundary')):
            with self.assertRaisesRegex(RuntimeError, 'verified legacy'):
                entrypoints.krita.execute(self.root, 'native-package', {})
        self.assertFalse((self.package / 'native-intent.json').exists())


if __name__ == '__main__':
    unittest.main()
