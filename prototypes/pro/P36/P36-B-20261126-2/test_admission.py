"""Admission regressions use real SQLite and files; fixtures are synthetic only."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import attempt_ledger
import authority_fixtures
import fixtures
import pipeline as p
from admission_fixtures import manufactured_production_declarations, semantic_inputs

try:
    import admission
except ModuleNotFoundError as error:
    if error.name != 'admission':
        raise
    admission = None


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.c = authority_fixtures.make_workspace(self.root / 'case')
        self.policy, self.annotations = semantic_inputs(self.c)
        self.ledger = self.root / 'attempts.sqlite3'
        attempt_ledger.initialize(self.ledger)
        self.metadata = fixtures.metadata()

    def check(self, stage='mesh', **changes):
        self.assertIsNotNone(admission, 'The integrated admission boundary must be implemented')
        args = {'asset_root': self.c['asset_root'], 'semantic_policy': self.policy,
                'annotations': self.annotations, 'ledger_path': self.ledger}
        args.update(changes)
        return admission.check_transition(self.c['experiments'], self.c['family'], self.c['binding'], stage, **args)

    def export(self, out=None, **changes):
        self.assertIsNotNone(admission, 'The staged export boundary must be implemented')
        args = {'asset_root': self.c['asset_root'], 'semantic_policy': self.policy,
                'annotations': self.annotations, 'ledger_path': self.ledger}
        args.update(changes)
        return admission.export_verified_bundle(self.c['experiments'], self.c['family'], self.c['binding'],
                                                 self.metadata, out or self.root / 'bundle', **args)

    def edit(self, statement, parameters=()):
        with self.c['workspace'].connection() as db:
            db.execute(statement, parameters)

    def assert_blocked(self, result, code=None):
        self.assertFalse(result['passed'], result)
        self.assertFalse(result['generation_submitted'])
        if code:
            self.assertIn(code, {block['code'] for block in result['blockers']}, result)

    def test_actual_workspace_transition_passes_without_mutation_or_submission(self):
        before = self.c['workspace'].snapshot()
        report = self.check()
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['action'], 'prepare-only')
        self.assertEqual(report['evidence_state'], 'implemented')
        self.assertFalse(report['generation_submitted'])
        self.assertEqual(report['selected_stages'], ['concept', 'turnaround', 'expressions', 'outfits'])
        self.assertEqual(report['ledger_stages'], ['concept', 'turnaround', 'expressions', 'outfits', 'mesh'])
        self.assertEqual(report['input_fingerprints']['family_sha256'], p.digest(self.c['family']))
        self.assertEqual(report, self.check())
        self.assertEqual(before, self.c['workspace'].snapshot())

    def test_withdrawn_acceptance_blocks_after_a_green_result(self):
        self.assertTrue(self.check()['passed'])
        self.edit('UPDATE asset_acceptances SET withdrawn_at=2 WHERE id=?', ('test-concept-front',))
        self.assert_blocked(self.check(), 'acceptance_withdrawn')

    def test_one_semantic_side_swap_vetoes_a_perfect_numeric_proxy(self):
        self.assertTrue(p.next_gate(self.c['family'], 'mesh', asset_root=self.c['asset_root'])['passed'])
        self.annotations['turnaround']['views'][0]['anchors']['left-iris']['value'] = 'blue'
        report = self.check()
        self.assert_blocked(report, 'semantic_identity_failed')
        self.assertTrue(any('semantic_mismatch' in item for item in report['semantic']['turnaround']['blockers']))

    def test_changed_source_bytes_block_after_a_green_result(self):
        self.assertTrue(self.check()['passed'])
        family = self.c['family']
        artifact = family['receipts'][family['heads']['concept']]['payload']['artifacts'][0]
        path = self.c['asset_root'] / artifact['path']
        path.write_bytes(path.read_bytes() + b'changed')
        self.assert_blocked(self.check(), 'media_verification_failed')

    def test_stale_binding_and_stale_semantic_concept_fail_closed(self):
        original = copy.deepcopy(self.c['binding'])
        self.c['binding']['stages']['concept']['receipt_id'] = 'f' * 64
        self.assert_blocked(self.check(), 'invalid_contract')
        self.c['binding'] = original
        self.annotations['turnaround']['concept']['receipt_digest'] = 'e' * 64
        self.assert_blocked(self.check(), 'semantic_identity_failed')

    def test_no_output_uncertain_attempt_blocks_target_absent_from_family(self):
        self.c = authority_fixtures.make_workspace(self.root / 'early', through='turnaround')
        self.policy, self.annotations = semantic_inputs(self.c)
        self.assertTrue(self.check('expressions')['passed'])
        attempt_ledger.reserve(self.ledger, family_id=self.c['family']['family_id'], stage='expressions',
                               request_id='test-no-output', job_id='unobserved-job', intent_sha256='c' * 64,
                               experiments=self.c['experiments'], workspace_id=self.c['family']['workspace_id'])
        self.assertFalse((self.c['experiments'] / 'runs' / 'unobserved-job').exists())
        self.assert_blocked(self.check('expressions'), 'uncertain_submission')

    def test_cached_report_and_unknown_annotation_method_are_never_admission_inputs(self):
        self.annotations['turnaround']['method'] = 'unrecognized_automatic_score'
        self.assert_blocked(self.check(), 'semantic_identity_failed')
        self.annotations['turnaround'] = {'passed': True, 'score': 1.0, 'policy_digest': 'a' * 64}
        self.assert_blocked(self.check(), 'semantic_identity_failed')

    def test_full_active_annotation_inventory_is_required(self):
        self.annotations.pop('toon')
        self.assert_blocked(self.check(), 'invalid_contract')

    def test_production_cannot_use_fixture_truth_semantic_labels(self):
        self.c = manufactured_production_declarations(self.c)
        self.policy, self.annotations = semantic_inputs(self.c)
        report = self.check()
        self.assert_blocked(report, 'synthetic_semantic_provenance')

    def test_target_receipt_is_checked_for_export_in_addition_to_ancestors(self):
        self.annotations['unreal']['views'][0]['anchors']['braid-side']['value'] = 'subject-right'
        self.assertTrue(self.check('unreal')['passed'])
        self.assert_blocked(self.check('unreal', include_target=True), 'semantic_identity_failed')

    def test_malformed_arguments_return_failed_reports(self):
        for options in ({'include_target': 'true'}, {'annotations': []}, {'semantic_policy': {'passed': True}}):
            with self.subTest(options=options):
                self.assert_blocked(self.check(**options))
        self.c['family'] = {'schema': 'wrong'}
        self.assert_blocked(self.check(), 'invalid_contract')

    def test_malformed_unicode_diagnostics_return_a_serializable_failed_report(self):
        report = self.check('\ud800')
        self.assert_blocked(report, 'invalid_contract')
        self.assertIsInstance(p.canonical_bytes(report), bytes)

    def test_successful_bundle_copies_verified_bytes_and_preserves_contract(self):
        import jsonschema
        out = self.root / 'bundle'
        report = self.export(out)
        self.assertTrue(report['passed'], report)
        self.assertTrue(report['ready'])
        self.assertTrue((out / 'READY.json').is_file())
        self.assertTrue((out / 'PARTIAL.json').is_file())
        self.assertEqual(p.load_json(out / 'family.json'), self.c['family'])
        manifest = p.load_json(out / 'pack.json')
        schema = p.load_json(Path(p.__file__).with_name('lumenfold.pack.schema.json'))
        jsonschema.Draft202012Validator(schema).validate(manifest)
        self.assertEqual(manifest['status'], 'draft')
        self.assertFalse(manifest['x-studio-character-pipeline']['consumer_admission']['current_direct_import_allowed'])
        for record in manifest['files'].values():
            target = out / 'assets' / 'packs' / manifest['id'] / record['path']
            self.assertEqual(target.stat().st_size, record['bytes'])
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), record['sha256'])
        ready = p.load_json(out / 'READY.json')
        self.assertEqual(ready['pack_sha256'], p.digest(manifest))
        self.assertEqual(ready['family_sha256'], p.digest(self.c['family']))
        self.assertFalse(ready['generation_submitted'])
        self.assertFalse(ready['native_import_performed'])

    def test_existing_destination_is_refused_without_overwrite_or_retry(self):
        out = self.root / 'bundle'
        self.assertTrue(self.export(out)['passed'])
        before = {str(path.relative_to(out)): path.read_bytes() for path in out.rglob('*') if path.is_file()}
        self.assert_blocked(self.export(out), 'destination_exists')
        after = {str(path.relative_to(out)): path.read_bytes() for path in out.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_authority_change_during_real_copy_retains_partial_and_blocks_ready(self):
        out = self.root / 'bundle'
        original = admission._copy_asset
        changed = False
        def withdraw(*args, **kwargs):
            nonlocal changed
            result = original(*args, **kwargs)
            if not changed:
                changed = True
                self.edit('UPDATE asset_acceptances SET withdrawn_at=2 WHERE id=?', ('test-concept-front',))
            return result
        with patch.object(admission, '_copy_asset', side_effect=withdraw):
            report = self.export(out)
        self.assert_blocked(report)
        self.assertTrue(report['partial_retained'])
        self.assertTrue((out / 'PARTIAL.json').is_file())
        self.assertFalse((out / 'READY.json').exists())
        self.assertTrue(any(path.is_file() for path in (out / 'assets').rglob('*')))

    def test_mutated_input_during_copy_cannot_write_ready(self):
        out = self.root / 'bundle'
        original = admission._copy_asset
        changed = False
        def mutate(*args, **kwargs):
            nonlocal changed
            result = original(*args, **kwargs)
            if not changed:
                changed = True
                self.metadata['notes'] = 'Changed after plan'
            return result
        with patch.object(admission, '_copy_asset', side_effect=mutate):
            report = self.export(out)
        self.assert_blocked(report, 'inputs_changed')
        self.assertFalse((out / 'READY.json').exists())
        self.assertTrue((out / 'PARTIAL.json').is_file())

    def test_withdrawal_during_last_copy_verification_cannot_write_ready(self):
        out = self.root / 'bundle'
        original = admission._verify_copied
        calls = 0
        def withdraw(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 2:
                self.edit('UPDATE asset_acceptances SET withdrawn_at=2 WHERE id=?', ('test-concept-front',))
            return result
        with patch.object(admission, '_verify_copied', side_effect=withdraw):
            report = self.export(out)
        self.assert_blocked(report)
        self.assertFalse((out / 'READY.json').exists())

    def test_changed_cli_input_file_during_copy_cannot_write_ready(self):
        inputs = {'family': self.c['family'], 'binding': self.c['binding'], 'metadata': self.metadata,
                  'semantic_policy': self.policy, 'annotations': self.annotations}
        paths = {}
        for name, value in inputs.items():
            paths[name] = self.root / (name + '.json')
            paths[name].write_bytes(p.canonical_bytes(value))
        original = admission._copy_asset
        changed = False
        def mutate(*args, **kwargs):
            nonlocal changed
            result = original(*args, **kwargs)
            if not changed:
                changed = True
                value = copy.deepcopy(self.metadata)
                value['notes'] = 'Input file changed; in-memory metadata stayed unchanged'
                paths['metadata'].write_bytes(p.canonical_bytes(value))
            return result
        with patch.object(admission, '_copy_asset', side_effect=mutate):
            report = self.export(_input_files=paths)
        self.assert_blocked(report, 'inputs_changed')
        self.assertFalse((self.root / 'bundle' / 'READY.json').exists())

    def test_changed_cli_input_file_during_final_authority_capture_cannot_write_ready(self):
        inputs = {'family': self.c['family'], 'binding': self.c['binding'], 'metadata': self.metadata,
                  'semantic_policy': self.policy, 'annotations': self.annotations}
        paths = {}
        for name, value in inputs.items():
            paths[name] = self.root / (name + '.json')
            paths[name].write_bytes(p.canonical_bytes(value))
        original = admission.check_transition
        calls = 0
        def mutate(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 2:
                changed = copy.deepcopy(self.metadata)
                changed['notes'] = 'CLI metadata changed during the last live capture'
                paths['metadata'].write_bytes(p.canonical_bytes(changed))
            return result
        with patch.object(admission, 'check_transition', side_effect=mutate):
            report = self.export(_input_files=paths)
        self.assertEqual(calls, 2)
        self.assert_blocked(report, 'inputs_changed')
        self.assertFalse((self.root / 'bundle' / 'READY.json').exists())
        self.assertTrue((self.root / 'bundle' / 'PARTIAL.json').is_file())

    def test_corrupt_ledger_is_a_failed_report(self):
        self.ledger.write_bytes(b'not a SQLite database')
        self.assert_blocked(self.check(), 'attempt_ledger_unavailable')

    def test_cli_preflight_and_export_use_explicit_input_files(self):
        documents = {'family': self.c['family'], 'binding': self.c['binding'], 'metadata': self.metadata,
                     'semantic-policy': self.policy, 'annotations': self.annotations}
        paths = {}
        for name, value in documents.items():
            paths[name] = self.root / (name + '.json')
            paths[name].write_bytes(p.canonical_bytes(value))
        common = ['--experiments', str(self.c['experiments']), '--asset-root', str(self.c['asset_root']),
                  '--ledger', str(self.ledger)]
        for name in ('family', 'binding', 'semantic-policy', 'annotations'):
            common.extend(['--' + name, str(paths[name])])
        entrypoint = [sys.executable, str(Path(admission.__file__))]
        first = subprocess.run(entrypoint + ['preflight', *common, '--stage', 'mesh'],
                               capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout[:1000])
        self.assertTrue(json.loads(first.stdout)['passed'])
        out = self.root / 'cli-bundle'
        second = subprocess.run(entrypoint + ['export', *common, '--metadata', str(paths['metadata']), '--out', str(out)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout[:1000])
        self.assertTrue(json.loads(second.stdout)['ready'])
        self.assertTrue((out / 'READY.json').is_file())

    def test_pinned_lumenfold_validator_checks_staged_copy(self):
        source = os.environ.get('P36_LUMENFOLD_ROOT')
        if not source:
            self.skipTest('Set P36_LUMENFOLD_ROOT to compare against the exact inspected consumer')
        result = self.export(lumenfold_root=source)
        self.assertTrue(result['passed'], result)
        self.assertTrue(result['consumer_validation']['passed'])
        self.assertFalse(result['consumer_validation']['native_import_performed'])

    def test_missing_ledger_and_output_outside_runtime_do_not_create_destinations(self):
        self.assert_blocked(self.check(ledger_path=self.root / 'missing.sqlite3'), 'attempt_ledger_unavailable')
        out = p.REPO_ROOT / 'not-a-runtime-export'
        self.assert_blocked(self.export(out), 'unsafe_destination')
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
