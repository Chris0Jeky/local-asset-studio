"""Real staged-bundle mutations; all Workspace/media inputs are synthetic tests."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import admission
import admission_fixtures
import attempt_ledger
import authority_fixtures
import fixtures
import pipeline as p
import sheet_identity

try:
    import handoff_verifier as verifier
except ModuleNotFoundError as error:
    if error.name != 'handoff_verifier': raise
    verifier = None


class HandoffVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'consumer-tests'
        runtime.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=runtime)
        cls.root = Path(cls.temp.name)
        cls.c = authority_fixtures.make_workspace(cls.root / 'source')
        cls.policy, cls.annotations = admission_fixtures.semantic_inputs(cls.c)
        cls.ledger = cls.root / 'attempts.sqlite3'
        attempt_ledger.initialize(cls.ledger)
        cls.original = cls.root / 'original'
        result = admission.export_verified_bundle(cls.c['experiments'], cls.c['family'], cls.c['binding'],
            fixtures.metadata(), cls.original, asset_root=cls.c['asset_root'], semantic_policy=cls.policy,
            annotations=cls.annotations, ledger_path=cls.ledger)
        if not result['passed']: raise AssertionError(result)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.case.cleanup)
        self.bundle = Path(self.case.name) / 'bundle'
        shutil.copytree(self.original, self.bundle)

    def read(self, name): return p.load_json(self.bundle / name)
    def write(self, name, value): (self.bundle / name).write_bytes(p.canonical_bytes(value))

    def verify(self, **options):
        self.assertIsNotNone(verifier, 'Offline handoff verifier must be implemented')
        return verifier.verify_handoff(self.bundle, allow_synthetic=True, **options)

    def assert_refused(self, report):
        self.assertFalse(report['passed'], report)
        self.assertTrue(report['blockers'], report)
        self.assertFalse(report['native_import_allowed'])
        self.assertFalse(report['generation_submitted'])
        p.canonical_bytes(report)

    def rehash(self):
        """Recompute unkeyed outer hashes, without repairing false inner claims."""
        files = {'family': 'family.json', 'binding': 'binding.json', 'metadata': 'character-metadata.json',
                 'semantic_policy': 'semantic-policy.json', 'annotations': 'annotations.json'}
        docs = {key: self.read(name) for key, name in files.items()}
        hashes = {key: p.digest(value) for key, value in docs.items()}
        captured = self.read('current-authority.json')
        captured['input_fingerprints'].update(family_sha256=hashes['family'], binding_sha256=hashes['binding'],
            annotations_sha256=hashes['annotations'],
            semantic_policy_sha256=sheet_identity.semantic_policy_digest(docs['semantic_policy']))
        for key, field in [('authority', 'capture_sha256'), ('ledger', 'snapshot_sha256')]:
            value = captured[key]
            if key == 'authority':
                value.update(family_sha256=hashes['family'], binding_sha256=hashes['binding'])
            value.pop(field, None); value[field] = p.digest(value)
        captured['capture_fingerprints'] = {'authority_sha256': captured['authority']['capture_sha256'],
            'ledger_sha256': captured['ledger']['snapshot_sha256'], 'semantic_sha256': p.digest(captured['semantic'])}
        captured.pop('report_sha256', None); captured['report_sha256'] = p.digest(captured)
        self.write('current-authority.json', captured)
        pack = self.read('pack.json'); ext = pack['x-studio-character-pipeline']
        ext.update(family_sha256=hashes['family'], stage_receipts=docs['family']['heads'])
        ext['consumer_admission'].update(source_family_sha256=hashes['family'],
            source_metadata_sha256=hashes['metadata'], admission_sha256=captured['report_sha256'])
        self.write('pack.json', pack)
        ready = self.read('READY.json')
        ready.update(family_sha256=hashes['family'], pack_sha256=p.digest(pack), authority_sha256=p.digest(captured),
                     admission_sha256=captured['report_sha256'], input_fingerprints=hashes)
        self.write('READY.json', ready)
        if (self.bundle / 'READY.pending.json').exists(): self.write('READY.pending.json', ready)
        if (self.bundle / 'PARTIAL.json').exists():
            partial = self.read('PARTIAL.json'); partial.update(family_sha256=hashes['family'], pack_sha256=p.digest(pack))
            self.write('PARTIAL.json', partial)

    def test_valid_offline_bundle_is_integrity_only_and_does_not_write(self):
        before = {str(path.relative_to(self.bundle)): path.read_bytes() for path in self.bundle.rglob('*') if path.is_file()}
        report = self.verify(expected_pack_id='p36-fixture')
        self.assertTrue(report['passed'], report)
        self.assertTrue(report['integrity_verified'])
        self.assertFalse(report['current_authority_checked'])
        self.assertFalse(report['native_import_allowed'])
        self.assertFalse(report['owner_authenticated'])
        self.assertTrue(report['synthetic'])
        self.assertEqual(before, {str(path.relative_to(self.bundle)): path.read_bytes()
                                 for path in self.bundle.rglob('*') if path.is_file()})
        self.assertEqual(report, self.verify(expected_pack_id='p36-fixture'))

    def test_synthetic_requires_explicit_permission(self):
        self.assertIsNotNone(verifier)
        self.assert_refused(verifier.verify_handoff(self.bundle))

    def test_valid_explicit_current_context_is_rechecked(self):
        report = self.verify(require_current=True, experiments=self.c['experiments'], ledger_path=self.ledger)
        self.assertTrue(report['passed'], report)
        self.assertTrue(report['current_authority_checked'])
        self.assertTrue(report['current_authority_matches'])
        self.assertFalse(report['native_import_allowed'])

    def test_destination_change_during_live_check_clears_integrity_result(self):
        original = admission.check_transition
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.assertTrue(result['passed'], result)
            pack = self.read('pack.json'); record = next(iter(pack['files'].values()))
            (self.bundle / 'assets' / 'packs' / pack['id'] / record['path']).write_bytes(b'late-destination-change')
            return result
        with patch.object(admission, 'check_transition', side_effect=mutate):
            report = self.verify(require_current=True, experiments=self.c['experiments'], ledger_path=self.ledger)
        self.assert_refused(report)
        self.assertFalse(report['integrity_verified'], report)

    def test_rehashing_unchanged_claims_preserves_valid_bundle(self):
        self.rehash()
        self.assertTrue(self.verify()['passed'])

    def test_consistent_descriptive_edit_is_integrity_not_author_authentication(self):
        metadata = self.read('character-metadata.json'); metadata['display_name'] = 'Self-consistent untrusted label'
        pack = self.read('pack.json'); pack['display_name'] = metadata['display_name']
        self.write('character-metadata.json', metadata); self.write('pack.json', pack); self.rehash()
        report = self.verify()
        self.assertTrue(report['passed'], report)
        self.assertFalse(report['owner_authenticated'])
        self.assertFalse(report['native_import_allowed'])

    def test_require_current_needs_both_explicit_owner_paths(self):
        for kwargs in ({}, {'experiments': self.c['experiments']}, {'ledger_path': self.ledger}):
            with self.subTest(kwargs=kwargs): self.assert_refused(self.verify(require_current=True, **kwargs))

    def test_changed_ledger_path_cannot_reuse_identical_empty_snapshot(self):
        other = self.root / 'other-ledger.sqlite3'
        attempt_ledger.initialize(other)
        self.addCleanup(other.unlink)
        self.assert_refused(self.verify(require_current=True, experiments=self.c['experiments'], ledger_path=other))

    def test_acceptance_withdrawn_after_export_is_offline_unknown_and_live_refused(self):
        with self.c['workspace'].connection() as db:
            db.execute("UPDATE asset_acceptances SET withdrawn_at=2 WHERE id='test-concept-front'")
        def restore():
            with self.c['workspace'].connection() as db:
                db.execute("UPDATE asset_acceptances SET withdrawn_at=NULL WHERE id='test-concept-front'")
        self.addCleanup(restore)
        self.assertTrue(self.verify()['passed'])
        report = self.verify(require_current=True, experiments=self.c['experiments'], ledger_path=self.ledger)
        self.assert_refused(report)
        self.assertTrue(report['integrity_verified'])
        self.assertFalse(report['current_authority_matches'])

    def test_changed_copied_asset_is_refused(self):
        pack = self.read('pack.json'); record = next(iter(pack['files'].values()))
        (self.bundle / 'assets' / 'packs' / pack['id'] / record['path']).write_bytes(b'changed')
        self.assert_refused(self.verify())

    def test_changed_metadata_is_refused_even_when_outer_hashes_are_recomputed(self):
        value = self.read('character-metadata.json'); value['display_name'] = 'Substituted metadata'
        self.write('character-metadata.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_changed_semantic_policy_is_refused_even_when_outer_hashes_are_recomputed(self):
        value = self.read('semantic-policy.json'); value['anchors']['left-iris']['value'] = 'blue'
        self.write('semantic-policy.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_one_semantic_side_swap_cannot_reuse_recorded_pass(self):
        value = self.read('annotations.json')
        value['turnaround']['views'][0]['anchors']['left-iris']['value'] = 'blue'
        self.write('annotations.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_copied_authority_row_is_refused_after_rehash(self):
        value = self.read('current-authority.json'); assets = value['authority']['snapshot']['assets']
        assets['turnaround/front']['acceptance'] = copy.deepcopy(assets['concept/front']['acceptance'])
        self.write('current-authority.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_changed_job_output_index_cannot_keep_original_asset_id(self):
        value = self.read('current-authority.json')
        value['authority']['snapshot']['assets']['concept/front']['output_index'] = 1
        self.write('current-authority.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_retained_attempts_from_inconsistent_source_roots_are_refused(self):
        captured = self.read('current-authority.json'); family = self.read('family.json')
        rows = []
        for index in (1, 2):
            row = {'family_id': family['family_id'], 'stage': 'mesh', 'request_id': 'old-' + str(index),
                   'job_id': 'retained-' + str(index), 'intent_sha256': 'c' * 64,
                   'workspace_id': family['workspace_id'], 'source_root_sha256': str(index) * 64,
                   'nonce': 'd' * 32, 'state': 'failed', 'observation_sha256': 'e' * 64, 'revision': 1}
            row['attempt_id'] = p.digest({key: row[key] for key in attempt_ledger.IDENTITY_FIELDS})
            rows.append(row)
        captured['ledger']['attempts'] = rows
        self.write('current-authority.json', captured); self.rehash()
        self.assert_refused(self.verify())

    def test_false_semantic_and_owner_claims_are_refused_after_rehash(self):
        value = self.read('current-authority.json')
        value['perceptual_identity_verified'] = True; value['reviewer_authenticated'] = True
        self.write('current-authority.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_extra_unsupported_admission_claim_is_refused_after_rehash(self):
        value = self.read('current-authority.json'); value['native_ready'] = True
        self.write('current-authority.json', value); self.rehash()
        self.assert_refused(self.verify())

    def test_ready_schema_boolean_and_direct_import_changes_are_refused(self):
        original = self.read('READY.json')
        for key, value in [('schema', 'las.p36-ready-handoff/999'), ('asset_copy_performed', 1),
                           ('current_direct_import_allowed', True), ('native_import_performed', True)]:
            with self.subTest(key=key):
                changed = copy.deepcopy(original); changed[key] = value
                self.write('READY.json', changed); self.write('READY.pending.json', changed)
                self.assert_refused(self.verify())

    def test_manifest_claims_cannot_be_promoted_or_extended(self):
        pack = self.read('pack.json'); pack['status'] = 'playable'
        pack['models']['glb']['joined'] = True
        self.write('pack.json', pack); self.rehash()
        self.assert_refused(self.verify())

    def test_removed_provenance_in_manifest_cannot_be_hidden_by_rehash(self):
        pack = self.read('pack.json'); next(iter(pack['files'].values())).pop('source')
        self.write('pack.json', pack); self.rehash()
        self.assert_refused(self.verify())

    def test_non_string_recursive_file_reference_is_refused_even_in_matching_metadata(self):
        metadata = self.read('character-metadata.json'); metadata['ue']['file'] = 1
        self.write('character-metadata.json', metadata)
        pack = self.read('pack.json'); pack['models']['ue']['file'] = 1
        self.write('pack.json', pack); self.rehash()
        self.assert_refused(self.verify())

    def test_redigested_reused_content_provenance_conflict_is_refused(self):
        family = self.read('family.json')
        receipt = copy.deepcopy(family['receipts'][family['heads']['unreal']])
        artifact = copy.deepcopy(family['receipts'][family['heads']['concept']]['payload']['artifacts'][0])
        artifact['key'] = 'reused-concept'; artifact['licence']['commercial'] = 'no'
        receipt['payload']['artifacts'].append(artifact)
        for dimension, state, actor in [('generation', 'completed', 'fixture'),
                                        ('inspection', 'inspected', 'fixture'), ('acceptance', 'accepted', 'owner')]:
            receipt = p.attest(receipt, dimension, state, actor, 'fixture:consumer-mutation')
        family['receipts'][receipt['id']] = receipt; family['heads']['unreal'] = receipt['id']
        self.write('family.json', family); self.rehash()
        report = self.verify(); self.assert_refused(report)
        self.assertIn('artifact_provenance_conflict', {b['code'] for b in report['blockers']})

    def test_synthetic_family_cannot_be_relabelled_production(self):
        family = self.read('family.json'); family['mode'] = 'production'
        self.write('family.json', family); self.rehash()
        self.assert_refused(self.verify())

    def test_missing_completion_and_missing_bound_sidecar_are_refused(self):
        for name in ['READY.json', 'binding.json']:
            with self.subTest(name=name):
                path = self.bundle / name; original = path.read_bytes(); path.unlink()
                self.assert_refused(self.verify()); path.write_bytes(original)

    def test_duplicate_json_keys_are_refused(self):
        (self.bundle / 'pack.json').write_bytes(b'{"schema":"lumenfold.pack/1","schema":"lumenfold.pack/1"}')
        self.assert_refused(self.verify())

    def test_sidecar_link_is_refused(self):
        path = self.bundle / 'binding.json'; path.unlink(); path.symlink_to(self.original / 'binding.json')
        self.assert_refused(self.verify())

    def test_asset_link_and_path_escape_are_refused(self):
        pack = self.read('pack.json'); record = next(iter(pack['files'].values()))
        path = self.bundle / 'assets' / 'packs' / pack['id'] / record['path']
        path.unlink(); path.symlink_to(self.original / 'assets' / 'packs' / pack['id'] / record['path'])
        self.assert_refused(self.verify())
        path.unlink(); path.write_bytes(b'ignored')
        record['path'] = '../outside'; self.write('pack.json', pack); self.rehash()
        self.assert_refused(self.verify())

    def test_expected_pack_id_is_an_explicit_constraint(self):
        self.assert_refused(self.verify(expected_pack_id='another-character'))

    def test_optional_retained_markers_must_match_when_present(self):
        pending = self.read('READY.pending.json'); pending['pack_sha256'] = '0' * 64
        self.write('READY.pending.json', pending); self.assert_refused(self.verify())
        (self.bundle / 'READY.pending.json').unlink()
        partial = self.read('PARTIAL.json'); partial['retry_allowed'] = True
        self.write('PARTIAL.json', partial); self.assert_refused(self.verify())

    def test_unrelated_failure_note_never_grants_or_removes_completion(self):
        self.write('FAILED.json', {'note': 'Unrelated retained diagnostic; not admission authority'})
        self.assertTrue(self.verify()['passed'])

    def test_cli_verifies_explicit_bundle(self):
        self.assertIsNotNone(verifier)
        result = subprocess.run([sys.executable, str(Path(verifier.__file__)), 'verify', '--bundle', str(self.bundle),
                                 '--allow-synthetic'], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout[:1000])
        self.assertTrue(json.loads(result.stdout)['integrity_verified'])


if __name__ == '__main__': unittest.main()
