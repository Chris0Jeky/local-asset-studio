"""Current-authority regressions against the shipped Studio SQLite schema."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

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


if __name__ == '__main__': unittest.main()
