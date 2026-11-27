"""Current-authority regressions against the shipped Studio SQLite schema."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import authority_fixtures as af
import pipeline as p
import studio_authority as sa


class CurrentAuthorityTests(unittest.TestCase):
    def setUp(self):
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'tests'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.c = af.make_workspace(Path(self.temp.name), through='turnaround')

    def capture(self, binding=None):
        return sa.capture_authority(self.c['experiments'], self.c['family'], binding or self.c['binding'])

    def reject(self, code):
        result = self.capture()
        self.assertFalse(result['passed'], result)
        self.assertIn(code, {b['code'] for b in result['blockers']})

    def edit(self, sql, params=()):
        with self.c['workspace'].connection() as db: db.execute(sql, params)

    def test_actual_workspace_schema_passes_without_mutating_database(self):
        before = self.c['workspace'].snapshot()
        first = self.capture(); second = self.capture()
        self.assertTrue(first['passed'], first)
        self.assertEqual(first, second)
        self.assertFalse(first['generation_submitted'])
        self.assertEqual(before, self.c['workspace'].snapshot())

    def test_withdrawn_acceptance_blocks_after_prior_green_capture(self):
        self.assertTrue(self.capture()['passed'])
        self.edit('UPDATE asset_acceptances SET withdrawn_at=2 WHERE id=?', ('test-concept-front',))
        self.reject('acceptance_withdrawn')

    def test_same_asset_id_in_different_workspace_is_refused(self):
        self.edit('UPDATE workspace_identity SET id=?', ('b' * 32,))
        self.reject('workspace_changed')

    def test_wrong_acceptance_digest_is_refused(self):
        self.edit('UPDATE asset_acceptances SET sha256=? WHERE id=?', ('f' * 64, 'test-concept-front'))
        self.reject('acceptance_subject_changed')

    def test_agent_acceptance_cannot_replace_local_user(self):
        self.edit('UPDATE asset_acceptances SET reviewer=? WHERE id=?', ('local-agent', 'test-concept-front'))
        self.reject('acceptance_not_owner_declared')

    def test_selected_review_is_not_acceptance(self):
        self.edit('DELETE FROM asset_acceptances WHERE id=?', ('test-concept-front',))
        self.edit('UPDATE assets SET review=?', ('selected',))
        self.reject('acceptance_missing')

    def test_acceptance_for_other_use_is_refused(self):
        self.edit('UPDATE asset_acceptances SET use=? WHERE id=?', ('Other game', 'test-concept-front'))
        self.reject('acceptance_use_changed')

    def test_changed_character_canon_is_refused(self):
        self.edit('UPDATE cards SET lineage=?', ('[]',))
        self.reject('canon_changed')

    def test_changed_character_card_revision_is_refused(self):
        self.edit('UPDATE cards SET revision=revision+1')
        self.reject('card_changed')

    def test_trashed_card_is_refused(self):
        self.edit('UPDATE cards SET trashed_at=2')
        self.reject('card_unavailable')

    def test_trashed_asset_is_refused(self):
        self.edit('UPDATE assets SET trashed_at=2 WHERE id=?', (self.c['binding']['concept_asset_id'],))
        self.reject('asset_unavailable')

    def test_rejected_asset_is_not_promoted_by_old_acceptance(self):
        self.edit('UPDATE assets SET review=? WHERE id=?', ('rejected', self.c['binding']['concept_asset_id']))
        self.reject('asset_review_conflict')

    def test_changed_workspace_bytes_are_rehashed(self):
        path = self.c['workspace'].file(self.c['binding']['concept_asset_id'])
        path.write_bytes(path.read_bytes() + b'changed')
        self.reject('asset_bytes_changed')

    def test_changed_receipt_asset_cannot_use_original_acceptance_binding(self):
        binding = copy.deepcopy(self.c['binding'])
        binding['stages']['concept']['artifacts']['front']['asset_id'] = 'other'
        with self.assertRaises(p.PipelineError): self.capture(binding)

    def test_missing_artifact_binding_cannot_silently_skip_review(self):
        binding = copy.deepcopy(self.c['binding']); binding['stages']['turnaround']['artifacts'].pop('back')
        with self.assertRaises(p.PipelineError): self.capture(binding)

    def test_binding_old_receipt_id_is_refused(self):
        binding = copy.deepcopy(self.c['binding']); binding['stages']['concept']['receipt_id'] = 'f' * 64
        with self.assertRaises(p.PipelineError): self.capture(binding)

    def test_uncertain_retained_job_blocks_even_with_accepted_artifact(self):
        af.set_job(self.c, 'concept', status='uncertain', pending_submission={'index': 0})
        self.reject('job_unresolved')

    def test_completed_label_with_pending_submission_still_blocks(self):
        af.set_job(self.c, 'concept', pending_submission={'index': 1})
        self.reject('job_unresolved')

    def test_missing_job_record_blocks(self):
        (self.c['experiments'] / 'runs' / 'p36-concept' / 'state.json').unlink()
        self.reject('job_record_unavailable')

    def test_duplicate_json_job_keys_block(self):
        (self.c['experiments'] / 'runs' / 'p36-concept' / 'state.json').write_text('{"status":"completed","status":"uncertain"}')
        self.reject('job_record_unavailable')

    def test_changed_completed_job_fingerprint_blocks(self):
        af.set_job(self.c, 'concept', controls={'changed': True})
        self.reject('job_record_changed')

    def test_missing_workflow_record_blocks(self):
        (self.c['experiments'] / 'runs' / 'p36-concept' / 'workflow.json').unlink()
        self.reject('job_record_unavailable')

    def test_wrong_output_index_or_source_is_refused(self):
        self.edit('UPDATE assets SET output_index=999 WHERE id=?', (self.c['binding']['concept_asset_id'],))
        self.reject('job_output_unbound')

    def test_private_media_cannot_be_exported_by_regular_binding(self):
        self.edit("UPDATE assets SET privacy='private' WHERE id=?", (self.c['binding']['concept_asset_id'],))
        self.reject('asset_unavailable')

    def test_linked_workspace_media_is_refused(self):
        path = self.c['workspace'].file(self.c['binding']['concept_asset_id'])
        target = path.with_suffix('.original'); path.rename(target)
        try: path.symlink_to(target)
        except OSError: self.skipTest('Host cannot create symlinks')
        self.reject('asset_bytes_changed')

    def test_missing_database_is_not_created(self):
        missing = Path(self.temp.name) / 'no-workspace'
        result = sa.capture_authority(missing, self.c['family'], self.c['binding'])
        self.assertFalse(result['passed'])
        self.assertFalse(missing.exists())

    def test_requested_stage_subset_still_rechecks_its_root_acceptance(self):
        self.edit('UPDATE asset_acceptances SET withdrawn_at=2 WHERE id=?', ('test-concept-front',))
        result = sa.capture_authority(self.c['experiments'], self.c['family'], self.c['binding'], stages=['turnaround'])
        self.assertFalse(result['passed'])
        self.assertIn('concept', result['stages'])

    def test_unknown_live_review_state_is_not_treated_as_good(self):
        self.edit('UPDATE assets SET review=?', ('invalid-state',))
        self.reject('authority_unavailable')

    def test_malformed_character_body_is_not_current_authority(self):
        for value in ('not-json', '{}', '{"who":4}', '{"who":"fixture","unknown":true}'):
            self.edit('UPDATE cards SET body=?', (value,))
            self.reject('authority_unavailable')

    def test_non_json_sqlite_primitive_returns_failed_report(self):
        self.edit('UPDATE assets SET review=?', (b'rejected',))
        self.reject('authority_unavailable')


class IndexedOutputAuthorityTests(unittest.TestCase):
    """Exercise the real post-registration output decoration, without a worker.

    Studio.__init__ starts unrelated services, so allocate the object and give
    index_outputs its real Workspace and paths. No request method is invoked.
    """

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('p36_index_output_server', p.REPO_ROOT / 'app' / 'server.py')
        cls.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.server)

    def setUp(self):
        runtime = p.REPO_ROOT / '.runtime' / 'pro' / 'P36-B-20261126-2' / 'authority-index-v2'
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def indexed(self, operation='generated', *, advise=True, quiet_wall=False):
        from workspace import AssetWorkspace
        import fixtures

        self.counter += 1
        root = self.root / str(self.counter)
        experiments, media = root / 'experiments', root / 'artifacts'
        workspace = AssetWorkspace(experiments)
        with workspace.connection() as db:
            workspace_id = db.execute('SELECT id FROM workspace_identity WHERE singleton=1').fetchone()['id']
        family = p.create_family('p36-index-fixture', workspace_id, 'p36-index-fixture', fixtures.policy(), mode='synthetic')
        receipt = fixtures.stage_receipt(family, 'concept', media)
        artifact = receipt['payload']['artifacts'][0]
        studio = object.__new__(self.server.Studio)
        studio.assets, studio.experiments, studio.comfy_root = workspace, experiments, root / 'comfy'
        job = {'id': 'indexed-' + operation, 'status': 'completed', 'privacy': 'regular',
               'created_at': 1, 'preset_id': 'fixture-index-only', 'preset_name': 'Synthetic index fixture',
               'controls': {}, 'batch_count': 1, 'parent_assets': [], 'outputs': []}
        if quiet_wall:
            job['look'] = {'options': {'quiet_wall': True}}
        if operation == 'asset.import':
            target = experiments / 'uploads' / 'index-fixture.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(media / artifact['path'], target)
            job.update(operation='asset.import', prompt_ids=[], submissions=[])
            job['outputs'] = [{'filename': 'original-fixture.png', 'uploaded_file': target.name,
                               'type': 'output', 'media_type': 'image'}]
        else:
            target = studio.comfy_root / 'output' / 'fixture' / 'index-fixture.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(media / artifact['path'], target)
            submission = {'index': 0, 'prompt_id': 'fixture-prompt', 'seed': 123, 'status': 'completed'}
            job.update(prompt_ids=['fixture-prompt'], submissions=[submission])
            # The real history collector supplies seed/prompt/media provenance.
            studio._collect_outputs(job, submission, {'outputs': {'image-node': {'images': [
                {'filename': target.name, 'subfolder': 'fixture', 'type': 'output'}]}}})
        studio.index_outputs(job, advise=advise)
        output = job['outputs'][0]
        self.assertIn('asset_id', output, 'The real Studio indexing path must register the output')
        asset = workspace.get(output['asset_id'])
        self.assertNotIn('asset_id', asset['source'], 'Registration saves source before Studio decorates the descriptor')
        self.assertNotIn('empty_picture', asset['source'])
        artifact['asset_id'] = asset['id']
        receipt = p.seal(receipt)
        for dimension, state, actor in [('generation', 'completed', 'fixture'),
                                         ('inspection', 'inspected', 'fixture'),
                                         ('acceptance', 'accepted', 'owner')]:
            receipt = p.attest(receipt, dimension, state, actor, 'fixture:real-index-output-test')
        family = p.record_receipt(family, receipt)
        acceptance = workspace.accept(asset['id'], {'reviewer': 'local-user', 'use': 'P36 index fixture concept',
            'sha256': artifact['sha256'], 'workspace_id': workspace_id,
            'note': 'Synthetic test declaration; no owner art acceptance.'})
        workspace.card_command({'action': 'create', 'kind': 'character', 'id': 'p36-index-fixture',
            'name': 'Synthetic index fixture', 'body': {'who': 'Synthetic swatch, no real character'},
            'lineage': [{'role': 'canon', 'asset_id': asset['id'], 'sha256': artifact['sha256']}]})
        run = experiments / 'runs' / job['id']
        run.mkdir(parents=True)
        workflow = p.canonical_bytes({'fixture': 'retained indexing evidence; no generation'})
        (run / 'workflow.json').write_bytes(workflow)
        binding = {'schema': 'las.p36-workspace-binding/1', 'family_id': family['family_id'],
            'workspace_id': workspace_id, 'character_card_id': 'p36-index-fixture', 'card_revision': 0,
            'concept_asset_id': asset['id'], 'stages': {'concept': {'receipt_id': receipt['id'],
            'artifacts': {artifact['key']: {'asset_id': asset['id'], 'sha256': artifact['sha256'],
                'acceptance_id': acceptance['acceptances'][0]['id'], 'use': 'P36 index fixture concept'}},
            'jobs': {job['id']: {'state_sha256': '', 'workflow_sha256': hashlib.sha256(workflow).hexdigest()}}}}}
        context = {'workspace': workspace, 'experiments': experiments, 'family': family, 'binding': binding,
                   'job': job, 'studio': studio, 'asset_id': asset['id'], 'state_path': run / 'state.json'}
        self.save_job(context)
        return context

    def save_job(self, context):
        raw = p.canonical_bytes(context['job'])
        context['state_path'].write_bytes(raw)
        context['binding']['stages']['concept']['jobs'][context['job']['id']]['state_sha256'] = hashlib.sha256(raw).hexdigest()

    def capture(self, context):
        return sa.capture_authority(context['experiments'], context['family'], context['binding'])

    def assert_output_rejected(self, context):
        result = self.capture(context)
        self.assertFalse(result['passed'], result)
        self.assertIn('job_output_unbound', {item['code'] for item in result['blockers']})

    def test_actual_generated_indexed_output_has_current_authority(self):
        context = self.indexed()
        self.assertIn('empty_picture', context['job']['outputs'][0])
        result = self.capture(context)
        self.assertTrue(result['passed'], result['blockers'])

    def test_actual_import_indexed_output_has_current_authority(self):
        context = self.indexed('asset.import')
        self.assertIn('empty_picture', context['job']['outputs'][0])
        result = self.capture(context)
        self.assertTrue(result['passed'], result['blockers'])

    def test_actual_index_without_advisory_still_binds_added_asset_id(self):
        context = self.indexed(advise=False)
        self.assertNotIn('empty_picture', context['job']['outputs'][0])
        self.assertTrue(self.capture(context)['passed'])

    def test_real_quiet_wall_metrics_are_post_registration_advisories(self):
        context = self.indexed(quiet_wall=True)
        output = context['job']['outputs'][0]
        self.assertEqual(output['text_safe']['method'], 'adjacent-luma-v1')
        self.assertNotIn('text_safe', context['workspace'].get(context['asset_id'])['source'])
        self.assertTrue(self.capture(context)['passed'])

    def test_real_quiet_wall_error_is_a_bounded_advisory(self):
        with patch.object(self.server.review_media, 'text_safe_metrics',
                          side_effect=ValueError('Synthetic diagnostic failure')):
            context = self.indexed(quiet_wall=True)
        self.assertEqual(context['job']['outputs'][0]['text_safe'], {'error': 'Synthetic diagnostic failure'})
        self.assertTrue(self.capture(context)['passed'])

    def test_real_registration_of_already_decorated_source_stays_bound(self):
        context = self.indexed(quiet_wall=True)
        workspace, job = context['workspace'], context['job']
        # A retained job can already carry indexing diagnostics when its asset
        # is registered again, for example when rebuilding a local Workspace.
        with workspace.connection() as db:
            db.execute('DELETE FROM asset_acceptances WHERE asset_id=?', (context['asset_id'],))
            db.execute('DELETE FROM assets WHERE id=?', (context['asset_id'],))
        context['studio'].index_outputs(job)
        stored = workspace.get(context['asset_id'])
        self.assertEqual(stored['source'], job['outputs'][0])
        self.assertIn('asset_id', stored['source'])
        acceptance = workspace.accept(context['asset_id'], {'reviewer': 'local-user', 'use': 'P36 index fixture concept',
            'sha256': stored['sha256'], 'workspace_id': context['binding']['workspace_id'],
            'note': 'Synthetic re-registration declaration.'})
        context['binding']['stages']['concept']['artifacts']['front']['acceptance_id'] = acceptance['acceptances'][0]['id']
        self.save_job(context)
        self.assertTrue(self.capture(context)['passed'])

    def test_reindex_storage_error_diagnostic_does_not_replace_verified_source(self):
        context = self.indexed()
        with patch.object(context['workspace'], 'register', side_effect=ValueError('Synthetic reindex storage fault')):
            context['studio'].index_outputs(context['job'])
        self.assertIn('snapshot_error', context['job']['outputs'][0])
        self.save_job(context)
        self.assertTrue(self.capture(context)['passed'])

    def test_wrong_output_asset_id_cannot_be_stripped_as_an_advisory(self):
        for bad in ('f' * 32, None, True):
            with self.subTest(bad=bad):
                context = self.indexed()
                context['job']['outputs'][0]['asset_id'] = bad
                self.save_job(context)
                self.assert_output_rejected(context)

    def test_filename_folder_type_prompt_and_unknown_changes_remain_bound(self):
        changes = [('filename', 'different.png'), ('subfolder', 'another-folder'), ('type', 'temp'),
                   ('prompt_id', 'another-prompt'), ('seed', 124), ('new_meaningful_field', 'unrecorded-source')]
        for field, value in changes:
            with self.subTest(field=field):
                context = self.indexed()
                context['job']['outputs'][0][field] = value
                if field == 'prompt_id':
                    # Keep the independent settled-job gate valid to exercise provenance binding.
                    context['job']['prompt_ids'] = [value]
                    context['job']['submissions'][0]['prompt_id'] = value
                self.save_job(context)
                self.assert_output_rejected(context)

    def test_import_uploaded_source_change_is_not_an_advisory(self):
        context = self.indexed('asset.import')
        context['job']['outputs'][0]['uploaded_file'] = 'other-upload.png'
        self.save_job(context)
        self.assert_output_rejected(context)

    def test_missing_original_descriptor_field_is_rejected(self):
        context = self.indexed()
        del context['job']['outputs'][0]['subfolder']
        self.save_job(context)
        self.assert_output_rejected(context)

    def test_changed_stored_source_does_not_get_normalized_into_a_match(self):
        context = self.indexed()
        source = context['workspace'].get(context['asset_id'])['source']
        source['filename'] = 'different-stored-source.png'
        with context['workspace'].connection() as db:
            db.execute('UPDATE assets SET source=? WHERE id=?', (p.canonical_bytes(source).decode(), context['asset_id']))
        self.assert_output_rejected(context)

    def test_wrong_asset_id_inside_stored_source_is_rejected(self):
        context = self.indexed()
        source = context['workspace'].get(context['asset_id'])['source']
        source['asset_id'] = 'f' * 32
        with context['workspace'].connection() as db:
            db.execute('UPDATE assets SET source=? WHERE id=?', (p.canonical_bytes(source).decode(), context['asset_id']))
        self.assert_output_rejected(context)

    def test_wrong_index_cannot_rebind_to_an_identical_descriptor(self):
        context = self.indexed()
        other = copy.deepcopy(context['job']['outputs'][0])
        # No asset_id hint: the Workspace's deterministic job/index identity must bind it.
        other.pop('asset_id')
        context['job']['outputs'].append(other)
        with context['workspace'].connection() as db:
            db.execute('UPDATE assets SET output_index=1 WHERE id=?', (context['asset_id'],))
        self.save_job(context)
        self.assert_output_rejected(context)

    def test_boolean_numeric_alias_is_not_equal_provenance(self):
        context = self.indexed()
        source = context['workspace'].get(context['asset_id'])['source']
        source['seed'] = 1
        with context['workspace'].connection() as db:
            db.execute('UPDATE assets SET source=? WHERE id=?', (p.canonical_bytes(source).decode(), context['asset_id']))
        context['job']['outputs'][0]['seed'] = True
        self.save_job(context)
        self.assert_output_rejected(context)

    def test_unknown_or_malformed_advisory_values_fail_closed(self):
        for field, value in [('empty_picture', {'accepted': True}), ('empty_picture', 'accepted'),
                             ('snapshot_error', {'path': 'replacement'}),
                             ('text_safe', {'accepted': True}), ('text_safe', {'error': 7})]:
            with self.subTest(field=field, value=value):
                context = self.indexed()
                context['job']['outputs'][0][field] = value
                self.save_job(context)
                self.assert_output_rejected(context)


if __name__ == '__main__': unittest.main()
