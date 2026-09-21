"""Substitution must not smuggle unstaged reference changes into old receipts."""
from __future__ import annotations

import copy
import unittest

import test_recipe_shortlist_apply as A
import test_setup_substitution as F
from studio_workflow import setup_substitution as S


class StagedInputIntegrityTests(unittest.TestCase):
    setUp = A.SetupApplyTests.setUp
    store = A.SetupApplyTests.store
    command = A.SetupApplyTests.command
    create = A.SetupApplyTests.create

    def test_substitution_cannot_change_staged_input_set_without_explicit_staging(self):
        original = self.create()
        staged = A.SetupApplyTests.apply(self, original)
        self.assertEqual(staged['revision'], 2)
        self.assertEqual(self.s.upload_count, 3)

        changed = copy.deepcopy(staged['draft'])
        changed['recipe']['controls'].update(F.draft()['recipe']['controls'])
        first_reference = staged['draft']['recipe']['references'][0]['file']
        changed['recipe']['controls']['reference'] = first_reference
        current = self.command(
            'replace', request_id='model-state-with-reference',
            draft_id=original['draft_id'], expected_revision=2, draft=changed,
        )

        card = F.profile()
        card['dependent_changes'].append({
            'control': 'reference',
            'before': first_reference,
            'after': 'not-staged.png',
            'reason': 'Fixture attempts to change a staged input without staging.',
        })
        report = S.request(F.substitution_request(current=changed, card=card))
        self.assertTrue(report['can_apply'])

        result = self.command(
            'substitute', request_id='unstaged-reference-substitution',
            draft_id=current['draft_id'], expected_revision=current['revision'],
            proposal_json=report['proposal_json'],
            approved_proposal_sha256=report['proposal_sha256'],
        )
        self.assertEqual(result['status'], 'failed')
        self.assertRegex(result['message'], 'staged|input|attach')
        self.assertEqual(self.store().get(current['draft_id'])['revision'], 3)
        self.assertEqual(self.s.upload_count, 3)


if __name__ == '__main__':
    unittest.main()
